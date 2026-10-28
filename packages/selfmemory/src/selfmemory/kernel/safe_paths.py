"""Path safety for the data root.

Every path a caller supplies is relative to an organization's root and is
checked twice: lexically (no NUL, no ``..``, no absolute escape) and then
against the filesystem, by resolving the deepest component that exists. The
second check is what stops a symlink planted inside a scope from becoming a
route out of it.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

__all__ = [
    "PathRefused",
    "safe_segment",
    "safe_rel_path",
    "resolve_contained",
    "is_within",
    "sanitize_upload_dir",
    "sanitize_filename",
]

_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")


class PathRefused(ValueError):
    """A path was rejected: traversal, outside its root, or not permitted."""


def safe_segment(value: str) -> str:
    """Validate an identifier used as one directory name (org, project, user ids).

    Ids become directory names, so they must not be able to carry a separator,
    a dot-dot, or anything a shell or git would treat specially.
    """
    if not isinstance(value, str) or not _SEGMENT.match(value):
        raise PathRefused(f"not a valid identifier: {value!r}")
    return value


def safe_rel_path(rel: str) -> str:
    """Normalise a caller-supplied relative path, refusing traversal.

    A leading ``/`` is stripped (callers often send ``/wiki/...``) and ``.``
    segments are dropped. ``..`` anywhere is refused outright rather than
    collapsed: a legitimate client never needs it, and collapsing is how
    ``a/../../etc`` turns into something that looks harmless.
    """
    if not rel or "\x00" in rel:
        raise PathRefused("path is required")
    parts = [p for p in rel.replace("\\", "/").split("/") if p not in ("", ".")]
    if not parts:
        raise PathRefused("path is required")
    if any(p == ".." for p in parts):
        raise PathRefused("path traversal is not allowed")
    # Dot-names are machinery, never content: refusing them keeps every
    # scope's .git (whose config git would execute from) out of reach.
    if any(p.startswith(".") for p in parts):
        raise PathRefused("hidden paths are not allowed")
    return "/".join(parts)


def is_within(child: Path | str, parent: Path | str) -> bool:
    c = os.path.normpath(str(child))
    p = os.path.normpath(str(parent))
    return c == p or c.startswith(p + os.sep)


def _real_deepest(path: Path) -> Path:
    """Realpath of the deepest existing ancestor, plus the not-yet-existing tail."""
    tail: list[str] = []
    cur = path
    while not cur.exists():
        if cur.parent == cur:
            break
        tail.append(cur.name)
        cur = cur.parent
    real = Path(os.path.realpath(cur))
    for name in reversed(tail):
        real = real / name
    return real


def resolve_contained(root: Path, rel: str) -> Path:
    """Join ``rel`` onto ``root`` and require the result to stay inside it.

    Symlink-aware: the deepest existing ancestor is resolved with
    ``realpath`` and compared with the resolved root, so a link inside the
    tree that points elsewhere is refused even though its lexical path looks
    contained.
    """
    clean = safe_rel_path(rel)
    root_real = Path(os.path.realpath(root))
    candidate = root / clean
    if not is_within(os.path.normpath(candidate), os.path.normpath(root)):
        raise PathRefused("path escapes its root")
    real = _real_deepest(candidate)
    if not is_within(real, root_real):
        raise PathRefused("path escapes its root")
    return candidate


_UNSAFE = re.compile(r"[^\w.\- ]")


def sanitize_filename(name: str) -> str:
    """A single safe file name from an uploaded one."""
    base = name.replace("\\", "/").split("/")[-1]
    base = _UNSAFE.sub("_", base).strip(" .").lstrip(".")
    return base[:200] or "upload"


def sanitize_upload_dir(rel_dir: str | None, max_segments: int = 10) -> str:
    """The directory part of a folder-drop path, made safe to recreate on disk."""
    if not rel_dir:
        return ""
    if "\x00" in rel_dir:
        raise PathRefused("path is not allowed")
    parts = [p for p in rel_dir.replace("\\", "/").split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        raise PathRefused("path traversal is not allowed")
    parts = [p.lstrip(".") or "_" for p in parts]
    cleaned = [_UNSAFE.sub("_", p).strip(" .") or "_" for p in parts]
    return "/".join(cleaned[:max_segments])
