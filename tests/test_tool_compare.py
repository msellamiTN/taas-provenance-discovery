from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import taas.studio.api as studio_api
from taas.policy import Policy
from taas.studio import tool_registry, tool_service
from tests.test_tool_retrieval_explanation import TOOLS, SNAPSHOT


@pytest.fixture(autouse=True)
def registry_snapshot(monkeypatch):
    monkeypatch.setattr(tool_registry, "load_processed", lambda: SNAPSHOT)
    tool_registry.reset_registry_caches()
    tool_service.reset_tool_service_caches()
    yield
    tool_registry.reset_registry_caches()
    tool_service.reset_tool_service_caches()


IDS = ["sample_registry::lookup_records", "sample_registry::delete_record", "files::read_file"]


def test_compare_returns_capability_and_differences():
    result = tool_service.compare_tools(IDS)
    assert result["schema"] == "taas.tool-compare/v1"
    assert result["summary"]["compared"] == 3
    assert set(result["tools"]) == set(IDS)
    for t in IDS:
        assert result["tools"][t]["capability"]["output_type"]
        assert result["tools"][t]["definition_hash_verified"] is True
    # tools diverge on effects and class, so differences is populated
    assert result["differences"]
    assert result["execution_performed"] is False
    assert result["comparison_semantics"].startswith("structural")


def test_compare_unknown_ids_reported():
    result = tool_service.compare_tools([IDS[0], "ghost::missing"])
    assert result["unknown_tool_ids"] == ["ghost::missing"]
    assert result["summary"]["compared"] == 1


def test_compare_eligibility_verdicts():
    policy = Policy.make("t", required={"read_only"}, lmin=0.5)
    result = tool_service.compare_tools(IDS, policy=policy)
    assert result["eligibility"] is not None
    assert result["eligibility"]["sample_registry::lookup_records"]["eligible"] is True


def test_compare_retrieval_scores_parity_with_retriever():
    from taas.types import parse_type
    engine = tool_service._tool_engine()
    reach = engine.H.reach([], [], [], engine.profile)
    goal_out = parse_type("record")
    expected = engine.retriever.scores("read records", goal_out, IDS, reach)
    result = tool_service.compare_tools(IDS, query="read records", goal_out="record")
    retrieval = result["retrieval"]
    assert retrieval is not None
    for t in IDS:
        assert retrieval["scores"][t]["fused"] == pytest.approx(expected[t])
        assert set(retrieval["scores"][t]["components"]) == {"lex", "den", "str"}


def test_compare_endpoint(monkeypatch):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "cmp-token")
    client = TestClient(studio_api.app)
    headers = {"Authorization": "Bearer cmp-token"}

    ok = client.post("/api/v1/tools/compare", headers=headers, json={
        "tool_ids": IDS[:2], "query": "read records"})
    assert ok.status_code == 200
    body = ok.json()
    assert body["schema"] == "taas.tool-compare/v1"
    assert body["execution_performed"] is False

    dup = client.post("/api/v1/tools/compare", headers=headers,
                      json={"tool_ids": [IDS[0], IDS[0]]})
    assert dup.status_code == 422

    malformed = client.post("/api/v1/tools/compare", headers=headers,
                            json={"tool_ids": ["nocolon", IDS[0]]})
    assert malformed.status_code == 422

    too_few = client.post("/api/v1/tools/compare", headers=headers,
                          json={"tool_ids": [IDS[0]]})
    assert too_few.status_code == 422

    extra = client.post("/api/v1/tools/compare", headers=headers,
                        json={"tool_ids": IDS[:2], "rogue": True})
    assert extra.status_code == 422
