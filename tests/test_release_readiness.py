from __future__ import annotations

import hashlib
import json

from taas.studio.release_readiness import evaluate_release_readiness


def _sha(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()
    ).hexdigest()


def _manifest():
    return {
        "apiVersion": "taas.ai/v1alpha1",
        "kind": "Agent",
        "metadata": {"id": "release-agent", "name": "Release Agent", "version": "1.0.0", "description": ""},
        "spec": {
            "model": {"provider": "huggingface", "model_id": "org/model", "revision": None},
            "instructions": "Assess a release candidate.",
            "goal_spec_template": None,
            "tool_allowlist": [],
            "resources": {"max_new_tokens": 1024, "timeout_seconds": 120, "max_tool_calls": 0},
            "approval": {"require_human_approval": True, "require_assurance": True, "allow_side_effects": False},
        },
    }


def _agent(manifest=None, state="validated"):
    manifest = manifest or _manifest()
    return {
        "agent_id": manifest["metadata"]["id"],
        "version": manifest["metadata"]["version"],
        "manifest": manifest,
        "manifest_sha256": _sha(manifest),
        "lifecycle_state": state,
        "registry_snapshot_id": None,
    }


def test_missing_trusted_assurance_and_approval_never_reports_ready():
    report = evaluate_release_readiness(agent=_agent(), snapshot=None)
    assert report["decision"] == "NEEDS_REVIEW"
    assert report["checks"]["manifest_structurally_valid"] is True
    assert report["checks"]["manifest_integrity_verified"] is True
    assert report["checks"]["agent_version_validated"] is True
    assert report["checks"]["trusted_assurance_evidence_verified"] is False
    assert report["checks"]["human_approval_record_verified"] is False
    assert report["authorization_granted"] is False
    assert report["execution_enabled"] is False


def test_draft_agent_is_blocked_even_if_manifest_is_valid():
    report = evaluate_release_readiness(agent=_agent(state="draft"), snapshot=None)
    assert report["decision"] == "BLOCKED"
    assert report["checks"]["agent_version_validated"] is False


def test_tampered_manifest_is_blocked():
    agent = _agent()
    agent["manifest"]["spec"]["instructions"] = "tampered"
    report = evaluate_release_readiness(agent=agent, snapshot=None)
    assert report["decision"] == "BLOCKED"
    assert report["checks"]["manifest_integrity_verified"] is False


def test_tool_grant_without_bound_snapshot_is_blocked():
    manifest = _manifest()
    manifest["spec"]["tool_allowlist"] = [{"server_id": "server-a", "tool_name": "lookup"}]
    manifest["spec"]["resources"]["max_tool_calls"] = 1
    agent = _agent(manifest)
    report = evaluate_release_readiness(agent=agent, snapshot=None)
    assert report["decision"] == "BLOCKED"
    assert report["checks"]["registry_snapshot_integrity_verified"] is False
    assert report["checks"]["all_declared_tool_grants_resolved"] is False


def test_snapshot_hash_and_exact_tool_definition_are_checked():
    manifest = _manifest()
    manifest["spec"]["tool_allowlist"] = [{"server_id": "server-a", "tool_name": "lookup"}]
    manifest["spec"]["resources"]["max_tool_calls"] = 1
    agent = _agent(manifest)
    snapshot_payload = {
        "servers": [{
            "server_id": "server-a",
            "tools": [{
                "name": "lookup",
                "definition_sha256": "a" * 64,
            }],
        }]
    }
    snapshot_id = _sha(snapshot_payload)
    agent["registry_snapshot_id"] = snapshot_id
    snapshot = {"snapshot_id": snapshot_id, "snapshot": snapshot_payload}
    report = evaluate_release_readiness(agent=agent, snapshot=snapshot)
    assert report["checks"]["registry_snapshot_integrity_verified"] is True
    assert report["checks"]["all_declared_tool_grants_resolved"] is True
    assert report["resolved_tool_grants"][0]["tool_definition_sha256"] == "a" * 64
    assert report["decision"] == "NEEDS_REVIEW"


def test_snapshot_content_tampering_is_blocked():
    manifest = _manifest()
    manifest["spec"]["tool_allowlist"] = [{"server_id": "server-a", "tool_name": "lookup"}]
    manifest["spec"]["resources"]["max_tool_calls"] = 1
    agent = _agent(manifest)
    payload = {"servers": [{"server_id": "server-a", "tools": [{"name": "lookup", "definition_sha256": "b" * 64}]}]}
    sid = _sha(payload)
    agent["registry_snapshot_id"] = sid
    payload["servers"][0]["tools"][0]["definition_sha256"] = "c" * 64
    report = evaluate_release_readiness(agent=agent, snapshot={"snapshot_id": sid, "snapshot": payload})
    assert report["decision"] == "BLOCKED"
    assert report["checks"]["registry_snapshot_integrity_verified"] is False
