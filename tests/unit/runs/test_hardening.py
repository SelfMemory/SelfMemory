"""Quotas, the audit log, session-home cleanup and the standalone worker."""

from __future__ import annotations

import os
import threading
import time
from dataclasses import replace
from datetime import timedelta

import pytest

from selfmemory.features.runs import homes
from selfmemory.features.runs import worker as worker_mod
from selfmemory.features.runs.store import QuotaExceededError, now
from selfmemory.features.tenancy.access import Principal
from selfmemory.features.wiki.service import WikiService
from selfmemory.platform.audit import AUDIT, AuditLog, ensure_audit_indexes
from selfmemory.platform.sandbox.isolation import IsolationStatus
from selfmemory.wiki_settings import load_settings
from tests.unit.runs.test_runs import FAKE_AGENT


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


# ------------------------------------------------------------------ settings


def test_settings_read_quota_retention_and_audit_knobs():
    s = load_settings(
        {
            "SELFMEMORY_MAX_RUNS_PER_OWNER_PER_DAY": "50",
            "SELFMEMORY_MAX_RUNS_PER_ORG_PER_DAY": "500",
            "SELFMEMORY_SESSION_HOME_RETENTION_S": "86400",
            "SELFMEMORY_AUDIT_RETENTION_DAYS": "1",
            "SELFMEMORY_WORKER": "off",
        }
    )
    assert s.max_runs_per_owner_per_day == 50
    assert s.max_runs_per_org_per_day == 500
    assert s.session_home_retention_s == 86400
    assert s.audit_retention_days == 1
    assert s.worker_enabled is False
    d = load_settings({})
    assert d.max_runs_per_owner_per_day == 0 and d.max_runs_per_org_per_day == 0
    assert d.session_home_retention_s == 30 * 86400
    assert d.audit_retention_days == 0


# --------------------------------------------------------------------- quota


def test_owner_daily_quota_refuses_extra_runs(service, world):
    service.settings = replace(service.settings, max_runs_per_owner_per_day=2)
    access = service.access(Principal(world.member), world.org_id)
    for _ in range(2):
        service.enqueue(access, command="query", message="q", scope_key=None)
    chat = service.chats.create(world.member, world.org_id, None, world.member)
    with pytest.raises(QuotaExceededError):
        service.enqueue(access, command="query", message="q", scope_key=None, chat=chat)
    # a refused turn leaves no message behind
    assert service.chats.messages_for(chat["_id"]) == []
    # another owner in the same org is unaffected
    other = service.access(Principal(world.owner), world.org_id)
    service.enqueue(other, command="query", message="q", scope_key=None)


def test_org_daily_quota_counts_every_owner(service, world):
    service.settings = replace(service.settings, max_runs_per_org_per_day=2)
    service.enqueue(
        service.access(Principal(world.member), world.org_id),
        command="query",
        message="q",
        scope_key=None,
    )
    owner = service.access(Principal(world.owner), world.org_id)
    service.enqueue(owner, command="query", message="q", scope_key=None)
    with pytest.raises(QuotaExceededError):
        service.enqueue(owner, command="query", message="q", scope_key=None)


def test_quota_resets_with_the_day(service, world, db):
    from selfmemory.features.runs.store import QUOTAS

    service.settings = replace(service.settings, max_runs_per_owner_per_day=1)
    access = service.access(Principal(world.member), world.org_id)
    service.enqueue(access, command="query", message="q", scope_key=None)
    with pytest.raises(QuotaExceededError):
        service.enqueue(access, command="query", message="q", scope_key=None)
    assert db[QUOTAS].find_one()["expiresAt"] is not None
    db[QUOTAS].delete_many({})  # what the TTL index does at midnight UTC
    service.enqueue(access, command="query", message="q", scope_key=None)


def test_org_refusal_gives_back_the_user_slot(service, world):
    service.settings = replace(
        service.settings, max_runs_per_owner_per_day=5, max_runs_per_org_per_day=1
    )
    member = service.access(Principal(world.member), world.org_id)
    service.enqueue(member, command="query", message="q", scope_key=None)
    with pytest.raises(QuotaExceededError):
        service.enqueue(member, command="query", message="q", scope_key=None)
    doc = service.quotas.col.find_one({"_id": {"$regex": "^user:"}})
    assert doc["n"] == 1


