"""Append-only audit log: who ran, read or wrote which scope, and when.

Records hold identifiers and scope names, never file content, so the log can
be kept for as long as org policy asks without becoming a copy of the data.
The class exposes no update or delete; old records leave only through the
optional TTL index (``audit_retention_days``).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from pymongo import ASCENDING, DESCENDING
from pymongo.errors import OperationFailure, PyMongoError

__all__ = ["AUDIT", "AuditLog", "ensure_audit_indexes"]

logger = logging.getLogger(__name__)

AUDIT = "audit_log"
_TTL_INDEX = "audit_ttl"


def ensure_audit_indexes(db, retention_days: int = 0) -> None:
    col = db[AUDIT]
    col.create_index([("orgId", ASCENDING), ("at", DESCENDING)])
    col.create_index([("orgId", ASCENDING), ("action", ASCENDING), ("at", ASCENDING)])
    col.create_index([("owner", ASCENDING), ("action", ASCENDING), ("at", ASCENDING)])
    try:
        existing = {i["name"]: i for i in col.list_indexes()}
        ttl = existing.get(_TTL_INDEX)
        want = retention_days * 86400 if retention_days > 0 else None
        if ttl is not None and ttl.get("expireAfterSeconds") != want:
            col.drop_index(_TTL_INDEX)
            ttl = None
        if want and ttl is None:
            col.create_index("at", name=_TTL_INDEX, expireAfterSeconds=want)
    except OperationFailure:
        logger.warning("audit retention index not updated")


class AuditLog:
    def __init__(self, db):
        self.col = db[AUDIT]

    def record(
        self,
        action: str,
        *,
        org_id: str | None,
        user_id: str | None,
        owner: str | None = None,
        scopes: list[str] | None = None,
        target: str | None = None,
        job_id: str | None = None,
        detail: dict | None = None,
    ) -> None:
        """Append one record. Never raises: a broken audit write must not fail
        the request it describes, but it is logged loudly."""
        doc = {
            "at": datetime.now(UTC),
            "action": action,
            "orgId": org_id,
            "userId": user_id,
            "owner": owner or user_id,
            "scopes": scopes or [],
            "target": target,
            "jobId": job_id,
            "detail": detail or {},
        }
        try:
            self.col.insert_one(doc)
        except PyMongoError:
            logger.exception("audit write failed for %s", action)

    def recent(
        self, org_id: str, limit: int = 100, before: datetime | None = None
    ) -> list[dict]:
        q: dict = {"orgId": org_id}
        if before is not None:
            q["at"] = {"$lt": before}
        return list(self.col.find(q).sort("at", DESCENDING).limit(limit))
