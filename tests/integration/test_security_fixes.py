"""Regression tests for the Hydra proxy, API key listing and key revocation."""

from __future__ import annotations

import json

import httpx
import pytest
from bson import ObjectId
from fastapi import FastAPI
from fastapi.testclient import TestClient

from selfmemory.features.api_keys.interfaces import http as api_keys_http
from selfmemory.platform import dependencies
from selfmemory.platform.dependencies import AuthContext, authenticate_api_key
from selfmemory.platform.ory import hydra_proxy
from selfmemory.platform.permissions import user_id_variants


@pytest.fixture
def patched_db(db, world, monkeypatch):
    for module in (dependencies, hydra_proxy, api_keys_http):
        monkeypatch.setattr(module, "mongo_db", db)
    return world


class FakeHydra:
    """Records admin API calls and answers with canned consent data."""

    def __init__(self, subject):
        self.subject = subject
        self.calls = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        self.calls.append((request.method, request.url.path, body))
        if request.url.path.endswith("/requests/consent"):
            return httpx.Response(
                200,
                json={
                    "subject": self.subject,
                    "requested_scope": ["openid", "memories:read"],
                    "client": {"client_id": "c1"},
                },
            )
        return httpx.Response(200, json={"redirect_to": "https://example/cb"})

    def last_put(self):
        return next(c for c in reversed(self.calls) if c[0] == "PUT")


def make_client(monkeypatch, hydra, ctx):
    real = httpx.AsyncClient
    monkeypatch.setattr(
        hydra_proxy.httpx,
        "AsyncClient",
        lambda **kw: real(transport=httpx.MockTransport(hydra.handler), **kw),
    )
    app = FastAPI()
    app.include_router(hydra_proxy.router)
    app.include_router(api_keys_http.router, prefix="/api/v1")
    app.dependency_overrides[authenticate_api_key] = lambda: ctx
    return TestClient(app)


def test_login_accept_uses_session_user_not_body(patched_db, monkeypatch):
    hydra = FakeHydra(patched_db.member)
    c = make_client(monkeypatch, hydra, AuthContext(user_id=patched_db.member))
    r = c.put(
        "/internal/hydra/login/accept",
        json={"login_challenge": "lc", "subject": patched_db.owner},
    )
    assert r.status_code == 200
    assert hydra.last_put()[2]["subject"] == patched_db.member


def test_login_accept_refuses_non_session_auth(patched_db, monkeypatch):
    hydra = FakeHydra(patched_db.member)
    ctx = AuthContext(user_id=patched_db.member, auth_type="api_key")
    c = make_client(monkeypatch, hydra, ctx)
    r = c.put("/internal/hydra/login/accept", json={"login_challenge": "lc"})
    assert r.status_code == 403
    assert not hydra.calls


def test_login_accept_requires_auth(patched_db):
    app = FastAPI()
    app.include_router(hydra_proxy.router)
    r = TestClient(app).put(
        "/internal/hydra/login/accept", json={"login_challenge": "lc"}
    )
    assert r.status_code == 401


def test_consent_accept_rejects_other_users_challenge(patched_db, monkeypatch):
    hydra = FakeHydra(patched_db.owner)
    c = make_client(monkeypatch, hydra, AuthContext(user_id=patched_db.member))
    r = c.put(
        "/internal/hydra/consent/accept",
        json={"consent_challenge": "cc", "grant_scope": ["openid"]},
    )
    assert r.status_code == 403
    assert not any(m == "PUT" for m, *_ in hydra.calls)


def test_consent_accept_limits_scopes_and_builds_claims(patched_db, monkeypatch):
    w = patched_db
    hydra = FakeHydra(w.member)
    c = make_client(monkeypatch, hydra, AuthContext(user_id=w.member))
    r = c.put(
        "/internal/hydra/consent/accept",
        json={
            "consent_challenge": "cc",
            "grant_scope": ["openid", "memories:write", "admin:everything"],
            "project_id": str(w.alpha),
            "session": {"access_token": {"project_id": str(w.alpha), "role": "x"}},
        },
    )
    assert r.status_code == 200
    payload = hydra.last_put()[2]
    assert payload["grant_scope"] == ["openid", "memories:write"]
    assert payload["session"]["access_token"] == {
        "project_id": str(w.alpha),
        "organization_id": str(w.org),
    }


def test_consent_accept_refuses_unowned_project(patched_db, monkeypatch):
    w = patched_db
    hydra = FakeHydra(w.outsider)
    c = make_client(monkeypatch, hydra, AuthContext(user_id=w.outsider))
    r = c.put(
        "/internal/hydra/consent/accept",
        json={
            "consent_challenge": "cc",
            "grant_scope": ["openid"],
            "session": {"access_token": {"project_id": str(w.alpha)}},
        },
    )
    assert r.status_code == 403
    assert not any(m == "PUT" for m, *_ in hydra.calls)


def test_list_api_keys_never_returns_key_material(patched_db, db, monkeypatch):
    w = patched_db
    db.api_keys.insert_one(
        {
            "projectId": w.alpha,
            "userId": w.member,
            "isActive": True,
            "keyPrefix": "sk_im_abcd...",
            "encryptedKey": "ciphertext",
        }
    )
    c = make_client(monkeypatch, FakeHydra(w.member), AuthContext(user_id=w.member))
    r = c.get(f"/api/v1/projects/{w.alpha}/api-keys")
    assert r.status_code == 200
    (key,) = r.json()["api_keys"]
    assert "api_key" not in key
    assert key["key_prefix"] == "sk_im_abcd..."
    assert "ciphertext" not in r.text


def test_revocation_matches_every_user_id_format(db):
    oid = ObjectId()
    db.users.insert_one({"_id": oid, "kratosId": "kratos-legacy"})
    db.api_keys.insert_many(
        [
            {"userId": oid, "isActive": True},
            {"userId": str(oid), "isActive": True},
            {"userId": "kratos-legacy", "isActive": True},
            {"userId": "someone-else", "isActive": True},
        ]
    )
    db.api_keys.update_many(
        {"userId": {"$in": user_id_variants(db, oid)}},
        {"$set": {"isActive": False}},
    )
    still_active = [k["userId"] for k in db.api_keys.find({"isActive": True})]
    assert still_active == ["someone-else"]


def test_variants_resolve_from_kratos_id_too(db):
    oid = ObjectId()
    db.users.insert_one({"_id": oid, "kratosId": "kratos-legacy"})
    assert set(map(str, user_id_variants(db, "kratos-legacy"))) == {
        "kratos-legacy",
        str(oid),
    }
