"""Confining configured paths to a directory.

A path that comes from configuration is still a path someone else chose. Code
that then creates parent directories or writes a file at it should first check
the result lands where it is supposed to -- otherwise an absolute path or a
``../`` segment in a setting writes somewhere on the host nobody intended.
"""

from __future__ import annotations

import os
from pathlib import Path

__all__ = ["resolve_within"]


def resolve_within(base: Path, configured: str) -> Path:
    """Resolve ``configured`` against ``base`` and refuse anything outside it.

    Relative paths resolve exactly as they would by joining onto ``base``. An
    absolute path is accepted only if it already points inside ``base``.

    Uses ``os.path.normpath`` plus a prefix check rather than
    ``Path.resolve()`` / ``is_relative_to``: it collapses ``..`` without
    touching the filesystem, so a not-yet-created file can be checked, and it
    is the form static analysers recognise as a path-traversal guard.

    Args:
        base: The directory the result must stay inside.
        configured: The configured path, relative to ``base`` or absolute.

    Returns:
        Path: The normalized path, guaranteed to be inside ``base``.

    Raises:
        ValueError: If the path is empty, is ``base`` itself, or escapes it.
    """
    root = os.path.normpath(base)
    candidate = os.path.normpath(Path(root) / configured)
    if not candidate.startswith(root + os.sep):
        raise ValueError(f"path must resolve inside {root}; got {configured!r}")
    return Path(candidate)
