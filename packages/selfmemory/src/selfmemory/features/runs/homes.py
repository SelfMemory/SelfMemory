"""Where agent session homes live, and how they go away.

A home holds an opencode transcript, which carries the text of every file the
run read. It is keyed by (organization, credential owner, chat, mount set):
never shared between owners, chats or scope selections. Turns without a chat
(one-shot tasks) share a per-owner ``_oneshot`` area, since nothing continues
their sessions.

A home is deleted with its chat, and any home unused for
``session_home_retention_s`` is deleted by the worker's housekeeping.
"""

from __future__ import annotations

import contextlib
import hashlib
import logging
import os
import shutil
import time
from typing import TYPE_CHECKING

from selfmemory.kernel.safe_paths import safe_segment

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["homes_root", "run_home", "chat_home", "delete_chat_home", "prune_homes"]

logger = logging.getLogger(__name__)

ONESHOT = "_oneshot"


def homes_root(settings) -> Path:
    return settings.data_root / ".homes"


def _owner_dir(settings, org_id: str, owner: str) -> Path:
    who = hashlib.sha256(owner.encode()).hexdigest()[:24]
    return homes_root(settings) / safe_segment(org_id) / who


def chat_home(settings, org_id: str, owner: str, chat_id: str | None) -> Path:
    """The directory holding every home of one chat (one per mount set)."""
    seg = safe_segment(chat_id) if chat_id else ONESHOT
    return _owner_dir(settings, org_id, owner) / seg


def run_home(settings, job: dict, digest: str) -> Path:
    owner = job.get("owner") or job["userId"]
    return chat_home(settings, job["orgId"], owner, job.get("chatId")) / digest


def touch(home: Path) -> None:
    """Mark a home as used now; retention counts from the last use."""
    with contextlib.suppress(OSError):
        os.utime(home)


def delete_chat_home(settings, chat: dict) -> bool:
    """Remove every session home of a chat. True when something was removed."""
    path = chat_home(settings, chat["orgId"], chat["owner"], chat["_id"])
    if not path.exists():
        return False
    shutil.rmtree(path, ignore_errors=True)
    return True


def prune_homes(settings, max_age_s: int, at: float | None = None) -> int:
    """Delete session homes (the per-digest directories) unused for
    ``max_age_s``, and the chat / owner / org directories they leave empty."""
    root = homes_root(settings)
    if not root.is_dir():
        return 0
    cutoff = (at if at is not None else time.time()) - max_age_s
    removed = 0
    # layout: root / org / owner / chat / digest
    for org in _dirs(root):
        for owner in _dirs(org):
            for chat in _dirs(owner):
                for home in _dirs(chat):
                    try:
                        if home.stat().st_mtime < cutoff:
                            shutil.rmtree(home, ignore_errors=True)
                            removed += 1
                    except OSError:
                        continue
                _rmdir_if_empty(chat)
            _rmdir_if_empty(owner)
        _rmdir_if_empty(org)
    if removed:
        logger.info("pruned %d session home(s)", removed)
    return removed


def _dirs(path: Path) -> list[Path]:
    try:
        return [p for p in path.iterdir() if p.is_dir() and not p.is_symlink()]
    except OSError:
        return []


def _rmdir_if_empty(path: Path) -> None:
    with contextlib.suppress(OSError):
        path.rmdir()
