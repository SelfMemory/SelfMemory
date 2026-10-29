"""HTTP surface for the knowledge wiki.

Every route authenticates through the existing Ory/API-key dependency, then
resolves the caller's scopes in one organization (``org_id``; optional when
the caller has exactly one org, or is a token pinned to a project). Paths in
requests and responses are relative to the organization root, e.g.
``wiki/projects/<id>/people/ada.md`` -- the same form the agent cites.

Runs are asynchronous: ``POST /runs`` returns 202 with a job id, and
``GET /runs/{id}/events`` streams the run as server-sent events that resume
from ``Last-Event-ID``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import time
from datetime import datetime
from typing import Literal

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from selfmemory.features.runs.store import (
    TERMINAL,
    QuotaExceededError,
    ScopeBusyError,
    job_summary,
)
from selfmemory.features.tenancy.access import AccessDenied, OrgAccess, Principal
from selfmemory.features.wiki.adapters.files import (
    IMAGE_EXTENSIONS,
    list_regular_files,
    list_wiki_files,
    looks_binary,
    remove_file,
    write_bytes,
)
from selfmemory.features.wiki.adapters.graph import (
    build_graph,
    build_history,
    build_timeline,
)
from selfmemory.features.wiki.adapters.okf import PROTECTED_WIKI_FILES
from selfmemory.features.wiki.adapters.search import search_pages
from selfmemory.features.wiki.service import UploadFile as StagedUpload
from selfmemory.features.wiki.service import WikiService, staging_dir
from selfmemory.kernel.safe_paths import PathRefused
from selfmemory.platform.dependencies import AuthContext, authenticate_api_key
from selfmemory.platform.sandbox.isolation import isolation_report

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/wiki", tags=["wiki"])

Side = Literal["wiki", "raw"]


def get_service(request: Request) -> WikiService:
    service = getattr(request.app.state, "wiki", None)
    if service is None:
        raise HTTPException(status_code=503, detail="wiki service is not initialised")
    return service


class Ctx:
    """Authenticated caller plus their resolved view of one organization."""

    def __init__(self, service: WikiService, principal: Principal, access: OrgAccess):
        self.service = service
        self.principal = principal
        self.access = access


def _errors(e: Exception) -> HTTPException:
    if isinstance(e, AccessDenied):
        return HTTPException(status_code=403, detail=str(e))
    if isinstance(e, PathRefused):
        return HTTPException(status_code=403, detail=str(e))
    if isinstance(e, ScopeBusyError):
        return HTTPException(status_code=409, detail=str(e))
    if isinstance(e, QuotaExceededError):
        return HTTPException(status_code=429, detail=str(e))
    if isinstance(e, KeyError):
        return HTTPException(status_code=404, detail="not found")
    return HTTPException(status_code=400, detail=str(e))


def principal_for(auth: AuthContext) -> Principal:
    """The wiki principal for a credential.

    A token (OAuth or API key) must be pinned to a project. One without a
    project claim would otherwise be treated like a dashboard session and
    reach personal notes and a writable org room.
    """
    if auth.auth_type != "session" and not auth.project_id:
        raise HTTPException(
            status_code=403, detail="this credential is not scoped to a project"
        )
    return Principal.from_auth(auth)


def get_principal(auth: AuthContext = Depends(authenticate_api_key)) -> Principal:
    return principal_for(auth)


def get_ctx(
    org_id: str | None = Query(None, description="Organization id"),
    auth: AuthContext = Depends(authenticate_api_key),
    service: WikiService = Depends(get_service),
) -> Ctx:
    principal = principal_for(auth)
    try:
        access = service.access(principal, org_id)
    except AccessDenied as e:
        raise HTTPException(status_code=403, detail=str(e)) from None
    return Ctx(service, principal, access)


def _jsonable(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    return value


# ---------------------------------------------------------------- scopes


@router.get("/scopes", summary="Scopes this caller can read in an organization")
def list_scopes(ctx: Ctx = Depends(get_ctx)):
    return ctx.access.summary()


@router.get("/status", summary="Agent isolation and credentials on this host")
def wiki_status(
    auth: AuthContext = Depends(authenticate_api_key),
    service: WikiService = Depends(get_service),
):
    return isolation_report(service.settings)


@router.get("/tree", summary="Wiki pages in every readable scope")
def tree(ctx: Ctx = Depends(get_ctx)):
    a = ctx.access
    out = []
    for s in a.scopes:
        ctx.service.ensure_scope(a, s)
        root = a.scope_root(s)
        files = [
            p.relative_to(a.root).as_posix()
            for p in list_wiki_files(root.abs)
            if not any(
                p.relative_to(a.root).as_posix().startswith(x + "/")
                for x in root.exclude
            )
        ]
        out.append({**s.summary(), "files": files})
    return {"org_id": a.org_id, "scopes": out}


# ------------------------------------------------------------------ files


@router.get("/file", summary="Read a wiki page or raw source")
def read_file(path: str = Query(...), ctx: Ctx = Depends(get_ctx)):
    try:
        scope, side, abs_path = ctx.access.resolve_path(path)
    except (AccessDenied, PathRefused) as e:
        raise _errors(e) from None
    if not abs_path.is_file():
        raise HTTPException(status_code=404, detail="not found")
    ctx.service.record(
        ctx.access, "file.read", scopes=[scope.key], target=path, detail={"side": side}
    )
    if abs_path.suffix.lower() in IMAGE_EXTENSIONS:
        # User-supplied bytes: never let them run as a page on this origin
        # (an uploaded SVG can carry script).
        headers = {
            "Cache-Control": "private, max-age=300",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; sandbox",
        }
        if abs_path.suffix.lower() == ".svg":
            headers["Content-Disposition"] = "attachment"
        return FileResponse(abs_path, headers=headers)
    data = abs_path.read_bytes()
    if looks_binary(data):
        return {"path": path, "side": side, "binary": True, "size": len(data)}
    return {
        "path": path,
        "side": side,
        "content": data.decode("utf-8", errors="replace"),
    }


class FileWrite(BaseModel):
    path: str
    content: str = Field(..., max_length=5_000_000)


@router.put("/file", summary="Create or replace a file (commits on the wiki side)")
def write_file(body: FileWrite, ctx: Ctx = Depends(get_ctx)):
    try:
        scope, side, abs_path = ctx.access.resolve_path(body.path, write=True)
        sha = None
        with ctx.service.lease(ctx.access, scope, f"edit:{ctx.principal.user_id}"):
            write_bytes(abs_path, body.content.encode("utf-8"))
            if side == "wiki":
                sha = ctx.service.commit(
                    ctx.access,
                    scope,
                    f"[edit] {abs_path.name}\n\nby {ctx.principal.user_id}",
                )
    except (AccessDenied, PathRefused, ScopeBusyError) as e:
        raise _errors(e) from None
    ctx.service.record(
        ctx.access,
        "file.write",
        scopes=[scope.key],
        target=body.path,
        detail={"side": side, "sha": sha},
    )
    return {"ok": True, "side": side, "sha": sha}


@router.delete("/file", summary="Delete one file (commits on the wiki side)")
def delete_file(path: str = Query(...), ctx: Ctx = Depends(get_ctx)):
    try:
        scope, side, abs_path = ctx.access.resolve_path(path, write=True)
        if (
            side == "wiki"
            and abs_path.parent == ctx.access.abs(scope.wiki_rel)
            and (abs_path.name in PROTECTED_WIKI_FILES)
        ):
            raise PathRefused(f"{abs_path.name} is maintained by the agent")
        sha = None
        with ctx.service.lease(ctx.access, scope, f"delete:{ctx.principal.user_id}"):
            if not remove_file(abs_path):
                raise HTTPException(status_code=404, detail="not found")
            if side == "wiki":
                sha = ctx.service.commit(
                    ctx.access,
                    scope,
                    f"[delete] {abs_path.name}\n\nby {ctx.principal.user_id}",
                )
    except (AccessDenied, PathRefused, ScopeBusyError) as e:
        raise _errors(e) from None
    ctx.service.record(
        ctx.access,
        "file.delete",
        scopes=[scope.key],
        target=path,
        detail={"side": side, "sha": sha},
    )
    return {"ok": True, "side": side, "sha": sha}


@router.get("/sources", summary="Raw sources uploaded to a scope")
def sources(
    scope: str = Query(...),
    limit: int = Query(500, ge=1, le=500),
    offset: int = Query(0, ge=0),
    ctx: Ctx = Depends(get_ctx),
):
    try:
        s = ctx.access.scope(scope)
    except AccessDenied as e:
        raise _errors(e) from None
    nested = [ctx.access.abs(r) for r in s.nested_rels("raw")]
    files = [
        p.relative_to(ctx.access.root).as_posix()
        for p in list_regular_files(ctx.access.abs(s.raw_rel))
        if not any(str(p).startswith(str(n) + "/") for n in nested)
    ]
    return {
        "scope": scope,
        "files": files[offset : offset + limit],
        "total": len(files),
        "has_more": offset + limit < len(files),
    }


@router.post("/upload", summary="Upload sources into a scope and queue an ingest")
async def upload(
    scope: str = Form(...),
    files: list[UploadFile] = File(...),
    paths: list[str] | None = Form(None),
    note: str | None = Form(None),
    ingest: bool = Form(True),
    ctx: Ctx = Depends(get_ctx),
):
    settings = ctx.service.settings
    if len(files) > settings.upload_max_files:
        raise HTTPException(status_code=400, detail="too many files")
    try:
        ctx.access.writable(scope)
    except AccessDenied as e:
        raise _errors(e) from None
    stage = staging_dir()
    try:
        staged: list[StagedUpload] = []
        skipped: list[dict] = []
        for i, f in enumerate(files):
            name = f.filename or f"upload-{i}"
            dest = stage / f"{i}"
            size = 0
            with dest.open("wb") as out:
                while chunk := await f.read(1024 * 1024):
                    size += len(chunk)
                    if size > settings.upload_max_bytes:
                        break
                    out.write(chunk)
            if size > settings.upload_max_bytes:
                skipped.append({"name": name, "why": "file is too large"})
                continue
            rel = paths[i] if paths and i < len(paths) else None
            rel_dir = (
                rel.replace("\\", "/").rsplit("/", 1)[0] if rel and "/" in rel else None
            )
            staged.append(StagedUpload(name, dest, rel_dir))
        result = await asyncio.to_thread(ctx.service.upload, ctx.access, scope, staged)
    except (AccessDenied, PathRefused) as e:
        raise _errors(e) from None
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    result["skipped"] = skipped + result["skipped"]
    if result["written"]:
        ctx.service.record(
            ctx.access,
            "file.upload",
            scopes=[scope],
            detail={"files": result["written"][:200], "count": len(result["written"])},
        )
    job = None
    if ingest and result["written"]:
        message = "\n".join(result["written"])
        if note and note.strip():
            message += f"\n\nPay particular attention to: {note.strip()}"
        try:
            job = await asyncio.to_thread(
                ctx.service.enqueue,
                ctx.access,
                command="ingest",
                message=message,
                scope_key=scope,
                display_text=f"Ingest {len(result['written'])} file(s)",
                files=result["written"],
            )
        except QuotaExceededError as e:
            raise HTTPException(
                status_code=429, detail=f"files were saved but not ingested: {e}"
            ) from None
    return {
        **result,
        "job_id": job["_id"] if job else None,
        "events": f"/api/wiki/runs/{job['_id']}/events" if job else None,
    }


# ------------------------------------------------------------------- runs


class RunRequest(BaseModel):
    command: Literal["ingest", "query", "lint"]
    message: str = Field("", max_length=100_000)
    scope: str | None = None
    chat_id: str | None = None
    display_text: str | None = Field(None, max_length=10_000)
    files: list[str] | None = None


@router.post("/runs", status_code=202, summary="Queue an ingest, query or lint run")
def create_run(body: RunRequest, ctx: Ctx = Depends(get_ctx)):
    chat = None
    if body.chat_id:
        chat = ctx.service.chats.owned(
            ctx.principal.owner, body.chat_id, ctx.access.org_id
        )
        if not chat:
            raise HTTPException(status_code=404, detail="chat not found")
    if body.files:
        for f in body.files:
            try:
                ctx.access.resolve_path(f)
            except (AccessDenied, PathRefused) as e:
                raise _errors(e) from None
    status = isolation_report(ctx.service.settings)
    if status["blocked"]:
        raise HTTPException(status_code=503, detail=status["detail"])
    try:
        job = ctx.service.enqueue(
            ctx.access,
            command=body.command,
            message=body.message,
            scope_key=body.scope,
            display_text=body.display_text,
            files=body.files,
            chat=chat,
        )
    except (AccessDenied, ValueError, QuotaExceededError) as e:
        raise _errors(e) from None
    return {
        "job_id": job["_id"],
        "status": job["status"],
        "events": f"/api/wiki/runs/{job['_id']}/events",
    }


@router.get("/runs", summary="Recent runs, or the active run of a chat")
def list_runs(chat_id: str | None = None, ctx: Ctx = Depends(get_ctx)):
    owner = ctx.principal.owner
    if chat_id:
        job = ctx.service.jobs.active_for_chat(owner, chat_id)
        return {"job": _jsonable(job_summary(job)) if job else None}
    jobs = ctx.service.jobs.recent(owner, ctx.access.org_id)
    return {"jobs": [_jsonable(job_summary(j)) for j in jobs]}


def _owned_job(service: WikiService, principal: Principal, job_id: str) -> dict:
    job = service.jobs.owned(principal.owner, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="run not found")
    return job


@router.get("/runs/{job_id}", summary="One run, with its result when finished")
def get_run(
    job_id: str,
    principal: Principal = Depends(get_principal),
    service: WikiService = Depends(get_service),
):
    job = _owned_job(service, principal, job_id)
    return _jsonable({**job_summary(job), "result": job.get("result")})


@router.delete("/runs/{job_id}", summary="Cancel a queued or running run")
def cancel_run(
    job_id: str,
    principal: Principal = Depends(get_principal),
    service: WikiService = Depends(get_service),
):
    _owned_job(service, principal, job_id)
    job = service.jobs.request_cancel(principal.owner, job_id)
    return {"id": job_id, "status": job["status"] if job else "unknown"}


@router.get("/runs/{job_id}/events", summary="Stream a run as server-sent events")
async def run_events(
    job_id: str,
    request: Request,
    after: int = Query(0, ge=0),
    principal: Principal = Depends(get_principal),
    service: WikiService = Depends(get_service),
):
    job = _owned_job(service, principal, job_id)
    last = request.headers.get("last-event-id")
    if last and last.isdigit():
        after = max(after, int(last))
    deadline = time.monotonic() + service.settings.run_timeout_s + 60

    def frame(seq: int | None, event: dict) -> str:
        head = f"id: {seq}\n" if seq is not None else ""
        return f"{head}data: {json.dumps(_jsonable(event))}\n\n"

    async def stream():
        cursor = after
        yield frame(
            None,
            {
                "kind": "job",
                "id": job["_id"],
                "status": job["status"],
                "command": job["command"],
                "scope": job.get("scope"),
                "attempts": job.get("attempts", 0),
            },
        )
        while True:
            if await request.is_disconnected():
                return
            rows = await asyncio.to_thread(service.jobs.read_events, job_id, cursor)
            for row in rows:
                cursor = row["seq"]
                yield frame(row["seq"], row["event"])
            if rows:
                continue
            current = await asyncio.to_thread(service.jobs.get, job_id)
            if current is None or current["status"] in TERMINAL:
                rest = await asyncio.to_thread(service.jobs.read_events, job_id, cursor)
                for row in rest:
                    cursor = row["seq"]
                    yield frame(row["seq"], row["event"])
                result = (current or {}).get("result") or {}
                yield frame(
                    None,
                    {
                        "kind": "done",
                        "status": (current or {}).get("status", "failed"),
                        "code": result.get("code"),
                    },
                )
                return
            if time.monotonic() > deadline:
                yield frame(
                    None, {"kind": "notice", "message": "stream deadline reached"}
                )
                return
            await asyncio.sleep(0.25)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )


# ------------------------------------------------------------------ chats


class ChatCreate(BaseModel):
    scope: str | None = None


@router.get("/chats", summary="List chats, or one chat with its messages")
def chats(chat_id: str | None = None, ctx: Ctx = Depends(get_ctx)):
    owner = ctx.principal.owner
    if chat_id:
        chat = ctx.service.chats.owned(owner, chat_id, ctx.access.org_id)
        if not chat:
            raise HTTPException(status_code=404, detail="chat not found")
        messages = ctx.service.chats.messages_for(chat_id)
        return _jsonable(
            {
                "chat": {
                    "id": chat["_id"],
                    "title": chat["title"],
                    "scope": chat["scope"],
                    "session_id": chat.get("sessionId"),
                },
                "messages": [
                    {
                        "role": m["role"],
                        "text": m["text"],
                        "meta": m.get("meta"),
                        "at": m["at"],
                    }
                    for m in messages
                ],
            }
        )
    rows = ctx.service.chats.list(owner, ctx.access.org_id)
    return _jsonable(
        {
            "chats": [
                {
                    "id": c["_id"],
                    "title": c["title"],
                    "scope": c["scope"],
                    "updated_at": c["updatedAt"],
                }
                for c in rows
            ]
        }
    )


@router.post("/chats", summary="Start a chat")
def create_chat(body: ChatCreate, ctx: Ctx = Depends(get_ctx)):
    if body.scope:
        try:
            ctx.access.scope(body.scope)
        except AccessDenied as e:
            raise _errors(e) from None
    chat = ctx.service.chats.create(
        ctx.principal.owner, ctx.access.org_id, body.scope, ctx.principal.user_id
    )
    return {"id": chat["_id"], "title": chat["title"]}


@router.delete(
    "/chats/{chat_id}", summary="Delete a chat, its messages and its agent session"
)
def delete_chat(
    chat_id: str,
    principal: Principal = Depends(get_principal),
    service: WikiService = Depends(get_service),
):
    if not service.delete_chat(principal, chat_id):
        raise HTTPException(status_code=404, detail="chat not found")
    return {"ok": True}


# ------------------------------------------------------- graph and search


@router.get("/graph", summary="Pages and links, for one scope or everything readable")
def graph(scope: str | None = None, ctx: Ctx = Depends(get_ctx)):
    try:
        roots = ctx.access.scope_roots(scope)
    except AccessDenied as e:
        raise _errors(e) from None
    return {"scope": scope, **build_graph(ctx.access.root, roots)}


@router.get("/timeline", summary="How the wiki graph grew, commit by commit")
def timeline(
    scope: str | None = None,
    limit: int = Query(80, ge=1, le=500),
    ctx: Ctx = Depends(get_ctx),
):
    try:
        roots = ctx.access.scope_roots(scope)
    except AccessDenied as e:
        raise _errors(e) from None
    return {"frames": build_timeline(roots, limit)}


@router.get("/history", summary="Git commit log of one scope or everything readable")
def history(
    scope: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    ctx: Ctx = Depends(get_ctx),
):
    try:
        roots = ctx.access.scope_roots(scope)
    except AccessDenied as e:
        raise _errors(e) from None
    return {"commits": build_history(roots, limit)}


@router.get("/search", summary="Lexical search over readable pages")
def search(
    q: str = Query(..., min_length=1, max_length=500),
    scope: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    ctx: Ctx = Depends(get_ctx),
):
    try:
        roots = ctx.access.scope_roots(scope)
    except AccessDenied as e:
        raise _errors(e) from None
    return {"query": q, "results": search_pages(ctx.access.root, roots, q, limit)}


# -------------------------------------------------------------- promotions


class PromotionDecision(BaseModel):
    scope: str
    id: str = Field(..., min_length=1, max_length=64)
    decision: Literal["approve", "reject"]


@router.get("/promotions", summary="Org-wide facts queued for the org room")
def promotions(ctx: Ctx = Depends(get_ctx)):
    return {"promotions": ctx.service.promotions(ctx.access)}


@router.post("/promotions/decide", summary="Approve or reject a promotion")
def decide_promotion(body: PromotionDecision, ctx: Ctx = Depends(get_ctx)):
    try:
        return ctx.service.decide_promotion(
            ctx.access, body.scope, body.id, body.decision
        )
    except (AccessDenied, KeyError, ValueError, ScopeBusyError) as e:
        raise _errors(e) from None
