"""Job queue, scope lease, and the worker running a (fake) agent end to end."""

from __future__ import annotations

import threading
from dataclasses import replace
from datetime import timedelta

import pytest
from pymongo.errors import DuplicateKeyError

from selfmemory.features.runs import worker as worker_mod
from selfmemory.features.runs.store import (
    JOBS,
    ChatStore,
    JobStore,
    ScopeBusyError,
    ScopeLease,
    ensure_indexes,
    now,
)
from selfmemory.features.tenancy.access import Principal
from selfmemory.features.wiki.adapters import git_repo as git
from selfmemory.features.wiki.service import WikiService
from selfmemory.platform.sandbox.isolation import IsolationStatus


def _job(store: JobStore, **kw):
    args = {
        "principal": {"userId": "u1", "pinnedProjectId": None, "owner": "u1"},
        "org_id": "o1",
        "command": "query",
        "scope": None,
        "message": "q",
        "display_text": "q",
    }
    args.update(kw)
    return store.create(**args)


class TestJobStore:
    def test_claim_is_fifo_and_exclusive(self, db):
        s = JobStore(db)
        first = _job(s)
        _job(s)
        claimed = s.claim("w1")
        assert claimed["_id"] == first["_id"] and claimed["attempts"] == 1
        assert s.claim("w2")["_id"] != first["_id"]
        assert s.claim("w3") is None

    def test_events_are_sequenced_and_owner_guarded(self, db):
        s = JobStore(db)
        j = _job(s)
        s.claim("w1")
        assert s.append(j["_id"], "w1", [{"kind": "text"}, {"kind": "text"}]) == 2
        assert s.append(j["_id"], "intruder", [{"kind": "x"}]) is None
        assert [e["seq"] for e in s.read_events(j["_id"], 0)] == [1, 2]
        assert [e["seq"] for e in s.read_events(j["_id"], 1)] == [2]
        assert s.finish(j["_id"], "w1", "done", {"answer": "a"})
        assert not s.finish(j["_id"], "w1", "done", {})

    def test_reaper_requeues_then_fails(self, db):
        s = JobStore(db)
        j = _job(s)
        s.claim("w1")
        later = now() + timedelta(seconds=120)
        assert s.reap_stale(later) == {"requeued": 1, "failed": 0}
        s.claim("w2")
        s.reap_stale(later)
        s.claim("w3")
        assert s.reap_stale(later) == {"requeued": 0, "failed": 1}
        assert s.get(j["_id"])["status"] == "failed"

    def test_requeue_delays_reclaim(self, db):
        s = JobStore(db)
        j = _job(s)
        s.claim("w1")
        assert s.requeue(j["_id"], "w1", delay_s=60)
        assert s.claim("w1") is None
        assert s.get(j["_id"])["attempts"] == 0

    def test_turns_of_one_chat_run_in_order(self, db):
        ensure_indexes(db)
        s = JobStore(db)
        first = _job(s, chat_id="c1")
        second = _job(s, chat_id="c1")
        other = _job(s)
        assert s.claim("w1")["_id"] == first["_id"]
        # the chat is busy, so the next claim skips its second turn
        assert s.claim("w2")["_id"] == other["_id"]
        assert s.claim("w3") is None
        s.finish(first["_id"], "w1", "done", {})
        assert s.claim("w3")["_id"] == second["_id"]

    def test_unique_index_stops_a_second_running_turn(self, db):
        ensure_indexes(db)
        s = JobStore(db)
        _job(s, chat_id="c1")
        s.claim("w1")
        late = _job(s, chat_id="c1")
        with pytest.raises(DuplicateKeyError):
            db[JOBS].update_one({"_id": late["_id"]}, {"$set": {"status": "running"}})

    def test_fair_share_caps_owner_and_org(self, db):
        s = JobStore(db)
        busy = {"userId": "u1", "pinnedProjectId": None, "owner": "u1"}
        calm = {"userId": "u2", "pinnedProjectId": None, "owner": "u2"}
        a1 = _job(s, principal=busy)
        _job(s, principal=busy)
        b1 = _job(s, principal=calm)
        assert s.claim("w", max_per_owner=1)["_id"] == a1["_id"]
        # u1 is at its cap, so u2 goes ahead of u1's older job
        assert s.claim("w", max_per_owner=1)["_id"] == b1["_id"]
        assert s.claim("w", max_per_owner=1) is None
        _job(s, principal=calm, org_id="o1")
        assert s.claim("w", max_per_org=2) is None
        assert s.claim("w", max_per_org=3) is not None

    def test_idle_agent_contexts_expire(self, db):
        chats = ChatStore(db)
        s = JobStore(db)
        old = chats.create("u1", "o1", None, kind="a2a")
        app = chats.create("u1", "o1", None)
        busy = chats.create("u1", "o1", None, kind="a2a")
        _job(s, chat_id=busy["_id"])
        assert chats.prune_idle("a2a", now() + timedelta(hours=2)) == 1
        assert chats.owned("u1", old["_id"]) is None
        assert chats.owned("u1", app["_id"]) and chats.owned("u1", busy["_id"])

    def test_cancel_queued_and_running(self, db):
        s = JobStore(db)
        q = _job(s)
        assert s.request_cancel("u1", q["_id"])["status"] == "cancelled"
        r = _job(s)
        s.claim("w1")
        flagged = s.request_cancel("u1", r["_id"])
        assert flagged["status"] == "running" and flagged["cancelRequestedAt"]
        assert s.request_cancel("someone-else", r["_id"]) is None
        assert s.owned("u1", "not-a-job-id") is None


