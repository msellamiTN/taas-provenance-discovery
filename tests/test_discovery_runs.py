from __future__ import annotations

import json
import os
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import taas.studio.api as studio_api
from taas.studio import discovery_runs, tool_registry, tool_service
from .test_registry_tool_discovery import GOAL_SPEC, FakeEngine
from .test_tool_retrieval_explanation import TOOLS, SNAPSHOT


@pytest.fixture(autouse=True)
def env(monkeypatch, tmp_path):
    monkeypatch.setattr(tool_registry, "load_processed", lambda: SNAPSHOT)
    tool_registry.reset_registry_caches()
    tool_service.reset_tool_service_caches()
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "runs-token")
    monkeypatch.setenv("TAAS_DISCOVERY_RUNS_PATH", str(tmp_path / "runs.sqlite3"))
    monkeypatch.setattr(studio_api, "DiscoveryEngine", FakeEngine)
    yield
    tool_registry.reset_registry_caches()
    tool_service.reset_tool_service_caches()


@pytest.fixture
def client():
    return TestClient(studio_api.app)


@pytest.fixture
def headers():
    return {"Authorization": "Bearer runs-token"}


def test_persist_then_read_back(client, headers):
    response = client.post("/api/v1/objectives/discover", headers=headers, json={
        "goal_spec": GOAL_SPEC,
        "human_review_confirmed": True,
        "registry_tool_ids": ["sample_registry::lookup_records"],
    })
    assert response.status_code == 200
    body = response.json()
    run_id = body["discovery_run_id"]
    assert run_id
    assert body["discovery_run_persisted"] is True

    listing = client.get("/api/v1/discovery/runs", headers=headers)
    assert listing.status_code == 200
    runs = listing.json()["runs"]
    assert any(r["run_id"] == run_id for r in runs)
    assert listing.json()["record_semantics"].endswith("not_execution")

    fetched = client.get(f"/api/v1/discovery/runs/{run_id}", headers=headers)
    assert fetched.status_code == 200
    run = fetched.json()
    assert run["schema"] == "taas.discovery-run/v1"
    assert run["tool_source"] == "registry_tool_ids"
    assert run["tool_ids"] == ["sample_registry::lookup_records"]
    assert run["tool_definition_hashes"]["sample_registry::lookup_records"]
    assert run["execution_record"] is False


def test_listing_filters(client, headers):
    for _ in range(2):
        client.post("/api/v1/objectives/discover", headers=headers, json={
            "goal_spec": GOAL_SPEC, "human_review_confirmed": True,
            "tools": [{"server": "s", "name": "t",
                       "input_schema": {"type": "object", "properties": {}}}],
        })
    by_status = client.get("/api/v1/discovery/runs?status=abstained", headers=headers)
    assert by_status.status_code == 200
    assert all(r["status"] == "abstained" for r in by_status.json()["runs"])
    by_tool = client.get(
        "/api/v1/discovery/runs?tool_id=s::t", headers=headers)
    assert by_tool.status_code == 200
    assert by_tool.json()["total_matching"] >= 2


def test_unknown_run_404(client, headers):
    response = client.get("/api/v1/discovery/runs/deadbeef", headers=headers)
    assert response.status_code == 404


def test_bounded_retention(monkeypatch, tmp_path):
    monkeypatch.setenv("TAAS_DISCOVERY_RUNS_PATH", str(tmp_path / "r.sqlite3"))
    monkeypatch.setenv("TAAS_DISCOVERY_RUNS_MAX_ROWS", "3")
    for i in range(5):
        discovery_runs.record_discovery_run(
            goal_spec={"i": i}, request={"i": i}, tool_source="request_tools",
            tool_ids=[f"s::t{i}"], tool_hashes={}, policy_fingerprint=None,
            status="abstained", certificate=None, hypergraph_projection=None)
    listing = discovery_runs.list_discovery_runs(limit=50)
    assert listing["total_matching"] == 3
    ids = {r["tool_ids"][0] for r in listing["runs"]}
    assert ids == {"s::t2", "s::t3", "s::t4"}


def test_request_fingerprint_changes_with_input(tmp_path, monkeypatch):
    monkeypatch.setenv("TAAS_DISCOVERY_RUNS_PATH", str(tmp_path / "r2.sqlite3"))
    a = discovery_runs.record_discovery_run(
        goal_spec={"a": 1}, request={"a": 1}, tool_source="request_tools",
        tool_ids=["s::t"], tool_hashes={}, policy_fingerprint=None,
        status="abstained", certificate=None, hypergraph_projection=None)
    b = discovery_runs.record_discovery_run(
        goal_spec={"a": 2}, request={"a": 2}, tool_source="request_tools",
        tool_ids=["s::t"], tool_hashes={}, policy_fingerprint=None,
        status="abstained", certificate=None, hypergraph_projection=None)
    ra = discovery_runs.get_discovery_run(a)
    rb = discovery_runs.get_discovery_run(b)
    assert ra["request_sha256"] != rb["request_sha256"]
    assert ra["goal_spec_sha256"] != rb["goal_spec_sha256"]
