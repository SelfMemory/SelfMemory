"""The /api/wiki HTTP surface, with auth overridden and Mongo mocked."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from selfmemory.features.tenancy.access import Principal
from selfmemory.features.wiki.interfaces import http as wiki_routes
from selfmemory.features.wiki.service import WikiService
from selfmemory.platform.dependencies import AuthContext, authenticate_api_key


class Caller:
    def __init__(self):
        self.ctx = None

    def __call__(self):
        return self.ctx


@pytest.fixture
def setup(db, world, settings, monkeypatch):
    monkeypatch.setattr(
        wiki_routes,
        "isolation_report",
        lambda _s: {"blocked": False, "detail": "test", "ok": True},
    )
    app = FastAPI()
    app.include_router(wiki_routes.router, prefix="/api/v1")
    app.state.wiki = WikiService(db, settings)
    caller = Caller()
    app.dependency_overrides[authenticate_api_key] = caller
    client = TestClient(app)

    def as_user(user_id, project_id=None):
        caller.ctx = AuthContext(
            user_id=user_id,
            project_id=project_id,
            auth_type="api_key" if project_id else "session",
        )
        return client

    return world, as_user, app.state.wiki


def test_scopes_and_tree(setup):
    world, as_user, _ = setup
    c = as_user(world.member)
    scopes = c.get("/api/v1/wiki/scopes").json()
    assert scopes["org_id"] == world.org_id
    tree = c.get("/api/v1/wiki/tree").json()
    by_key = {s["key"]: s for s in tree["scopes"]}
    alpha = by_key[f"project:{world.alpha}"]
    # lazily scaffolded, and the parent's listing excludes the sub-project
    assert f"wiki/projects/{world.alpha}/index.md" in alpha["files"]
    assert not any(str(world.child) in f for f in alpha["files"])


def test_outsider_gets_403(setup):
    world, as_user, _ = setup
    r = as_user(world.outsider).get(
        "/api/v1/wiki/scopes", params={"org_id": world.org_id}
    )
    assert r.status_code == 403


def test_file_write_read_delete_and_permissions(setup):
    world, as_user, _ = setup
    c = as_user(world.member)
    path = f"wiki/projects/{world.alpha}/people/ada.md"
    r = c.put(
        "/api/v1/wiki/file",
        json={"path": path, "content": "---\ntype: Person\n---\nAda"},
    )
    assert r.status_code == 200 and r.json()["sha"]
    assert "Ada" in c.get("/api/v1/wiki/file", params={"path": path}).json()["content"]
    # read-only scopes and other projects are refused
    assert (
        c.put(
            "/api/v1/wiki/file", json={"path": "wiki/org/x.md", "content": "x"}
        ).status_code
        == 403
    )
    beta = f"wiki/projects/{world.beta}/x.md"
    assert c.get("/api/v1/wiki/file", params={"path": beta}).status_code == 403
    assert (
        c.get("/api/v1/wiki/file", params={"path": "wiki/../../etc/passwd"}).status_code
        == 403
    )
    # reserved files survive
    idx = f"wiki/projects/{world.alpha}/index.md"
    assert c.delete("/api/v1/wiki/file", params={"path": idx}).status_code == 403
    assert c.delete("/api/v1/wiki/file", params={"path": path}).status_code == 200
    assert c.get("/api/v1/wiki/file", params={"path": path}).status_code == 404


def test_upload_stores_raw_and_queues_ingest(setup):
    world, as_user, service = setup
    c = as_user(world.member)
    key = f"project:{world.alpha}"
    r = c.post(
        "/api/v1/wiki/upload",
        data={"scope": key, "paths": ["deck/notes.txt"], "note": "focus on dates"},
        files=[("files", ("notes.txt", b"Q3 launch is on 2026-11-02", "text/plain"))],
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["written"] == [f"raw/projects/{world.alpha}/deck/notes.txt"]
    job = service.jobs.get(body["job_id"])
    assert job["command"] == "ingest" and job["scope"] == key
    assert "focus on dates" in job["message"]
    src = c.get("/api/v1/wiki/sources", params={"scope": key}).json()
    assert src["files"] == body["written"]
    # a second upload of the same name never overwrites the first
    again = c.post(
        "/api/v1/wiki/upload",
        data={"scope": key, "ingest": "false"},
        files=[("files", ("notes.txt", b"other", "text/plain"))],
    ).json()
    assert again["written"] == [f"raw/projects/{world.alpha}/notes.txt"]
    assert again["job_id"] is None


def test_upload_into_read_only_scope_refused(setup):
    world, as_user, _ = setup
    r = as_user(world.member).post(
        "/api/v1/wiki/upload",
        data={"scope": f"project:{world.child}"},
        files=[("files", ("a.txt", b"x", "text/plain"))],
    )
    assert r.status_code == 403


def test_runs_chats_and_events(setup):
    world, as_user, service = setup
    c = as_user(world.member)
    chat = c.post("/api/v1/wiki/chats", json={}).json()
    r = c.post(
        "/api/v1/wiki/runs",
        json={"command": "query", "message": "who is ada?", "chat_id": chat["id"]},
    )
    assert r.status_code == 202
    job_id = r.json()["job_id"]
    assert (
        c.get("/api/v1/wiki/runs", params={"chat_id": chat["id"]}).json()["job"]["id"]
        == job_id
    )
    listed = c.get("/api/v1/wiki/chats").json()["chats"]
    assert listed[0]["title"] == "who is ada?"

    # finish the job as a worker would, then stream it
    service.jobs.claim("w1")
    service.jobs.append(job_id, "w1", [{"kind": "text", "text": "Ada wrote code."}])
    service.jobs.finish(job_id, "w1", "done", {"code": 0, "answer": "Ada wrote code."})
    events = c.get(f"/api/v1/wiki/runs/{job_id}/events").text
    assert "Ada wrote code." in events and '"kind": "done"' in events
    resumed = c.get(
        f"/api/v1/wiki/runs/{job_id}/events", headers={"Last-Event-ID": "1"}
    ).text
    assert "Ada wrote code." not in resumed
    assert (
        c.get(f"/api/v1/wiki/runs/{job_id}").json()["result"]["answer"]
        == "Ada wrote code."
    )

    # another user cannot see or cancel it
    other = as_user(world.owner)
    assert other.get(f"/api/v1/wiki/runs/{job_id}").status_code == 404
    assert other.delete(f"/api/v1/wiki/runs/{job_id}").status_code == 404


def test_run_validation(setup):
    world, as_user, _ = setup
    c = as_user(world.member)
    assert (
        c.post(
            "/api/v1/wiki/runs", json={"command": "query", "message": ""}
        ).status_code
        == 400
    )
    assert (
        c.post(
            "/api/v1/wiki/runs",
            json={"command": "ingest", "message": "x", "scope": "org"},
        ).status_code
        == 403
    )
    assert c.post("/api/v1/wiki/runs", json={"command": "lint"}).status_code == 202
    assert (
        c.post(
            "/api/v1/wiki/runs",
            json={"command": "query", "message": "x", "chat_id": "nope"},
        ).status_code
        == 404
    )


def test_graph_search_and_pinned_key(setup):
    world, as_user, _ = setup
    c = as_user(world.member)
    base = f"wiki/projects/{world.alpha}"
    c.put(
        "/api/v1/wiki/file",
        json={"path": f"{base}/a.md", "content": "Alpha links [b](/b.md) quarterly"},
    )
    c.put(
        "/api/v1/wiki/file",
        json={
            "path": f"{base}/b.md",
            "content": "---\ntitle: Bee\n---\nquarterly plan",
        },
    )
    g = c.get("/api/v1/wiki/graph", params={"scope": f"project:{world.alpha}"}).json()
    assert {"from": f"{base}/a.md", "to": f"{base}/b.md"} in g["edges"]
    hits = c.get("/api/v1/wiki/search", params={"q": "quarterly"}).json()["results"]
    assert {h["path"] for h in hits} == {f"{base}/a.md", f"{base}/b.md"}
    frames = c.get("/api/v1/wiki/timeline").json()["frames"]
    assert frames and frames[-1]["nodes"]

    # an API key pinned to beta cannot read alpha, and needs no org_id
    k = as_user(world.owner, project_id=str(world.beta))
    assert (
        k.get("/api/v1/wiki/search", params={"q": "quarterly"}).json()["results"] == []
    )
    assert (
        k.get("/api/v1/wiki/file", params={"path": f"{base}/a.md"}).status_code == 403
    )


def test_git_metadata_is_unreachable_and_svg_is_inert(setup):
    world, as_user, _ = setup
    c = as_user(world.member)
    c.get("/api/v1/wiki/tree")  # scaffolds alpha, creating its .git
    cfg = f"wiki/projects/{world.alpha}/.git/config"
    assert c.get("/api/v1/wiki/file", params={"path": cfg}).status_code == 403
    r = c.put(
        "/api/v1/wiki/file",
        json={"path": cfg, "content": "[core]\nfsmonitor=touch /tmp/x"},
    )
    assert r.status_code == 403
    svg = f"wiki/projects/{world.alpha}/images/x.svg"
    c.put(
        "/api/v1/wiki/file",
        json={"path": svg, "content": "<svg><script>alert(1)</script></svg>"},
    )
    r = c.get("/api/v1/wiki/file", params={"path": svg})
    assert r.headers["content-disposition"] == "attachment"
    assert "sandbox" in r.headers["content-security-policy"]
    assert r.headers["x-content-type-options"] == "nosniff"


def test_client_cannot_supply_a_session_id(setup):
    world, as_user, service = setup
    c = as_user(world.member)
    r = c.post(
        "/api/v1/wiki/runs",
        json={"command": "query", "message": "x", "session_id": "ses_someone_else"},
    )
    assert r.status_code == 202
    assert service.jobs.get(r.json()["job_id"])["sessionId"] is None


def test_symlink_into_another_scope_is_refused(setup):
    world, as_user, service = setup
    c = as_user(world.member)
    c.get("/api/v1/wiki/tree")
    owner = as_user(world.owner)
    owner.put(
        "/api/v1/wiki/file",
        json={"path": f"wiki/projects/{world.beta}/secret.md", "content": "beta only"},
    )
    access = service.access(Principal(world.member), world.org_id)
    alpha = access.root / "wiki" / "projects" / str(world.alpha)
    (alpha / "link").symlink_to(access.root / "wiki" / "projects" / str(world.beta))
    c = as_user(world.member)
    leak = f"wiki/projects/{world.alpha}/link/secret.md"
    assert c.get("/api/v1/wiki/file", params={"path": leak}).status_code == 403
    assert (
        c.put("/api/v1/wiki/file", json={"path": leak, "content": "x"}).status_code
        == 403
    )


def test_pinned_key_cannot_read_session_runs_or_chats(setup):
    world, as_user, _ = setup
    session = as_user(world.member)
    chat = session.post("/api/v1/wiki/chats", json={}).json()
    job = session.post(
        "/api/v1/wiki/runs", json={"command": "query", "message": "personal question"}
    ).json()["job_id"]
    key = as_user(world.member, project_id=str(world.alpha))
    assert key.get(f"/api/v1/wiki/runs/{job}").status_code in (403, 404)
    assert key.get(
        "/api/v1/wiki/chats", params={"chat_id": chat["id"]}
    ).status_code in (
        403,
        404,
    )


def test_token_without_project_is_refused(setup):
    world, as_user, _ = setup
    c = as_user(world.member)
    c.app.dependency_overrides[authenticate_api_key] = lambda: AuthContext(
        user_id=world.member, auth_type="oauth"
    )
    assert c.get("/api/v1/wiki/scopes").status_code == 403


def test_chat_from_another_org_is_not_readable(setup, db):
    world, as_user, service = setup
    c = as_user(world.member)
    foreign = service.chats.create(world.member, "000000000000000000000000", None)
    r = c.get("/api/v1/wiki/chats", params={"chat_id": foreign["_id"]})
    assert r.status_code == 404
