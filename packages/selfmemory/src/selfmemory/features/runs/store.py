"""Durable state for agent runs: jobs, their event streams, leases and chats.

All of it lives in MongoDB so any number of API processes and workers can
share it. Every mutation a worker makes is guarded on ``workerId`` and
``status: running``, so a worker that lost a job (its heartbeat went stale and
the reaper handed the job to someone else) can no longer write to it.
"""

from __future__ import annotations

import logging
import re
import secrets
import time
from collections import Counter
from datetime import UTC, datetime, timedelta

from pymongo import ASCENDING, DESCENDING, ReturnDocument
from pymongo.errors import DuplicateKeyError, OperationFailure

__all__ = [
    "JOBS",
    "EVENTS",
    "LEASES",
    "CHATS",
    "MESSAGES",
    "ensure_indexes",
    "JobStore",
    "ChatStore",
    "ScopeLease",
    "ScopeBusyError",
    "now",
]

logger = logging.getLogger(__name__)

JOBS = "wiki_jobs"
EVENTS = "wiki_job_events"
LEASES = "wiki_leases"
CHATS = "wiki_chats"
MESSAGES = "wiki_chat_messages"

MAX_EVENTS_PER_JOB = 20_000
STALE_HEARTBEAT_S = 60
MAX_ATTEMPTS = 3
# Oldest queued jobs a claim looks at when the ones in front are held back by
# a fair-share cap or a busy chat.
CLAIM_SCAN = 50
TERMINAL = ("done", "failed", "cancelled")
_JOB_ID = re.compile(r"^[0-9a-f]{32}$")


def now() -> datetime:
    return datetime.now(UTC)


def ensure_indexes(db) -> None:
    db[JOBS].create_index([("status", ASCENDING), ("createdAt", ASCENDING)])
    db[JOBS].create_index([("status", ASCENDING), ("heartbeatAt", ASCENDING)])
    db[JOBS].create_index([("chatId", ASCENDING), ("status", ASCENDING)])
    db[JOBS].create_index([("owner", ASCENDING), ("createdAt", DESCENDING)])
    # One opencode session takes one turn at a time: at most one running job
    # per chat, enforced by Mongo so two workers cannot both claim one.
    try:
        db[JOBS].create_index(
            [("chatId", ASCENDING)],
            name="one_running_per_chat",
            unique=True,
            partialFilterExpression={
                "status": "running",
                "chatId": {"$type": "string"},
            },
        )
    except OperationFailure:
        # two turns of one chat were already running (from before this rule);
        # claim() still checks, and the next start creates the index
        logger.warning("one_running_per_chat index not created yet")
    db[EVENTS].create_index([("jobId", ASCENDING), ("seq", ASCENDING)], unique=True)
    db[LEASES].create_index("expiresAt", expireAfterSeconds=0)
    db[CHATS].create_index(
        [("owner", ASCENDING), ("orgId", ASCENDING), ("updatedAt", DESCENDING)]
    )
    db[CHATS].create_index([("kind", ASCENDING), ("updatedAt", ASCENDING)])
    db[MESSAGES].create_index([("chatId", ASCENDING), ("at", ASCENDING)])


def valid_job_id(job_id: str | None) -> bool:
    return bool(job_id) and bool(_JOB_ID.match(job_id))


