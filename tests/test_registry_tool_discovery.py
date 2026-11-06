from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from types import SimpleNamespace

import taas.studio.api as studio_api
from taas.studio import tool_registry, tool_service
from tests.test_tool_retrieval_explanation import TOOLS, SNAPSHOT

GOAL_SPEC = {
    "prompt": "List records", "prompt_inputs": ["text"],
    "goals": [{"id": "g1", "class": "retrieve", "in": ["query"],
               "out": "record[]", "eff": ["read(records)"], "sigma": "data",
               "deps": [], "desc": "List records"}],
}


@pytest.fixture(autouse=True)
def registry_snapshot(monkeypatch):
    monkeypatch.setattr(tool_registry, "load_processed", lambda: SNAPSHOT)
    tool_registry.reset_registry_caches()
    tool_service.reset_tool_service_caches()
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "disc-token")
    yield
    tool_registry.reset_registry_caches()
    tool_service.reset_tool_service_caches()


@pytest.fixture
def client():
    return TestClient(studio_api.app)


@pytest.fixture
def headers():
    return {"Authorization": "Bearer disc-token"}


class FakeEngine:
    last_contracts = None

    def __init__(self, contracts, profile, trust, cfg):
        FakeEngine.last_contracts = list(contracts)
        self.H = SimpleNamespace()
        self.composer = SimpleNamespace(model_edges=lambda goals: [])

    def discover(self, spec, policy):
        return SimpleNamespace(
            spec=spec, gap=SimpleNamespace(gap=[], rho=0.0),
            compose=SimpleNamespace(reachability=None, candidates=[], regime="exact", stats={}),
            certificate=None, counterexample=None, toolkit=None, time_s=0.01, abstained=True,
        )


def test_registry_tool_ids_resolve_real_contracts(client, headers, monkeypatch):
    monkeypatch.setattr(studio_api, "DiscoveryEngine", FakeEngine)
    response = client.post("/api/v1/objectives/discover", headers=headers, json={
        "goal_spec": GOAL_SPEC,
        "human_review_confirmed": True,
        "registry_tool_ids": ["sample_registry::lookup_records"],
    })
    assert response.status_code == 200
    body = response.json()
    assert body["tool_source"] == "registry_tool_ids"
    assert body["execution_performed"] is False
    assert FakeEngine.last_contracts is not None
    assert all(t.tool == "sample_registry::lookup_records" for t in FakeEngine.last_contracts)


def test_request_tools_source_label_preserved(client, headers, monkeypatch):
    monkeypatch.setattr(studio_api, "DiscoveryEngine", FakeEngine)
    response = client.post("/api/v1/objectives/discover", headers=headers, json={
        "goal_spec": GOAL_SPEC,
        "human_review_confirmed": True,
        "tools": [{"server": "s", "name": "t", "input_schema": {"type": "object", "properties": {}}}],
    })
    assert response.status_code == 200
    assert response.json()["tool_source"] == "request_tools"


def test_unresolved_registry_id_rejected_422(client, headers):
    response = client.post("/api/v1/objectives/discover", headers=headers, json={
        "goal_spec": GOAL_SPEC,
        "human_review_confirmed": True,
        "registry_tool_ids": ["ghost::missing", "sample_registry::lookup_records"],
    })
    assert response.status_code == 422
    assert "ghost::missing" in str(response.json())


def test_malformed_registry_id_rejected(client, headers):
    response = client.post("/api/v1/objectives/discover", headers=headers, json={
        "goal_spec": GOAL_SPEC,
        "human_review_confirmed": True,
        "registry_tool_ids": ["no-separator-here"],
    })
    assert response.status_code == 422


def test_both_sources_rejected(client, headers):
    response = client.post("/api/v1/objectives/discover", headers=headers, json={
        "goal_spec": GOAL_SPEC,
        "human_review_confirmed": True,
        "tools": [{"server": "s", "name": "t", "input_schema": {"type": "object", "properties": {}}}],
        "registry_tool_ids": ["sample_registry::lookup_records"],
    })
    assert response.status_code == 422


def test_empty_sources_rejected(client, headers):
    response = client.post("/api/v1/objectives/discover", headers=headers, json={
        "goal_spec": GOAL_SPEC,
        "human_review_confirmed": True,
    })
    assert response.status_code == 422
