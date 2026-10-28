"""MCP wiki tools: WikiClient wire calls and the tools' OAuth scope checks."""

from __future__ import annotations

import json
import os

for _k, _v in {
    "MCP_SERVER_URL": "http://127.0.0.1:1/mcp",
    "SELFMEMORY_API_HOST": "http://core.test",
}.items():
    os.environ.setdefault(_k, _v)
# Importing the MCP app loads .env; never export telemetry from tests.
os.environ["OTEL_ENABLED"] = "false"

import httpx  # noqa: E402
import pytest  # noqa: E402

from selfmemory.apps import mcp as mcp_app  # noqa: E402
from selfmemory.features.wiki.interfaces.mcp import wiki_client  # noqa: E402
from selfmemory.features.wiki.interfaces.mcp.wiki_client import (  # noqa: E402
    WikiClient,
    WikiError,
    scope_for_path,
)

SCOPES = {
    "org_id": "o1",
    "scopes": [
        {"key": "org", "wiki": "wiki/org", "raw": "raw/org", "writable": False},
        {
            "key": "project:p",
            "wiki": "wiki/projects/p",
            "raw": "raw/projects/p",
            "writable": True,
        },
        {
            "key": "project:c",
            "wiki": "wiki/projects/p/c",
            "raw": "raw/projects/p/c",
            "writable": True,
        },
    ],
}

# ------------------------------------------------------------- WikiClient


