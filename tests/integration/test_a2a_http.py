"""The A2A JSON-RPC endpoint: contexts map to chats, tasks to query runs."""

from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from selfmemory.features.a2a.interfaces import http as a2a_routes
from selfmemory.features.wiki.service import WikiService
from selfmemory.platform.dependencies import AuthContext, authenticate_api_key


@pytest.fixture
def setup(db, world, settings, monkeypatch):
    monkeypatch.setattr(
        a2a_routes,
        "isolation_report",
        lambda _s: {"blocked": False, "detail": "test", "ok": True},
    )
    app = FastAPI()
    app.include_router(a2a_routes.router, prefix="/api/v1")
    app.include_router(a2a_routes.card_router)
    app.state.wiki = WikiService(db, settings)
    state = {"ctx": None}
    app.dependency_overrides[authenticate_api_key] = lambda: state["ctx"]
    client = TestClient(app)

    def as_user(user_id):
        state["ctx"] = AuthContext(user_id=user_id, auth_type="session")
        return client

    return world, as_user, app.state.wiki


def _send(text, context_id=None, method="message/send", **params):
    message = {
        "role": "user",
        "messageId": "m1",
        "parts": [{"kind": "text", "text": text}],
    }
    if context_id:
        message["contextId"] = context_id
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": {"message": message, **params},
    }


def test_agent_card(setup):
    _, as_user, _ = setup
    card = as_user("x").get("/.well-known/agent-card.json").json()
    assert card["url"].endswith("/api/v1/a2a")
    assert card["capabilities"]["streaming"] is True
    assert card["skills"][0]["id"] == "ask-wiki"


def test_send_without_context_starts_a_fresh_one(setup):
    world, as_user, service = setup
    c = as_user(world.member)
    first = c.post("/api/v1/a2a", json=_send("who is ada?")).json()["result"]
    second = c.post("/api/v1/a2a", json=_send("who is bob?")).json()["result"]
    assert first["status"]["state"] == "submitted"
    assert first["contextId"] and first["contextId"] != second["contextId"]
    chat = service.chats.owned(world.member, first["contextId"])
    assert chat["kind"] == "a2a"
    job = service.jobs.get(first["id"])
    assert job["command"] == "query" and job["chatId"] == first["contextId"]


def test_follow_up_reuses_context_and_queues_behind(setup):
    world, as_user, service = setup
    c = as_user(world.member)
    first = c.post("/api/v1/a2a", json=_send("q1")).json()["result"]
    follow = c.post("/api/v1/a2a", json=_send("q2", first["contextId"])).json()
    assert follow["result"]["contextId"] == first["contextId"]
    assert service.jobs.claim("w")["_id"] == first["id"]
    assert service.jobs.claim("w") is None  # same context waits its turn


def test_unknown_or_foreign_context_is_refused(setup):
    world, as_user, service = setup
    first = as_user(world.member).post("/api/v1/a2a", json=_send("q")).json()
    r = as_user(world.owner).post(
        "/api/v1/a2a", json=_send("q", first["result"]["contextId"])
    )
    assert r.json()["error"]["code"] == a2a_routes.INVALID_PARAMS
    # an app chat is not an agent context
    app_chat = service.chats.create(world.member, world.org_id, None, world.member)
    r = as_user(world.member).post("/api/v1/a2a", json=_send("q", app_chat["_id"]))
    assert "error" in r.json()


def test_get_cancel_and_ownership(setup):
    world, as_user, service = setup
    c = as_user(world.member)
    task = c.post("/api/v1/a2a", json=_send("q")).json()["result"]
    get = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tasks/get",
        "params": {"id": task["id"]},
    }
    assert c.post("/api/v1/a2a", json=get).json()["result"]["id"] == task["id"]
    other = as_user(world.owner).post("/api/v1/a2a", json=get).json()
    assert other["error"]["code"] == a2a_routes.TASK_NOT_FOUND
    cancel = {**get, "method": "tasks/cancel"}
    done = as_user(world.member).post("/api/v1/a2a", json=cancel).json()["result"]
    assert done["status"]["state"] == "canceled"
    again = as_user(world.member).post("/api/v1/a2a", json=cancel).json()
    assert again["error"]["code"] == a2a_routes.TASK_NOT_CANCELABLE


def test_completed_task_carries_the_answer(setup):
    world, as_user, service = setup
    c = as_user(world.member)
    task = c.post("/api/v1/a2a", json=_send("q")).json()["result"]
    service.jobs.claim("w")
    service.jobs.finish(task["id"], "w", "done", {"answer": "Ada wrote it."})
    stream = c.post(
        "/api/v1/a2a",
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tasks/resubscribe",
            "params": {"id": task["id"]},
        },
    )
    frames = [
        json.loads(line[6:])["result"]
        for line in stream.text.splitlines()
        if line.startswith("data: ")
    ]
    assert frames[0]["kind"] == "task" and frames[0]["status"]["state"] == "completed"
    assert frames[1]["artifact"]["parts"][0]["text"] == "Ada wrote it."
    assert frames[-1]["final"] is True


def test_bad_requests(setup):
    world, as_user, _ = setup
    c = as_user(world.member)
    assert c.post("/api/v1/a2a", json={"x": 1}).json()["error"]["code"] == -32600
    r = c.post("/api/v1/a2a", json={**_send("q"), "method": "nope"}).json()
    assert r["error"]["code"] == a2a_routes.METHOD_NOT_FOUND
    empty = _send("")
    assert c.post("/api/v1/a2a", json=empty).json()["error"]["code"] == -32004
