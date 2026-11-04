import pytest
from fastapi.testclient import TestClient

from taas.contracts import make_contract
from taas.data.registries import RawTool
from taas.effects import parse_effects
from taas.experiments.baseline_catalog import (
    baseline_index, baselines_for_experiment, load_baseline_catalog,
    validate_baseline_selection,
)
from taas.experiments.baseline_runner import run_baseline
from taas.experiments.registry_baselines import run_effect_baseline, run_typing_baseline
from taas.policy import Policy
from taas.retrieval import HybridRetriever
from taas.goals import parse_goal_spec
from taas.studio.experiments_api import app


client = TestClient(app)


def _fixture():
    contracts = [
        make_contract("reviews::search_reviews", {"query": "query"}, "record:review",
                      ["read(reviews)"], tool_class="search", description="Search customer reviews"),
        make_contract("reviews::list_reviews", {"query": "query"}, "record:review",
                      ["read(reviews)"], tool_class="search", description="List review records"),
        make_contract("reports::write_summary", {"reviews": "record:review"}, "text",
                      ["write(reports)"], tool_class="write", description="Write review summary"),
        make_contract("web::search_web", {"query": "query"}, "document:web",
                      ["egress(*)"], tool_class="search", description="Search web pages"),
    ]
    retriever = HybridRetriever().fit(contracts)
    spec = parse_goal_spec({
        "prompt": "Search customer reviews",
        "prompt_inputs": ["query"],
        "goals": [{
            "id": "g1", "class": "search", "in": ["query"],
            "out": "record:review", "eff": ["read(reviews)"],
            "sigma": "data", "desc": "Search customer reviews",
        }],
    })
    raw = RawTool(
        server="reviews", name="search_reviews", description="Search customer reviews",
        input_schema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
        output_schema={"type": "object"},
        annotations={"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    )
    return contracts, retriever, spec, raw


def test_baseline_catalog_all_experiment_references_resolve():
    catalog = load_baseline_catalog()
    index = baseline_index(catalog)
    assert len(index) == 31
    for experiment_id in [f"E{i}" for i in range(1, 23)]:
        baselines_for_experiment(experiment_id)


def test_experiment_baseline_selection_is_scoped():
    selected = validate_baseline_selection("E8", ["bm25", "mcp_zero"])
    assert [x["id"] for x in selected] == ["bm25", "mcp_zero"]
    with pytest.raises(ValueError):
        validate_baseline_selection("E8", ["autotool_adapted"])


def test_typing_and_effect_registry_baselines_do_not_read_evaluator_labels():
    _, _, _, raw = _fixture()
    structural = run_typing_baseline("typing_structural", [raw])
    lexical = run_typing_baseline("typing_schema_lexical", [raw])
    declared = run_effect_baseline("effects_declared", [raw])
    inferred = run_effect_baseline("effects_lexical", [raw])
    assert structural["evaluator_labels_read"] is False
    assert lexical["evaluator_labels_read"] is False
    assert declared["predictions"][0]["effects"] == ["read(*)"]
    assert "egress(*)" in inferred["predictions"][0]["effects"] or "read(*)" in inferred["predictions"][0]["effects"]


def test_probe_baseline_is_blocked_until_isolated_runtime_exists():
    _, _, _, raw = _fixture()
    result = run_effect_baseline("effects_probe", [raw])
    assert result["status"] == "blocked_runtime_probe_not_implemented"
    assert result["prediction_count"] == 0


@pytest.mark.parametrize("baseline_id", [
    "all_tools", "bm25", "dense_lsa", "rag_mcp", "mcp_zero",
    "per_subtask", "colt_adapted", "toolscope_adapted", "cmtf_adapted",
])
def test_executable_retrieval_baseline_adapters_return_typed_result(baseline_id):
    contracts, retriever, spec, _ = _fixture()
    scenes = [{"split": "train", "tools": ["reviews::search_reviews", "reviews::list_reviews"]}]
    result = run_baseline(
        baseline_id, retriever, spec, spec.prompt, list(retriever.contracts), top_k=3,
        policy=Policy.make("read-only", allowed=["read(*)"]),
        training_scenes=scenes,
        parameters={"merge_threshold": 0.99},
    )
    assert result.baseline_id == baseline_id
    assert result.status == "completed"
    assert all(t in retriever.contracts for t in result.selected_tools)


def test_colt_adapter_rejects_evaluation_scene_data():
    _, retriever, spec, _ = _fixture()
    with pytest.raises(ValueError):
        run_baseline("colt_adapted", retriever, spec, spec.prompt, list(retriever.contracts),
                     training_scenes=[{"split": "test", "tools": ["reviews::search_reviews"]}])


def test_toolscope_adapter_preserves_original_tool_ids():
    _, retriever, spec, _ = _fixture()
    result = run_baseline("toolscope_adapted", retriever, spec, spec.prompt,
                          list(retriever.contracts), top_k=3, parameters={"merge_threshold": 1.0})
    assert set(result.selected_tools).issubset(set(retriever.contracts))
    assert result.details["provider_tool_ids_preserved"] is True


def test_cmtf_reports_stepwise_frontier_and_cumulative_union():
    _, retriever, spec, _ = _fixture()
    result = run_baseline("cmtf_adapted", retriever, spec, spec.prompt,
                          list(retriever.contracts), policy=Policy.make("read", allowed=["read(*)"]))
    assert result.status == "completed"
    assert result.stepwise_frontiers
    assert "cumulative_union_reported" in result.details


def test_autotool_requires_hash_revalidated_confirmed_trajectories():
    contracts, retriever, spec, _ = _fixture()
    tool = "reviews::search_reviews"
    traj = [{
        "query": spec.prompt, "tool_ids": [tool], "confirmed": True,
        "registry_hash": "registry-v1", "policy_hash": "policy-v1",
        "tool_hashes": {tool: retriever.contracts[tool].h},
    }]
    result = run_baseline(
        "autotool_adapted", retriever, spec, spec.prompt, list(retriever.contracts),
        trajectories=traj, registry_hash="registry-v1", policy_hash="policy-v1",
        tool_hashes={t: c.h for t, c in retriever.contracts.items()},
    )
    assert result.status == "completed"
    assert tool in result.selected_tools
    assert result.details["tool_definition_hash_revalidated"] is True


def test_studio_exposes_baseline_catalog_and_experiment_specific_set(monkeypatch):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    headers = {"Authorization": "Bearer test-token"}
    catalog = client.get("/api/v1/baselines/catalog", headers=headers)
    assert catalog.status_code == 200
    assert catalog.json()["total"] == 31
    e8 = client.get("/api/v1/experiments/catalog/E8/baselines", headers=headers)
    assert e8.status_code == 200
    ids = {x["id"] for x in e8.json()["baselines"]}
    assert {"bm25", "dense_lsa", "mcp_zero", "colt_adapted", "toolscope_adapted", "cmtf_adapted"} <= ids
    detail = client.get("/api/v1/baselines/catalog/mcp_zero", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["implementation"] == "partial_adapter"


def test_run_validation_rejects_baseline_not_in_experiment(monkeypatch):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    headers = {"Authorization": "Bearer test-token"}
    response = client.post("/api/v1/experiments/validate", headers=headers, json={
        "experiment_id": "E8", "variant": "Full_PaMCP",
        "dataset_snapshot": {"name": "MCPToolBench++", "version_or_hash": "sha256:abc"},
        "split": "test", "parameters": {}, "seeds": [1], "baseline": "autotool_adapted",
    })
    assert response.status_code == 422


def test_run_validation_accepts_baseline_for_experiment(monkeypatch):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    headers = {"Authorization": "Bearer test-token"}
    response = client.post("/api/v1/experiments/validate", headers=headers, json={
        "experiment_id": "E8", "variant": "Full_PaMCP",
        "dataset_snapshot": {"name": "MCPToolBench++", "version_or_hash": "sha256:abc"},
        "split": "test", "parameters": {}, "seeds": [1], "baseline": "bm25",
    })
    assert response.status_code == 200
    assert response.json()["configuration"]["baseline"] == "bm25"
