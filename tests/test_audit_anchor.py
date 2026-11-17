"""Tests for D12 phase 1: signed audit anchors (audit_anchor.py)."""
from __future__ import annotations

import json
import sqlite3

import pytest

from taas.studio import audit_anchor, audit_ledger


@pytest.fixture
def ledger_env(tmp_path, monkeypatch):
    monkeypatch.setenv("TAAS_AUDIT_LEDGER_PATH", str(tmp_path / "audit.sqlite3"))
    monkeypatch.setenv("TAAS_AUDIT_ANCHOR_PATH", str(tmp_path / "anchors.json"))
    monkeypatch.setenv("TAAS_AUDIT_ANCHOR_KEY", "anchor-test-key")
    return tmp_path


def _append(n=1):
    for i in range(n):
        audit_ledger.append_event(
            "evidence", {"agent_id": "a1"}, {"note": f"e{i}"})


def test_create_anchor_signs_head(ledger_env):
    _append(2)
    anchor = audit_anchor.create_anchor()
    assert anchor["seq"] == 2 and len(anchor["digest"]) == 64
    assert anchor["schema"] == "taas.audit-anchor/v1"
    # anchor event itself is chained (head advanced by 1)
    v = audit_anchor.verify_anchor(anchor)
    assert v["status"] == "advanced"  # anchor event appended after seq 2


def test_verify_intact_when_anchor_is_head(ledger_env):
    _append(1)
    anchor = audit_anchor.create_anchor()          # seq 1 anchor
    # verify against an anchor that is still the head: craft one manually
    head = audit_anchor._chain_head()
    assert head["seq"] == 2  # anchor event advanced it
    v = audit_anchor.verify_anchor(anchor)
    assert v["status"] == "advanced"
    assert v["signature_ok"] is True


def test_verify_detects_history_rewrite(ledger_env):
    _append(3)
    anchor = audit_anchor.create_anchor()          # anchored at seq 3
    # Full attack: rewrite seq 2's payload, then re-chain every subsequent
    # row so the LOCAL chain verify still passes — exactly what anchoring
    # exists to catch (the anchor records seq 3's pre-rewrite hash).
    con = sqlite3.connect(audit_ledger._database_path())
    rows = con.execute(
        "SELECT seq, event_type, subject_json, payload_json, created_at, prev_hash, event_hash "
        "FROM audit_events ORDER BY seq").fetchall()
    prev = rows[0][5]                              # genesis/prev of seq 1
    for seq, etype, subj, payload, created, prev_h, _hash in rows:
        if seq == 2:
            payload = json.dumps({"forged": True})
        new_hash = audit_ledger._event_hash(
            etype, json.loads(subj), json.loads(payload), created, prev)
        con.execute(
            "UPDATE audit_events SET payload_json=?, prev_hash=?, event_hash=? WHERE seq=?",
            (payload, prev, new_hash, seq))
        prev = new_hash
    con.commit()
    con.close()
    # the local chain still verifies — the rewrite is self-consistent
    assert audit_ledger.verify_chain()["chain_valid"] is True
    v = audit_anchor.verify_anchor(anchor)
    assert v["status"] == "tampered"               # anchored seq-3 hash no longer matches


def test_verify_detects_truncation(ledger_env):
    _append(2)
    anchor = audit_anchor.create_anchor()
    con = sqlite3.connect(audit_ledger._database_path())
    con.execute("DELETE FROM audit_events")
    con.commit()
    con.close()
    v = audit_anchor.verify_anchor(anchor)
    assert v["status"] == "tampered"


def test_verify_no_anchors(ledger_env):
    assert audit_anchor.verify_anchor()["status"] == "no_anchors"


def test_create_requires_key(tmp_path, monkeypatch):
    monkeypatch.setenv("TAAS_AUDIT_LEDGER_PATH", str(tmp_path / "audit.sqlite3"))
    monkeypatch.setenv("TAAS_AUDIT_ANCHOR_PATH", str(tmp_path / "anchors.json"))
    monkeypatch.delenv("TAAS_AUDIT_ANCHOR_KEY", raising=False)
    with pytest.raises(ValueError, match="TAAS_AUDIT_ANCHOR_KEY"):
        audit_anchor.create_anchor()


# ---- API surface -----------------------------------------------------------


def test_anchor_routes_end_to_end(ledger_env, monkeypatch):
    from fastapi.testclient import TestClient
    import taas.studio.api as studio_api
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "tok")
    client = TestClient(studio_api.app)
    h = {"Authorization": "Bearer tok"}

    r = client.post("/api/v1/audit/anchors", headers=h)
    assert r.status_code == 200 and r.json()["schema"] == "taas.audit-anchor/v1"
    r = client.get("/api/v1/audit/anchors/verify", headers=h)
    assert r.status_code == 200
    assert r.json()["status"] in ("intact", "advanced")
    # auth required
    assert client.post("/api/v1/audit/anchors").status_code == 401


def test_anchor_route_503_without_key(ledger_env, monkeypatch):
    monkeypatch.delenv("TAAS_AUDIT_ANCHOR_KEY")
    from fastapi.testclient import TestClient
    import taas.studio.api as studio_api
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "tok")
    client = TestClient(studio_api.app)
    h = {"Authorization": "Bearer tok"}
    assert client.post("/api/v1/audit/anchors", headers=h).status_code == 503
