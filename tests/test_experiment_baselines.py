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
    }, prompt="Search customer reviews")
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


def test_baseline_preview_runs_retrieval_without_evaluator_labels(monkeypatch):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    headers = {"Authorization": "Bearer test-token"}
    response = client.post("/api/v1/baselines/preview", headers=headers, json={
        "experiment_id": "E8",
        "baseline_ids": ["bm25", "rag_mcp"],
        "goal_spec": {
            "prompt": "Search customer reviews",
            "prompt_inputs": ["query"],
            "goals": [{
                "id": "g1", "class": "search", "in": ["query"],
                "out": "record:review", "eff": ["read(reviews)"],
                "sigma": "data", "desc": "Search customer reviews",
            }],
        },
        "tools": [
            {
                "server": "reviews", "name": "search_reviews",
                "description": "Search customer reviews",
                "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
                "output_schema": {"type": "object"},
                "annotations": {"readOnlyHint": True},
            },
            {
                "server": "reviews", "name": "list_reviews",
                "description": "List review records",
                "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
                "output_schema": {"type": "object"},
                "annotations": {"readOnlyHint": True},
            },
            {
                "server": "web", "name": "search_web",
                "description": "Search web pages",
                "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
                "output_schema": {"type": "object"},
            },
        ],
        "top_k": 2,
    })
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["baseline_count"] == 2
    assert data["evaluator_labels_accessed"] is False
    assert data["mcp_tools_executed"] is False
    assert [x["result"]["baseline_id"] for x in data["results"]] == ["bm25", "rag_mcp"]
    assert all(x["result"]["status"] == "completed" for x in data["results"])


def test_baseline_preview_executes_e2_typing_controls(monkeypatch):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    headers = {"Authorization": "Bearer test-token"}
    response = client.post("/api/v1/baselines/preview", headers=headers, json={
        "experiment_id": "E2",
        "baseline_ids": ["typing_structural", "typing_schema_lexical"],
        "goal_spec": {
            "prompt": "Find reviews",
            "goals": [{
                "id": "g1", "class": "search", "in": ["query"],
                "out": "record", "sigma": "data", "desc": "Find reviews",
            }],
        },
        "tools": [{
            "server": "reviews", "name": "search_reviews",
            "description": "Search customer reviews",
            "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}},
            "output_schema": {"type": "object"},
        }],
    })
    assert response.status_code == 200, response.text
    results = response.json()["results"]
    assert results[0]["result"]["status"] == "completed"
    assert results[0]["result"]["evaluator_labels_read"] is False
    assert results[0]["result"]["predictions"][0]["inputs"]["query"] == "text"


def test_baseline_preview_rejects_baseline_outside_experiment(monkeypatch):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    headers = {"Authorization": "Bearer test-token"}
    response = client.post("/api/v1/baselines/preview", headers=headers, json={
        "experiment_id": "E8", "baseline_ids": ["autotool_adapted"],
        "goal_spec": {"goals": [{"id": "g1", "class": "search", "out": "text", "desc": "Search"}]},
        "tools": [{"server": "s", "name": "t", "description": "tool", "input_schema": {}}],
    })
    assert response.status_code == 422


def test_existing_taas_studio_mounts_baseline_routes(monkeypatch):
    from taas.studio.api import app as core_app
    core_client = TestClient(core_app)
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    headers = {"Authorization": "Bearer test-token"}
    response = core_client.get("/api/v1/baselines/catalog", headers=headers)
    assert response.status_code == 200
    assert response.json()["total"] == 31
    mapped = core_client.get("/api/v1/experiments/catalog/E14/baselines", headers=headers)
    assert mapped.status_code == 200
    assert "progent_runtime" in {x["id"] for x in mapped.json()["baselines"]}


def test_policy_controls_distinguish_default_mcp_hints_from_closed_world_filter():
    from taas.experiments.policy_baselines import run_policy_baseline

    _, _, _, positive_hint_tool = _fixture()
    no_hint_tool = RawTool(
        server="other", name="unknown_action", description="Perform an operation",
        input_schema={"type": "object", "properties": {}}, annotations=None,
    )
    false_hint_tool = RawTool(
        server="other", name="write_file", description="Write a file",
        input_schema={"type": "object", "properties": {}},
        annotations={"readOnlyHint": False},
    )
    tools = [positive_hint_tool, no_hint_tool, false_hint_tool]
    default = run_policy_baseline("mcp_default_annotations", tools)
    closed = run_policy_baseline("closed_world_annotations", tools)
    assert default["selected_tool_ids"] == [x.id for x in tools]
    assert len(closed["selected_tool_ids"]) == 1
    assert closed["selected_tool_ids"] == [positive_hint_tool.id]
    assert default["annotations_treated_as_verified_evidence"] is False
    assert default["annotation_counts"] == {"true": 1, "false": 1, "missing": 1, "invalid": 0}


