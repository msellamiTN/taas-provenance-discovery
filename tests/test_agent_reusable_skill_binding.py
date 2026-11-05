from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from taas.studio import agent_registry, skill_registry
from taas.studio.agent_context import build_agent_intelligence_context
from taas.studio.agent_skill_bindings import (
    AgentSkillBindingConflict,
    AgentSkillBindingNotFound,
    resolve_agent_skill_references,
)
from taas.studio.agent_spec import validate_agent_manifest
from taas.studio.skill_spec import validate_skill_manifest
import taas.studio.api as studio_api


def skill_manifest():
    return {
        "apiVersion": "taas.ai/v1alpha1",
        "kind": "Skill",
        "metadata": {
            "id": "date-difference",
            "name": "Date difference",
            "version": "1.0.0",
            "description": "Calculate date differences from independently sourced dates.",
        },
        "spec": {
            "instructions": "Acquire each date independently, then compute the exact year difference.",
            "trigger_phrases": ["year difference", "date difference"],
            "tags": ["research", "calculation"],
        },
    }


def agent_manifest(skill_digest: str):
    return {
        "apiVersion": "taas.ai/v1alpha1",
        "kind": "Agent",
        "metadata": {
            "id": "research-assistant",
            "name": "Research Assistant",
            "version": "1.0.0",
        },
        "spec": {
            "model": {"provider": "huggingface", "model_id": "org/model"},
            "instructions": "Preserve the user's requested outcomes.",
            "skill_refs": [{
                "id": "date-difference",
                "version": "1.0.0",
                "manifest_sha256": skill_digest,
            }],
            "tool_allowlist": [],
            "resources": {"max_new_tokens": 512, "timeout_seconds": 90, "max_tool_calls": 0},
            "approval": {"require_human_approval": True, "require_assurance": True, "allow_side_effects": False},
        },
    }


def publish_skill():
    created = skill_registry.create_draft(validate_skill_manifest(skill_manifest()), actor="test-author")
    skill_registry.transition("date-difference", "1.0.0", "validated", actor="test-reviewer")
    published = skill_registry.transition("date-difference", "1.0.0", "published", actor="test-publisher")
    return published


@pytest.fixture
def registries(monkeypatch, tmp_path):
    monkeypatch.setenv("TAAS_SKILL_REGISTRY_PATH", str(tmp_path / "skills.sqlite3"))
    monkeypatch.setenv("TAAS_AGENT_REGISTRY_PATH", str(tmp_path / "agents.sqlite3"))
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "binding-test-token")
    monkeypatch.setenv("TAAS_STUDIO_ACTOR", "binding-api-test")
    return tmp_path


def test_agent_manifest_accepts_exact_skill_reference_and_preserves_legacy_shape(registries):
    published = publish_skill()
    normalized = validate_agent_manifest(agent_manifest(published["manifest_sha256"]))
    assert normalized["spec"]["skill_refs"][0]["id"] == "date-difference"
    assert normalized["spec"]["skill_refs"][0]["manifest_sha256"] == published["manifest_sha256"]

    legacy = agent_manifest(published["manifest_sha256"])
    legacy["spec"].pop("skill_refs")
    normalized_legacy = validate_agent_manifest(legacy)
    assert "skill_refs" not in normalized_legacy["spec"]


def test_agent_manifest_rejects_duplicate_or_embedded_reference_collisions(registries):
    published = publish_skill()
    payload = agent_manifest(published["manifest_sha256"])
    payload["spec"]["skill_refs"].append(dict(payload["spec"]["skill_refs"][0]))
    with pytest.raises(Exception, match="duplicate Skill IDs"):
        validate_agent_manifest(payload)

    payload = agent_manifest(published["manifest_sha256"])
    payload["spec"]["skills"] = [{
        "id": "date-difference", "name": "Embedded duplicate", "version": "1.0.0",
        "instructions": "Conflicting guidance.", "trigger_phrases": ["date difference"],
    }]
    with pytest.raises(Exception, match="must not share IDs"):
        validate_agent_manifest(payload)


def test_binding_resolves_exact_published_version_and_context_provenance(registries):
    published = publish_skill()
    manifest = validate_agent_manifest(agent_manifest(published["manifest_sha256"]))
    resolved, references = resolve_agent_skill_references(manifest)
    assert references == [{
        "id": "date-difference", "version": "1.0.0",
        "manifest_sha256": published["manifest_sha256"],
        "lifecycle_state": "published", "source": "skill_registry",
    }]
    context, trace = build_agent_intelligence_context(
        resolved, "Find two dates and calculate the year difference."
    )
    assert [item["id"] for item in context["skills"]] == ["date-difference"]
    assert trace["selected_skill_ids"] == ["date-difference"]
    assert trace["skills"][0]["instructions_sha256"]
    assert set(context["skills"][0]) == {"id", "name", "description", "instructions"}


