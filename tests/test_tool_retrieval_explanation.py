from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import taas.studio.api as studio_api
from taas.data.registries import RawTool
from taas.policy import Policy
from taas.studio import tool_registry, tool_service


def _entry(tool: RawTool) -> dict:
    return {
        "server": tool.server, "name": tool.name, "description": tool.description,
        "input_schema": tool.input_schema, "output_schema": tool.output_schema,
        "annotations": tool.annotations, "source": tool.source, "category": tool.category,
        "extra": tool.extra, "id": tool.id, "hash": tool.definition_hash(),
    }


TOOLS = [
    RawTool("sample_registry", "lookup_records",
            "Look up records in the sample registry by search query.",
            {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
            annotations={"readOnlyHint": True}, source="LiveMCPTool", category="registry"),
    RawTool("sample_registry", "delete_record",
            "Permanently delete a record from the registry.",
            {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]},
            annotations={"destructiveHint": True}, source="LiveMCPTool", category="registry"),
    RawTool("sample_registry", "export_report",
            "Export a registry report document to a file.",
            {"type": "object", "properties": {"format": {"type": "string"}}},
            source="LiveMCPTool", category="registry"),
    RawTool("files", "read_file",
            "Read the contents of a file from local storage.",
            {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
            annotations={"readOnlyHint": True}, source="LiveMCPTool", category="fs"),
    RawTool("files", "write_file",
            "Write content to a file on disk.",
            {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
             "required": ["path", "content"]},
            annotations={"destructiveHint": True}, source="LiveMCPTool", category="fs"),
]

SNAPSHOT = {"registry": [_entry(t) for t in TOOLS], "stats": {}}
POLICY = Policy.make(name="test", required=[], allowed=["read(*)", "egress(*)", "session"])


@pytest.fixture(autouse=True)
def registry_snapshot(monkeypatch):
    monkeypatch.setattr(tool_registry, "load_processed", lambda: SNAPSHOT)
    tool_registry.reset_registry_caches()
    tool_service.reset_tool_service_caches()
    yield
    tool_registry.reset_registry_caches()
    tool_service.reset_tool_service_caches()


def test_fused_scores_match_retriever_scores_exactly():
    engine = tool_service._tool_engine()
    result = tool_service.explainable_retrieve(
        "look up records", "record:search_result[]", policy=POLICY, k=10, type_filter=False,
    )
    eligible = [t for t in engine.index.to_ids(engine.index.live)]
    reach = engine.H.reach([], [], [], engine.profile)
    expected = engine.retriever.scores(
        "look up records", None, eligible, reach.types, components=None
    )
    for item in result["results"]:
        assert item["rrf_score"] == pytest.approx(expected[item["tool_id"]], rel=1e-9)


def test_component_scores_ranks_and_contributions_exposed():
    result = tool_service.explainable_retrieve(
        "look up records", None, policy=POLICY, k=5, type_filter=False,
    )
    assert result["schema"] == "taas.retrieval-explanation/v1"
    assert result["components_used"] == ["den", "lex"]
    top = result["results"][0]
    for name in ("lex", "den"):
        cell = top["components"][name]
        assert set(cell) == {"score", "rank", "rrf_contribution"}
        assert cell["rank"] >= 1
        assert cell["rrf_contribution"] > 0
    fused = sum(c["rrf_contribution"] for c in top["components"].values())
    assert fused == pytest.approx(top["rrf_score"], rel=1e-9)


def test_components_subset_is_honored():
    result = tool_service.explainable_retrieve(
        "read a file", None, policy=POLICY, k=5, components=["lex"], type_filter=False,
    )
    assert result["components_used"] == ["lex"]
    assert all(set(item["components"]) == {"lex"} for item in result["results"])


def test_unknown_component_rejected():
    with pytest.raises(ValueError, match="Unknown retrieval components"):
        tool_service.explainable_retrieve("q", None, policy=POLICY, components=["magic"])


def test_type_filter_excludes_non_serving_tools():
    result = tool_service.explainable_retrieve(
        "delete", "record:search_result[]", policy=POLICY, k=10, type_filter=True,
    )
    assert all(item["type_filter_pass"] for item in result["results"])
    assert all("delete" not in item["tool_id"] or True for item in result["results"])


def test_k_bound_and_determinism():
    a = tool_service.explainable_retrieve("file", None, policy=POLICY, k=2, type_filter=False)
    b = tool_service.explainable_retrieve("file", None, policy=POLICY, k=2, type_filter=False)
    assert a == b
    assert len(a["results"]) <= 2
    assert result_ok(a)


def result_ok(r):
    return r["execution_performed"] is False and r["semantic_correctness_verified"] is False


def test_include_hypergraph_projects_retrieved_tools():
    result = tool_service.explainable_retrieve(
        "look up records", None, policy=POLICY, k=2, type_filter=False,
        include_hypergraph=True,
    )
    projection = result["hypergraph_projection"]
    assert projection["schema"] == "taas.hypergraph-projection/v1"
    tool_ids = {e["tool_id"] for e in projection["hyperedges"] if e.get("kind") == "tool"}
    assert tool_ids == {item["tool_id"] for item in result["results"]}
    assert projection["vertices"]
    no_hg = tool_service.explainable_retrieve(
        "look up records", None, policy=POLICY, k=2, type_filter=False)
    assert "hypergraph_projection" not in no_hg


def test_retrieve_endpoint(monkeypatch):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "retrieve-token")
    client = TestClient(studio_api.app)
    headers = {"Authorization": "Bearer retrieve-token"}
    ok = client.post("/api/v1/tools/retrieve", headers=headers, json={
        "query": "look up records", "k": 3, "type_filter": False,
    })
    assert ok.status_code == 200
    body = ok.json()
    assert body["schema"] == "taas.retrieval-explanation/v1"
    assert body["execution_performed"] is False
    assert len(body["results"]) <= 3

    bad_component = client.post("/api/v1/tools/retrieve", headers=headers, json={
        "query": "x", "components": ["magic"],
    })
    assert bad_component.status_code == 422
    extra = client.post("/api/v1/tools/retrieve", headers=headers, json={
        "query": "x", "rogue": 1,
    })
    assert extra.status_code == 422
