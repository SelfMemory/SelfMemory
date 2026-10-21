"""Tenancy: who reads and writes which scope, and where paths resolve."""

from __future__ import annotations

import pytest

from selfmemory.features.tenancy.access import (
    AccessDenied,
    Principal,
    default_org_id,
    resolve_org_access,
)
from selfmemory.features.wiki.domain.layout import owning_scope_key
from selfmemory.kernel.safe_paths import (
    PathRefused,
    resolve_contained,
    safe_rel_path,
    sanitize_upload_dir,
)


def keys(access):
    return {s.key for s in access.scopes}


class TestPaths:
    @pytest.mark.parametrize("bad", ["", "../x", "a/../../b", "a/\x00b", "wiki/../raw"])
    def test_traversal_refused(self, bad):
        with pytest.raises(PathRefused):
            safe_rel_path(bad)

    def test_leading_slash_and_dots_normalised(self):
        assert safe_rel_path("/wiki/./org//x.md") == "wiki/org/x.md"

    def test_symlink_out_of_root_refused(self, tmp_path):
        root = tmp_path / "root"
        (root / "wiki").mkdir(parents=True)
        outside = tmp_path / "outside"
        outside.mkdir()
        (root / "wiki" / "link").symlink_to(outside)
        with pytest.raises(PathRefused):
            resolve_contained(root, "wiki/link/secret.md")

    def test_upload_dir_is_sanitised(self):
        assert sanitize_upload_dir("deck/<q1>/notes") == "deck/_q1_/notes"
        with pytest.raises(PathRefused):
            sanitize_upload_dir("a/../b")

    def test_owner_of_nested_path_needs_a_real_child(self):
        def is_child(p, c):
            return (p, c) == ("p1", "c1")

        assert owning_scope_key("wiki/projects/p1/c1/x.md", is_child) == (
            "wiki",
            "project:c1",
        )
        assert owning_scope_key("wiki/projects/p1/people/x.md", is_child) == (
            "wiki",
            "project:p1",
        )
        assert owning_scope_key("raw/org/a.pdf", is_child) == ("raw", "org")
        with pytest.raises(PathRefused):
            owning_scope_key("elsewhere/x.md", is_child)


class TestScopes:
    def test_member_sees_org_their_projects_and_own_notes(self, db, world, settings):
        a = resolve_org_access(db, settings, Principal(world.member), world.org_id)
        assert keys(a) == {
            "org",
            f"project:{world.alpha}",
            f"project:{world.child}",
            f"user:{world.member}",
        }
        assert not a.scope("org").writable
        assert a.scope(f"project:{world.alpha}").writable
        assert not a.scope(f"project:{world.child}").writable

    def test_owner_sees_and_writes_everything_but_others_notes(
        self, db, world, settings
    ):
        a = resolve_org_access(db, settings, Principal(world.owner), world.org_id)
        assert f"project:{world.beta}" in keys(a)
        assert a.scope("org").writable
        assert f"user:{world.member}" not in keys(a)

    def test_outsider_is_refused(self, db, world, settings):
        with pytest.raises(AccessDenied):
            resolve_org_access(db, settings, Principal(world.outsider), world.org_id)

    def test_parent_membership_does_not_grant_child(self, db, world, settings):
        db.project_members.delete_many({"projectId": world.child})
        a = resolve_org_access(db, settings, Principal(world.member), world.org_id)
        assert f"project:{world.child}" not in keys(a)
        # and a path inside the child is not readable through the parent
        with pytest.raises(AccessDenied):
            a.resolve_path(f"wiki/projects/{world.alpha}/{world.child}/x.md")

    def test_pinned_credential_sees_its_project_and_org_only(self, db, world, settings):
        p = Principal(world.member, pinned_project_id=str(world.alpha))
        a = resolve_org_access(db, settings, p, world.org_id)
        assert keys(a) == {"org", f"project:{world.alpha}", f"project:{world.child}"}
        assert not a.scope("org").writable

    def test_default_org(self, db, world):
        assert default_org_id(db, Principal(world.member), None) == world.org_id
        pinned = Principal(world.member, pinned_project_id=str(world.beta))
        assert default_org_id(db, pinned, None) == world.org_id

    def test_write_needs_writable_scope(self, db, world, settings):
        a = resolve_org_access(db, settings, Principal(world.member), world.org_id)
        with pytest.raises(AccessDenied):
            a.resolve_path("wiki/org/x.md", write=True)
        scope, side, path = a.resolve_path(
            f"wiki/projects/{world.alpha}/x.md", write=True
        )
        assert scope.key == f"project:{world.alpha}" and side == "wiki"
        assert path == a.root / "wiki" / "projects" / str(world.alpha) / "x.md"


class TestMountPlan:
    def test_ingest_masks_children_and_remounts_readable_ones(
        self, db, world, settings
    ):
        a = resolve_org_access(db, settings, Principal(world.member), world.org_id)
        plan = a.mount_plan("ingest", f"project:{world.alpha}")
        alpha = a.root / "wiki" / "projects" / str(world.alpha)
        child = alpha / str(world.child)
        assert plan["write_dir"] == alpha
        assert child in plan["mask_dirs"]
        assert child in plan["read_dirs"]  # readable, so mounted back read-only
        assert a.root / "raw" / "projects" / str(world.alpha) in plan["read_dirs"]
        assert a.root / "wiki" / "org" in plan["read_dirs"]

    def test_query_without_scope_reads_everything_readable(self, db, world, settings):
        a = resolve_org_access(db, settings, Principal(world.member), world.org_id)
        plan = a.mount_plan("query", None)
        assert plan["write_dir"] is None
        assert a.root / "wiki" / "users" / world.member in plan["read_dirs"]
        assert not any(str(world.beta) in str(d) for d in plan["read_dirs"])

    def test_ingest_into_read_only_scope_refused(self, db, world, settings):
        a = resolve_org_access(db, settings, Principal(world.member), world.org_id)
        with pytest.raises(AccessDenied):
            a.mount_plan("ingest", f"project:{world.child}")


def test_hidden_paths_refused():
    for bad in ("wiki/projects/p/.git/config", "wiki/org/.hidden.md", ".agent/x"):
        with pytest.raises(PathRefused):
            safe_rel_path(bad)
    assert sanitize_upload_dir(".git/hooks") == "git/hooks"


def test_mount_plan_masks_every_scope_git_dir(db, world, settings):
    a = resolve_org_access(db, settings, Principal(world.member), world.org_id)
    plan = a.mount_plan("ingest", f"project:{world.alpha}")
    alpha = a.root / "wiki" / "projects" / str(world.alpha)
    assert alpha / ".git" in plan["mask_dirs"]
    assert a.root / "wiki" / "org" / ".git" in plan["mask_dirs"]
