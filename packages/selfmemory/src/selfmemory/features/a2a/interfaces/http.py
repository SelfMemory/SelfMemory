"""The A2A JSON-RPC endpoint and the agent card.

Implemented methods: ``message/send``, ``message/stream``, ``tasks/get``,
``tasks/cancel`` and ``tasks/resubscribe``. Authentication and authorization
are the wiki's own: the caller's bearer credential, resolved by ``get_ctx``,
and every run re-derives its mount set from ``OrgAccess`` when it starts.
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse

from selfmemory.features.runs.store import TERMINAL
from selfmemory.features.tenancy.access import AccessDenied
from selfmemory.features.wiki.interfaces.http import Ctx, get_ctx
from selfmemory.platform.sandbox.isolation import isolation_report

router = APIRouter(prefix="/a2a", tags=["a2a"])
card_router = APIRouter(tags=["a2a"])

PROTOCOL_VERSION = "0.3.0"
MAX_MESSAGE = 100_000
POLL_S = 0.25

# JSON-RPC and A2A error codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
TASK_NOT_FOUND = -32001
TASK_NOT_CANCELABLE = -32002
UNSUPPORTED = -32004

_STATE = {
    "queued": "submitted",
    "running": "working",
    "done": "completed",
    "failed": "failed",
    "cancelled": "canceled",
}


class RpcError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def agent_card(base_url: str) -> dict:
    base = base_url.rstrip("/")
    return {
        "protocolVersion": PROTOCOL_VERSION,
        "name": "SelfMemory Wiki",
        "description": "Answers questions from your organization's knowledge "
        "wiki, citing the pages it read. Sees only the projects your "
        "credential can read.",
        "url": f"{base}/api/v1/a2a",
        "preferredTransport": "JSONRPC",
        "version": "1.0.0",
        "capabilities": {"streaming": True, "pushNotifications": False},
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["text/markdown"],
        "securitySchemes": {"bearer": {"type": "http", "scheme": "bearer"}},
        "security": [{"bearer": []}],
        "skills": [
            {
                "id": "ask-wiki",
                "name": "Ask the wiki",
                "description": "Answer a question from the wiki, with citations. "
                "Pass metadata.scope (e.g. project:<id>) to narrow it; omit "
                "contextId for an independent question, reuse it for a "
                "follow-up.",
                "tags": ["knowledge", "wiki", "search"],
                "examples": ["How do we rotate the payments API keys?"],
            }
        ],
    }


@card_router.get("/.well-known/agent-card.json", include_in_schema=False)
def well_known_card(request: Request):
    return agent_card(str(request.base_url))


@router.get("/.well-known/agent-card.json", summary="A2A agent card")
def card(request: Request):
    return agent_card(str(request.base_url))


# ------------------------------------------------------------------ mapping


def _iso(value) -> str:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.isoformat()
    return datetime.now(UTC).isoformat()


def _text_message(text: str, task_id: str, context_id: str | None) -> dict:
    return {
        "kind": "message",
        "role": "agent",
        "messageId": f"{task_id}-answer",
        "taskId": task_id,
        "contextId": context_id,
        "parts": [{"kind": "text", "text": text}],
    }


def task_view(job: dict) -> dict:
    """An A2A Task for one job."""
    state = _STATE.get(job["status"], "unknown")
    result = job.get("result") or {}
    status: dict[str, Any] = {
        "state": state,
        "timestamp": _iso(job.get("finishedAt") or job.get("startedAt")),
    }
    if state in ("failed", "canceled") and result.get("error"):
        status["message"] = _text_message(
            result["error"], job["_id"], job.get("chatId")
        )
    task: dict[str, Any] = {
        "kind": "task",
        "id": job["_id"],
        "contextId": job.get("chatId"),
        "status": status,
        "metadata": {"scope": job.get("scope")},
    }
    if state == "completed":
        task["artifacts"] = [
            {
                "artifactId": f"{job['_id']}-answer",
                "name": "answer",
                "parts": [{"kind": "text", "text": result.get("answer", "")}],
            }
        ]
    return task


def _status_event(job: dict, final: bool) -> dict:
    view = task_view(job)
    return {
        "kind": "status-update",
        "taskId": job["_id"],
        "contextId": job.get("chatId"),
        "status": view["status"],
        "final": final,
    }


# ------------------------------------------------------------------ methods


def _message_text(params: dict) -> tuple[str, dict]:
    message = params.get("message")
    if not isinstance(message, dict):
        raise RpcError(INVALID_PARAMS, "params.message is required")
    parts = message.get("parts") or []
    texts = [
        p["text"]
        for p in parts
        if isinstance(p, dict)
        and p.get("kind") == "text"
        and isinstance(p.get("text"), str)
    ]
    text = "\n".join(texts).strip()
    if not text:
        raise RpcError(UNSUPPORTED, "only text parts are supported")
    if len(text) > MAX_MESSAGE:
        raise RpcError(INVALID_PARAMS, "message is too long")
    if message.get("taskId"):
        raise RpcError(UNSUPPORTED, "tasks do not take further input")
    return text, message


def _start_task(ctx: Ctx, params: dict) -> dict:
    text, message = _message_text(params)
    meta = {**(params.get("metadata") or {}), **(message.get("metadata") or {})}
    scope = meta.get("scope") or None
    if scope is not None and not isinstance(scope, str):
        raise RpcError(INVALID_PARAMS, "metadata.scope must be a string")
    service = ctx.service
    context_id = message.get("contextId")
    if context_id:
        chat = service.chats.owned(ctx.principal.owner, context_id, ctx.access.org_id)
        if not chat or chat.get("kind") != "a2a":
            raise RpcError(INVALID_PARAMS, "unknown or expired contextId")
    else:
        try:
            if scope:
                ctx.access.scope(scope)
        except AccessDenied as e:
            raise RpcError(INVALID_PARAMS, str(e)) from None
        chat = service.chats.create(
            ctx.principal.owner,
            ctx.access.org_id,
            scope,
            ctx.principal.user_id,
            kind="a2a",
        )
    status = isolation_report(service.settings)
    if status["blocked"]:
        raise RpcError(UNSUPPORTED, status["detail"])
    try:
        return service.enqueue(
            ctx.access,
            command="query",
            message=text,
            scope_key=scope or chat.get("scope") or None,
            chat=chat,
            meta={"source": "a2a", "messageId": message.get("messageId")},
        )
    except (AccessDenied, ValueError) as e:
        raise RpcError(INVALID_PARAMS, str(e)) from None


def _owned(ctx: Ctx, params: dict) -> dict:
    task_id = params.get("id")
    job = ctx.service.jobs.owned(ctx.principal.owner, task_id) if task_id else None
    if not job:
        raise RpcError(TASK_NOT_FOUND, "task not found")
    return job


async def _wait(ctx: Ctx, job: dict, timeout_s: float) -> dict:
    deadline = time.monotonic() + timeout_s
    while job["status"] not in TERMINAL and time.monotonic() < deadline:
        await asyncio.sleep(POLL_S)
        job = await asyncio.to_thread(ctx.service.jobs.get, job["_id"]) or job
    return job


async def _events(ctx: Ctx, request: Request, job: dict, rpc_id):
    """SSE frames: the task, a status update per state change, then a final one."""

    def frame(result: dict) -> str:
        return f"data: {json.dumps({'jsonrpc': '2.0', 'id': rpc_id, 'result': result})}\n\n"

    yield frame(task_view(job))
    last = job["status"]
    deadline = time.monotonic() + ctx.service.settings.run_timeout_s + 60
    while job["status"] not in TERMINAL and time.monotonic() < deadline:
        if await request.is_disconnected():
            return  # the run carries on; tasks/resubscribe picks it up
        await asyncio.sleep(POLL_S)
        job = await asyncio.to_thread(ctx.service.jobs.get, job["_id"]) or job
        if job["status"] != last and job["status"] not in TERMINAL:
            last = job["status"]
            yield frame(_status_event(job, final=False))
    if job["status"] in TERMINAL:
        view = task_view(job)
        for artifact in view.get("artifacts", []):
            yield frame(
                {
                    "kind": "artifact-update",
                    "taskId": job["_id"],
                    "contextId": job.get("chatId"),
                    "artifact": artifact,
                    "lastChunk": True,
                }
            )
    yield frame(_status_event(job, final=True))


def _rpc_error(rpc_id, code: int, message: str) -> JSONResponse:
    return JSONResponse(
        {"jsonrpc": "2.0", "id": rpc_id, "error": {"code": code, "message": message}}
    )


@router.post("", summary="A2A JSON-RPC endpoint")
async def rpc(request: Request, ctx: Ctx = Depends(get_ctx)):
    try:
        body = await request.json()
    except ValueError:
        return _rpc_error(None, PARSE_ERROR, "invalid JSON")
    if not isinstance(body, dict) or body.get("jsonrpc") != "2.0":
        return _rpc_error(None, INVALID_REQUEST, "not a JSON-RPC 2.0 request")
    rpc_id = body.get("id")
    method = body.get("method")
    params = body.get("params") or {}
    if not isinstance(params, dict):
        return _rpc_error(rpc_id, INVALID_PARAMS, "params must be an object")

    def ok(result: dict) -> JSONResponse:
        return JSONResponse({"jsonrpc": "2.0", "id": rpc_id, "result": result})

    def stream(job: dict) -> StreamingResponse:
        return StreamingResponse(
            _events(ctx, request, job, rpc_id),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    try:
        if method == "message/send":
            job = await asyncio.to_thread(_start_task, ctx, params)
            config = params.get("configuration") or {}
            if config.get("blocking"):
                job = await _wait(ctx, job, ctx.service.settings.run_timeout_s)
            return ok(task_view(job))
        if method == "message/stream":
            job = await asyncio.to_thread(_start_task, ctx, params)
            return stream(job)
        if method == "tasks/get":
            return ok(task_view(_owned(ctx, params)))
        if method == "tasks/resubscribe":
            return stream(_owned(ctx, params))
        if method == "tasks/cancel":
            job = _owned(ctx, params)
            if job["status"] in TERMINAL:
                raise RpcError(TASK_NOT_CANCELABLE, f"task is {job['status']}")
            ctx.service.jobs.request_cancel(ctx.principal.owner, job["_id"])
            return ok(task_view(ctx.service.jobs.get(job["_id"]) or job))
        raise RpcError(METHOD_NOT_FOUND, f"unknown method {method!r}")
    except RpcError as e:
        return _rpc_error(rpc_id, e.code, e.message)