def test_positive_and_closed_world_lexical_controls_report_distinct_reasoning():
    from taas.experiments.policy_baselines import run_policy_baseline

    read_tool = RawTool(
        server="files", name="list_files", description="List files in a folder",
        input_schema={"type": "object", "properties": {}},
    )
    unknown_tool = RawTool(
        server="misc", name="operate", description="Perform an operation",
        input_schema={"type": "object", "properties": {}},
    )
    write_tool = RawTool(
        server="files", name="delete_file", description="Delete a file",
        input_schema={"type": "object", "properties": {}},
    )
    tools = [read_tool, unknown_tool, write_tool]
    positive = run_policy_baseline("lexical_positive", tools)
    closed = run_policy_baseline("lexical_closed_world", tools)
    assert positive["selected_tool_ids"] == [read_tool.id]
    assert set(closed["selected_tool_ids"]) == {read_tool.id, unknown_tool.id}
    assert write_tool.id in closed["rejected_tool_ids"]


def test_verified_evidence_policy_control_is_blocked_without_real_evidence():
    from taas.experiments.policy_baselines import run_policy_baseline

    _, _, _, raw = _fixture()
    result = run_policy_baseline("verified_evidence", [raw])
    assert result["status"] == "blocked_missing_independent_evidence_store"
    assert result["selected_tool_ids"] == []
    assert result["evaluator_labels_read"] is False


def test_studio_preview_supports_policy_baselines_and_blocks_missing_evidence(monkeypatch):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    headers = {"Authorization": "Bearer test-token"}
    response = client.post("/api/v1/baselines/preview", headers=headers, json={
        "experiment_id": "E4",
        "baseline_ids": [
            "mcp_default_annotations", "closed_world_annotations",
            "lexical_positive", "lexical_closed_world", "verified_evidence",
        ],
        "goal_spec": {
            "prompt": "List files",
            "prompt_inputs": ["text"],
            "goals": [{
                "id": "g1", "class": "retrieve", "in": ["text"],
                "out": "record:file", "eff": ["read(*)"],
                "sigma": "data", "desc": "List files",
            }],
        },
        "tools": [
            {
                "server": "files", "name": "list_files",
                "description": "List files in a folder",
                "input_schema": {"type": "object", "properties": {}},
                "annotations": {"readOnlyHint": True},
            },
            {
                "server": "files", "name": "delete_file",
                "description": "Delete a file",
                "input_schema": {"type": "object", "properties": {}},
                "annotations": {"readOnlyHint": False},
            },
        ],
    })
    assert response.status_code == 200, response.text
    results = {x["baseline"]["id"]: x["result"] for x in response.json()["results"]}
    assert len(results["mcp_default_annotations"]["selected_tool_ids"]) == 2
    assert results["closed_world_annotations"]["selected_tool_ids"] == ["files::list_files"]
    assert results["verified_evidence"]["status"] == "blocked_missing_independent_evidence_store"


def test_studio_page_exposes_experiment_and_baseline_workbench():
    from taas.studio.api import app as core_app
    page = TestClient(core_app).get("/")
    assert page.status_code == 200
    for marker in [
        'id="experiments"', 'id="experiment-catalog-load"',
        'id="experiment-baselines-load"', 'id="baseline-preview-run"',
        'id="experiment-baseline-cards"', 'id="baseline-preview-results"',
        '/api/v1/baselines/preview',
    ]:
        assert marker in page.text


def test_baseline_preview_validates_collection_goal_types(monkeypatch):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    headers = {"Authorization": "Bearer test-token"}
    response = client.post("/api/v1/baselines/preview", headers=headers, json={
        "experiment_id": "E8",
        "baseline_ids": ["bm25"],
        "goal_spec": {
            "prompt": "List review records",
            "prompt_inputs": ["query"],
            "goals": [{
                "id": "g1", "class": "retrieve", "in": ["query"],
                "out": "record:review[]", "sigma": "data",
                "desc": "List review records",
            }],
        },
        "tools": [{
            "server": "reviews", "name": "list_reviews",
            "description": "List review records",
            "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}},
        }],
    })
    assert response.status_code == 200, response.text


def test_baseline_preview_rejects_malformed_goal_spec_before_adapter(monkeypatch):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    headers = {"Authorization": "Bearer test-token"}
    response = client.post("/api/v1/baselines/preview", headers=headers, json={
        "experiment_id": "E8", "baseline_ids": ["bm25"],
        "goal_spec": {
            "prompt": "List reviews",
            "goals": [{
                "id": "g1", "class": "retrieve", "out": "not_a_supported_type",
                "sigma": "data", "desc": "List reviews",
            }],
        },
        "tools": [{
            "server": "reviews", "name": "list_reviews",
            "description": "List review records",
            "input_schema": {"type": "object", "properties": {}},
        }],
    })
    assert response.status_code == 422
    assert "semantic type" in response.json()["detail"]