def test_binding_fails_closed_for_draft_skill_and_digest_mismatch(registries):
    draft = skill_registry.create_draft(validate_skill_manifest(skill_manifest()))
    manifest = validate_agent_manifest(agent_manifest(draft["manifest_sha256"]))
    with pytest.raises(AgentSkillBindingConflict, match="must be published"):
        resolve_agent_skill_references(manifest)

    publish_skill()
    manifest = validate_agent_manifest(agent_manifest("0" * 64))
    with pytest.raises(AgentSkillBindingConflict, match="digest does not match"):
        resolve_agent_skill_references(manifest)


def test_binding_reports_missing_exact_skill_version(registries):
    manifest = validate_agent_manifest(agent_manifest("a" * 64))
    with pytest.raises(AgentSkillBindingNotFound, match="does not exist"):
        resolve_agent_skill_references(manifest)


def test_authenticated_agent_api_resolves_references_during_lifecycle(registries):
    published = publish_skill()
    client = TestClient(studio_api.app)
    headers = {"Authorization": "Bearer binding-test-token"}
    payload = agent_manifest(published["manifest_sha256"])

    validated_manifest = client.post("/api/v1/agents/validate", json=payload, headers=headers)
    assert validated_manifest.status_code == 200
    assert validated_manifest.json()["resolved_skill_references"][0]["source"] == "skill_registry"

    created = client.post("/api/v1/agents", json=payload, headers=headers)
    assert created.status_code == 201
    assert created.json()["resolved_skill_references"][0]["manifest_sha256"] == published["manifest_sha256"]

    validated = client.post(
        "/api/v1/agents/research-assistant/versions/1.0.0/validate", headers=headers
    )
    assert validated.status_code == 200
    assert "pinned_skill_resolution" in validated.json()["validation_scope"]

    published_agent = client.post(
        "/api/v1/agents/research-assistant/versions/1.0.0/publish", headers=headers
    )
    assert published_agent.status_code == 200
    assert published_agent.json()["resolved_skill_references"][0]["id"] == "date-difference"
    assert published_agent.json()["tools_authorized"] is False
    assert published_agent.json()["execution_enabled"] is False


def test_authenticated_agent_api_rejects_unpublished_or_unpinned_skill(registries):
    draft = skill_registry.create_draft(validate_skill_manifest(skill_manifest()))
    client = TestClient(studio_api.app)
    headers = {"Authorization": "Bearer binding-test-token"}
    payload = agent_manifest(draft["manifest_sha256"])
    response = client.post("/api/v1/agents", json=payload, headers=headers)
    assert response.status_code == 409
    assert "must be published" in response.json()["detail"]

    publish_skill()
    payload = agent_manifest("f" * 64)
    response = client.post("/api/v1/agents", json=payload, headers=headers)
    assert response.status_code == 409
    assert "digest does not match" in response.json()["detail"]


def test_agent_objective_prepare_injects_external_skill_and_emits_digest_trace(monkeypatch, registries):
    published = publish_skill()
    manifest = validate_agent_manifest(agent_manifest(published["manifest_sha256"]))
    saved = agent_registry.create_draft(manifest)

    calls = []
    class FakeRuntime:
        def decompose(self, prompt, context="", max_new_tokens=1200, agent_context=None):
            calls.append(agent_context)
            return {
                "text": "not-json", "json_valid": False, "parse_error": "test candidate rejected",
                "goal_spec": None, "model_id": "org/model", "latency_seconds": 0.01,
            }

    monkeypatch.setattr(studio_api, "get_model_runtime", lambda: FakeRuntime())
    monkeypatch.setattr(studio_api, "prepare_agent_candidate", lambda result, prompt, contract: result)
    monkeypatch.setattr(studio_api, "build_objective_context", lambda prompt: "")
    response = studio_api.agent_decompose(studio_api.AgentDecomposeRequest(
        prompt="Find two dates and calculate the year difference.",
        agent_id="research-assistant", agent_version="1.0.0",
    ))
    assert calls and calls[0]["skills"][0]["id"] == "date-difference"
    trace = response["agent_intelligence_context"]
    assert trace["external_skill_references"][0]["manifest_sha256"] == published["manifest_sha256"]
    assert trace["skills"][0]["source"] == "skill_registry"
    assert trace["skills"][0]["registry_manifest_sha256"] == published["manifest_sha256"]
    assert response["workflow"]["tool_execution"] == "disabled"
