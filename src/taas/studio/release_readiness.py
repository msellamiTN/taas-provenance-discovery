"""Evidence-backed Agent release readiness assessment.

The assessment is deliberately separate from authorization and execution.
A READY result requires every declared check to be supported by trusted,
verifiable evidence; missing integrations therefore remain non-ready.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Callable, Mapping

from pydantic import ValidationError

from taas.studio.agent_spec import validate_agent_manifest
from taas.studio import assurance_evidence


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _check(checks: dict[str, bool], blockers: list[dict[str, str]], key: str,
           passed: bool, reason: str, detail: str) -> None:
    checks[key] = bool(passed)
    if not passed:
        blockers.append({"code": reason, "detail": detail})


def build_release_subject_binding(agent: dict[str, Any]) -> dict[str, Any]:
    """Exact identity that assurance evidence and approvals must be bound to.

    Evidence recorded against a different manifest digest or MCP snapshot never
    satisfies this binding, so tampering with either artifact voids the gate.
    """
    return {
        "agent_id": agent.get("agent_id"),
        "version": agent.get("version"),
        "manifest_sha256": agent.get("manifest_sha256"),
        "registry_snapshot_id": agent.get("registry_snapshot_id"),
    }


def evidence_store_lookup(agent: dict[str, Any],
                          environ: Mapping[str, str] | None = None) -> Callable[[str], dict[str, Any]]:
    """Look up verified assurance evidence for one Agent version binding."""
    binding = build_release_subject_binding(agent)

    def lookup(expected_type: str) -> dict[str, Any]:
        try:
            found = assurance_evidence.list_verified_evidence_for_subject(
                binding, expected_type=expected_type, environ=environ
            )
        except assurance_evidence.EvidenceError as exc:
            return {"available": False, "record": None, "error": str(exc)}
        record = found["valid"][0] if found["valid"] else None
        return {"available": record is not None, "record": record, "error": None}

    return lookup


def evaluate_release_readiness(
    *, agent: dict[str, Any], snapshot: dict[str, Any] | None,
    evidence_lookup: Callable[[str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return a deterministic readiness report without granting execution rights."""
    checks: dict[str, bool] = {}
    blockers: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    manifest = agent.get("manifest")
    try:
        normalized = validate_agent_manifest(manifest)
        structural_valid = normalized == manifest
    except (ValidationError, TypeError, ValueError):
        normalized = None
        structural_valid = False
    _check(
        checks, blockers, "manifest_structurally_valid", structural_valid,
        "agent_manifest_invalid_or_noncanonical",
        "The stored Agent manifest failed schema or canonical-form validation.",
    )

    expected_manifest_hash = agent.get("manifest_sha256")
    try:
        actual_manifest_hash = _canonical_sha256(manifest)
        manifest_hash_valid = (
            isinstance(expected_manifest_hash, str)
            and re.fullmatch(r"[0-9a-f]{64}", expected_manifest_hash) is not None
            and actual_manifest_hash == expected_manifest_hash
        )
    except (TypeError, ValueError):
        manifest_hash_valid = False
    _check(
        checks, blockers, "manifest_integrity_verified", manifest_hash_valid,
        "agent_manifest_integrity_check_failed",
        "The canonical manifest digest does not match the immutable registry digest.",
    )

    lifecycle = agent.get("lifecycle_state")
    lifecycle_valid = lifecycle in {"validated", "published"}
    _check(
        checks, blockers, "agent_version_validated", lifecycle_valid,
        "agent_version_not_in_validated_state",
        "Release assessment requires a structurally validated Agent version.",
    )

    spec = manifest.get("spec", {}) if isinstance(manifest, dict) else {}
    grants = spec.get("tool_allowlist", []) if isinstance(spec, dict) else []
    snapshot_id = agent.get("registry_snapshot_id")
    snapshot_payload = snapshot.get("snapshot") if isinstance(snapshot, dict) else None
    snapshot_hash_valid = False
    if snapshot is not None and isinstance(snapshot_payload, dict):
        try:
            snapshot_hash_valid = (
                snapshot.get("snapshot_id") == snapshot_id
                and _canonical_sha256(snapshot_payload) == snapshot_id
            )
        except (TypeError, ValueError):
            snapshot_hash_valid = False

    snapshot_required = bool(grants)
    if snapshot_required:
        _check(
            checks, blockers, "registry_snapshot_integrity_verified", snapshot_hash_valid,
            "mcp_registry_snapshot_missing_or_invalid",
            "Tool grants require the exact content-addressed MCP registry snapshot bound to this Agent version.",
        )
    else:
        checks["registry_snapshot_integrity_verified"] = (
            True if not snapshot_id else snapshot_hash_valid
        )
        if snapshot_id and not snapshot_hash_valid:
            blockers.append({
                "code": "bound_mcp_registry_snapshot_invalid",
                "detail": "The Agent has a bound MCP snapshot whose content hash could not be verified.",
            })

    resolved: list[dict[str, str]] = []
    unresolved: list[dict[str, str]] = []
    tools_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    if snapshot_hash_valid and isinstance(snapshot_payload, dict):
        for server in snapshot_payload.get("servers", []):
            if not isinstance(server, dict):
                continue
            for tool in server.get("tools", []):
                if isinstance(tool, dict):
                    tools_by_key[(server.get("server_id"), tool.get("name"))] = tool

    for grant in grants if isinstance(grants, list) else []:
        if not isinstance(grant, dict):
            unresolved.append({"server_id": "", "tool_name": ""})
            continue
        key = (grant.get("server_id"), grant.get("tool_name"))
        tool = tools_by_key.get(key)
        definition_hash = tool.get("definition_sha256") if isinstance(tool, dict) else None
        if isinstance(definition_hash, str) and re.fullmatch(r"[0-9a-f]{64}", definition_hash):
            resolved.append({
                "server_id": str(key[0]),
                "tool_name": str(key[1]),
                "tool_definition_sha256": definition_hash,
            })
        else:
            unresolved.append({"server_id": str(key[0]), "tool_name": str(key[1])})

    _check(
        checks, blockers, "all_declared_tool_grants_resolved",
        len(unresolved) == 0,
        "agent_tool_grants_unresolved",
        "Every declared tool grant must resolve to an exact tool definition hash in the bound registry snapshot.",
    )

    approval = spec.get("approval", {}) if isinstance(spec, dict) else {}
    requires_assurance = approval.get("require_assurance", True) is True
    evidence_summary: dict[str, Any] = {}

    def _evidence_check(check_key: str, evidence_type: str,
                        missing_code: str, missing_detail: str,
                        not_integrated_code: str, not_integrated_detail: str) -> None:
        if evidence_lookup is None:
            checks[check_key] = False
            blockers.append({"code": not_integrated_code, "detail": not_integrated_detail})
            evidence_summary[evidence_type] = {"available": False, "reason": "not_integrated"}
            return
        outcome = evidence_lookup(evidence_type)
        record = outcome.get("record")
        checks[check_key] = bool(outcome.get("available") and isinstance(record, dict))
        evidence_summary[evidence_type] = {
            "available": checks[check_key],
            "evidence_id": record.get("evidence_id") if isinstance(record, dict) else None,
            "issuer": record.get("issuer") if isinstance(record, dict) else None,
            "assessor": record.get("assessor") if isinstance(record, dict) else None,
            "expires_at": record.get("expires_at") if isinstance(record, dict) else None,
            "error": outcome.get("error"),
        }
        if not checks[check_key]:
            detail = missing_detail
            if outcome.get("error"):
                detail = detail + " Evidence lookup failed closed: " + str(outcome["error"])
            blockers.append({"code": missing_code, "detail": detail})

    _evidence_check(
        "trusted_assurance_evidence_verified", "provenance_verification",
        "trusted_assurance_evidence_missing_or_expired",
        "No valid, fresh assurance evidence is bound to this exact Agent version and registry snapshot.",
        "trusted_assurance_evidence_pipeline_not_integrated",
        "A trusted, verifiable assurance evidence bundle is not yet integrated into release validation.",
    )
    if not requires_assurance:
        warnings.append({
            "code": "agent_assurance_not_required_by_manifest",
            "detail": "The Agent manifest does not require assurance; platform governance may still require it.",
        })

    _evidence_check(
        "human_approval_record_verified", "human_approval",
        "human_approval_record_missing_or_expired",
        "No valid, fresh human approval record is bound to this exact Agent version and registry snapshot.",
        "human_approval_workflow_not_integrated",
        "No trusted human approval record or approval workflow is available to this release gate.",
    )

    ready = bool(checks) and all(checks.values()) and not blockers
    if ready:
        decision = "READY"
    elif any(item["code"] in {
        "agent_manifest_invalid_or_noncanonical",
        "agent_manifest_integrity_check_failed",
        "agent_version_not_in_validated_state",
        "mcp_registry_snapshot_missing_or_invalid",
        "bound_mcp_registry_snapshot_invalid",
        "agent_tool_grants_unresolved",
    } for item in blockers):
        decision = "BLOCKED"
    else:
        decision = "NEEDS_REVIEW"

    return {
        "agent": {
            "agent_id": agent.get("agent_id"),
            "version": agent.get("version"),
            "lifecycle_state": lifecycle,
            "manifest_sha256": expected_manifest_hash,
            "registry_snapshot_id": snapshot_id,
        },
        "decision": decision,
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
        "resolved_tool_grants": resolved,
        "unresolved_tool_grants": unresolved,
        "evidence": evidence_summary,
        "decision_scope": "release_readiness_diagnostic_only",
        "authorization_granted": False,
        "execution_enabled": False,
        "human_approval_granted": False,
        "assessor_claim_truth_verified": False,
    }
