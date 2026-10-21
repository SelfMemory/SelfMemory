"""Scopes and the on-disk layout. The layout *is* the tenancy.

Each organization owns one tree under the data root::

    orgs/<org>/wiki/org                       the org room: every member reads it
    orgs/<org>/wiki/projects/<p>              a project
    orgs/<org>/wiki/projects/<p>/<c>          a sub-project, inside its parent
    orgs/<org>/wiki/users/<u>                 one person's private notes
    orgs/<org>/raw/...                        the same four shapes, for sources

Every scope directory under ``wiki/`` is its own git repository and its own
Open Knowledge Format bundle.

A sub-project lives *inside* its parent's directory. That is why the owner of a
path is derived from the layout (and the list of real sub-projects) instead of
by testing which of the caller's roots contains it: a containment test would
hand a member of an umbrella project every sub-project beneath it, and
membership of a parent does not confer membership of a child.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from selfmemory.kernel.safe_paths import PathRefused, safe_rel_path, safe_segment

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = [
    "Scope",
    "ORG_KEY",
    "org_scope_rel",
    "project_scope_rel",
    "user_scope_rel",
    "owning_scope_key",
    "scope_kind",
]

ORG_KEY = "org"
SIDES = ("wiki", "raw")


@dataclass(frozen=True)
class Scope:
    """One tenancy unit, resolved for a particular caller.

    Paths are relative to the organization root, so they are what API clients
    send and what the agent cites (``wiki/projects/<p>/people/ada.md``).
    """

    key: str
    kind: str  # "org" | "project" | "user"
    label: str
    org_id: str
    wiki_rel: str
    raw_rel: str
    writable: bool
    parent: str | None = None
    children: tuple[str, ...] = ()
    # Wiki directories a question asked in this scope reads. An umbrella
    # project includes the sub-projects the caller is a member of; nothing
    # else ever reads more than its own directory.
    read_rels: tuple[str, ...] = field(default=())
    # Every real sub-project nested inside this scope's directory, readable by
    # the caller or not. Walks and agent mounts of this scope must mask them:
    # they are separate scopes with their own membership.
    nested: tuple[str, ...] = ()

    def rel(self, side: str) -> str:
        if side not in SIDES:
            raise PathRefused(f"unknown side: {side!r}")
        return self.wiki_rel if side == "wiki" else self.raw_rel

    def nested_rels(self, side: str) -> tuple[str, ...]:
        return tuple(f"{self.rel(side)}/{child}" for child in self.nested)

    def summary(self) -> dict:
        return {
            "key": self.key,
            "kind": self.kind,
            "label": self.label,
            "writable": self.writable,
            "parent": self.parent,
            "children": list(self.children),
            "wiki": self.wiki_rel,
            "raw": self.raw_rel,
        }


def scope_kind(key: str) -> str:
    if key == ORG_KEY:
        return "org"
    prefix, _, ident = key.partition(":")
    if prefix in ("project", "user") and ident:
        return prefix
    raise PathRefused(f"not a scope key: {key!r}")


def org_scope_rel(side: str) -> str:
    return f"{side}/org"


def project_scope_rel(side: str, project_id: str, parent_id: str | None = None) -> str:
    if parent_id:
        return f"{side}/projects/{safe_segment(parent_id)}/{safe_segment(project_id)}"
    return f"{side}/projects/{safe_segment(project_id)}"


def user_scope_rel(side: str, user_id: str) -> str:
    return f"{side}/users/{safe_segment(user_id)}"


def owning_scope_key(
    rel_path: str, is_child: Callable[[str, str], bool]
) -> tuple[str, str]:
    """The scope a path belongs to, from the layout alone.

    Returns ``(side, scope_key)``. ``is_child(parent, child)`` says whether
    ``child`` is a real sub-project of ``parent``; without it a category
    folder whose name happened to look like an id would be mistaken for a
    sub-project, and a sub-project would be mistaken for a category folder.
    """
    parts = safe_rel_path(rel_path).split("/")
    if len(parts) < 2 or parts[0] not in SIDES:
        raise PathRefused("path is not inside any scope")
    side, area = parts[0], parts[1]
    if area == "org":
        return side, ORG_KEY
    if area == "users" and len(parts) >= 3:
        return side, f"user:{parts[2]}"
    if area == "projects" and len(parts) >= 3:
        parent = parts[2]
        if len(parts) >= 4 and is_child(parent, parts[3]):
            return side, f"project:{parts[3]}"
        return side, f"project:{parent}"
    raise PathRefused("path is not inside any scope")
