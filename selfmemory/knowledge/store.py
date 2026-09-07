"""Persistence for the knowledge base.

Deliberately shaped like the Postgres schema this will run on in the server:
every row is scoped by ``project_id``, page writes are optimistically locked on
a version counter, and one compaction applies as a single transaction. SQLite
is the local/embedded implementation; a ``PostgresKnowledgeStore`` implementing the
same ABC can be dropped in without touching the compactor.
"""

from __future__ import annotations

import json
import re
import sqlite3
import threading
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

from selfmemory.knowledge.models import IndexEntry, LogEntry, Page, Source, utcnow


class ConcurrentEditError(RuntimeError):
    """Raised when a page changed underneath an in-flight compaction."""


class KnowledgeStore(ABC):
    """Storage interface for a multi-tenant knowledge base."""

    @abstractmethod
    def get_page(self, project_id: str, slug: str) -> Page | None: ...

    @abstractmethod
    def list_pages(self, project_id: str) -> list[Page]: ...

    @abstractmethod
    def index(self, project_id: str) -> list[IndexEntry]: ...

    @abstractmethod
    def search(self, project_id: str, query: str, limit: int = 8) -> list[Page]: ...

    @abstractmethod
    def apply(
        self,
        project_id: str,
        writes: list[tuple[Page, int | None]],
        log_entries: list[LogEntry],
    ) -> None:
        """Apply page writes and log entries atomically.

        Each write is ``(page, expected_version)``. ``None`` means the page must
        not already exist. A version mismatch raises ``ConcurrentEditError`` and
        rolls the whole batch back.
        """

    @abstractmethod
    def page_version(self, project_id: str, slug: str) -> int | None: ...

    @abstractmethod
    def add_source(self, project_id: str, source: Source) -> None: ...

    @abstractmethod
    def get_source(self, project_id: str, source_id: str) -> Source | None: ...

    @abstractmethod
    def log(self, project_id: str, limit: int = 50) -> list[LogEntry]: ...

    @abstractmethod
    def get_schema_doc(self, project_id: str) -> str: ...

    @abstractmethod
    def set_schema_doc(self, project_id: str, text: str) -> None: ...


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:80] or "untitled"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS pages (
    project_id  TEXT NOT NULL,
    slug        TEXT NOT NULL,
    title       TEXT NOT NULL,
    body        TEXT NOT NULL,
    frontmatter TEXT NOT NULL DEFAULT '{}',
    version     INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    PRIMARY KEY (project_id, slug)
);

CREATE VIRTUAL TABLE IF NOT EXISTS pages_fts USING fts5(
    slug, title, body, project_id UNINDEXED, tokenize = 'porter unicode61'
);

CREATE TABLE IF NOT EXISTS sources (
    project_id TEXT NOT NULL,
    id         TEXT NOT NULL,
    content    TEXT NOT NULL,
    metadata   TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    PRIMARY KEY (project_id, id)
);

