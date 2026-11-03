"""Fail-closed, evidence-aware authorization preflight for Agent invocations.

This module deliberately produces a decision preview only. It does not issue
approval tokens, authorize MCP calls, or invoke tools. Missing trusted policy,
principal, effect assessment, or assurance evidence is a hard deny.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Mapping

from taas.policy import Declassification, Policy
from taas.provenance import LEVELS
from taas.studio.execution_gateway import GatewayDenied, canonical_hash, policy_fingerprint


class AuthorizationConfigurationError(ValueError):
    """Trusted authorization configuration is missing or malformed."""


@dataclass(frozen=True)
class TrustedAuthorizationConfig:
    principal: str
    policy_version: str
    policy: Policy
    policy_sha256: str


def load_trusted_authorization_config(
    environ: Mapping[str, str] | None = None,
) -> TrustedAuthorizationConfig:
    """Load policy and service principal exclusively from operator environment."""
    env = os.environ if environ is None else environ
    principal = env.get("TAAS_STUDIO_PRINCIPAL", "").strip()
    version = env.get("TAAS_STUDIO_POLICY_VERSION", "").strip()
    raw = env.get("TAAS_STUDIO_POLICY_JSON", "").strip()
    if not principal:
        raise AuthorizationConfigurationError("TAAS_STUDIO_PRINCIPAL is not configured")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}", principal):
        raise AuthorizationConfigurationError("TAAS_STUDIO_PRINCIPAL has an invalid service identity")
    if not version or len(version) > 128:
        raise AuthorizationConfigurationError("TAAS_STUDIO_POLICY_VERSION is not configured")
    if not raw:
        raise AuthorizationConfigurationError("TAAS_STUDIO_POLICY_JSON is not configured")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AuthorizationConfigurationError("TAAS_STUDIO_POLICY_JSON must be valid JSON") from exc
    if not isinstance(payload, dict):
        raise AuthorizationConfigurationError("TAAS_STUDIO_POLICY_JSON must contain an object")
    try:
        json.dumps(payload, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise AuthorizationConfigurationError("Policy configuration must contain finite JSON values") from exc

    allowed_keys = {
        "name", "allowed", "required", "forbidden", "encoding", "lmin",
        "visible", "declass", "egress_threshold", "forbidden_pairs",
        "prompt_label", "credentials",
    }
    unknown = set(payload) - allowed_keys
    if unknown:
        raise AuthorizationConfigurationError(
            "Unknown policy configuration fields: " + ", ".join(sorted(unknown))
        )
    allowed = payload.get("allowed")
    if not isinstance(allowed, list) or not allowed or any(not isinstance(x, str) for x in allowed):
        raise AuthorizationConfigurationError("Policy allowed must be a non-empty array of effect strings")
    for key in ("required", "forbidden"):
        value = payload.get(key, [])
        if not isinstance(value, list) or any(not isinstance(x, str) for x in value):
            raise AuthorizationConfigurationError(f"Policy {key} must be an array of strings")
    visible = payload.get("visible")
    credentials = payload.get("credentials")
    for key, value in (("visible", visible), ("credentials", credentials)):
        if value is not None and (
            not isinstance(value, list) or any(not isinstance(x, str) for x in value)
        ):
            raise AuthorizationConfigurationError(f"Policy {key} must be null or an array of strings")
    pairs = payload.get("forbidden_pairs", [["private_read", "egress_any"]])
    if not isinstance(pairs, list) or any(
        not isinstance(pair, list) or len(pair) != 2 or any(not isinstance(x, str) for x in pair)
        for pair in pairs
    ):
        raise AuthorizationConfigurationError("Policy forbidden_pairs must be pairs of strings")
    encoding = payload.get("encoding", "positive")
    if encoding not in {"positive", "closed_world"}:
        raise AuthorizationConfigurationError("Policy encoding must be positive or closed_world")
    egress_threshold = payload.get("egress_threshold", "internal")
    if not isinstance(egress_threshold, str) or not egress_threshold or len(egress_threshold) > 64:
        raise AuthorizationConfigurationError("Policy egress_threshold must be a non-empty label string")
    rules = payload.get("declass", [])
    if not isinstance(rules, list):
        raise AuthorizationConfigurationError("Policy declass must be an array")
    declass = []
    for rule in rules:
        if not isinstance(rule, dict):
            raise AuthorizationConfigurationError("Each declassification rule must be an object")
        try:
            min_evidence = rule.get("min_evidence", "obs")
            min_records = int(rule.get("min_records", 10))
            if min_evidence not in LEVELS or min_records < 1:
                raise ValueError("Invalid evidence threshold or record count")
            tool_classes = rule.get("tool_classes", ["aggregate"])
            tools = rule.get("tools", [])
            if not isinstance(tool_classes, list) or any(not isinstance(x, str) for x in tool_classes):
                raise ValueError("Invalid tool_classes")
            if not isinstance(tools, list) or any(not isinstance(x, str) for x in tools):
                raise ValueError("Invalid tools")
            declass.append(Declassification(
                label_from=rule["label_from"],
                label_to=rule["label_to"],
                tool_classes=frozenset(tool_classes),
                tools=frozenset(tools),
                min_evidence=min_evidence,
                min_records=min_records,
            ))
        except (KeyError, TypeError, ValueError) as exc:
            raise AuthorizationConfigurationError("Invalid policy declassification rule") from exc
    try:
        policy = Policy.make(
            name=str(payload.get("name", "operator-policy")),
            required=payload.get("required", []),
            allowed=allowed,
            lmin=payload.get("lmin", "obs"),
            forbidden=frozenset(payload.get("forbidden", [])),
            encoding=str(payload.get("encoding", "positive")),
            visible=frozenset(visible) if visible is not None else None,
            declass=tuple(declass),
            egress_threshold=str(egress_threshold),
            forbidden_pairs=tuple(tuple(pair) for pair in pairs),
            prompt_label=str(payload.get("prompt_label", "public")),
            credentials=frozenset(credentials) if credentials is not None else None,
        )
        fingerprint = canonical_hash({
            "policy_version": version,
            "policy_fingerprint": policy_fingerprint(policy),
        })
    except (TypeError, ValueError, KeyError, GatewayDenied) as exc:
        raise AuthorizationConfigurationError("Policy configuration could not be normalized") from exc
    return TrustedAuthorizationConfig(principal, version, policy, fingerprint)


def build_authorization_preflight(
    *,
    agent: dict[str, Any],
    snapshot: dict[str, Any] | None,
    server_id: str,
    tool_name: str,
    arguments: dict[str, Any],
    goal_spec: dict[str, Any],
    trusted_config: TrustedAuthorizationConfig | None,
    configuration_error: str | None = None,
) -> dict[str, Any]:
    """Return a deterministic authorization readiness preview; never grants access."""
    reasons: list[str] = []
    checks: dict[str, bool] = {}

    checks["agent_published"] = agent.get("lifecycle_state") == "published"
    if not checks["agent_published"]:
        reasons.append("agent_version_not_published")

    bound_snapshot_id = agent.get("registry_snapshot_id")
    checks["snapshot_bound"] = isinstance(bound_snapshot_id, str) and bool(bound_snapshot_id)
    if not checks["snapshot_bound"]:
        reasons.append("agent_version_has_no_bound_mcp_snapshot")

    snapshot_payload = snapshot.get("snapshot", {}) if isinstance(snapshot, dict) else {}
    snapshot_matches = (
        snapshot is not None
        and snapshot.get("snapshot_id") == bound_snapshot_id
        and isinstance(snapshot_payload, dict)
    )
    checks["snapshot_integrity_available"] = bool(snapshot_matches)
    if not snapshot_matches:
        reasons.append("bound_mcp_snapshot_unavailable_or_mismatched")

    manifest = agent.get("manifest", {})
    spec = manifest.get("spec", {}) if isinstance(manifest, dict) else {}
    grants = spec.get("tool_allowlist", []) if isinstance(spec, dict) else []
    grant_matches = any(
        isinstance(grant, dict)
        and grant.get("server_id") == server_id
        and grant.get("tool_name") == tool_name
        for grant in grants
    )
    checks["agent_grant_declared"] = grant_matches
    if not grant_matches:
        reasons.append("tool_not_declared_in_agent_allowlist")

    tool = None
    if snapshot_matches:
        for server in snapshot_payload.get("servers", []):
            if isinstance(server, dict) and server.get("server_id") == server_id:
                tool = next((
                    item for item in server.get("tools", [])
                    if isinstance(item, dict) and item.get("name") == tool_name
                ), None)
                break
    definition_hash = tool.get("definition_sha256") if isinstance(tool, dict) else None
    checks["tool_definition_resolved"] = (
        isinstance(definition_hash, str)
        and re.fullmatch(r"[0-9a-f]{64}", definition_hash) is not None
    )
    if not checks["tool_definition_resolved"]:
        reasons.append("exact_tool_definition_not_resolved")

    configured_principal = os.environ.get("TAAS_STUDIO_PRINCIPAL", "").strip()
    checks["trusted_service_principal_configured"] = bool(
        re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}", configured_principal)
    )
    checks["server_policy_configured"] = trusted_config is not None
    if not checks["trusted_service_principal_configured"]:
        reasons.append("trusted_service_principal_not_configured")
    if trusted_config is None:
        reasons.append(configuration_error or "trusted_server_policy_not_configured")

    # No trusted effect-assessment or assurance-evidence store is integrated yet.
    # Client-supplied effects/evidence are intentionally not accepted as substitutes.
    checks["trusted_effect_assessment_available"] = False
    checks["assurance_evidence_available"] = False
    reasons.extend([
        "trusted_effect_assessment_pipeline_not_integrated",
        "assurance_evidence_store_not_integrated",
    ])

    try:
        arguments_hash = canonical_hash(arguments)
        goal_spec_hash = canonical_hash(goal_spec)
    except GatewayDenied as exc:
        raise ValueError(str(exc)) from exc

    binding = {
        "agent_id": agent.get("agent_id"),
        "agent_version": agent.get("version"),
        "agent_manifest_sha256": agent.get("manifest_sha256"),
        "mcp_snapshot_id": bound_snapshot_id,
        "server_id": server_id,
        "tool_name": tool_name,
        "tool_definition_sha256": definition_hash if checks["tool_definition_resolved"] else None,
        "arguments_sha256": arguments_hash,
        "goal_spec_sha256": goal_spec_hash,
        "principal": trusted_config.principal if trusted_config else None,
        "policy_version": trusted_config.policy_version if trusted_config else None,
        "policy_sha256": trusted_config.policy_sha256 if trusted_config else None,
    }
    return {
        "decision": "deny",
        "decision_scope": "preflight_only",
        "checks": checks,
        "deny_reasons": reasons,
        "binding": binding,
        "approval_issued": False,
        "tools_authorized": False,
        "execution_enabled": False,
        "execution_attempted": False,
        "limitations": [
            "This endpoint does not issue approval tokens or authorize invocation.",
            "Human identity is not established by the Studio bearer token.",
            "Trusted effect assessment and assurance evidence are not yet integrated.",
        ],
    }
