from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

import taas.studio.api as studio_api
from taas.studio import audit_ledger


@pytest.fixture(autouse=True)
def env(monkeypatch, tmp_path):
    db = tmp_path / "audit.sqlite3"
    monkeypatch.setenv("TAAS_AUDIT_LEDGER_PATH", str(db))
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "audit-token")
    yield


def test_chain_links_events(monkeypatch):
    a = audit_ledger.append_event("evidence", {"tool": "s::t"}, {"k": 1})
    b = audit_ledger.append_event("signature", {"skill": "x@1"}, {"k": 2})
    assert a["prev_hash"] == "0" * 64
    assert b["prev_hash"] == a["event_hash"]
    assert b["event_hash"] != a["event_hash"]


def test_verify_valid_chain():
    for i in range(5):
        audit_ledger.append_event("discovery_run", {"run_id": str(i)}, {"i": i})
    result = audit_ledger.verify_chain()
    assert result["chain_valid"] is True
    assert result["event_count"] == 5
    assert result["first_divergence"] is None
    assert result["execution_performed"] is False


def test_verify_detects_tampering():
    for i in range(3):
        audit_ledger.append_event("evidence", {"i": i}, {})
    db = audit_ledger._database_path()
    conn = sqlite3.connect(db)
    conn.execute("UPDATE audit_events SET payload_json = ? WHERE seq = 2",
                 ('{"forged": true}',))
    conn.commit(); conn.close()
    result = audit_ledger.verify_chain()
    assert result["chain_valid"] is False
    assert result["first_divergence"]["seq"] == 2


def test_unknown_event_type_rejected():
    with pytest.raises(ValueError):
        audit_ledger.append_event("execution", {}, {})


def test_audit_endpoints():
    client = TestClient(studio_api.app)
    headers = {"Authorization": "Bearer audit-token"}
    audit_ledger.append_event("policy_verdict", {"agent": "a@1"}, {"v": "allow"})
    verify = client.get("/api/v1/audit/verify", headers=headers)
    assert verify.status_code == 200
    assert verify.json()["schema"] == "taas.audit-verify/v1"
    assert verify.json()["chain_valid"] is True
    events = client.get("/api/v1/audit/events?event_type=policy_verdict", headers=headers)
    assert events.status_code == 200
    assert events.json()["count"] == 1
    unauth = client.get("/api/v1/audit/verify")
    assert unauth.status_code in (401, 403)
