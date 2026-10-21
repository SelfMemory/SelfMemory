"""Lexical search over readable wiki pages.

Not a retrieval layer for the agent -- the agent navigates the OKF indexes
itself. This exists for clients that need a quick "which pages mention X"
without starting a run: the MCP server's ``search`` tool and the UI's command
palette. Plain term matching over the files, scored by where terms occur.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from selfmemory.features.wiki.adapters.files import list_wiki_files
from selfmemory.features.wiki.adapters.okf import page_title, parse_frontmatter

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from selfmemory.features.wiki.adapters.graph import ScopeRoot

__all__ = ["search_pages"]

_TOKEN = re.compile(r"[\w-]{2,}", re.UNICODE)
_RESERVED = {"index.md", "log.md", "promotions.md"}


def _terms(query: str) -> list[str]:
    return list(dict.fromkeys(t.lower() for t in _TOKEN.findall(query)))[:12]


def _snippet(body: str, terms: list[str], width: int = 220) -> str:
    low = body.lower()
    pos = min((low.find(t) for t in terms if t in low), default=0)
    start = max(0, pos - width // 3)
    text = " ".join(body[start : start + width].split())
    return ("…" if start else "") + text + ("…" if start + width < len(body) else "")


def search_pages(
    org_root: Path,
    scopes: Iterable[ScopeRoot],
    query: str,
    limit: int = 20,
    max_files: int = 5000,
) -> list[dict]:
    terms = _terms(query)
    if not terms:
        return []
    hits: list[tuple[float, dict]] = []
    scanned = 0
    for scope in scopes:
        for path in list_wiki_files(scope.abs):
            pid = path.relative_to(org_root).as_posix()
            if path.name in _RESERVED or any(
                pid.startswith(x + "/") for x in scope.exclude
            ):
                continue
            scanned += 1
            if scanned > max_files:
                break
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            meta, body = parse_frontmatter(text)
            title = page_title(text, path.stem)
            low_body, low_title = body.lower(), title.lower()
            desc = str(meta.get("description") or "")
            tags = " ".join(str(t) for t in meta.get("tags") or [] if t)
            head = f"{low_title} {desc.lower()} {tags.lower()} {pid.lower()}"
            score = 0.0
            matched = 0
            for t in terms:
                in_head = t in head
                n = low_body.count(t)
                if in_head or n:
                    matched += 1
                score += (5.0 if in_head else 0.0) + min(n, 10)
            if not matched:
                continue
            score *= matched / len(terms)
            hits.append(
                (
                    score,
                    {
                        "path": pid,
                        "scope": scope.key,
                        "title": title,
                        "description": desc,
                        "type": meta.get("type"),
                        "snippet": _snippet(body, terms),
                        "score": round(score, 2),
                    },
                )
            )
    hits.sort(key=lambda h: h[0], reverse=True)
    return [h[1] for h in hits[:limit]]