def test_lease_excludes_and_expires(db):
    a = ScopeLease(db, "/scope", "a", ttl_s=30, wait_s=0)
    a.acquire()
    b = ScopeLease(db, "/scope", "b", ttl_s=30, wait_s=0)
    with pytest.raises(ScopeBusyError):
        b.acquire()
    db["wiki_leases"].update_one(
        {"_id": "/scope"}, {"$set": {"expiresAt": now() - timedelta(seconds=1)}}
    )
    b.acquire()  # takes over the expired lease
    assert not a.renew()
    b.release()


# ------------------------------------------------------------------ worker

FAKE_AGENT = r"""#!/bin/sh
# Stands in for `opencode run --format json`: writes a page when it has a
# SCOPE_ROOT inside the org (an ingest) and streams opencode-shaped events.
case "$*" in *selfmemory-ingest*)
  mkdir -p "$SCOPE_ROOT/people"
  printf -- '---\ntype: Person\ntitle: Ada\n---\nAda wrote the first program.\n' > "$SCOPE_ROOT/people/ada.md"
  ;;
esac
echo '{"type":"tool_use","sessionID":"ses_fake","part":{"tool":"write","state":{"status":"completed","title":"people/ada.md"}}}'
echo '{"type":"step_finish","sessionID":"ses_fake","part":{"tokens":{"input":10,"output":5},"cost":0.01}}'
echo '{"type":"text","sessionID":"ses_fake","part":{"text":"Filed wiki/people/ada.md"}}'
"""


@pytest.fixture
def service(db, settings, tmp_path, monkeypatch):
    agent = tmp_path / "fake-opencode"
    agent.write_text(FAKE_AGENT)
    agent.chmod(0o755)
    unconfined = IsolationStatus(
        kind=None,
        ok=False,
        blocked=False,
        required=False,
        acknowledged=True,
        detail="test",
    )
    monkeypatch.setattr(worker_mod, "require_isolation", lambda _s: unconfined)
    return WikiService(db, replace(settings, agent_bin=str(agent)))


def _run(service, job):
    claimed = service.jobs.claim("w1")
    assert claimed["_id"] == job["_id"]
    worker_mod.execute_job(service, claimed, "w1", threading.Event())
    return service.jobs.get(job["_id"])


def test_ingest_run_writes_commits_and_records_chat(service, world):
    access = service.access(Principal(world.member), world.org_id)
    chat = service.chats.create(world.member, world.org_id, None, world.member)
    key = f"project:{world.alpha}"
    job = service.enqueue(
        access, command="ingest", message="raw/x.md", scope_key=key, chat=chat
    )
    done = _run(service, job)
    assert done["status"] == "done", done["result"]
    result = done["result"]
    assert result["answer"] == "Filed wiki/people/ada.md"
    assert result["commit"]["scope"] == key
    assert result["tokens"] == {"input": 10, "output": 5}
    scope_dir = access.abs(access.scope(key).wiki_rel)
    assert (scope_dir / "people" / "ada.md").exists()
    assert "ingest |" in git.history(scope_dir, 1)[0].message
    kinds = [e["event"]["kind"] for e in service.jobs.read_events(job["_id"], 0)]
    assert kinds[0] == "start" and "commit" in kinds and "text" in kinds
    msgs = service.chats.messages_for(chat["_id"])
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert service.chats.owned(world.member, chat["_id"])["sessionId"] == "ses_fake"


def test_query_run_writes_nothing(service, world):
    access = service.access(Principal(world.member), world.org_id)
    job = service.enqueue(
        access, command="query", message="who is ada?", scope_key=None
    )
    done = _run(service, job)
    assert done["status"] == "done"
    assert done["result"]["commit"] is None


def test_run_fails_when_access_was_revoked(service, world, db):
    access = service.access(Principal(world.member), world.org_id)
    job = service.enqueue(
        access, command="ingest", message="x", scope_key=f"project:{world.alpha}"
    )
    db.organization_members.delete_many({"userId": world.member})
    db.project_members.delete_many({"userId": world.member})
    done = _run(service, job)
    assert done["status"] == "failed"
    assert "can no longer run here" in done["result"]["error"]


