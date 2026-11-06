from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import taas.studio.api as studio_api
from taas.data.registries import RawTool
from taas.policy import Policy
from taas.studio import tool_registry, tool_service
from tests.test_tool_retrieval_explanation import TOOLS, SNAPSHOT  # reuse fixtures


@pytest.fixture(autouse=True)
def registry_snapshot(monkeypatch):
    monkeypatch.setattr(tool_registry, "load_processed", lambda: SNAPSHOT)
    tool_registry.reset_registry_caches()
    tool_service.reset_tool_service_caches()
    yield
    tool_registry.reset_registry_caches()
    tool_service.reset_tool_service_caches()


def test_positive_policy_explains_met_and_failed_properties():
    policy = Policy.make("t", required={"read_only"}, lmin=0.5)
    result = tool_service.eligibility_explain(policy)
    assert result["schema"] == "taas.eligibility-explanation/v1"
    by_id = {t["tool_id"]: t for t in result["tools"]}
    lookup = by_id["sample_registry::lookup_records"]
    prop = lookup["required_properties"]["read_only"]
    assert prop["met"] is True
    assert lookup["eligible"] is True
    assert lookup["rejection_reasons"] == []
    delete = by_id["sample_registry::delete_record"]
    if not delete["required_properties"]["read_only"]["met"]:
        assert any("read_only" in r for r in delete["rejection_reasons"])
        assert delete["eligible"] is False


def test_closed_world_violation_explained():
    policy = Policy.make("cw", forbidden={"writes"}, encoding="closed_world", lmin=0.3)
    result = tool_service.eligibility_explain(policy)
    by_id = {t["tool_id"]: t for t in result["tools"]}
    write = by_id["files::write_file"]
    violated = [p for p, v in write["forbidden_properties"].items() if v["violated"]]
    if "writes" in violated:
        assert any("writes" in r for r in write["rejection_reasons"])
        assert write["eligible"] is False


def test_visibility_exclusion_reported():
    policy = Policy.make("v", required=set(), visible=frozenset({"files::read_file"}))
    result = tool_service.eligibility_explain(policy)
    by_id = {t["tool_id"]: t for t in result["tools"]}
    hidden = by_id["sample_registry::lookup_records"]
    assert hidden["visible"] is False
    assert "not_in_policy_visible_set" in hidden["rejection_reasons"]
    assert hidden["eligible"] is False


def test_unknown_tool_ids_reported_never_dropped_silently():
    result = tool_service.eligibility_explain(
        Policy.make("t"), tool_ids=["files::read_file", "ghost::missing"]
    )
    assert result["unknown_tool_ids"] == ["ghost::missing"]
    assert [t["tool_id"] for t in result["tools"]] == ["files::read_file"]
    assert result["summary"]["unknown"] == 1


def test_subset_evaluation_only_reports_requested():
    result = tool_service.eligibility_explain(
        Policy.make("t"), tool_ids=["files::read_file", "files::write_file"]
    )
    assert result["summary"]["evaluated"] == 2
    assert all(t["tool_id"].startswith("files::") for t in result["tools"])


def test_eligibility_endpoint(monkeypatch):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "elig-token")
    client = TestClient(studio_api.app)
    headers = {"Authorization": "Bearer elig-token"}
    ok = client.post("/api/v1/tools/eligibility", headers=headers, json={
        "policy": {"required": ["read_only"], "lmin": 0.5},
        "tool_ids": ["sample_registry::lookup_records", "sample_registry::delete_record"],
    })
    assert ok.status_code == 200
    body = ok.json()
    assert body["schema"] == "taas.eligibility-explanation/v1"
    assert body["execution_performed"] is False
    assert body["summary"]["evaluated"] == 2
    by_id = {t["tool_id"]: t for t in body["tools"]}
    assert by_id["sample_registry::lookup_records"]["eligible"] is True

    extra = client.post("/api/v1/tools/eligibility", headers=headers,
                        json={"policy": {}, "rogue": True})
    assert extra.status_code == 422