class JobStore:
    def __init__(self, db):
        self.jobs = db[JOBS]
        self.events = db[EVENTS]

    def create(
        self,
        *,
        principal: dict,
        org_id: str,
        command: str,
        scope: str | None,
        message: str,
        display_text: str,
        files: list[str] | None = None,
        chat_id: str | None = None,
        session_id: str | None = None,
        meta: dict | None = None,
    ) -> dict:
        job = {
            "_id": secrets.token_hex(16),
            "userId": principal["userId"],
            "owner": principal["owner"],
            "principal": principal,
            "orgId": org_id,
            "chatId": chat_id,
            "command": command,
            "scope": scope,
            "message": message,
            "displayText": display_text,
            "files": files or [],
            "sessionId": session_id,
            "meta": meta or {},
            "status": "queued",
            "createdAt": now(),
            "startedAt": None,
            "finishedAt": None,
            "heartbeatAt": None,
            "workerId": None,
            "attempts": 0,
            "seq": 0,
            "notBefore": None,
            "cancelRequestedAt": None,
            "result": None,
        }
        self.jobs.insert_one(job)
        return job

    def claim(
        self,
        worker_id: str,
        *,
        max_per_owner: int | None = None,
        max_per_org: int | None = None,
    ) -> dict | None:
        """Claim the oldest job that may run now.

        A job is held back while its chat already has a running turn (turns of
        one chat run in arrival order), or while its owner or organization is
        at its fair-share cap across all workers. The caps are checked against
        a snapshot, so racing workers can overshoot them by one each; the
        one-turn-per-chat rule is exact (a unique index).
        """
        t = now()
        ready = {
            "status": "queued",
            "$or": [{"notBefore": None}, {"notBefore": {"$lte": t}}],
        }
        owners: Counter = Counter()
        orgs: Counter = Counter()
        busy_chats: set[str] = set()
        for r in self.jobs.find(
            {"status": "running"}, {"owner": 1, "orgId": 1, "chatId": 1}
        ):
            owners[r.get("owner")] += 1
            orgs[r.get("orgId")] += 1
            if r.get("chatId"):
                busy_chats.add(r["chatId"])
        candidates = (
            self.jobs.find(ready, {"owner": 1, "orgId": 1, "chatId": 1})
            .sort("createdAt", ASCENDING)
            .limit(CLAIM_SCAN)
        )
        for c in candidates:
            chat_id = c.get("chatId")
            if chat_id:
                if chat_id in busy_chats:
                    continue
                # later turns of this chat wait behind this one either way
                busy_chats.add(chat_id)
            if max_per_owner is not None and owners[c.get("owner")] >= max_per_owner:
                continue
            if max_per_org is not None and orgs[c.get("orgId")] >= max_per_org:
                continue
            try:
                job = self.jobs.find_one_and_update(
                    {"_id": c["_id"], **ready},
                    {
                        "$set": {
                            "status": "running",
                            "workerId": worker_id,
                            "startedAt": t,
                            "heartbeatAt": t,
                        },
                        "$inc": {"attempts": 1},
                    },
                    return_document=ReturnDocument.AFTER,
                )
            except DuplicateKeyError:
                continue  # another worker started a turn of this chat
            if job:
                return job
        return None

    def heartbeat(self, job_id: str, worker_id: str) -> dict | None:
        """``None`` means this worker no longer owns the job and must stop."""
        return self.jobs.find_one_and_update(
            {"_id": job_id, "workerId": worker_id, "status": "running"},
            {"$set": {"heartbeatAt": now()}},
            return_document=ReturnDocument.AFTER,
        )

    def append(self, job_id: str, worker_id: str, events: list[dict]) -> int | None:
        """Append events with consecutive sequence numbers. Readers resume by seq."""
        if not events:
            return None
        bumped = self.jobs.find_one_and_update(
            {"_id": job_id, "workerId": worker_id, "status": "running"},
            {"$inc": {"seq": len(events)}},
            return_document=ReturnDocument.AFTER,
        )
        if not bumped:
            return None
        first = bumped["seq"] - len(events) + 1
        t = now()
        self.events.insert_many(
            [
                {"jobId": job_id, "seq": first + i, "at": t, "event": e}
                for i, e in enumerate(events)
            ]
        )
        return bumped["seq"]

    def read_events(self, job_id: str, after: int, limit: int = 500) -> list[dict]:
        rows = (
            self.events.find({"jobId": job_id, "seq": {"$gt": after}})
            .sort("seq", ASCENDING)
            .limit(limit)
        )
        return [{"seq": r["seq"], "event": r["event"]} for r in rows]

    def requeue(self, job_id: str, worker_id: str, delay_s: float = 5.0) -> bool:
        """Hand a claimed job back without counting the attempt (scope was busy).

        ``notBefore`` keeps the same job from being reclaimed at once, since
        claiming is oldest-first and it is the oldest job in the queue.
        """
        res = self.jobs.update_one(
            {"_id": job_id, "workerId": worker_id, "status": "running"},
            {
                "$set": {
                    "status": "queued",
                    "workerId": None,
                    "heartbeatAt": None,
                    "notBefore": now() + timedelta(seconds=delay_s),
                },
                "$inc": {"attempts": -1},
            },
        )
        return res.modified_count == 1

    def finish(self, job_id: str, worker_id: str, status: str, result: dict) -> bool:
        res = self.jobs.update_one(
            {"_id": job_id, "workerId": worker_id, "status": "running"},
            {
                "$set": {
                    "status": status,
                    "result": result,
                    "finishedAt": now(),
                    "heartbeatAt": now(),
                }
            },
        )
        return res.modified_count == 1

    def get(self, job_id: str) -> dict | None:
        return self.jobs.find_one({"_id": job_id}) if valid_job_id(job_id) else None

    def owned(self, owner: str, job_id: str) -> dict | None:
        if not valid_job_id(job_id):
            return None
        return self.jobs.find_one({"_id": job_id, "owner": owner})

    def request_cancel(self, owner: str, job_id: str) -> dict | None:
        job = self.owned(owner, job_id)
        if not job:
            return None
        if job["status"] == "queued":
            cancelled = self.jobs.find_one_and_update(
                {"_id": job_id, "owner": owner, "status": "queued"},
                {
                    "$set": {
                        "status": "cancelled",
                        "cancelRequestedAt": now(),
                        "finishedAt": now(),
                    }
                },
                return_document=ReturnDocument.AFTER,
            )
            if cancelled:
                return cancelled
        flagged = self.jobs.find_one_and_update(
            {"_id": job_id, "owner": owner, "status": "running"},
            {"$set": {"cancelRequestedAt": now()}},
            return_document=ReturnDocument.AFTER,
        )
        return flagged or self.owned(owner, job_id)

    def active_for_chat(self, owner: str, chat_id: str) -> dict | None:
        return self.jobs.find_one(
            {
                "owner": owner,
                "chatId": chat_id,
                "status": {"$in": ["queued", "running"]},
            },
            sort=[("createdAt", DESCENDING)],
        )

    def recent(
        self, owner: str, org_id: str | None = None, limit: int = 20
    ) -> list[dict]:
        q: dict = {"owner": owner}
        if org_id:
            q["orgId"] = org_id
        return list(self.jobs.find(q).sort("createdAt", DESCENDING).limit(limit))

    def reap_stale(
        self, at: datetime | None = None, stale_s: int = STALE_HEARTBEAT_S
    ) -> dict:
        """Requeue running jobs whose worker went silent; fail them after 3 tries."""
        at = at or now()
        cutoff = at - timedelta(seconds=stale_s)
        requeued = failed = 0
        for job in self.jobs.find(
            {"status": "running", "heartbeatAt": {"$lt": cutoff}}
        ):
            guard = {
                "_id": job["_id"],
                "workerId": job["workerId"],
                "status": "running",
            }
            if job.get("attempts", 0) >= MAX_ATTEMPTS:
                res = self.jobs.update_one(
                    guard,
                    {
                        "$set": {
                            "status": "failed",
                            "finishedAt": at,
                            "result": {
                                "code": 1,
                                "answer": "",
                                "error": "the worker running this job stopped "
                                f"responding ({job.get('attempts')} attempts)",
                                "tools": [],
                                "tokens": {},
                                "cost": 0,
                            },
                        }
                    },
                )
                failed += res.modified_count
            else:
                res = self.jobs.update_one(
                    guard,
                    {
                        "$set": {
                            "status": "queued",
                            "workerId": None,
                            "heartbeatAt": None,
                        }
                    },
                )
                requeued += res.modified_count
        return {"requeued": requeued, "failed": failed}

    def prune_finished(self, older_than: datetime) -> int:
        ids = [
            j["_id"]
            for j in self.jobs.find(
                {"status": {"$in": list(TERMINAL)}, "finishedAt": {"$lt": older_than}},
                {"_id": 1},
            )
        ]
        if ids:
            self.events.delete_many({"jobId": {"$in": ids}})
            self.jobs.delete_many({"_id": {"$in": ids}})
        return len(ids)


