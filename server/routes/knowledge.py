"""HTTP surface for knowledge-page memory.

Mirrors the auth and project-resolution behaviour of the existing memory
endpoints: session-authenticated callers name a project and have permissions
looked up; token-authenticated callers are pinned to the project their key was
issued for.

The read endpoints split by cost. ``/ask`` is one model call over full-text
hits. ``/research`` runs an agent over a materialized copy of the pages -- far
slower, and the only path that answers questions needing more than one hop.
"""

from __future__ import annotations

import logging
import os

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from selfmemory.knowledge import (
    AgentSessionError,
    KnowledgeMemory,
    SQLiteKnowledgeStore,
)

from ..dependencies import AuthContext, authenticate_api_key, get_user_permissions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])

KNOWLEDGE_DB = os.getenv("SELFMEMORY_KNOWLEDGE_DB", "knowledge.db")
_store = SQLiteKnowledgeStore(KNOWLEDGE_DB)


def _memory() -> KnowledgeMemory:
    return KnowledgeMemory(store=_store)


# ============================================================================
# Project resolution
# ============================================================================


def _resolve_project(
    auth: AuthContext,
    requested_project_id: str | None,
    *,
    permission: str,
) -> str:
    """Authorize one project for this caller, or raise.

    Read paths must go through this for every project they touch -- a workspace
    is built from the returned ids, and anything materialized is assumed read
    whatever the answer ends up saying.
    """
    flag = {"read": "canRead", "write": "canWrite", "delete": "canDelete"}[permission]
    detail = f"Permission denied - {permission} access required"

    # Token auth (API key / Hydra): pinned to the key's own project.
    if auth.project_id is not None:
        if requested_project_id and requested_project_id != auth.project_id:
            raise HTTPException(
                status_code=403,
                detail="API key is not authorized for the requested project",
            )
        if not auth.permissions or not getattr(auth.permissions, flag):
            raise HTTPException(status_code=403, detail=detail)
        return auth.project_id

    # Session auth: the project comes from the request and is looked up.
    if not requested_project_id:
        raise HTTPException(
            status_code=400,
            detail="project_id required for session authentication",
        )
    try:
        ObjectId(requested_project_id)
    except Exception as err:
        raise HTTPException(
            status_code=400, detail="Invalid project_id format"
        ) from err

    permissions = get_user_permissions(auth.user_id, requested_project_id)
    if not getattr(permissions, flag):
        raise HTTPException(status_code=403, detail=detail)
    return requested_project_id


# ============================================================================
# Schemas
# ============================================================================


class RememberRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=100_000)
    metadata: dict | None = None
    project_id: str | None = None


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4_000)
    project_id: str | None = None


class ResearchRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4_000)
    project_id: str | None = None
    project_ids: list[str] | None = Field(
        default=None,
        description=(
            "Query across several projects. Every one is authorized "
            "individually; unauthorized ids are rejected, not skipped."
        ),
    )
    timeout: int = Field(default=180, ge=10, le=600)


class LintRequest(BaseModel):
    project_id: str | None = None


# ============================================================================
# Write
# ============================================================================


@router.post("/memories", summary="Ingest a source and compact it into pages")
def remember(
    body: RememberRequest,
    auth: AuthContext = Depends(authenticate_api_key),
):
    project_id = _resolve_project(auth, body.project_id, permission="write")
    metadata = {**(body.metadata or {}), "createdBy": auth.user_id}

    result = _memory().remember(body.text, metadata=metadata, project_id=project_id)
    logger.info(
        "knowledge ingest: project=%s source=%s created=%d updated=%d",
        project_id,
        result.source_id,
        len(result.created),
        len(result.updated),
    )
    return {
        "source_id": result.source_id,
        "created": result.created,
        "updated": result.updated,
        "considered": result.pages_considered,
    }


@router.post("/lint", summary="Audit the knowledge base for decay")
def lint(
    body: LintRequest,
    auth: AuthContext = Depends(authenticate_api_key),
):
    project_id = _resolve_project(auth, body.project_id, permission="write")
    findings = _memory().lint(project_id=project_id)
    return {
        "count": len(findings),
        "findings": [
            {
                "kind": f.kind,
                "slugs": f.slugs,
                "detail": f.detail,
                "fix": f.fix,
            }
            for f in findings
        ],
    }


# ============================================================================
# Read
# ============================================================================


@router.post("/ask", summary="Answer from full-text hits (one model call)")
def ask(
    body: AskRequest,
    auth: AuthContext = Depends(authenticate_api_key),
):
    project_id = _resolve_project(auth, body.project_id, permission="read")
    answer = _memory().ask(body.question, project_id=project_id)
    return {"answer": answer.text, "citations": answer.citations}


@router.post("/research", summary="Answer by running an agent over the pages")
def research(
    body: ResearchRequest,
    auth: AuthContext = Depends(authenticate_api_key),
):
    requested = body.project_ids or [body.project_id]
    projects = [
        _resolve_project(auth, pid, permission="read")
        for pid in dict.fromkeys(requested)
    ]

    memory = _memory()
    if not memory.runner.available():
        raise HTTPException(
            status_code=503,
            detail="Agent runtime unavailable - /ask is still served",
        )

    try:
        answer = memory.research(
            body.question, project_ids=projects, timeout=body.timeout
        )
    except AgentSessionError as err:
        logger.warning("research failed: projects=%s error=%s", projects, err)
        raise HTTPException(
            status_code=502, detail=f"Agent session failed: {err}"
        ) from err

    return {
        "answer": answer.text,
        "citations": answer.citations,
        "projects": projects,
    }


@router.get("/pages", summary="List every page with its summary")
def list_pages(
    project_id: str | None = None,
    auth: AuthContext = Depends(authenticate_api_key),
):
    resolved = _resolve_project(auth, project_id, permission="read")
    return {
        "pages": [
            {
                "slug": e.slug,
                "title": e.title,
                "summary": e.summary,
                "updated_at": e.updated_at.isoformat(),
            }
            for e in _memory().index(project_id=resolved)
        ]
    }


@router.get("/pages/{slug:path}", summary="Read one page in full")
def get_page(
    slug: str,
    project_id: str | None = None,
    auth: AuthContext = Depends(authenticate_api_key),
):
    resolved = _resolve_project(auth, project_id, permission="read")
    page = _memory().page(slug, project_id=resolved)
    if page is None:
        raise HTTPException(status_code=404, detail=f"No page {slug!r}")
    return {
        "slug": page.slug,
        "title": page.title,
        "body": page.body,
        "summary": page.summary,
        "sources": page.sources,
        "markdown": page.to_markdown(),
        "created_at": page.created_at.isoformat(),
        "updated_at": page.updated_at.isoformat(),
    }


@router.get("/log", summary="Recent operations, newest first")
def get_log(
    project_id: str | None = None,
    limit: int = 50,
    auth: AuthContext = Depends(authenticate_api_key),
):
    resolved = _resolve_project(auth, project_id, permission="read")
    entries = _memory().log(limit=min(limit, 500), project_id=resolved)
    return {
        "entries": [
            {"ts": e.ts.isoformat(), "op": e.op, "detail": e.detail} for e in entries
        ]
    }
