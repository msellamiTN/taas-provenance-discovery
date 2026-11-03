import pytest
from pydantic import ValidationError

from taas.studio.authorization_preflight import (
    AuthorizationConfigurationError,
    build_authorization_preflight,
    load_trusted_authorization_config,
)
from taas.studio.api import AgentAuthorizationPreflightRequest


def _env():
    return {
        "TAAS_STUDIO_PRINCIPAL": "taas-studio-service",
        "TAAS_STUDIO_POLICY_VERSION": "2026-11-03.1",
        "TAAS_STUDIO_POLICY_JSON": '{"name":"docs-read","allowed":["read(docs)"],"required":[]}',
    }


def _agent():
    return {
        "agent_id": "research-agent",
        "version": "1.0.0",
        "manifest_sha256": "a" * 64,
        "lifecycle_state": "published",
        "registry_snapshot_id": "b" * 64,
        "manifest": {
            "spec": {
                "tool_allowlist": [
                    {"server_id": "docs", "tool_name": "search"}
                ]
            }
        },
    }


def _snapshot():
    return {
        "snapshot_id": "b" * 64,
        "snapshot": {
            "servers": [{
                "server_id": "docs",
                "tools": [{
                    "name": "search",
                    "definition_sha256": "c" * 64,
                }],
            }]
        },
    }


def test_trusted_authorization_config_requires_operator_principal_policy_and_version():
    with pytest.raises(AuthorizationConfigurationError, match="PRINCIPAL"):
        load_trusted_authorization_config({})
    with pytest.raises(AuthorizationConfigurationError, match="POLICY_VERSION"):
        load_trusted_authorization_config({
            "TAAS_STUDIO_PRINCIPAL": "taas-studio-service",
            "TAAS_STUDIO_POLICY_JSON": '{"allowed":["read(docs)"]}',
        })
    with pytest.raises(AuthorizationConfigurationError, match="valid JSON"):
        load_trusted_authorization_config({
            **_env(),
            "TAAS_STUDIO_POLICY_JSON": "{broken",
        })


def test_trusted_policy_fingerprint_is_versioned_and_deterministic():
    first = load_trusted_authorization_config(_env())
    again = load_trusted_authorization_config(_env())
    changed = load_trusted_authorization_config({
        **_env(),
        "TAAS_STUDIO_POLICY_VERSION": "2026-11-03.2",
    })
    assert first.policy_sha256 == again.policy_sha256
    assert first.policy_sha256 != changed.policy_sha256
    assert first.principal == "taas-studio-service"


def test_preflight_binds_agent_snapshot_tool_goal_args_and_server_identity_but_fails_closed():
    config = load_trusted_authorization_config(_env())
    result = build_authorization_preflight(
        agent=_agent(),
        snapshot=_snapshot(),
        server_id="docs",
        tool_name="search",
        arguments={"query": "project status"},
        goal_spec={"prompt": "Find project status", "goals": [{"id": "g1"}]},
        trusted_config=config,
    )
    assert result["decision"] == "deny"
    assert result["checks"]["agent_published"] is True
    assert result["checks"]["snapshot_bound"] is True
    assert result["checks"]["snapshot_integrity_available"] is True
    assert result["checks"]["agent_grant_declared"] is True
    assert result["checks"]["tool_definition_resolved"] is True
    assert result["checks"]["tool_arguments_schema_validated"] is False
    assert result["checks"]["human_approval_workflow_available"] is False
    assert result["checks"]["trusted_service_principal_configured"] is True
    assert result["checks"]["server_policy_configured"] is True
    assert "trusted_effect_assessment_pipeline_not_integrated" in result["deny_reasons"]
    assert "assurance_evidence_store_not_integrated" in result["deny_reasons"]
    assert "tool_argument_schema_validation_not_integrated" in result["deny_reasons"]
    assert "human_approval_workflow_not_integrated" in result["deny_reasons"]
    assert result["binding"]["tool_definition_sha256"] == "c" * 64
    assert result["binding"]["mcp_snapshot_id"] == "b" * 64
    assert result["binding"]["policy_version"] == "2026-11-03.1"
    assert result["approval_issued"] is False
    assert result["tools_authorized"] is False
    assert result["execution_enabled"] is False
    assert result["execution_attempted"] is False


def test_preflight_denies_unpublished_agent_unbound_snapshot_and_unlisted_tool():
    result = build_authorization_preflight(
        agent={
            **_agent(),
            "lifecycle_state": "validated",
            "registry_snapshot_id": None,
        },
        snapshot=None,
        server_id="shell",
        tool_name="run",
        arguments={"command": "whoami"},
        goal_spec={"prompt": "inspect"},
        trusted_config=None,
        configuration_error="TAAS_STUDIO_POLICY_JSON is not configured",
    )
    assert result["decision"] == "deny"
    assert "agent_version_not_published" in result["deny_reasons"]
    assert "agent_version_has_no_bound_mcp_snapshot" in result["deny_reasons"]
    assert "tool_not_declared_in_agent_allowlist" in result["deny_reasons"]
    assert "TAAS_STUDIO_POLICY_JSON is not configured" in result["deny_reasons"]


def test_preflight_request_rejects_client_supplied_authority_fields():
    payload = {
        "server_id": "docs",
        "tool_name": "search",
        "arguments": {"query": "x"},
        "goal_spec": {"prompt": "x", "goals": [{"id": "g1"}]},
        "principal": "browser-user",
        "effects": ["read(docs)"],
        "assurance_evidence_hash": "d" * 64,
        "policy": {"allowed": ["read(*)"]},
    }
    with pytest.raises(ValidationError):
        AgentAuthorizationPreflightRequest.model_validate(payload)
