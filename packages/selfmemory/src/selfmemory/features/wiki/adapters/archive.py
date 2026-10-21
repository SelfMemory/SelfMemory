"""Moving a deleted project's or organization's wiki aside.

Deleting a project in Mongo used to leave nothing behind on disk because
there was nothing on disk. Now a project owns a wiki (with its git history)
and raw sources, so deletion moves them under ``<data root>/.trash/`` instead
of erasing them: recovery is an operator ``mv``, not a backup restore.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from selfmemory.features.wiki.adapters.files import move_to_trash
from selfmemory.features.wiki.domain.layout import project_scope_rel
from selfmemory.wiki_settings import load_settings

logger = logging.getLogger(__name__)


def _stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def archive_project(project: dict) -> list[str]:
    settings = load_settings()
    org_id = str(project["organizationId"])
    parent = project.get("parentProjectId")
    moved = []
    for side in ("wiki", "raw"):
        rel = project_scope_rel(
            side, str(project["_id"]), str(parent) if parent else None
        )
        dest = move_to_trash(
            settings.org_root(org_id) / rel,
            settings.trash_root,
            f"{_stamp()}-org-{org_id}-project-{project['_id']}-{side}",
        )
        if dest:
            moved.append(str(dest))
    return moved


def archive_org(org_id: str) -> str | None:
    settings = load_settings()
    dest = move_to_trash(
        settings.org_root(org_id), settings.trash_root, f"{_stamp()}-org-{org_id}"
    )
    return str(dest) if dest else None
