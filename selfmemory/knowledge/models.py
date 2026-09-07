"""Core data types for the knowledge base.

Memory is stored as three layers:

* ``Source`` -- immutable raw material. Never edited, only read.
* ``Page``   -- LLM-owned markdown. Created, rewritten and merged by the
  compactor. This is the layer that compounds.
* ``Schema`` -- per-project conventions describing how the base is organised.
  Co-evolved by the user and the LLM.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Source:
    """An immutable piece of raw material ingested into the knowledge base."""

    id: str
    content: str
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=utcnow)


@dataclass
class Page:
    """A single knowledge page: markdown body plus frontmatter metadata.

    ``summary`` lives in frontmatter rather than as a column because it is
    LLM-authored alongside the body and is what the index is built from.
    """

    slug: str
    title: str
    body: str
    frontmatter: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    @property
    def summary(self) -> str:
        return self.frontmatter.get("summary", "")

    @property
    def sources(self) -> list[str]:
        return list(self.frontmatter.get("sources", []))

    def to_markdown(self) -> str:
        """Render the page as it would appear on disk, frontmatter included."""
        import yaml

        fm = yaml.safe_dump(self.frontmatter, sort_keys=True).strip()
        return f"---\n{fm}\n---\n\n# {self.title}\n\n{self.body.strip()}\n"


@dataclass
class LogEntry:
    """One line of ``log.md`` -- an append-only record of operations."""

    ts: datetime
    op: str
    detail: str


@dataclass
class IndexEntry:
    """One line of ``index.md`` -- what the compactor reads to orient itself."""

    slug: str
    title: str
    summary: str
    updated_at: datetime


@dataclass
class PageEdit:
    """A single edit the compactor wants to make."""

    op: str  # "create" | "update" | "noop"
    slug: str
    title: str = ""
    summary: str = ""
    body: str = ""
    reason: str = ""


@dataclass
class CompactionResult:
    """What one ingest actually did to the knowledge base."""

    source_id: str
    edits: list[PageEdit] = field(default_factory=list)
    pages_considered: list[str] = field(default_factory=list)

    @property
    def created(self) -> list[str]:
        return [e.slug for e in self.edits if e.op == "create"]

    @property
    def updated(self) -> list[str]:
        return [e.slug for e in self.edits if e.op == "update"]
