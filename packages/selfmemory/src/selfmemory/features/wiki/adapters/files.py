"""Server-side file access inside the data root.

These functions take absolute paths that the access layer has already resolved
and checked. They make no authorization decision of their own -- one place
decides, and it is the access layer.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = [
    "walk_files",
    "list_wiki_files",
    "list_regular_files",
    "looks_binary",
    "remove_symlinks",
    "write_bytes",
    "remove_file",
    "move_to_trash",
]

IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".svg",
    ".avif",
    ".bmp",
    ".tiff",
    ".tif",
    ".heic",
}


def walk_files(
    root: Path, accept: Callable[[str], bool], max_depth: int = 12
) -> list[Path]:
    """Every regular file under ``root`` that ``accept`` admits, sorted.

    Never follows a symlink, to a file or a directory: a link can never be the
    route by which a walk leaves its scope. Dot-directories (``.git``) are
    skipped because they are machinery, not content.
    """
    out: list[Path] = []
    if not root.is_dir() or root.is_symlink():
        return out

    def visit(directory: Path, depth: int) -> None:
        if depth > max_depth:
            return
        try:
            entries = list(os.scandir(directory))
        except OSError:
            return
        for entry in entries:
            if entry.name.startswith("."):
                continue
            if entry.is_symlink():
                continue
            if entry.is_dir(follow_symlinks=False):
                visit(Path(entry.path), depth + 1)
            elif entry.is_file(follow_symlinks=False) and accept(entry.name):
                out.append(Path(entry.path))

    visit(root, 1)
    return sorted(out)


def list_wiki_files(root: Path, max_depth: int = 12) -> list[Path]:
    """Markdown pages in a scope."""
    return walk_files(root, lambda n: n.lower().endswith(".md"), max_depth)


def list_regular_files(root: Path, max_depth: int = 12) -> list[Path]:
    """Every file in a directory: raw sources are not only markdown."""
    return walk_files(root, lambda _n: True, max_depth)


def remove_symlinks(root: Path) -> list[str]:
    """Delete every symlink under ``root``; returns their relative paths.

    Run on an agent's write scope after each ingest. A link the agent created
    could point at another scope, and nothing downstream (git, the file API,
    the next sandbox mount) should ever be asked to follow it.
    """
    removed: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        here = Path(dirpath)
        for name in [*dirnames, *filenames]:
            p = here / name
            if p.is_symlink():
                p.unlink()
                removed.append(p.relative_to(root).as_posix())
        dirnames[:] = [d for d in dirnames if not (here / d).is_symlink()]
    return removed


def looks_binary(data: bytes) -> bool:
    """NUL in the first 8KB, or too much undecodable text, means binary."""
    head = data[:8192]
    if b"\x00" in head:
        return True
    text = head.decode("utf-8", errors="replace")
    return bool(text) and text.count("�") / len(text) > 0.02


def write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    tmp.write_bytes(content)
    tmp.replace(path)


def remove_file(path: Path) -> bool:
    """Remove one regular file. Refuses directories: a scope is a git repo, and
    deletions are meant to be explicit file removals, never ``rm -r``."""
    if path.is_symlink() or not path.is_file():
        return False
    path.unlink()
    return True


def move_to_trash(path: Path, trash_root: Path, label: str) -> Path | None:
    """Move a whole directory aside instead of deleting it.

    Used when a project is deleted: the wiki is the organization's knowledge
    and its git history, so removal is reversible by an operator rather than
    immediate and permanent.
    """
    if not path.exists():
        return None
    trash_root.mkdir(parents=True, exist_ok=True)
    dest = trash_root / label
    n = 1
    while dest.exists():
        dest = trash_root / f"{label}-{n}"
        n += 1
    shutil.move(str(path), str(dest))
    return dest
