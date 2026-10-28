"""Who may read and write which scope, derived from selfmemory's tenancy.

The mapping onto the existing Ory-backed model:

- **org room** (``org``): every active member of the organization reads it;
  the org owner and admins write it.
- **project** (``project:<id>``): the existing project permissions decide --
  org owner or project owner get full access, otherwise ``project_members``
  ``canRead``/``canWrite``.
- **sub-project**: a project with ``parentProjectId``. Its own permissions
  decide; membership of the parent confers nothing.
- **personal** (``user:<identity>``): only that person.

A caller authenticated by an API key or OAuth token is pinned to one project:
they see that project (and its readable sub-projects) plus the org room
read-only, never anyone's personal notes.

This is the single gate on the data API. Paths are resolved here, against the
layout, and never trusted from the caller.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from bson import ObjectId
from bson.errors import InvalidId

from selfmemory.features.wiki.adapters.graph import ScopeRoot
from selfmemory.features.wiki.domain.layout import (
    ORG_KEY,
    Scope,
    org_scope_rel,
    owning_scope_key,
    project_scope_rel,
    user_scope_rel,
)
from selfmemory.kernel.safe_paths import (
    PathRefused,
    is_within,
    resolve_contained,
    safe_segment,
)

if TYPE_CHECKING:
    from selfmemory.wiki_settings import WikiSettings

__all__ = [
    "AccessDenied",
    "Principal",
    "OrgAccess",
    "resolve_org_access",
    "default_org_id",
]


class AccessDenied(PermissionError):
    """The caller may not see or change this. Mapped to 403 (or 404)."""


@dataclass(frozen=True)
class Principal:
    user_id: str  # Kratos identity id
    pinned_project_id: str | None = None

    @classmethod
    def from_auth(cls, auth) -> Principal:
        # Session callers carry no project; token callers are pinned to theirs.
        return cls(user_id=auth.user_id, pinned_project_id=auth.project_id or None)

    @property
    def owner(self) -> str:
        """Who owns runs and chats this principal creates.

        A credential pinned to a project is a separate owner from the same
        person's session: a project API key must not read the runs and chats
        (and so the answers drawn from personal notes or other projects) that
        its holder created through the dashboard.
        """
        if self.pinned_project_id:
            return f"{self.user_id}#project:{self.pinned_project_id}"
        return self.user_id

    def to_doc(self) -> dict:
        return {
            "userId": self.user_id,
            "pinnedProjectId": self.pinned_project_id,
            "owner": self.owner,
        }

    @classmethod
    def from_doc(cls, doc: dict) -> Principal:
        return cls(user_id=doc["userId"], pinned_project_id=doc.get("pinnedProjectId"))


def _oid(value: str, what: str) -> ObjectId:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError) as e:
        raise AccessDenied(f"invalid {what}") from e


def _owns(doc: dict, kratos_id: str, user_oid) -> bool:
    return doc.get("ownerId") in (kratos_id, user_oid)


def _user_doc_id(db, kratos_id: str):
    user = db.users.find_one({"$or": [{"_id": kratos_id}, {"kratosId": kratos_id}]})
    if not user:
        raise AccessDenied("unknown user")
    return user["_id"]


@dataclass
class OrgAccess:
    """One caller's resolved view of one organization."""

    org_id: str
    org_name: str
    root: Path
    principal: Principal
    is_admin: bool
    scopes: list[Scope]
    # every real sub-project in the org, readable or not: parent -> children
    children: dict[str, set[str]] = field(default_factory=dict)

    # ----------------------------------------------------------------- lookup

    def scope(self, key: str) -> Scope:
        for s in self.scopes:
            if s.key == key:
                return s
        raise AccessDenied(f"no such scope for this account: {key}")

    def writable(self, key: str) -> Scope:
        s = self.scope(key)
        if not s.writable:
            raise AccessDenied(f"scope is read-only for this account: {key}")
        return s

    def is_child(self, parent: str, child: str) -> bool:
        return child in self.children.get(parent, set())

    def abs(self, rel: str) -> Path:
        return self.root / rel

    def scope_root(self, s: Scope) -> ScopeRoot:
        return ScopeRoot(
            key=s.key,
            rel=s.wiki_rel,
            abs=self.abs(s.wiki_rel),
            exclude=s.nested_rels("wiki"),
        )

    def scope_roots(self, key: str | None = None) -> list[ScopeRoot]:
        chosen = [self.scope(key)] if key else self.scopes
        if key:
            # an umbrella project also covers the sub-projects the caller reads
            s = chosen[0]
            chosen += [self.scope(f"project:{c}") for c in self._readable_children(s)]
        return [self.scope_root(s) for s in chosen]

    def _readable_children(self, s: Scope) -> list[str]:
        keys = {x.key for x in self.scopes}
        return [c for c in s.nested if f"project:{c}" in keys]

    # ------------------------------------------------------------------ paths

    def resolve_path(
        self, rel: str, *, write: bool = False, allow_dir: bool = False
    ) -> tuple[Scope, str, Path]:
        """Resolve an org-root-relative path for this caller.

        The owning scope is derived from the layout, then must be one of the
        caller's scopes (writable, if ``write``), and the resolved path must
        stay inside that scope's directory after symlinks are followed.
        """
        side, key = owning_scope_key(rel, self.is_child)
        scope = self.writable(key) if write else self.scope(key)
        scope_dir = self.abs(scope.rel(side))
        path = resolve_contained(self.root, rel)
        if not is_within(path, scope_dir):
            raise PathRefused("path is not inside any scope you can read")
        # The lexical path proves nothing about where a symlink inside the
        # scope points (an agent with a writable scope can create one), so the
        # real path must also land in this scope and outside its sub-projects.
        real = Path(os.path.realpath(path))
        if not is_within(real, os.path.realpath(scope_dir)) or any(
            is_within(real, os.path.realpath(self.abs(r)))
            for r in scope.nested_rels(side)
        ):
            raise PathRefused("path is not inside any scope you can read")
        if path.is_symlink():
            raise PathRefused("symlinks are not served")
        if path.is_dir() and not allow_dir:
            raise PathRefused("path is a directory")
        return scope, side, path

    # ------------------------------------------------------------------ runs

    def mount_plan(self, command: str, key: str | None) -> dict:
        """Directories an agent run may read and write, re-derived at run time.

        Every mounted scope directory has its nested sub-projects masked; the
        ones this caller may read are mounted back on top, read-only. An
        ingest writes only its own scope's wiki and reads that scope's raw
        sources, its readable sub-projects and the org room.
        """
        reads: list[Scope]
        write_dir: Path | None = None
        raw_dir: Path | None = None
        if command == "ingest":
            if not key:
                raise AccessDenied("ingest needs a scope")
            target = self.writable(key)
            write_dir = self.abs(target.wiki_rel)
            raw_dir = self.abs(target.raw_rel)
            reads = [target]
        elif key:
            reads = [self.scope(key)]
        else:
            reads = list(self.scopes)
        # an umbrella scope brings in the sub-projects the caller can read
        expanded: dict[str, Scope] = {s.key: s for s in reads}
        for s in reads:
            for c in self._readable_children(s):
                expanded.setdefault(f"project:{c}", self.scope(f"project:{c}"))
        # the org room is context for everyone who can read it
        org = next((s for s in self.scopes if s.key == ORG_KEY), None)
        if org is not None:
            expanded.setdefault(ORG_KEY, org)

        read_dirs = [self.abs(s.wiki_rel) for s in expanded.values()]
        if raw_dir is not None:
            read_dirs.append(raw_dir)
        mask: list[Path] = []
        for s in expanded.values():
            mask += [self.abs(r) for r in s.nested_rels("wiki")]
            # Each scope's repository metadata stays out of reach: a .git/config
            # an agent could edit is a command the server's next commit runs.
            mask.append(self.abs(s.wiki_rel) / ".git")
            if raw_dir is not None and s.key == key:
                mask += [self.abs(r) for r in s.nested_rels("raw")]
        labels = {s.wiki_rel: s.label for s in expanded.values()}
        return {
            "read_dirs": sorted(set(read_dirs), key=lambda p: (len(p.parts), str(p))),
            "write_dir": write_dir,
            "mask_dirs": sorted(set(mask)),
            "labels": labels,
        }

    def summary(self) -> dict:
        return {
            "org_id": self.org_id,
            "org_name": self.org_name,
            "is_admin": self.is_admin,
            "pinned_project_id": self.principal.pinned_project_id,
            "scopes": [s.summary() for s in self.scopes],
        }


