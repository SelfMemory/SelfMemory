"""Open Knowledge Format (v0.2) helpers: scaffolding, frontmatter, promotions.

The agent writes pages; the server only scaffolds a new scope, reads
frontmatter for display, and maintains the promotion queue's statuses.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import yaml

from selfmemory.features.wiki.adapters.git_repo import (
    commit_scope,
    ensure_repo,
    write_excludes,
)

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "scaffold_scope",
    "parse_frontmatter",
    "page_title",
    "Promotion",
    "parse_promotions",
    "set_promotion_status",
    "PROTECTED_WIKI_FILES",
]

PROTECTED_WIKI_FILES = {"index.md", "log.md"}

_FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", re.DOTALL)


def _today() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def scaffold_scope(
    scope_dir: Path, key: str, label: str, nested: tuple[str, ...] = ()
) -> str | None:
    """Create a scope's reserved files and its repository, if not already there.

    Idempotent: an existing ``index.md`` means the scope is scaffolded, and
    nothing is touched. Returns the initial commit sha when one was made.
    """
    scope_dir.mkdir(parents=True, exist_ok=True)
    index = scope_dir / "index.md"
    if index.exists():
        ensure_repo(scope_dir)
        write_excludes(scope_dir, nested)
        return None
    today = _today()
    index.write_text(
        f'---\nokf_version: "0.2"\n---\n\n# {label}\n\n_No pages yet._\n',
        encoding="utf-8",
    )
    log = scope_dir / "log.md"
    if not log.exists():
        log.write_text(
            "# Directory Update Log\n\n"
            f"## {today}\n"
            f"* **Initialization**: Created scope `{key}`.\n",
            encoding="utf-8",
        )
    if key != "org":
        promotions = scope_dir / "promotions.md"
        if not promotions.exists():
            promotions.write_text(
                "# Promotions\n\n"
                "Facts from this scope that look org-wide, queued for review.\n\n"
                "_Nothing queued._\n",
                encoding="utf-8",
            )
    return commit_scope(scope_dir, f"[{today}] init | scope {key} created", nested)


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split YAML frontmatter from a page. Malformed YAML yields ``{}``."""
    m = _FRONTMATTER.match(text)
    if not m:
        return {}, text
    try:
        data = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    return data, text[m.end() :]


def page_title(text: str, fallback: str) -> str:
    meta, body = parse_frontmatter(text)
    title = meta.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


# ---------------------------------------------------------------------------
# Promotions
#
# The agent never writes upward. When it finds an org-wide fact while
# ingesting into a project or personal scope it appends to that scope's
# promotions.md:
#
#     ## [2026-05-28] proposed | <one-line fact>
#     source: raw/projects/<p>/deck.md
#     rationale: <why it is org-wide>
#
# A reviewer approves (the fact is ingested into the org room) or rejects it;
# either way the status word in the heading is rewritten so the queue is a
# record, not just a backlog.
# ---------------------------------------------------------------------------

_PROMO_HEAD = re.compile(
    r"^##\s*\[(?P<date>[^\]]+)\]\s*(?P<status>proposed|approved|rejected)\s*\|\s*(?P<fact>.+?)\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Promotion:
    id: str
    date: str
    status: str
    fact: str
    source: str
    rationale: str
    line: int

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "date": self.date,
            "status": self.status,
            "fact": self.fact,
            "source": self.source,
            "rationale": self.rationale,
        }


def _promo_id(date: str, fact: str) -> str:
    return hashlib.sha256(f"{date}|{fact}".encode()).hexdigest()[:16]


def parse_promotions(text: str) -> list[Promotion]:
    lines = text.splitlines()
    out: list[Promotion] = []
    for i, line in enumerate(lines):
        m = _PROMO_HEAD.match(line)
        if not m:
            continue
        source = rationale = ""
        for follow in lines[i + 1 : i + 8]:
            if follow.startswith("## "):
                break
            key, _, value = follow.partition(":")
            if key.strip().lower() == "source":
                source = value.strip()
            elif key.strip().lower() == "rationale":
                rationale = value.strip()
        date, fact = m.group("date").strip(), m.group("fact").strip()
        out.append(
            Promotion(
                id=_promo_id(date, fact),
                date=date,
                status=m.group("status").lower(),
                fact=fact,
                source=source,
                rationale=rationale,
                line=i,
            )
        )
    return out


def set_promotion_status(text: str, promo_id: str, status: str) -> str:
    """Rewrite one entry's status word. Raises ``KeyError`` if it is absent."""
    if status not in ("approved", "rejected"):
        raise ValueError("status must be approved or rejected")
    lines = text.splitlines(keepends=True)
    for promo in parse_promotions(text):
        if promo.id == promo_id:
            line = lines[promo.line]
            lines[promo.line] = re.sub(
                r"\b(proposed|approved|rejected)\b", status, line, count=1, flags=re.I
            )
            return "".join(lines)
    raise KeyError(promo_id)