def test_busy_scope_requeues_ingest(service, world):
    access = service.access(Principal(world.member), world.org_id)
    key = f"project:{world.alpha}"
    job = service.enqueue(access, command="ingest", message="x", scope_key=key)
    service.ensure_all(access)  # scaffolding takes the lease too
    held = service.lease(access, access.scope(key), "someone", wait_s=0)
    held.acquire()
    try:
        after = _run(service, job)
    finally:
        held.release()
    assert after["status"] == "queued" and after["attempts"] == 0


def test_enqueue_validates(service, world):
    access = service.access(Principal(world.member), world.org_id)
    with pytest.raises(ValueError):
        service.enqueue(access, command="query", message="  ", scope_key=None)
    lint = service.enqueue(access, command="lint", message="", scope_key=None)
    assert lint["command"] == "lint"
    from selfmemory.features.tenancy.access import AccessDenied

    with pytest.raises(AccessDenied):
        service.enqueue(access, command="ingest", message="x", scope_key="org")


def test_promotion_approval_queues_org_ingest(service, world):
    owner = service.access(Principal(world.owner), world.org_id)
    key = f"project:{world.alpha}"
    scope = owner.scope(key)
    service.ensure_scope(owner, scope)
    promos = owner.abs(scope.wiki_rel) / "promotions.md"
    promos.write_text(
        promos.read_text()
        + "\n## [2026-10-01] proposed | Laptops use disk encryption\n"
        "source: raw/projects/a/it.md\nrationale: policy\n"
    )
    [p] = service.promotions(owner)
    member = service.access(Principal(world.member), world.org_id)
    from selfmemory.features.tenancy.access import AccessDenied

    with pytest.raises(AccessDenied):  # members cannot write the org room
        service.decide_promotion(member, key, p["id"], "approve")
    out = service.decide_promotion(owner, key, p["id"], "approve")
    job = service.jobs.get(out["job_id"])
    assert job["command"] == "ingest" and job["scope"] == "org"
    assert service.promotions(owner)[0]["status"] == "approved"
    with pytest.raises(ValueError):
        service.decide_promotion(owner, key, p["id"], "reject")


def test_each_owner_gets_its_own_agent_home(service, world):
    from selfmemory.features.runs.worker import _run_home

    a = {"owner": "u1", "userId": "u1", "orgId": world.org_id}
    b = {"owner": "u1#project:p", "userId": "u1", "orgId": world.org_id}
    c = {"owner": "u2", "userId": "u2", "orgId": world.org_id}
    homes = {_run_home(service.settings, j, "d1") for j in (a, b, c)}
    assert len(homes) == 3
    assert _run_home(service.settings, a, "d1") != _run_home(service.settings, a, "d2")
    assert all(service.settings.agent_home not in h.parents for h in homes)


def test_ingest_removes_symlinks_the_agent_created(service, world, tmp_path):
    access = service.access(Principal(world.member), world.org_id)
    key = f"project:{world.alpha}"
    service.ensure_scope(access, access.scope(key))
    alpha = access.abs(access.scope(key).wiki_rel)
    (alpha / "escape").symlink_to(tmp_path)
    job = service.enqueue(access, command="ingest", message="x", scope_key=key)
    done = _run(service, job)
    assert done["status"] == "done"
    assert not (alpha / "escape").exists() and not (alpha / "escape").is_symlink()


def test_session_resets_when_the_readable_scopes_change(service, world):
    access = service.access(Principal(world.member), world.org_id)
    chat = service.chats.create(world.member, world.org_id, None, world.member)
    first = service.enqueue(
        access, command="query", message="q1", scope_key=None, chat=chat
    )
    _run(service, first)
    saved = service.chats.owned(world.member, chat["_id"])
    assert saved["sessionId"] == "ses_fake" and saved["sessionScope"]

    same = service.enqueue(
        access, command="query", message="q2", scope_key=None, chat=saved
    )
    _run(service, same)
    notices = [
        e["event"]
        for e in service.jobs.read_events(same["_id"], 0)
        if e["event"]["kind"] == "notice"
    ]
    assert notices == []

    narrower = service.enqueue(
        access,
        command="query",
        message="q3",
        scope_key=f"project:{world.alpha}",
        chat=saved,
    )
    _run(service, narrower)
    notices = [
        e["event"]["message"]
        for e in service.jobs.read_events(narrower["_id"], 0)
        if e["event"]["kind"] == "notice"
    ]
    assert any("new agent session" in m for m in notices)
    after = service.chats.owned(world.member, chat["_id"])
    assert after["sessionScope"] != saved["sessionScope"]
