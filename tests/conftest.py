"""Shared fixtures for the wiki tests.

The server package reads Ory and Mongo settings at import time. Tests never
talk to either -- auth is overridden and Mongo is ``mongomock`` -- so harmless
placeholders are set before anything under ``server`` is imported.
"""

from __future__ import annotations

import os

for _k, _v in {
    "MONGODB_URI": "mongodb://127.0.0.1:1/selfmemory_test",
    "KRATOS_PUBLIC_URL": "http://127.0.0.1:1",
    "KRATOS_ADMIN_URL": "http://127.0.0.1:1",
    "HYDRA_PUBLIC_URL": "http://127.0.0.1:1",
    "HYDRA_ADMIN_URL": "http://127.0.0.1:1",
    "ENVIRONMENT": "development",
    "SELFMEMORY_WORKER": "off",
}.items():
    os.environ.setdefault(_k, _v)

import mongomock  # noqa: E402
import pytest  # noqa: E402
from bson import ObjectId  # noqa: E402

from selfmemory.wiki_settings import load_settings  # noqa: E402


@pytest.fixture
def settings(tmp_path):
    return load_settings(
        {
            "SELFMEMORY_DATA_ROOT": str(tmp_path / "data"),
            "SELFMEMORY_AGENT_BIN": "/bin/false",
            "ENVIRONMENT": "development",
        }
    )


class World:
    """A small org: owner, a member with mixed permissions, an outsider.

    Projects: ``alpha`` (member reads+writes), ``beta`` (member has nothing),
    and ``alpha-child``, a sub-project of alpha the member can only read.
    """

    def __init__(self, db):
        self.db = db
        self.owner = "kratos-owner"
        self.member = "kratos-member"
        self.outsider = "kratos-outsider"
        for uid in (self.owner, self.member, self.outsider):
            db.users.insert_one({"_id": uid, "email": f"{uid}@example.com"})
        self.org = ObjectId()
        db.organizations.insert_one(
            {"_id": self.org, "name": "Acme", "ownerId": self.owner}
        )
        db.organization_members.insert_one(
            {
                "organizationId": self.org,
                "userId": self.member,
                "role": "member",
                "status": "active",
            }
        )
        self.alpha = ObjectId()
        self.beta = ObjectId()
        self.child = ObjectId()
        db.projects.insert_many(
            [
                {
                    "_id": self.alpha,
                    "name": "Alpha",
                    "organizationId": self.org,
                    "ownerId": self.owner,
                },
                {
                    "_id": self.beta,
                    "name": "Beta",
                    "organizationId": self.org,
                    "ownerId": self.owner,
                },
                {
                    "_id": self.child,
                    "name": "Alpha Child",
                    "organizationId": self.org,
                    "ownerId": self.owner,
                    "parentProjectId": self.alpha,
                },
            ]
        )
        db.project_members.insert_many(
            [
                {
                    "projectId": self.alpha,
                    "userId": self.member,
                    "permissions": {"canRead": True, "canWrite": True},
                },
                {
                    "projectId": self.child,
                    "userId": self.member,
                    "permissions": {"canRead": True, "canWrite": False},
                },
            ]
        )

    @property
    def org_id(self) -> str:
        return str(self.org)


@pytest.fixture
def db():
    return mongomock.MongoClient()["selfmemory_test"]


@pytest.fixture
def world(db):
    return World(db)