def job_summary(job: dict) -> dict:
    return {
        "id": job["_id"],
        "org_id": job.get("orgId"),
        "status": job["status"],
        "command": job["command"],
        "scope": job.get("scope"),
        "chat_id": job.get("chatId"),
        "display_text": job.get("displayText"),
        "created_at": job.get("createdAt"),
        "started_at": job.get("startedAt"),
        "finished_at": job.get("finishedAt"),
        "attempts": job.get("attempts", 0),
        "seq": job.get("seq", 0),
    }


# ---------------------------------------------------------------------------
# Chats
# ---------------------------------------------------------------------------


class ChatStore:
    def __init__(self, db):
        self.chats = db[CHATS]
        self.messages = db[MESSAGES]

    def create(
        self,
        owner: str,
        org_id: str,
        scope: str | None,
        user_id: str | None = None,
        kind: str = "app",
    ) -> dict:
        """A conversation. ``kind`` is "app" (the chat screen, kept until the
        user deletes it) or "a2a" (an agent's context, expired when idle)."""
        t = now()
        chat = {
            "_id": secrets.token_hex(12),
            "kind": kind,
            "owner": owner,
            "userId": user_id or owner.split("#", 1)[0],
            "orgId": org_id,
            "scope": scope or "",
            "sessionId": None,
            # which mount set the session was built on; see worker.scope_digest
            "sessionScope": None,
            "title": "New chat",
            "createdAt": t,
            "updatedAt": t,
        }
        self.chats.insert_one(chat)
        return chat

    def owned(
        self, owner: str, chat_id: str | None, org_id: str | None = None
    ) -> dict | None:
        if not chat_id or not isinstance(chat_id, str) or len(chat_id) > 64:
            return None
        q = {"_id": chat_id, "owner": owner}
        if org_id is not None:
            q["orgId"] = org_id
        return self.chats.find_one(q)

    def list(self, owner: str, org_id: str, limit: int = 60) -> list[dict]:
        return list(
            self.chats.find({"owner": owner, "orgId": org_id})
            .sort("updatedAt", DESCENDING)
            .limit(limit)
        )

    def messages_for(self, chat_id: str) -> list[dict]:
        return list(self.messages.find({"chatId": chat_id}).sort("at", ASCENDING))

    def add_user_turn(self, chat: dict, text: str, meta: dict) -> None:
        t = now()
        self.messages.insert_one(
            {"chatId": chat["_id"], "role": "user", "text": text, "meta": meta, "at": t}
        )
        update: dict = {"updatedAt": t}
        if chat.get("title") == "New chat" and text.strip():
            update["title"] = text.strip().splitlines()[0][:60]
        self.chats.update_one({"_id": chat["_id"]}, {"$set": update})

    def add_assistant_turn(
        self,
        chat_id: str,
        text: str,
        meta: dict,
        session_id: str | None,
        session_scope: str | None = None,
    ) -> None:
        t = now()
        self.messages.insert_one(
            {
                "chatId": chat_id,
                "role": "assistant",
                "text": text,
                "meta": meta,
                "at": t,
            }
        )
        update: dict = {"updatedAt": t}
        if session_id:
            update["sessionId"] = session_id
            update["sessionScope"] = session_scope
        self.chats.update_one({"_id": chat_id}, {"$set": update})

    def prune_idle(self, kind: str, older_than: datetime) -> int:
        """Delete chats of ``kind`` untouched since ``older_than``, with their
        messages. Chats with a queued or running turn are left alone."""
        ids = [
            c["_id"]
            for c in self.chats.find(
                {"kind": kind, "updatedAt": {"$lt": older_than}}, {"_id": 1}
            )
        ]
        if not ids:
            return 0
        active = {
            j["chatId"]
            for j in self.chats.database[JOBS].find(
                {"chatId": {"$in": ids}, "status": {"$in": ["queued", "running"]}},
                {"chatId": 1},
            )
        }
        ids = [i for i in ids if i not in active]
        if ids:
            self.messages.delete_many({"chatId": {"$in": ids}})
            self.chats.delete_many({"_id": {"$in": ids}})
        return len(ids)

    def delete(self, owner: str, chat_id: str) -> bool:
        chat = self.owned(owner, chat_id)
        if not chat:
            return False
        self.messages.delete_many({"chatId": chat_id})
        self.chats.delete_one({"_id": chat_id})
        return True


