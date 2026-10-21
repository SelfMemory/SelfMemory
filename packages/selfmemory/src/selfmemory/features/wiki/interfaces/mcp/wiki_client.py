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

    async def ask(
        self, question: str, scope: str | None = None, wait_s: float = 300.0
    ) -> dict:
        """Queue a read-only query run and wait for its answer."""
        job = await self._request(
            "POST",
            "/api/v1/wiki/runs",
            json={"command": "query", "message": question, "scope": scope},
        )
        job_id = job["job_id"]
        deadline = time.monotonic() + wait_s
        delay = 1.0
        while time.monotonic() < deadline:
            run = await self._request("GET", f"/api/v1/wiki/runs/{job_id}")
            if run["status"] in TERMINAL:
                return run
            await asyncio.sleep(delay)
            delay = min(delay * 1.5, 5.0)
        return {"id": job_id, "status": "running", "result": None}
