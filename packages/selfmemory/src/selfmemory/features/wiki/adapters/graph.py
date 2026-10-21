"""The shape of the wiki: pages as nodes, links as edges, and how it grew.

Links follow OKF §6:

- bundle-absolute ``[t](/tables/orders.md)`` resolves from the scope root;
- relative ``[t](../tables/orders.md)`` resolves from the page's directory;
- ``[[wiki-links]]`` with a folder (``[[tables/orders]]``) resolve from the
  scope root, plain ones (``[[orders]]``) from the page's directory.

All ids are paths relative to the organization root, e.g.
``wiki/projects/<p>/tables/orders.md``.
"""

from __future__ import annotations

import re
import threading
from collections import OrderedDict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from selfmemory.features.wiki.adapters import git_repo as git
from selfmemory.features.wiki.adapters.files import list_wiki_files

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

__all__ = [
    "resolve_link",
    "outbound_links",
    "build_graph",
    "build_timeline",
    "ScopeRoot",
]

_WIKI_LINK = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
_MD_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+\.md)(?:#[^)]*)?\)")
_EXTERNAL = re.compile(r"^(?:[a-z][a-z0-9+.-]*:)", re.IGNORECASE)


@dataclass(frozen=True)
class ScopeRoot:
    key: str
    rel: str  # e.g. "wiki/projects/abc"
    abs: Path
    # Sub-project directories nested inside this one. They are separate scopes
    # with their own membership, so a walk of the parent must not see them.
    exclude: tuple[str, ...] = ()


def _join_relative(target: str, from_id: str) -> str:
    out = from_id.split("/")[:-1]
    for part in target.split("/"):
        if part == "..":
            if out:
                out.pop()
        elif part not in (".", ""):
            out.append(part)
    return "/".join(out) + ".md"


def resolve_link(target: str, from_id: str, scope_rel: str, style: str) -> str:
    cleaned = target.strip()
    cleaned = cleaned[:-3] if cleaned.endswith(".md") else cleaned
    if cleaned.startswith("/"):
        return f"{scope_rel}/{cleaned.lstrip('/')}.md"
    if style == "md" or cleaned.startswith(("./", "../")):
        return _join_relative(cleaned, from_id)
    if "/" in cleaned:
        return f"{scope_rel}/{cleaned}.md"
    return _join_relative(cleaned, from_id)


def outbound_links(body: str, from_id: str, scope_rel: str) -> list[str]:
    seen: dict[str, None] = {}
    for m in _WIKI_LINK.finditer(body):
        to = resolve_link(m.group(1), from_id, scope_rel, "wiki")
        if to != from_id:
            seen.setdefault(to)
    for m in _MD_LINK.finditer(body):
        href = m.group(1).strip()
        if _EXTERNAL.match(href):
            continue
        to = resolve_link(href, from_id, scope_rel, "md")
        if to != from_id:
            seen.setdefault(to)
    return list(seen)


# Per-scope parse results keyed by the scope's HEAD commit, so a graph request
# re-reads only scopes that changed since the last one. Uncommitted edits
# (none are expected: every write path commits) would show at the next commit.
_CACHE_MAX = 256
_cache: OrderedDict[tuple[str, str], dict[str, list[str]]] = OrderedDict()
_cache_lock = threading.Lock()


def _scope_links(org_root: Path, scope: ScopeRoot) -> dict[str, list[str]]:
    sha = git.head_sha(scope.abs)
    cache_key = (str(scope.abs), sha) if sha else None
    if cache_key:
        with _cache_lock:
            hit = _cache.get(cache_key)
            if hit is not None:
                _cache.move_to_end(cache_key)
                return hit
    pages: dict[str, list[str]] = {}
    for path in list_wiki_files(scope.abs):
        page_id = path.relative_to(org_root).as_posix()
        if any(page_id.startswith(x.rstrip("/") + "/") for x in scope.exclude):
            continue
        try:
            body = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        pages[page_id] = outbound_links(body, page_id, scope.rel)
    if cache_key:
        with _cache_lock:
            _cache[cache_key] = pages
            while len(_cache) > _CACHE_MAX:
                _cache.popitem(last=False)
    return pages


def build_graph(org_root: Path, scopes: Iterable[ScopeRoot]) -> dict:
    pages: dict[str, list[str]] = {}
    owner: dict[str, str] = {}
    for scope in scopes:
        for page_id, links in _scope_links(org_root, scope).items():
            pages[page_id] = links
            owner[page_id] = scope.key

    nodes = {
        pid: {
            "id": pid,
            "label": pid.rsplit("/", 1)[-1].removesuffix(".md"),
            "scope": owner[pid],
            "links": 0,
            "orphan": True,
        }
        for pid in pages
    }
    edges = []
    broken = 0
    for src, targets in pages.items():
        for dst in targets:
            if dst not in nodes:
                broken += 1
                continue
            edges.append({"from": src, "to": dst})
            nodes[dst]["links"] += 1
            nodes[src]["orphan"] = False
            nodes[dst]["orphan"] = False
    return {"nodes": list(nodes.values()), "edges": edges, "broken": broken}


def _frames_for(scope: ScopeRoot, limit: int) -> list[dict]:
    commits = git.history(scope.abs, limit=limit, oldest_first=True)
    links: dict[str, list[str]] = {}
    frames = []
    prefix = scope.rel + "/"
    for c in commits:
        for f in git.commit_files(scope.abs, c.sha):
            if f.endswith(".md"):
                pid = prefix + f
                links[pid] = outbound_links(
                    git.show_file(scope.abs, c.sha, f), pid, scope.rel
                )
        present = {
            prefix + f
            for f in git.tree_files(scope.abs, c.sha)
            if f.endswith(".md")
            and not any((prefix + f).startswith(x + "/") for x in scope.exclude)
        }
        edges = [
            [src, dst]
            for src in present
            for dst in links.get(src, [])
            if dst in present
        ]
        frames.append(
            {
                "id": c.sha,
                "sha": c.sha[:7],
                "date": c.date,
                "message": c.message,
                "scope": scope.key,
                "nodes": sorted(present),
                "edges": edges,
            }
        )
    return frames


def build_timeline(scopes: Iterable[ScopeRoot], limit: int = 80) -> list[dict]:
    """The wiki as it stood after each commit, across every readable scope.

    Scopes are separate repositories, so one moment in time is the union of
    wherever each scope had got to by then.
    """
    flat = [f for s in scopes for f in _frames_for(s, limit)]
    flat.sort(key=lambda f: f["date"])
    latest: dict[str, dict] = {}
    merged = []
    for f in flat:
        latest[f["scope"]] = f
        nodes: set[str] = set()
        edges: list[list[str]] = []
        for state in latest.values():
            nodes.update(state["nodes"])
            edges.extend(state["edges"])
        merged.append({**f, "nodes": sorted(nodes), "edges": edges})
    return merged
