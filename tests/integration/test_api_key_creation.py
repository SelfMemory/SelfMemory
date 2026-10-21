"""API key creation is only allowed from an interactive session."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from selfmemory.features.api_keys.interfaces import http as api_keys_http
from selfmemory.platform import dependencies
from selfmemory.platform.dependencies import AuthContext, authenticate_api_key


@pytest.fixture
def client_for(db, world, monkeypatch):
    for module in (dependencies, api_keys_http):
        monkeypatch.setattr(module, "mongo_db", db)

    def make(ctx):
        app = FastAPI()
        app.include_router(api_keys_http.router, prefix="/api/v1")
        app.dependency_overrides[authenticate_api_key] = lambda: ctx
        return TestClient(app)

    return make


@pytest.mark.parametrize("auth_type", ["api_key", "oauth"])
def test_token_credentials_cannot_create_keys(client_for, world, db, auth_type):
    ctx = AuthContext(
        user_id=world.owner, project_id=str(world.alpha), auth_type=auth_type
    )
    before = db.api_keys.count_documents({})
    r = client_for(ctx).post(
        f"/api/v1/projects/{world.beta}/api-keys", json={"name": "k"}
    )
    assert r.status_code == 403
    assert db.api_keys.count_documents({}) == before


def test_session_can_create_key(client_for, world, db):
    ctx = AuthContext(user_id=world.owner, auth_type="session")
    r = client_for(ctx).post(
        f"/api/v1/projects/{world.alpha}/api-keys", json={"name": "k"}
    )
    assert r.status_code == 200, r.text
    assert db.api_keys.count_documents({"projectId": world.alpha}) == 1
