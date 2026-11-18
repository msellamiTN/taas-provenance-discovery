"""Real E2E tests for the token broker — dev-mode issuer, opaque tokens."""
from __future__ import annotations

import os
import time

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("jwt")


@pytest.fixture
def broker_env(tmp_path, monkeypatch):
    monkeypatch.setenv("TAAS_BROKER_DEV_SECRET", "test-secret-key-padded-to-32-bytes-long")
    monkeypatch.setenv("TAAS_BROKER_TOKEN_STORE", str(tmp_path / "tokens.sqlite3"))
    monkeypatch.delenv("TAAS_BROKER_ISSUER", raising=False)
    monkeypatch.delenv("TAAS_BROKER_JWKS_URI", raising=False)
    from taas.broker import api
    return TestClient(api.app)


def test_dev_mint_and_exchange(broker_env):
    mint = broker_env.post("/dev/issue", data={
        "subject": "agent-1",
        "scope": "mcp:tools:list:server:taas-demo"})
    assert mint.status_code == 200
    subject = mint.json()["subject_token"]

    exchange = broker_env.post("/token", data={
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "subject_token": subject,
        "requested_scope": "mcp:tools:list:server:taas-demo"})
    assert exchange.status_code == 200
    issued = exchange.json()
    assert issued["token_type"] == "Bearer"
    assert issued["expires_in"] <= 300
    # opaque — must NOT be a decodable JWT carrying claims
    assert issued["access_token"].count(".") == 0

    intro = broker_env.post("/introspect",
                            data={"token": issued["access_token"]})
    assert intro.status_code == 200 and intro.json()["active"] is True
    assert intro.json()["sub"] == "agent-1"


def test_downscope_rejects_widening(broker_env):
    mint = broker_env.post("/dev/issue", data={
        "subject": "agent-1", "scope": "mcp:tools:list:server:taas-demo"})
    subject = mint.json()["subject_token"]
    # request a different server than the grant — must fail
    exchange = broker_env.post("/token", data={
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "subject_token": subject,
        "requested_scope": "mcp:tools:list:server:other-server"})
    assert exchange.status_code == 403


def test_invalid_subject_token(broker_env):
    exchange = broker_env.post("/token", data={
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "subject_token": "not-a-jwt",
        "requested_scope": "mcp:tools:list:server:taas-demo"})
    assert exchange.status_code == 401


def test_wrong_grant_type(broker_env):
    exchange = broker_env.post("/token", data={
        "grant_type": "password", "subject_token": "x",
        "requested_scope": "mcp:tools:list:server:taas-demo"})
    assert exchange.status_code == 400


def test_expired_token_inactive(broker_env, tmp_path, monkeypatch):
    mint = broker_env.post("/dev/issue", data={
        "subject": "agent-1", "scope": "mcp:tools:list:server:taas-demo",
        "ttl_seconds": -1})
    subject = mint.json()["subject_token"]
    exchange = broker_env.post("/token", data={
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "subject_token": subject,
        "requested_scope": "mcp:tools:list:server:taas-demo"})
    # subject already expired → rejected at validation
    assert exchange.status_code == 401


def test_introspect_unknown(broker_env):
    intro = broker_env.post("/introspect", data={"token": "bogus"})
    assert intro.json() == {"active": False}