# ---------------------------------------------------------------------------
# Scope lease
#
# Writers to one scope (an ingest's commit, a manual edit) are serialised by a
# Mongo document whose _id is the scope directory. A module-level lock would
# only serialise one process; the lease serialises every API process and
# worker. It carries a TTL renewed by a heartbeat, so a killed holder releases
# by expiry instead of wedging the scope, and a hard deadline so no holder can
# keep it forever.
# ---------------------------------------------------------------------------


class ScopeBusyError(RuntimeError):
    pass


class ScopeLease:
    def __init__(
        self,
        db,
        scope: str,
        owner: str,
        ttl_s: float = 30.0,
        wait_s: float = 30.0,
        max_hold_s: float = 600.0,
    ):
        self.leases = db[LEASES]
        self.scope = scope
        self.owner = f"{owner}#{secrets.token_hex(4)}"
        self.ttl_s = ttl_s
        self.wait_s = wait_s
        self.max_hold_s = max_hold_s

    def _doc(self, t: datetime) -> dict:
        return {
            "_id": self.scope,
            "owner": self.owner,
            "acquiredAt": t,
            "expiresAt": t + timedelta(seconds=self.ttl_s),
            "deadlineAt": t + timedelta(seconds=self.max_hold_s),
        }

    def acquire(self) -> None:
        give_up = time.monotonic() + self.wait_s
        while True:
            t = now()
            try:
                self.leases.insert_one(self._doc(t))
                return
            except DuplicateKeyError:
                pass
            # take over a lease whose holder stopped renewing it
            taken = self.leases.find_one_and_update(
                {"_id": self.scope, "expiresAt": {"$lt": t}},
                {"$set": self._doc(t)},
            )
            if taken:
                return
            if time.monotonic() >= give_up:
                raise ScopeBusyError(f"scope is busy: {self.scope}")
            time.sleep(0.25)

    def renew(self) -> bool:
        """Extend the TTL. False once the lease is lost or past its deadline."""
        t = now()
        res = self.leases.update_one(
            {"_id": self.scope, "owner": self.owner, "deadlineAt": {"$gt": t}},
            {"$set": {"expiresAt": t + timedelta(seconds=self.ttl_s)}},
        )
        return res.modified_count == 1

    def release(self) -> None:
        self.leases.delete_one({"_id": self.scope, "owner": self.owner})

    def __enter__(self) -> ScopeLease:
        self.acquire()
        return self

    def __exit__(self, *exc) -> None:
        self.release()
