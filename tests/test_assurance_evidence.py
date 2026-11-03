from datetime import datetime, timedelta, timezone

import pytest

from taas.studio.assurance_evidence import (
    EvidenceConfigurationError,
    EvidenceError,
    attest_evidence,
    store_evidence,
    get_verified_evidence,
)


def _env(tmp_path):
    return {
        "TAAS_EVIDENCE_ATTESTATION_KEY": "test-only-attestation-key-32-bytes-min",
        "TAAS_EVIDENCE_DB_PATH": str(tmp_path / "evidence.sqlite3"),
    }


def _binding():
    return {
        "agent_id": "research-agent",
        "agent_version": "1.0.0",
        "agent_manifest_sha256": "a" * 64,
        "mcp_snapshot_id": "b" * 64,
        "server_id": "docs",
        "tool_name": "search",
        "tool_definition_sha256": "c" * 64,
        "arguments_sha256": "d" * 64,
        "goal_spec_sha256": "e" * 64,
        "principal": "service:studio",
        "policy_version": "policy-7",
        "policy_sha256": "f" * 64,
    }


def test_attestation_requires_operator_key():
    with pytest.raises(EvidenceConfigurationError):
        attest_evidence(
            evidence_type="trusted_effect_assessment",
            subject_binding=_binding(),
            issuer="taas-studio",
            assessor="effect-assessor-v1",
            method="static-analysis",
            payload={"effects": ["read(docs)"]},
            environ={},
        )


def test_evidence_envelope_is_bound_and_content_addressed(tmp_path):
    env = _env(tmp_path)
    envelope = attest_evidence(
        evidence_type="trusted_effect_assessment",
        subject_binding=_binding(),
        issuer="taas-studio",
        assessor="effect-assessor-v1",
        method="static-analysis",
        payload={"effects": ["read(docs)"], "confidence": "high"},
        environ=env,
    )
    first = store_evidence(envelope, environ=env)
    second = store_evidence(envelope, environ=env)
    assert first["evidence_id"] == second["evidence_id"]
    assert first["subject_binding_sha256"] == second["subject_binding_sha256"]
    assert first["payload_sha256"] == second["payload_sha256"]


def test_tampered_payload_and_attestation_are_rejected(tmp_path):
    env = _env(tmp_path)
    envelope = attest_evidence(
        evidence_type="tool_schema_validation",
        subject_binding=_binding(),
        issuer="taas-studio",
        assessor="json-schema-validator",
        method="json-schema-draft-2020-12",
        payload={"valid": True, "schema_sha256": "c" * 64},
        environ=env,
    )
    changed = {**envelope, "payload": {"valid": False}}
    with pytest.raises(EvidenceError, match="payload hash"):
        store_evidence(changed, environ=env)
    changed = {**envelope, "attestation_sha256": "0" * 64}
    with pytest.raises(EvidenceError, match="attestation"):
        store_evidence(changed, environ=env)


def test_expiry_and_timezone_are_validated(tmp_path):
    env = _env(tmp_path)
    now = datetime.now(timezone.utc)
    with pytest.raises(EvidenceError, match="timezone"):
        attest_evidence(
            evidence_type="provenance_verification",
            subject_binding=_binding(),
            issuer="taas-studio",
            assessor="provenance-verifier",
            method="digest-check",
            payload={"verified": True},
            observed_at=datetime.now(),
            environ=env,
        )
    with pytest.raises(EvidenceError, match="later"):
        from taas.studio.assurance_evidence import _unsigned_record
        _unsigned_record(
            evidence_type="provenance_verification",
            subject_binding=_binding(),
            issuer="taas-studio",
            assessor="provenance-verifier",
            method="digest-check",
            observed_at=now.isoformat(),
            expires_at=(now - timedelta(seconds=1)).isoformat(),
            payload={"verified": True},
        )



def test_retrieval_rechecks_signature_exact_binding_and_freshness(tmp_path):
    env = _env(tmp_path)
    binding = _binding()
    envelope = attest_evidence(
        evidence_type="trusted_effect_assessment",
        subject_binding=binding,
        issuer="taas-studio",
        assessor="effect-assessor-v1",
        method="static-analysis",
        payload={"effects": ["read(docs)"]},
        ttl_seconds=120,
        environ=env,
    )
    stored = store_evidence(envelope, environ=env)
    verified = get_verified_evidence(
        stored["evidence_id"], expected_type="trusted_effect_assessment",
        expected_binding=binding, environ=env,
    )
    assert verified["payload"] == {"effects": ["read(docs)"]}
    assert verified["evidence_id"] == stored["evidence_id"]

    altered = {**binding, "arguments_sha256": "9" * 64}
    with pytest.raises(EvidenceError, match="different invocation"):
        get_verified_evidence(
            stored["evidence_id"], expected_type="trusted_effect_assessment",
            expected_binding=altered, environ=env,
        )
    with pytest.raises(EvidenceError, match="not currently fresh"):
        get_verified_evidence(
            stored["evidence_id"], expected_type="trusted_effect_assessment",
            expected_binding=binding, environ=env,
            now=datetime.now(timezone.utc) + timedelta(minutes=5),
        )


def test_evidence_type_cannot_be_substituted(tmp_path):
    env = _env(tmp_path)
    envelope = attest_evidence(
        evidence_type="provenance_verification",
        subject_binding=_binding(),
        issuer="taas-studio",
        assessor="provenance-verifier",
        method="digest-check",
        payload={"verified": True},
        environ=env,
    )
    stored = store_evidence(envelope, environ=env)
    with pytest.raises(EvidenceError, match="type does not match"):
        get_verified_evidence(
            stored["evidence_id"], expected_type="trusted_effect_assessment",
            expected_binding=_binding(), environ=env,
        )
