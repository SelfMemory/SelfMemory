"""A thin client for the core server's wiki API, used by the MCP tools.

The caller's own credential (OAuth access token or API key) is forwarded as
the bearer token, so the core server applies exactly the access that caller
has: a token pinned to a project sees that project and the org room, nothing
else. The MCP server never holds broader credentials of its own.
"""

from __future__ import annotations

import asyncio
import time

import httpx

TERMINAL = {"done", "failed", "cancelled"}


class WikiError(RuntimeError):
    pass


class WikiClient:
    def __init__(self, host: str, token: str, timeout: float = 30.0):
        self.host = host.rstrip("/")
        self.headers = {"Authorization": f"Bearer {token}"}
        self.timeout = timeout

    async def _request(self, method: str, path: str, **kw) -> dict:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.request(
                method, f"{self.host}{path}", headers=self.headers, **kw
            )
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("detail")
            except ValueError:
                detail = resp.text[:300]
            raise WikiError(f"{resp.status_code}: {detail}")
        return resp.json()

    async def search(self, query: str, limit: int = 10) -> dict:
        return await self._request(
            "GET", "/api/v1/wiki/search", params={"q": query, "limit": limit}
        )

    async def fetch(self, path: str) -> dict:
        return await self._request("GET", "/api/v1/wiki/file", params={"path": path})

    async def tree(self) -> dict:
        return await self._request("GET", "/api/v1/wiki/tree")

    async def scopes(self) -> dict:
        return await self._request("GET", "/api/v1/wiki/scopes")

    async def read_file(self, path: str) -> dict:
        """Raw file content plus its side and owning scope key."""
        page, scopes = await asyncio.gather(self.fetch(path), self.scopes())
        return {**page, "scope": scope_for_path(path, scopes.get("scopes", []))}

    async def write_file(self, path: str, content: str) -> dict:
        return await self._request(
            "PUT", "/api/v1/wiki/file", json={"path": path, "content": content}
        )

    async def delete_file(self, path: str) -> dict:
        return await self._request("DELETE", "/api/v1/wiki/file", params={"path": path})

    async def start_run(
        self, command: str, message: str = "", scope: str | None = None
    ) -> dict:
        """Queue a run and return ``{job_id, status, events}`` without waiting."""
        return await self._request(
            "POST",
            "/api/v1/wiki/runs",
            json={"command": command, "message": message, "scope": scope},
        )

    async def run(self, run_id: str) -> dict:
        return await self._request("GET", f"/api/v1/wiki/runs/{run_id}")

    async def cancel_run(self, run_id: str) -> dict:
        return await self._request("DELETE", f"/api/v1/wiki/runs/{run_id}")

    async def wait_run(self, run_id: str, wait_s: float = 300.0) -> dict:
        """Poll a run until it finishes, or report it still running at the
        deadline."""
        deadline = time.monotonic() + wait_s
        delay = 1.0
        while time.monotonic() < deadline:
            run = await self.run(run_id)
            if run["status"] in TERMINAL:
                return run
            await asyncio.sleep(delay)
            delay = min(delay * 1.5, 5.0)
        return {"id": run_id, "status": "running", "result": None}

    async def ask(
        self, question: str, scope: str | None = None, wait_s: float = 300.0
    ) -> dict:
        """Queue a read-only query run and wait for its answer."""
        job = await self.start_run("query", question, scope)
        return await self.wait_run(job["job_id"], wait_s)


def scope_for_path(path: str, scopes: list[dict]) -> str | None:
    """The key of the scope owning ``path`` (longest wiki/raw prefix wins, so a
    sub-project's file maps to the sub-project, not its parent)."""
    best, best_len = None, -1
    for s in scopes:
        for root in (s.get("wiki"), s.get("raw")):
            if (
                root
                and (path == root or path.startswith(root + "/"))
                and len(root) > best_len
            ):
                best, best_len = s.get("key"), len(root)
    return best
