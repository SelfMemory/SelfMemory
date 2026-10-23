"""Operations shared by the HTTP routes and the worker.

Routes authenticate and parse; the worker executes runs; everything that
touches the data root or the queue in between goes through here, so the
rules (scaffold lazily, commit under a lease, re-check entitlement at run
time) live in one place.
"""

from __future__ import annotations

import logging
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from selfmemory.features.runs.homes import delete_chat_home
from selfmemory.features.runs.store import (
    ChatStore,
    JobStore,
    QuotaExceededError,
    ScopeLease,
)
from selfmemory.features.tenancy.access import (
    AccessDenied,
    OrgAccess,
    Principal,
    default_org_id,
    resolve_org_access,
)
from selfmemory.features.uploads.convert import convert_file
from selfmemory.features.wiki.adapters import git_repo as git
from selfmemory.features.wiki.adapters.files import write_bytes
from selfmemory.features.wiki.adapters.okf import (
    parse_promotions,
    scaffold_scope,
    set_promotion_status,
)
from selfmemory.features.wiki.domain.layout import ORG_KEY, Scope
from selfmemory.kernel.logging import sanitize_for_log
from selfmemory.kernel.safe_paths import (
    PathRefused,
    is_within,
    resolve_contained,
    sanitize_filename,
    sanitize_upload_dir,
)
from selfmemory.platform.audit import AuditLog

if TYPE_CHECKING:
    from selfmemory.wiki_settings import WikiSettings

__all__ = ["WikiService", "UploadFile"]

logger = logging.getLogger(__name__)

COMMANDS = ("ingest", "query", "lint")


def _today() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


class UploadFile:
    """A file staged on disk for conversion, with the name the client gave it."""

    def __init__(self, name: str, staged: Path, rel_dir: str | None = None):
        self.name = name
        self.staged = staged
        self.rel_dir = rel_dir