CREATE TABLE IF NOT EXISTS kb_log (
    project_id TEXT NOT NULL,
    ts         TEXT NOT NULL,
    op         TEXT NOT NULL,
    detail     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS kb_log_ts ON kb_log (project_id, ts);

CREATE TABLE IF NOT EXISTS kb_schema_doc (
    project_id TEXT PRIMARY KEY,
    body       TEXT NOT NULL
);
"""

DEFAULT_SCHEMA_DOC = """\
# Knowledge schema

Conventions for this knowledge base. Edit freely -- the compactor reads this on every
ingest and follows it.

## Page kinds
- `person/*`   -- one page per person
- `project/*`  -- one page per project or piece of work
- `topic/*`    -- concepts, preferences, recurring themes
- `event/*`    -- things that happened, dated

## Rules
- One fact lives on exactly one page. Prefer updating over appending.
- When a new source contradicts a page, keep the newer claim and record the
  older one under a `## Superseded` section with its date.
- Cross-link with `[[slug]]` whenever another page is mentioned.
- Keep pages under ~400 words. Split rather than let a page sprawl.
"""


class SQLiteKnowledgeStore(KnowledgeStore):
    """Embedded store backed by SQLite + FTS5."""

    def __init__(self, path: str | Path = ":memory:"):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # -- reads ---------------------------------------------------------

    def _row_to_page(self, row: sqlite3.Row) -> Page:
        return Page(
            slug=row["slug"],
            title=row["title"],
            body=row["body"],
            frontmatter=json.loads(row["frontmatter"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def get_page(self, project_id: str, slug: str) -> Page | None:
        row = self._conn.execute(
            "SELECT * FROM pages WHERE project_id = ? AND slug = ?",
            (project_id, slug),
        ).fetchone()
        return self._row_to_page(row) if row else None

    def page_version(self, project_id: str, slug: str) -> int | None:
        row = self._conn.execute(
            "SELECT version FROM pages WHERE project_id = ? AND slug = ?",
            (project_id, slug),
        ).fetchone()
        return row["version"] if row else None

    def list_pages(self, project_id: str) -> list[Page]:
        rows = self._conn.execute(
            "SELECT * FROM pages WHERE project_id = ? ORDER BY slug", (project_id,)
        ).fetchall()
        return [self._row_to_page(r) for r in rows]

    def index(self, project_id: str) -> list[IndexEntry]:
        return [
            IndexEntry(
                slug=p.slug,
                title=p.title,
                summary=p.summary,
                updated_at=p.updated_at,
            )
            for p in self.list_pages(project_id)
        ]

    def search(self, project_id: str, query: str, limit: int = 8) -> list[Page]:
        """Full-text search. Postgres will use ``tsvector`` here instead."""
        match = _fts_query(query)
        if not match:
            return []
        try:
            rows = self._conn.execute(
                "SELECT slug FROM pages_fts WHERE project_id = ? AND pages_fts "
                "MATCH ? ORDER BY rank LIMIT ?",
                (project_id, match, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        pages = [self.get_page(project_id, r["slug"]) for r in rows]
        return [p for p in pages if p is not None]

    def get_source(self, project_id: str, source_id: str) -> Source | None:
        row = self._conn.execute(
            "SELECT * FROM sources WHERE project_id = ? AND id = ?",
            (project_id, source_id),
        ).fetchone()
        if not row:
            return None
        return Source(
            id=row["id"],
            content=row["content"],
            metadata=json.loads(row["metadata"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def log(self, project_id: str, limit: int = 50) -> list[LogEntry]:
        rows = self._conn.execute(
            "SELECT * FROM kb_log WHERE project_id = ? ORDER BY ts DESC LIMIT ?",
            (project_id, limit),
        ).fetchall()
        return [
            LogEntry(ts=datetime.fromisoformat(r["ts"]), op=r["op"], detail=r["detail"])
            for r in rows
        ]

    def get_schema_doc(self, project_id: str) -> str:
        row = self._conn.execute(
            "SELECT body FROM kb_schema_doc WHERE project_id = ?", (project_id,)
        ).fetchone()
        return row["body"] if row else DEFAULT_SCHEMA_DOC

    # -- writes --------------------------------------------------------

    def set_schema_doc(self, project_id: str, text: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO kb_schema_doc (project_id, body) VALUES (?, ?) "
                "ON CONFLICT(project_id) DO UPDATE SET body = excluded.body",
                (project_id, text),
            )

    def add_source(self, project_id: str, source: Source) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR IGNORE INTO sources "
                "(project_id, id, content, metadata, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    project_id,
                    source.id,
                    source.content,
                    json.dumps(source.metadata),
                    source.created_at.isoformat(),
                ),
            )

    def apply(
        self,
        project_id: str,
        writes: list[tuple[Page, int | None]],
        log_entries: list[LogEntry],
    ) -> None:
        now = utcnow().isoformat()
        with self._lock, self._conn:
            for page, expected in writes:
                current = self._conn.execute(
                    "SELECT version FROM pages WHERE project_id = ? AND slug = ?",
                    (project_id, page.slug),
                ).fetchone()
                current_version = current["version"] if current else None
                if current_version != expected:
                    raise ConcurrentEditError(
                        f"page {page.slug!r} changed during compaction "
                        f"(expected version {expected}, found {current_version})"
                    )

                fm = json.dumps(page.frontmatter)
                if current_version is None:
                    self._conn.execute(
                        "INSERT INTO pages (project_id, slug, title, body, "
                        "frontmatter, version, created_at, updated_at) "
                        "VALUES (?, ?, ?, ?, ?, 1, ?, ?)",
                        (project_id, page.slug, page.title, page.body, fm, now, now),
                    )
                else:
                    self._conn.execute(
                        "UPDATE pages SET title = ?, body = ?, frontmatter = ?, "
                        "version = version + 1, updated_at = ? "
                        "WHERE project_id = ? AND slug = ?",
                        (page.title, page.body, fm, now, project_id, page.slug),
                    )
                self._conn.execute(
                    "DELETE FROM pages_fts WHERE project_id = ? AND slug = ?",
                    (project_id, page.slug),
                )
                self._conn.execute(
                    "INSERT INTO pages_fts (slug, title, body, project_id) "
                    "VALUES (?, ?, ?, ?)",
                    (page.slug, page.title, page.body, project_id),
                )

            for entry in log_entries:
                self._conn.execute(
                    "INSERT INTO kb_log (project_id, ts, op, detail) "
                    "VALUES (?, ?, ?, ?)",
                    (project_id, entry.ts.isoformat(), entry.op, entry.detail),
                )


_TOKEN_RE = re.compile(r"[A-Za-z0-9_]{2,}")
_STOPWORDS = frozenset(
    [
        "the",
        "a",
        "an",
        "and",
        "or",
        "of",
        "to",
        "in",
        "for",
        "on",
        "with",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "it",
        "its",
        "this",
        "that",
        "these",
        "those",
        "i",
        "you",
        "he",
        "she",
        "they",
        "we",
        "my",
        "your",
        "his",
        "her",
        "their",
        "our",
        "as",
        "at",
        "by",
        "from",
        "not",
        "no",
        "do",
        "does",
        "did",
        "have",
        "has",
        "had",
        "will",
        "would",
        "can",
        "could",
        "should",
        "about",
    ]
)


def _fts_query(text: str) -> str:
    """Turn free text into a safe FTS5 OR-query, dropping stopwords."""
    tokens = [t.lower() for t in _TOKEN_RE.findall(text) if t.lower() not in _STOPWORDS]
    seen: list[str] = []
    for t in tokens:
        if t not in seen:
            seen.append(t)
    return " OR ".join(seen[:24])
