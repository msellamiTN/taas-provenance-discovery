from __future__ import annotations

import pytest
from pydantic import ValidationError

from taas.studio import skill_dependency_graph, skill_registry
from taas.studio.agent_skill_bindings import resolve_agent_skill_references
from taas.studio.agent_spec import validate_agent_manifest
from taas.studio.skill_spec import validate_skill_manifest


def _manifest(skill_id: str, *, dependencies=None, instructions=None):
    spec = {
        "instructions": instructions or f"Instructions for {skill_id}.",
        "trigger_phrases": [f"trigger {skill_id}"],
        "tags": ["test"],
    }
    if dependencies is not None:
        spec["dependencies"] = dependencies
    return {
        "apiVersion": "taas.ai/v1alpha1",
        "kind": "Skill",
        "metadata": {
            "id": skill_id,
            "name": skill_id.replace("-", " ").title(),
            "version": "1.0.0",
        },
        "spec": spec,
    }


def _publish(payload):
    manifest = validate_skill_manifest(payload)
    created = skill_registry.create_draft(manifest, actor="dag-test-author")
    skill_registry.transition(created["skill_id"], created["version"], "validated", actor="dag-reviewer")
    return skill_registry.transition(
        created["skill_id"], created["version"], "published", actor="dag-publisher"
    )


@pytest.fixture
def registry(monkeypatch, tmp_path):
    monkeypatch.setenv("TAAS_SKILL_REGISTRY_PATH", str(tmp_path / "skills.sqlite3"))


def test_legacy_skill_manifest_preserves_canonical_shape_without_dependencies():
    normalized = validate_skill_manifest(_manifest("legacy-skill"))
    assert "dependencies" not in normalized["spec"]


def test_skill_manifest_validates_exact_dependency_pins_and_rejects_duplicates():
    reference = {
        "id": "base-skill",
        "version": "1.0.0",
        "manifest_sha256": "a" * 64,
    }
    normalized = validate_skill_manifest(
        _manifest("composed-skill", dependencies=[reference])
    )
    assert normalized["spec"]["dependencies"][0] == reference
    with pytest.raises(ValidationError, match="same Skill ID"):
        validate_skill_manifest(
            _manifest("composed-skill", dependencies=[reference, reference])
        )
    with pytest.raises(ValidationError, match="cannot depend on itself"):
        validate_skill_manifest(
            _manifest(
                "composed-skill",
                dependencies=[{**reference, "id": "composed-skill"}],
            )
        )


def test_dependency_graph_resolves_exact_published_dag_dependency_first(registry):
    leaf = _publish(_manifest("leaf-skill"))
    middle = _publish(_manifest("middle-skill", dependencies=[{
        "id": "leaf-skill",
        "version": "1.0.0",
        "manifest_sha256": leaf["manifest_sha256"],
    }]))
    root = _publish(_manifest("root-skill", dependencies=[{
        "id": "middle-skill",
        "version": "1.0.0",
        "manifest_sha256": middle["manifest_sha256"],
    }]))

    first = skill_dependency_graph.resolve_skill_dependency_graph(
        "root-skill", "1.0.0", root["manifest_sha256"]
    )
    second = skill_dependency_graph.resolve_skill_dependency_graph(
        "root-skill", "1.0.0", root["manifest_sha256"]
    )
    assert [(node["id"], node["version"]) for node in first["nodes"]] == [
        ("leaf-skill", "1.0.0"),
        ("middle-skill", "1.0.0"),
        ("root-skill", "1.0.0"),
    ]
    assert first["graph_sha256"] == second["graph_sha256"]
    assert len(first["edges"]) == 2
    assert first["tools_authorized"] is False
    assert first["execution_enabled"] is False


def test_dependency_graph_fails_closed_for_digest_mismatch_and_unpublished(registry):
    draft = skill_registry.create_draft(validate_skill_manifest(_manifest("draft-skill")))
    with pytest.raises(skill_dependency_graph.SkillDependencyConflict, match="must be published"):
        skill_dependency_graph.resolve_skill_dependency_graph(
            "draft-skill", "1.0.0", draft["manifest_sha256"]
        )

    published = _publish(_manifest("published-skill"))
    with pytest.raises(skill_dependency_graph.SkillDependencyConflict, match="digest does not match"):
        skill_dependency_graph.resolve_skill_dependency_graph(
            "published-skill", "1.0.0", "0" * 64
        )