def test_quota_counter_never_overshoots_under_concurrency(db):
    from selfmemory.features.runs.store import QuotaCounter

    counter = QuotaCounter(db)
    results: list[bool] = []
    lock = threading.Lock()

    def take():
        ok = counter.take("user", "u1", 5)
        with lock:
            results.append(ok)

    threads = [threading.Thread(target=take) for _ in range(30)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert results.count(True) == 5


def test_create_run_route_maps_quota_to_429(service, world, monkeypatch):
    from fastapi import HTTPException

    from selfmemory.features.wiki.interfaces import http

    access = service.access(Principal(world.member), world.org_id)
    service.settings = replace(service.settings, max_runs_per_owner_per_day=1)
    ctx = http.Ctx(service, Principal(world.member), access)
    monkeypatch.setattr(http, "isolation_report", lambda _s: {"blocked": False})
    http.create_run(http.RunRequest(command="query", message="q"), ctx)
    with pytest.raises(HTTPException) as e:
        http.create_run(http.RunRequest(command="query", message="q"), ctx)
    assert e.value.status_code == 429


# --------------------------------------------------------------------- audit


def test_audit_log_is_append_only_and_has_no_mutators(db):
    log = AuditLog(db)
    log.record("file.read", org_id="o1", user_id="u1", scopes=["org"], target="x")
    assert not any(hasattr(log, m) for m in ("update", "delete", "remove", "clear"))
    rows = log.recent("o1")
    assert len(rows) == 1
    assert rows[0]["owner"] == "u1" and rows[0]["scopes"] == ["org"]
    assert "content" not in rows[0]["detail"]


def test_audit_write_failure_does_not_raise(db, monkeypatch):
    from pymongo.errors import PyMongoError

    log = AuditLog(db)

    def boom(_doc):
        raise PyMongoError("down")

    monkeypatch.setattr(log.col, "insert_one", boom)
    log.record("file.read", org_id="o1", user_id="u1")


def test_audit_retention_index_follows_setting(db):
    ensure_audit_indexes(db, 0)
    assert "audit_ttl" not in {i["name"] for i in db[AUDIT].list_indexes()}
    ensure_audit_indexes(db, 30)
    ttl = {i["name"]: i for i in db[AUDIT].list_indexes()}["audit_ttl"]
    assert ttl["expireAfterSeconds"] == 30 * 86400
    ensure_audit_indexes(db, 0)
    assert "audit_ttl" not in {i["name"] for i in db[AUDIT].list_indexes()}


def test_runs_are_audited_with_mounted_scopes(service, world):
    access = service.access(Principal(world.member), world.org_id)
    key = f"project:{world.alpha}"
    job = service.enqueue(access, command="ingest", message="raw/x.md", scope_key=key)
    done = _run(service, job)
    assert done["status"] == "done"
    rows = {r["action"]: r for r in service.audit.col.find({"jobId": job["_id"]})}
    assert set(rows) == {"run.queued", "run.started", "run.finished"}
    assert rows["run.queued"]["scopes"] == [key]
    assert rows["run.queued"]["userId"] == world.member
    started = rows["run.started"]
    assert started["scopes"]  # the scopes that were bound into the sandbox
    assert started["detail"]["writable"] == key
    assert started["detail"]["isolation"] == "unconfined"
    finished = rows["run.finished"]
    assert finished["detail"]["status"] == "done"
    assert finished["detail"]["commit"] == done["result"]["commit"]["sha"]


def test_file_routes_are_audited(service, world):
    from selfmemory.features.wiki.interfaces import http

    access = service.access(Principal(world.member), world.org_id)
    service.ensure_all(access)
    ctx = http.Ctx(service, Principal(world.member), access)
    scope = access.scope(f"project:{world.alpha}")
    path = f"{scope.wiki_rel}/notes/a.md"
    http.write_file(http.FileWrite(path=path, content="hello"), ctx)
    http.read_file(path, ctx)
    http.delete_file(path, ctx)
    rows = list(service.audit.col.find({"action": {"$regex": "^file\\."}}))
    assert [r["action"] for r in rows] == ["file.write", "file.read", "file.delete"]
    assert all(r["scopes"] == [scope.key] and r["target"] == path for r in rows)
    assert all("hello" not in str(r) for r in rows)


# ------------------------------------------------------------- session homes


def test_homes_are_keyed_by_chat(service, world):
    a = {"owner": "u1", "userId": "u1", "orgId": world.org_id, "chatId": "c1"}
    b = {**a, "chatId": "c2"}
    c = {**a, "chatId": None}
    hs = {homes.run_home(service.settings, j, "d1") for j in (a, b, c)}
    assert len(hs) == 3
    assert homes.ONESHOT in str(homes.run_home(service.settings, c, "d1"))


def test_deleting_a_chat_deletes_its_session_home(service, world):
    access = service.access(Principal(world.member), world.org_id)
    chat = service.chats.create(world.member, world.org_id, None, world.member)
    keep = service.chats.create(world.member, world.org_id, None, world.member)
    for c in (chat, keep):
        _run(
            service,
            service.enqueue(
                access, command="query", message="q", scope_key=None, chat=c
            ),
        )
    s = service.settings
    gone = homes.chat_home(s, world.org_id, world.member, chat["_id"])
    kept = homes.chat_home(s, world.org_id, world.member, keep["_id"])
    assert gone.is_dir() and kept.is_dir()
    assert service.delete_chat(Principal(world.member), chat["_id"])
    assert not gone.exists() and kept.is_dir()
    assert service.chats.owned(world.member, chat["_id"]) is None
    assert service.audit.col.count_documents({"action": "chat.delete"}) == 1
    # someone else's chat id is not theirs to delete
    assert not service.delete_chat(Principal(world.owner), keep["_id"])
    assert kept.is_dir()


def test_idle_a2a_contexts_take_their_homes_with_them(service, world):
    s = service.settings
    chat = service.chats.create(world.member, world.org_id, None, kind="a2a")
    home = homes.chat_home(s, world.org_id, world.member, chat["_id"]) / "d1"
    home.mkdir(parents=True)
    n = service.chats.prune_idle(
        "a2a",
        now() + timedelta(hours=2),
        on_delete=lambda c: homes.delete_chat_home(s, c),
    )
    assert n == 1 and not home.parent.exists()


def test_prune_homes_expires_unused_homes(settings):
    old = homes.chat_home(settings, "o1", "u1", "c1") / "d-old"
    fresh = homes.chat_home(settings, "o1", "u1", "c2") / "d-new"
    for h in (old, fresh):
        (h / ".local").mkdir(parents=True)
    past = time.time() - 40 * 86400
    os.utime(old, (past, past))
    assert homes.prune_homes(settings, 30 * 86400) == 1
    assert not old.exists() and not old.parent.exists()
    assert fresh.is_dir()


def test_run_marks_its_home_as_used(service, world):
    access = service.access(Principal(world.member), world.org_id)
    chat = service.chats.create(world.member, world.org_id, None, world.member)
    _run(
        service,
        service.enqueue(
            access, command="query", message="q", scope_key=None, chat=chat
        ),
    )
    root = homes.chat_home(service.settings, world.org_id, world.member, chat["_id"])
    (home,) = list(root.iterdir())
    assert time.time() - home.stat().st_mtime < 60
    assert homes.prune_homes(service.settings, 30 * 86400) == 0


# --------------------------------------------------------- standalone worker


def test_standalone_worker_drains_queue_while_api_worker_is_off(service, world):
    """With SELFMEMORY_WORKER=off the API only queues; a separate Worker (what
    ``make worker`` starts) claims and finishes the jobs."""
    assert load_settings({"SELFMEMORY_WORKER": "off"}).worker_enabled is False
    access = service.access(Principal(world.member), world.org_id)
    jobs = [
        service.enqueue(access, command="query", message="q", scope_key=None)
        for _ in range(2)
    ]
    w = worker_mod.Worker(service, worker_id="pool-1", idle_s=0.05)
    w.start()
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if all(service.jobs.get(j["_id"])["status"] == "done" for j in jobs):
                break
            time.sleep(0.1)
    finally:
        w.stop()
    for j in jobs:
        got = service.jobs.get(j["_id"])
        assert got["status"] == "done" and got["workerId"] == "pool-1"


def test_worker_entry_point_is_importable():
    from selfmemory.apps import worker as app_worker

    assert app_worker.main is worker_mod.main


# ------------------------------------------------------------- fair share


def test_flooding_owner_cannot_starve_another_owner(db):
    from selfmemory.features.runs.store import CLAIM_SCAN, JobStore

    store = JobStore(db)

    def job(owner, org="o1", chat=None):
        return store.create(
            principal={"userId": owner, "pinnedProjectId": None, "owner": owner},
            org_id=org,
            command="query",
            scope=None,
            message="q",
            display_text="q",
            chat_id=chat,
        )

    for _ in range(CLAIM_SCAN * 2):
        job("flooder")
    store.jobs.update_many({}, {"$set": {"createdAt": now() - timedelta(hours=1)}})
    victim = job("victim")
    assert store.claim("w1", max_per_owner=1)["owner"] == "flooder"
    # the flooder is at its cap; the victim's job is claimed despite the backlog
    assert store.claim("w1", max_per_owner=1)["_id"] == victim["_id"]
    assert store.claim("w1", max_per_owner=1) is None


def test_busy_chat_backlog_does_not_block_other_jobs(db):
    from selfmemory.features.runs.store import CLAIM_SCAN, JobStore

    store = JobStore(db)
    p = {"userId": "u1", "pinnedProjectId": None, "owner": "u1"}
    args = {"org_id": "o1", "command": "query", "scope": None, "message": "q"}
    for _ in range(CLAIM_SCAN + 5):
        store.create(principal=p, display_text="q", chat_id="c1", **args)
    other = store.create(principal=p, display_text="q", chat_id="c2", **args)
    assert store.claim("w1")["chatId"] == "c1"
    assert store.claim("w1")["_id"] == other["_id"]


def test_queued_jobs_per_owner_are_capped(service, world):
    service.settings = replace(service.settings, max_queued_per_owner=2)
    access = service.access(Principal(world.member), world.org_id)
    for _ in range(2):
        service.enqueue(access, command="query", message="q", scope_key=None)
    with pytest.raises(QuotaExceededError):
        service.enqueue(access, command="query", message="q", scope_key=None)
    service.jobs.claim("w1")  # one leaves the queue, so there is room again
    service.enqueue(access, command="query", message="q", scope_key=None)