@pytest.fixture
def wire(monkeypatch):
    """Route WikiClient's httpx calls to a recorder; ``routes`` maps
    ``(method, path)`` to a JSON body or ``(status, body)``."""
    calls: list[httpx.Request] = []
    routes: dict[tuple[str, str], object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        out = routes.get((request.method, request.url.path), {})
        status, body = out if isinstance(out, tuple) else (200, out)
        return httpx.Response(status, json=body)

    real = httpx.AsyncClient

    def factory(**kw):
        return real(transport=httpx.MockTransport(handler), **kw)

    monkeypatch.setattr(wiki_client.httpx, "AsyncClient", factory)
    return calls, routes


def _client() -> WikiClient:
    return WikiClient("http://core.test/", "tok")


@pytest.mark.asyncio
async def test_write_file_puts_path_and_content_with_caller_token(wire):
    calls, routes = wire
    routes[("PUT", "/api/v1/wiki/file")] = {"ok": True, "side": "wiki", "sha": "a"}
    out = await _client().write_file("wiki/projects/p/x.md", "# X\n")
    assert out["sha"] == "a"
    (req,) = calls
    assert req.headers["authorization"] == "Bearer tok"
    assert json.loads(req.content) == {
        "path": "wiki/projects/p/x.md",
        "content": "# X\n",
    }


@pytest.mark.asyncio
async def test_delete_file_sends_path_as_query(wire):
    calls, _ = wire
    await _client().delete_file("raw/projects/p/a.md")
    (req,) = calls
    assert req.method == "DELETE"
    assert req.url.params["path"] == "raw/projects/p/a.md"


@pytest.mark.asyncio
async def test_start_run_cancel_and_status(wire):
    calls, routes = wire
    routes[("POST", "/api/v1/wiki/runs")] = {"job_id": "j1", "status": "queued"}
    routes[("GET", "/api/v1/wiki/runs/j1")] = {"id": "j1", "status": "running"}
    routes[("DELETE", "/api/v1/wiki/runs/j1")] = {"id": "j1", "status": "cancelled"}
    c = _client()
    assert (await c.start_run("ingest", "facts", "project:p"))["job_id"] == "j1"
    assert json.loads(calls[0].content) == {
        "command": "ingest",
        "message": "facts",
        "scope": "project:p",
    }
    assert (await c.run("j1"))["status"] == "running"
    assert (await c.cancel_run("j1"))["status"] == "cancelled"


@pytest.mark.asyncio
async def test_read_file_adds_owning_scope(wire):
    _, routes = wire
    routes[("GET", "/api/v1/wiki/file")] = {
        "path": "wiki/projects/p/c/x.md",
        "side": "wiki",
        "content": "hi",
    }
    routes[("GET", "/api/v1/wiki/scopes")] = SCOPES
    out = await _client().read_file("wiki/projects/p/c/x.md")
    assert out == {
        "path": "wiki/projects/p/c/x.md",
        "side": "wiki",
        "content": "hi",
        "scope": "project:c",
    }


@pytest.mark.asyncio
async def test_core_errors_surface_as_wiki_error(wire):
    _, routes = wire
    routes[("PUT", "/api/v1/wiki/file")] = (403, {"detail": "read-only scope"})
    with pytest.raises(WikiError, match="403: read-only scope"):
        await _client().write_file("wiki/org/x.md", "x")


@pytest.mark.asyncio
async def test_wait_run_reports_running_at_deadline(wire):
    _, routes = wire
    routes[("GET", "/api/v1/wiki/runs/j1")] = {"id": "j1", "status": "running"}
    out = await _client().wait_run("j1", wait_s=0)
    assert out == {"id": "j1", "status": "running", "result": None}


def test_scope_for_path_prefers_the_nested_scope():
    s = SCOPES["scopes"]
    assert scope_for_path("wiki/projects/p/x.md", s) == "project:p"
    assert scope_for_path("raw/projects/p/c/y.pdf", s) == "project:c"
    assert scope_for_path("wiki/projects/pp/x.md", s) is None
    assert scope_for_path("wiki/org/index.md", s) == "org"


# ------------------------------------------------------------------ tools


class FakeWiki:
    """Stands in for WikiClient; records calls and the token it was built with."""

    instances: list[FakeWiki] = []

    def __init__(self, host: str, token: str):
        self.token = token
        self.calls: list[tuple] = []
        FakeWiki.instances.append(self)

    def _rec(self, name, *args, result=None):
        self.calls.append((name, *args))
        return result

    async def scopes(self):
        return self._rec("scopes", result=SCOPES)

    async def tree(self):
        return self._rec(
            "tree",
            result={
                "scopes": [
                    {"key": "org", "label": "Org", "writable": False, "files": ["a"]},
                    {"key": "project:p", "label": "P", "writable": True, "files": []},
                ]
            },
        )

    async def read_file(self, path):
        return self._rec(
            "read_file", path, result={"path": path, "side": "wiki", "scope": "org"}
        )

    async def write_file(self, path, content):
        return self._rec(
            "write_file", path, content, result={"ok": True, "side": "wiki"}
        )

    async def delete_file(self, path):
        return self._rec("delete_file", path, result={"ok": True})

    async def start_run(self, command, message="", scope=None):
        return self._rec(
            "start_run",
            command,
            message,
            scope,
            result={"job_id": "j1", "status": "queued"},
        )

    async def run(self, run_id):
        return self._rec(
            "run",
            run_id,
            result={"id": run_id, "status": "done", "command": "ingest", "result": {}},
        )

    async def cancel_run(self, run_id):
        return self._rec(
            "cancel_run", run_id, result={"id": run_id, "status": "cancelled"}
        )

    async def ask(self, question, scope=None):
        return self._rec(
            "ask",
            question,
            scope,
            result={"id": "j2", "status": "running", "result": None},
        )


class Ctx:
    """An MCP context whose request carries the middleware's auth context."""

    def __init__(self, scopes: list[str]):
        auth = {
            "auth_type": "oauth",
            "user_id": "u1",
            "project_id": "p",
            "scopes": scopes,
            "raw_token": "tok",
        }
        request = type("Req", (), {"scope": {"auth_context": auth}})()
        self.request_context = type("RC", (), {"request": request})()


@pytest.fixture
def token(monkeypatch):
    """Build a context whose token has the given OAuth scopes; WikiClient is
    replaced by a fake."""
    FakeWiki.instances = []
    monkeypatch.setattr(mcp_app, "WikiClient", FakeWiki)
    return lambda *scopes: Ctx(list(scopes))


def _ok(out: dict) -> dict:
    assert not out.get("isError"), out
    return out["structuredContent"]


def _err(out: dict) -> str:
    assert out.get("isError"), out
    return json.loads(out["content"][0]["text"])["error"]


WRITE_CALLS = {
    "write_file": lambda c: mcp_app.write_file("wiki/projects/p/x.md", "x", c),
    "delete_file": lambda c: mcp_app.delete_file("wiki/projects/p/x.md", c),
    "ingest": lambda c: mcp_app.ingest("project:p", "facts", c),
    "cancel_run": lambda c: mcp_app.cancel_run("j1", c),
}


@pytest.mark.asyncio
@pytest.mark.parametrize("tool", sorted(WRITE_CALLS))
async def test_write_tools_reject_a_read_only_token(token, tool):
    c = token("memories:read")
    msg = _err(await WRITE_CALLS[tool](c))
    assert "memories:write" in msg
    assert FakeWiki.instances == []  # never reached the core API


@pytest.mark.asyncio
@pytest.mark.parametrize("tool", sorted(WRITE_CALLS))
async def test_write_tools_forward_the_caller_token(token, tool):
    c = token("memories:read", "memories:write")
    _ok(await WRITE_CALLS[tool](c))
    (client,) = FakeWiki.instances
    assert client.token == "tok"


@pytest.mark.asyncio
async def test_read_tools_need_memories_read(token):
    c = token("memories:write")
    assert "memories:read" in _err(await mcp_app.list_scopes(c))
    assert "memories:read" in _err(await mcp_app.run_status("j1", c))


@pytest.mark.asyncio
async def test_write_file_passes_path_and_content(token):
    c = token("memories:read", "memories:write")
    _ok(await mcp_app.write_file("wiki/projects/p/x.md", "# X", c))
    assert FakeWiki.instances[0].calls == [
        ("write_file", "wiki/projects/p/x.md", "# X")
    ]


@pytest.mark.asyncio
async def test_ingest_returns_run_id_without_waiting(token):
    c = token("memories:read", "memories:write")
    out = _ok(await mcp_app.ingest("project:p", "facts", c))
    assert out == {"status": "queued", "run_id": "j1"}
    assert FakeWiki.instances[0].calls == [
        ("start_run", "ingest", "facts", "project:p")
    ]


@pytest.mark.asyncio
async def test_list_files_filters_to_one_scope(token):
    c = token("memories:read")
    out = _ok(await mcp_app.list_files(c, scope="org"))
    assert [s["key"] for s in out["scopes"]] == ["org"]
    assert out["scopes"][0]["files"] == ["a"]
    assert len(_ok(await mcp_app.list_files(c))["scopes"]) == 2
    assert "not found" in _err(await mcp_app.list_files(c, scope="project:x"))


@pytest.mark.asyncio
async def test_read_file_and_list_scopes(token):
    c = token("memories:read")
    out = _ok(await mcp_app.read_file("wiki/org/a.md", c))
    assert out["scope"] == "org"
    assert _ok(await mcp_app.list_scopes(c))["org_id"] == "o1"


@pytest.mark.asyncio
async def test_run_status_returns_status_and_result(token):
    c = token("memories:read")
    out = _ok(await mcp_app.run_status("j1", c))
    assert out == {"run_id": "j1", "status": "done", "command": "ingest", "result": {}}


@pytest.mark.asyncio
async def test_ask_without_wait_returns_run_id_immediately(token):
    c = token("memories:read")
    out = _ok(await mcp_app.ask("why?", c, scope="org", wait=False))
    assert out == {"status": "queued", "run_id": "j1"}
    assert FakeWiki.instances[0].calls == [("start_run", "query", "why?", "org")]


@pytest.mark.asyncio
async def test_ask_wait_timeout_returns_running_with_run_id(token):
    c = token("memories:read")
    out = _ok(await mcp_app.ask("why?", c))
    assert out["status"] == "running"
    assert out["run_id"] == "j2"


@pytest.mark.asyncio
async def test_tool_annotations():
    tools = {t.name: t for t in await mcp_app.mcp.list_tools()}
    assert set(mcp_app.TOOL_NAMES) <= set(tools)
    w = tools["write_file"].annotations
    assert (w.readOnlyHint, w.destructiveHint) == (False, False)
    d = tools["delete_file"].annotations
    assert (d.readOnlyHint, d.destructiveHint) == (False, True)
    assert tools["read_file"].annotations.readOnlyHint is True
