from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from taas.hypergraph_projection import PROJECTION_SCHEMA, project_skill_dependency_graph
from taas.studio import skill_registry
from taas.studio.skill_spec import validate_skill_manifest
import taas.studio.api as studio_api


def _skill(skill_id: str, dependencies=None):
    spec = {"instructions": f"Guidance for {skill_id}.", "trigger_phrases": [skill_id], "tags": ["test"]}
    if dependencies is not None:
        spec["dependencies"] = dependencies
    return {
        "apiVersion": "taas.ai/v1alpha1",
        "kind": "Skill",
        "metadata": {"id": skill_id, "name": skill_id.title(), "version": "1.0.0"},
        "spec": spec,
    }


def _publish(payload):
    manifest = validate_skill_manifest(payload)
    created = skill_registry.create_draft(manifest, actor="hypergraph-test")
    skill_registry.transition(created["skill_id"], created["version"], "validated", actor="reviewer")
    return skill_registry.transition(created["skill_id"], created["version"], "published", actor="publisher")


@pytest.fixture
def registry(monkeypatch, tmp_path):
    monkeypatch.setenv("TAAS_SKILL_REGISTRY_PATH", str(tmp_path / "skills.sqlite3"))


def test_skill_dependency_projection_preserves_exact_pins_and_direction():
    root = {"id": "root-skill", "version": "1.0.0", "manifest_sha256": "a" * 64}
    dependency = {"id": "base-skill", "version": "2.0.0", "manifest_sha256": "b" * 64}
    graph = {
        "root": root,
        "nodes": [
            {"id": "base-skill", "version": "2.0.0", "manifest_sha256": "b" * 64,
             "lifecycle_state": "published", "name": "Base Skill", "source": "skill_registry"},
            {"id": "root-skill", "version": "1.0.0", "manifest_sha256": "a" * 64,
             "lifecycle_state": "published", "name": "Root Skill", "source": "skill_registry"},
        ],
        "edges": [{"from": root, "to": dependency, "relation": "depends_on"}],
        "topological_order": [dependency, root],
        "graph_sha256": "c" * 64,
        "semantic_correctness_verified": False,
        "tools_authorized": False,
        "execution_enabled": False,
    }
    projection = project_skill_dependency_graph(graph)
    assert projection["schema"] == PROJECTION_SCHEMA
    assert projection["projection_domain"] == "skill_dependency_dag"
    assert projection["summary"]["skill_count"] == 2
    assert projection["summary"]["dependency_count"] == 1
    edge = projection["hyperedges"][0]
    assert edge["kind"] == "skill_dependency"
    assert edge["source_vertex"] == "skill:root-skill@1.0.0"
    assert edge["target_vertex"] == "skill:base-skill@2.0.0"
    assert edge["authorization_effect"] == "none"
    assert edge["execution_effect"] == "none"
    root_node = next(node for node in projection["vertices"] if node["root"])
    assert root_node["manifest_sha256"] == "a" * 64
    assert projection["graph_metadata"]["graph_sha256"] == "c" * 64
    assert projection["graph_metadata"]["tools_authorized"] is False


def test_skill_dependency_projection_rejects_unknown_edge_nodes():
    graph = {
        "root": {"id": "root", "version": "1.0.0", "manifest_sha256": "a" * 64},
        "nodes": [{"id": "root", "version": "1.0.0", "manifest_sha256": "a" * 64}],
        "edges": [{"from": {"id": "root", "version": "1.0.0"},
                   "to": {"id": "missing", "version": "1.0.0"}, "relation": "depends_on"}],
        "topological_order": [],
        "graph_sha256": "b" * 64,
    }
    with pytest.raises(ValueError, match="unknown or identical"):
        project_skill_dependency_graph(graph)


def test_authenticated_skill_hypergraph_projection_api(registry, monkeypatch):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "skill-hypergraph-token")
    base = _publish(_skill("hypergraph-base"))
    root = _publish(_skill("hypergraph-root", dependencies=[{
        "id": "hypergraph-base", "version": "1.0.0",
        "manifest_sha256": base["manifest_sha256"],
    }]))
    client = TestClient(studio_api.app)
    endpoint = "/api/v1/hypergraph/skills/hypergraph-root/versions/1.0.0"

    assert client.get(endpoint).status_code == 401
    response = client.get(endpoint, headers={"Authorization": "Bearer skill-hypergraph-token"})
    assert response.status_code == 200
    body = response.json()
    projection = body["hypergraph_projection"]
    assert body["projection_source"] == "taas_core_skill_dependency_resolver"
    assert [node["skill_id"] for node in projection["vertices"]] == [
        "hypergraph-base", "hypergraph-root"
    ]
    assert projection["summary"]["dependency_count"] == 1
    assert body["tools_authorized"] is False
    assert body["execution_enabled"] is False