class WikiService:
    def __init__(self, db, settings: WikiSettings):
        self.db = db
        self.settings = settings
        self.jobs = JobStore(db)
        self.chats = ChatStore(db)
        self.audit = AuditLog(db)

    def record(self, access: OrgAccess, action: str, **kw) -> None:
        """Append an audit record for the caller behind ``access``."""
        self.audit.record(
            action,
            org_id=access.org_id,
            user_id=access.principal.user_id,
            owner=access.principal.owner,
            **kw,
        )

    # ------------------------------------------------------------ access

    def access(self, principal: Principal, org_id: str | None) -> OrgAccess:
        org = default_org_id(self.db, principal, org_id)
        return resolve_org_access(self.db, self.settings, principal, org)

    def ensure_scope(self, access: OrgAccess, scope: Scope) -> None:
        """Create a scope's directories, reserved files and repository on first use.

        Lazy on purpose: organizations and projects are created by several code
        paths (the API, the dashboard writing to Mongo directly, invitations),
        and hooking all of them would be fragile. Idempotent and cheap once done.
        """
        wiki_dir = access.abs(scope.wiki_rel)
        raw_dir = access.abs(scope.raw_rel)
        raw_dir.mkdir(parents=True, exist_ok=True)
        if (wiki_dir / "index.md").exists() and git.is_repo(wiki_dir):
            scaffold_scope(wiki_dir, scope.key, scope.label, scope.nested)
            return
        # First use: several workers or requests may get here at once, and
        # two concurrent ``git init``s in one directory fail. The lease makes
        # one of them do it; the others then find it done.
        with self.lease(access, scope, "scaffold"):
            scaffold_scope(wiki_dir, scope.key, scope.label, scope.nested)

    def ensure_all(self, access: OrgAccess) -> None:
        for s in access.scopes:
            self.ensure_scope(access, s)

    def lease(self, access: OrgAccess, scope: Scope, owner: str, **kw) -> ScopeLease:
        return ScopeLease(self.db, str(access.abs(scope.wiki_rel)), owner, **kw)

    def commit(self, access: OrgAccess, scope: Scope, message: str) -> str | None:
        return git.commit_scope(access.abs(scope.wiki_rel), message, scope.nested)

    # -------------------------------------------------------------- runs

    def enqueue(
        self,
        access: OrgAccess,
        *,
        command: str,
        message: str,
        scope_key: str | None,
        display_text: str | None = None,
        files: list[str] | None = None,
        chat: dict | None = None,
        session_id: str | None = None,
        meta: dict | None = None,
    ) -> dict:
        if command not in COMMANDS:
            raise ValueError("command must be ingest, query or lint")
        if command != "lint" and not message.strip():
            raise ValueError("message is required")
        if command == "ingest":
            if not scope_key:
                raise ValueError("ingest needs a scope")
            access.writable(scope_key)
        elif scope_key:
            access.scope(scope_key)
        self.check_quota(access)
        display = display_text or message
        if chat is not None:
            self.chats.add_user_turn(
                chat,
                display,
                {"mode": command, "scope": scope_key, "files": files or []},
            )
        job = self.jobs.create(
            principal=access.principal.to_doc(),
            org_id=access.org_id,
            command=command,
            scope=scope_key,
            message=message,
            display_text=display,
            files=files,
            chat_id=chat["_id"] if chat else None,
            session_id=session_id or (chat or {}).get("sessionId"),
            meta=meta,
        )
        self.record(
            access,
            "run.queued",
            scopes=[scope_key] if scope_key else [],
            job_id=job["_id"],
            detail={"command": command, "chatId": job["chatId"]},
        )
        return job

    def check_quota(self, access: OrgAccess) -> None:
        """Refuse a new run once the owner or the organization used up its
        runs for the rolling day (``max_runs_per_*_per_day``; 0 = no limit)."""
        s = self.settings
        since = self.audit.window_start(86400)
        if s.max_runs_per_owner_per_day and (
            self.audit.count_since("run.queued", since, owner=access.principal.owner)
            >= s.max_runs_per_owner_per_day
        ):
            raise QuotaExceededError(
                f"daily run quota reached ({s.max_runs_per_owner_per_day} per user)"
            )
        if s.max_runs_per_org_per_day and (
            self.audit.count_since("run.queued", since, org_id=access.org_id)
            >= s.max_runs_per_org_per_day
        ):
            raise QuotaExceededError(
                f"daily run quota reached ({s.max_runs_per_org_per_day} per "
                "organization)"
            )

    # ------------------------------------------------------------- chats

    def delete_chat(self, principal: Principal, chat_id: str) -> bool:
        """Delete a chat, its messages and its agent session homes."""
        chat = self.chats.delete(principal.owner, chat_id)
        if chat is None:
            return False
        delete_chat_home(self.settings, chat)
        self.audit.record(
            "chat.delete",
            org_id=chat.get("orgId"),
            user_id=principal.user_id,
            owner=principal.owner,
            target=chat_id,
        )
        return True

    # ------------------------------------------------------------ upload

    def upload(
        self, access: OrgAccess, scope_key: str, uploads: list[UploadFile]
    ) -> dict:
        """Convert and store uploads in a scope's raw directory.

        Raw sources are immutable once ingested, so a name that already exists
        gets a numeric suffix rather than being overwritten.
        """
        scope = access.writable(scope_key)
        self.ensure_scope(access, scope)
        raw_root = access.abs(scope.raw_rel)
        written: list[str] = []
        skipped: list[dict] = []
        for up in uploads:
            try:
                rel_dir = sanitize_upload_dir(up.rel_dir)
                name = sanitize_filename(up.name)
                converted = convert_file(name, up.staged)
                target_dir = (
                    resolve_contained(raw_root, rel_dir) if rel_dir else raw_root
                )
                if any(
                    is_within(target_dir, access.abs(r))
                    for r in scope.nested_rels("raw")
                ):
                    raise PathRefused(
                        "cannot upload into a sub-project from its parent"
                    )
                dest = _unique(target_dir / converted.name)
                write_bytes(dest, converted.content)
                if converted.asset:
                    write_bytes(
                        _unique(target_dir / "assets" / converted.asset),
                        up.staged.read_bytes(),
                    )
                written.append(dest.relative_to(access.root).as_posix())
            except (PathRefused, OSError) as e:
                skipped.append({"name": up.name, "why": str(e)})
        return {"written": written, "skipped": skipped}

    # -------------------------------------------------------- promotions

    def promotions(self, access: OrgAccess) -> list[dict]:
        out = []
        for s in access.scopes:
            if s.key == ORG_KEY:
                continue
            path = access.abs(s.wiki_rel) / "promotions.md"
            if path.is_symlink() or not path.is_file():
                continue
            for p in parse_promotions(
                path.read_text(encoding="utf-8", errors="replace")
            ):
                out.append({**p.to_dict(), "scope": s.key, "scope_label": s.label})
        return out

    def decide_promotion(
        self, access: OrgAccess, scope_key: str, promo_id: str, decision: str
    ) -> dict:
        """Approve (ingest the fact into the org room) or reject a proposal.

        Only someone who can write the org room may decide. The reviewer must
        also be able to read the proposing scope, which ``access.scope``
        enforces, so a decision never reveals a proposal to someone outside it.
        """
        if decision not in ("approve", "reject"):
            raise ValueError("decision must be approve or reject")
        org = access.writable(ORG_KEY)
        scope = access.scope(scope_key)
        path = access.abs(scope.wiki_rel) / "promotions.md"
        status = "approved" if decision == "approve" else "rejected"
        # Read, check and write under the scope lease, so two reviewers cannot
        # both act on one proposal and a concurrent ingest's new proposals are
        # not overwritten by a stale copy. The org-room ingest is queued only
        # after the decision is durably recorded.
        with self.lease(access, scope, "promotion"):
            if path.is_symlink() or not path.is_file():
                raise KeyError(promo_id)
            text = path.read_text(encoding="utf-8")
            promo = next((p for p in parse_promotions(text) if p.id == promo_id), None)
            if promo is None:
                raise KeyError(promo_id)
            if promo.status != "proposed":
                raise ValueError(f"already {promo.status}")
            path.write_text(
                set_promotion_status(text, promo_id, status), encoding="utf-8"
            )
            self.commit(
                access, scope, f"[{_today()}] promotion | {status}: {promo.fact[:60]}"
            )
        job = None
        if decision == "approve":
            self.ensure_scope(access, org)
            job = self.enqueue(
                access,
                command="ingest",
                scope_key=ORG_KEY,
                message=(
                    "An org-wide fact was approved for the org room. File it as an "
                    "OKF concept (or update the existing one).\n\n"
                    f"Fact: {promo.fact}\nSource: {promo.source}\n"
                    f"Rationale: {promo.rationale}\nProposed in scope: {scope.label}"
                ),
                display_text=f"Promote to org room: {promo.fact[:80]}",
                meta={"promotion": {"scope": scope_key, "id": promo_id}},
            )
        logger.info(
            "promotion %s in %s: %s",
            sanitize_for_log(promo_id),
            sanitize_for_log(scope_key),
            status,
        )
        return {"status": status, "job_id": job["_id"] if job else None}


def _unique(path: Path) -> Path:
    if not path.exists():
        return path
    stem, suffix = path.name, ""
    if "." in path.name:
        stem, _, ext = path.name.partition(".")
        suffix = "." + ext
    n = 2
    while True:
        candidate = path.with_name(f"{stem}-{n}{suffix}")
        if not candidate.exists():
            return candidate
        n += 1


def staging_dir() -> Path:
    return Path(tempfile.mkdtemp(prefix="selfmemory-upload-"))


__all__ += ["AccessDenied", "staging_dir"]