def test_colt_preview_marks_non_training_scenes_invalid_without_crashing_batch(monkeypatch):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    headers = {"Authorization": "Bearer test-token"}
    response = client.post("/api/v1/baselines/preview", headers=headers, json={
        "experiment_id": "E8", "baseline_ids": ["colt_adapted", "bm25"],
        "goal_spec": {
            "prompt": "Find reviews", "prompt_inputs": ["query"],
            "goals": [{
                "id": "g1", "class": "search", "in": ["query"],
                "out": "record:review", "sigma": "data", "desc": "Find reviews",
            }],
        },
        "tools": [{
            "server": "reviews", "name": "search_reviews",
            "description": "Search reviews",
            "input_schema": {"type": "object", "properties": {}},
        }],
        "training_scenes": [{"split": "test", "tools": ["reviews::search_reviews"]}],
    })
    assert response.status_code == 200
    results = {x["baseline"]["id"]: x["result"] for x in response.json()["results"]}
    assert results["colt_adapted"]["status"] == "invalid_adapter_configuration"
    assert results["bm25"]["status"] == "completed"


def test_baseline_preview_registry_hash_is_order_invariant(monkeypatch):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    headers = {"Authorization": "Bearer test-token"}
    base = {
        "experiment_id": "E8", "baseline_ids": ["bm25"],
        "goal_spec": {
            "prompt": "Search reviews", "prompt_inputs": ["query"],
            "goals": [{
                "id": "g1", "class": "search", "in": ["query"],
                "out": "record:review", "sigma": "data", "desc": "Search reviews",
            }],
        },
        "top_k": 2,
    }
    one = {
        "server": "reviews", "name": "search_reviews", "description": "Search reviews",
        "input_schema": {"type": "object", "properties": {}},
    }
    two = {
        "server": "reviews", "name": "list_reviews", "description": "List reviews",
        "input_schema": {"type": "object", "properties": {}},
    }
    a = client.post("/api/v1/baselines/preview", headers=headers, json={**base, "tools": [one, two]})
    b = client.post("/api/v1/baselines/preview", headers=headers, json={**base, "tools": [two, one]})
    assert a.status_code == b.status_code == 200
    assert a.json()["registry_snapshot"]["sha256"] == b.json()["registry_snapshot"]["sha256"]


def test_pamcp_variant_runner_exposes_uncertified_no_cert_semantics():
    from taas.experiments.variant_runner import run_pamcp_variant

    contracts, _, spec, _ = _fixture()
    policy = Policy.make("read-only-preview", allowed=["read(*)"], lmin="ann")
    result = run_pamcp_variant("PaMCP_NoCert", contracts, {
        "prompt": spec.prompt,
        "prompt_inputs": [str(x) for x in spec.prompt_inputs],
        "goals": [{
            "id": "g1", "class": "search", "in": ["query"],
            "out": "record:review", "eff": ["read(reviews)"],
            "sigma": "data", "desc": "Search customer reviews",
        }],
    }, policy, top_k=2)
    assert result["variant_id"] == "PaMCP_NoCert"
    assert result["certificate"] is None
    assert result["certificate_valid"] is False
    assert result["backward_closure"] is False
    assert result["joint_compatibility_effect_flow_checks"] is False
    assert result["evaluator_labels_accessed"] is False
    assert result["mcp_tools_executed"] is False


def test_e18_preview_accepts_primary_pamcp_factorial_variants(monkeypatch):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    headers = {"Authorization": "Bearer test-token"}
    variants = ["Full_PaMCP", "PaMCP_NoGap", "PaMCP_Declared", "PaMCP_NoCert"]
    response = client.post("/api/v1/baselines/preview", headers=headers, json={
        "experiment_id": "E18",
        "baseline_ids": [],
        "pamcp_variants": variants,
        "goal_spec": {
            "prompt": "Search customer reviews",
            "prompt_inputs": ["query"],
            "goals": [{
                "id": "g1", "class": "search", "in": ["query"],
                "out": "record:review", "eff": ["read(reviews)"],
                "sigma": "data", "desc": "Search customer reviews",
            }],
        },
        "tools": [{
            "server": "reviews", "name": "search_reviews",
            "description": "Search customer reviews",
            "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}},
            "annotations": {"readOnlyHint": True},
        }],
        "policy": {"name": "read-only-preview", "allowed": ["read(*)"], "lmin": "ann"},
        "top_k": 2,
    })
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["baseline_count"] == 0
    assert data["pamcp_variant_count"] == 4
    assert {x["variant"] for x in data["pamcp_variant_results"]} == set(variants)
    for item in data["pamcp_variant_results"]:
        assert item["result"]["evaluator_labels_accessed"] is False
        assert item["result"]["mcp_tools_executed"] is False


def test_pamcp_variants_are_restricted_to_e18(monkeypatch):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    headers = {"Authorization": "Bearer test-token"}
    response = client.post("/api/v1/baselines/preview", headers=headers, json={
        "experiment_id": "E8", "baseline_ids": [],
        "pamcp_variants": ["Full_PaMCP"],
        "goal_spec": {
            "prompt": "Find a tool",
            "goals": [{
                "id": "g1", "class": "search", "in": [],
                "out": "document", "sigma": "data", "desc": "Find a tool",
            }],
        },
        "tools": [{"server": "s", "name": "t", "description": "tool", "input_schema": {}}],
    })
    assert response.status_code == 422