def _perms_from_member(member: dict | None) -> tuple[bool, bool]:
    if not member:
        return False, False
    p = member.get("permissions") or {}
    return bool(p.get("canRead")), bool(p.get("canWrite"))


def resolve_org_access(
    db, settings: WikiSettings, principal: Principal, org_id: str
) -> OrgAccess:
    """Compute every scope the principal may read in one organization.

    A fixed number of indexed reads regardless of project count: the org, the
    caller's org membership, the org's projects, and the caller's project
    memberships.
    """
    org_oid = _oid(org_id, "organization id")
    safe_segment(org_id)
    org = db.organizations.find_one({"_id": org_oid})
    if not org:
        raise AccessDenied("organization not found")
    kratos_id = principal.user_id
    user_oid = _user_doc_id(db, kratos_id)
    safe_segment(str(kratos_id))

    org_owner = _owns(org, kratos_id, user_oid)
    member = db.organization_members.find_one(
        {"organizationId": org_oid, "userId": user_oid, "status": "active"}
    )
    in_org = org_owner or member is not None
    is_admin = org_owner or (
        member is not None and member.get("role") in ("owner", "admin")
    )

    projects = list(db.projects.find({"organizationId": org_oid}))
    by_id = {str(p["_id"]): p for p in projects}
    children: dict[str, set[str]] = {}
    for pid, p in by_id.items():
        parent = p.get("parentProjectId")
        if parent is not None and str(parent) in by_id:
            children.setdefault(str(parent), set()).add(pid)

    memberships = {
        str(m["projectId"]): m
        for m in db.project_members.find(
            {"userId": user_oid, "projectId": {"$in": [p["_id"] for p in projects]}}
        )
    }

    pinned = principal.pinned_project_id
    if pinned is not None and pinned not in by_id:
        raise AccessDenied("this credential's project is not in that organization")

    def access(pid: str) -> tuple[bool, bool]:
        p = by_id[pid]
        if org_owner or _owns(p, kratos_id, user_oid):
            return True, True
        return _perms_from_member(memberships.get(pid))

    def visible(pid: str) -> bool:
        if pinned is None:
            return True
        parent = by_id[pid].get("parentProjectId")
        return pid == pinned or (parent is not None and str(parent) == pinned)

    scopes: list[Scope] = []
    if in_org:
        scopes.append(
            Scope(
                key=ORG_KEY,
                kind="org",
                label=f"{org.get('name', 'Organization')} (org room)",
                org_id=org_id,
                wiki_rel=org_scope_rel("wiki"),
                raw_rel=org_scope_rel("raw"),
                writable=is_admin and pinned is None,
            )
        )
    for pid, p in sorted(by_id.items(), key=lambda kv: str(kv[1].get("name", ""))):
        if not visible(pid):
            continue
        can_read, can_write = access(pid)
        if not can_read:
            continue
        parent = p.get("parentProjectId")
        parent_id = str(parent) if parent is not None and str(parent) in by_id else None
        nested = tuple(sorted(children.get(pid, set())))
        scopes.append(
            Scope(
                key=f"project:{pid}",
                kind="project",
                label=str(p.get("name") or pid),
                org_id=org_id,
                wiki_rel=project_scope_rel("wiki", pid, parent_id),
                raw_rel=project_scope_rel("raw", pid, parent_id),
                writable=can_write,
                parent=f"project:{parent_id}" if parent_id else None,
                children=nested,
                nested=nested,
            )
        )
    if pinned is None:
        scopes.append(
            Scope(
                key=f"user:{kratos_id}",
                kind="user",
                label="My notes",
                org_id=org_id,
                wiki_rel=user_scope_rel("wiki", kratos_id),
                raw_rel=user_scope_rel("raw", kratos_id),
                writable=True,
            )
        )
    if not in_org and not any(s.kind == "project" for s in scopes):
        raise AccessDenied("not a member of this organization")

    return OrgAccess(
        org_id=org_id,
        org_name=str(org.get("name", "")),
        root=settings.org_root(org_id),
        principal=principal,
        is_admin=is_admin,
        scopes=scopes,
        children=children,
    )


def default_org_id(db, principal: Principal, organization_id: str | None) -> str:
    """The org a request is about when the caller did not name one.

    Token callers belong to their project's org. A session caller with exactly
    one organization gets that one; with several, they must say which.
    """
    if principal.pinned_project_id:
        project = db.projects.find_one(
            {"_id": _oid(principal.pinned_project_id, "project id")}
        )
        if not project:
            raise AccessDenied("this credential's project no longer exists")
        return str(project["organizationId"])
    if organization_id:
        return organization_id
    user_oid = _user_doc_id(db, principal.user_id)
    org_ids = {
        str(m["organizationId"])
        for m in db.organization_members.find({"userId": user_oid, "status": "active"})
    }
    org_ids |= {
        str(o["_id"])
        for o in db.organizations.find(
            {"ownerId": {"$in": [principal.user_id, user_oid]}}
        )
    }
    if len(org_ids) == 1:
        return org_ids.pop()
    if not org_ids:
        raise AccessDenied("you are not a member of any organization")
    raise AccessDenied("org_id is required: you belong to several organizations")