def test_dependency_graph_detects_cycles_even_for_corrupt_registry_data(monkeypatch):
    records = {
        ("alpha-skill", "1.0.0"): {
            "skill_id": "alpha-skill", "version": "1.0.0",
            "manifest_sha256": "a" * 64, "lifecycle_state": "published",
            "manifest": {
                "metadata": {"id": "alpha-skill", "version": "1.0.0", "name": "Alpha"},
                "spec": {"instructions": "Alpha", "trigger_phrases": ["alpha"], "dependencies": [{
                    "id": "beta-skill", "version": "1.0.0", "manifest_sha256": "b" * 64
                }]},
            },
        },
        ("beta-skill", "1.0.0"): {
            "skill_id": "beta-skill", "version": "1.0.0",
            "manifest_sha256": "b" * 64, "lifecycle_state": "published",
            "manifest": {
                "metadata": {"id": "beta-skill", "version": "1.0.0", "name": "Beta"},
                "spec": {"instructions": "Beta", "trigger_phrases": ["beta"], "dependencies": [{
                    "id": "alpha-skill", "version": "1.0.0", "manifest_sha256": "a" * 64
                }]},
            },
        },
    }
    monkeypatch.setattr(skill_registry, "get_version", lambda sid, ver: records[(sid, ver)])
    with pytest.raises(skill_dependency_graph.SkillDependencyCycle, match="cycle detected"):
        skill_dependency_graph.resolve_skill_dependency_graph(
            "alpha-skill", "1.0.0", "a" * 64
        )


def test_dependency_graph_rejects_conflicting_versions_and_enforces_bounds(registry):
    first = _publish(_manifest("shared-skill"))
    second_payload = _manifest("shared-skill", instructions="Version two instructions.")
    second_payload["metadata"]["version"] = "2.0.0"
    second = _publish(second_payload)
    left = _publish(_manifest("left-skill", dependencies=[{
        "id": "shared-skill", "version": "1.0.0",
        "manifest_sha256": first["manifest_sha256"],
    }]))
    root = _publish(_manifest("conflict-root", dependencies=[{
        "id": "left-skill", "version": "1.0.0",
        "manifest_sha256": left["manifest_sha256"],
    }, {
        "id": "shared-skill", "version": "2.0.0",
        "manifest_sha256": second["manifest_sha256"],
    }]))
    with pytest.raises(skill_dependency_graph.SkillDependencyConflict, match="conflicting versions"):
        skill_dependency_graph.resolve_skill_dependency_graph(
            "conflict-root", "1.0.0", root["manifest_sha256"]
        )

    with pytest.raises(skill_dependency_graph.SkillDependencyLimitExceeded, match="maximum 1 nodes"):
        skill_dependency_graph.resolve_skill_dependency_graph(
            "conflict-root", "1.0.0", root["manifest_sha256"], max_nodes=1
        )


def test_agent_binding_materializes_transitive_dependencies_in_topological_order(registry):
    base = _publish(_manifest("base-skill"))
    root = _publish(_manifest("root-skill", dependencies=[{
        "id": "base-skill", "version": "1.0.0",
        "manifest_sha256": base["manifest_sha256"],
    }]))
    agent = {
        "apiVersion": "taas.ai/v1alpha1",
        "kind": "Agent",
        "metadata": {"id": "dag-agent", "name": "DAG Agent", "version": "1.0.0"},
        "spec": {
            "model": {"provider": "huggingface", "model_id": "org/model"},
            "instructions": "Preserve requested outcomes.",
            "skill_refs": [{
                "id": "root-skill", "version": "1.0.0",
                "manifest_sha256": root["manifest_sha256"],
            }],
            "tool_allowlist": [],
            "resources": {"max_new_tokens": 512, "timeout_seconds": 90, "max_tool_calls": 0},
            "approval": {"require_human_approval": True, "require_assurance": True, "allow_side_effects": False},
        },
    }
    resolved, references = resolve_agent_skill_references(validate_agent_manifest(agent))
    assert [skill["id"] for skill in resolved["spec"]["skills"]] == [
        "base-skill", "root-skill"
    ]
    assert references[0]["dependency_graph_sha256"]
    assert references[0]["resolved_dependencies"][0]["id"] == "base-skill"
    assert references[0]["resolved_dependencies"][0]["manifest_sha256"] == base["manifest_sha256"]
