import re

import pytest

from fastapi.testclient import TestClient

from taas.studio.api import app

client = TestClient(app)


def test_health_is_public():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_discovery_requires_token(monkeypatch):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    response = client.post("/api/v1/discover", json={"goal_spec": {}, "tools": [{"server": "s", "name": "t"}]})
    assert response.status_code == 401


def test_discovery_returns_server_owned_hypergraph_projection(monkeypatch):
    from types import SimpleNamespace

    import taas.studio.api as api
    from taas.contracts import make_contract
    from taas.hypergraph import Derivation, Hypergraph, ReachResult
    from taas.types import parse_type

    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    contract = make_contract(
        "orders::list_orders",
        {"customer_id": "identifier"},
        "record[]",
        ["read(orders)"],
        description="List orders",
        source_label="internal",
    )
    graph = Hypergraph()
    graph.add(contract)
    reach = ReachResult(
        types={parse_type("identifier"), parse_type("record[]")},
        derivations={
            "identifier": Derivation("prompt", "identifier", (), "prompt"),
            "record[]": Derivation(
                contract.tool, "record[]", ("identifier",), "tool", 0.95
            ),
        },
        bridges=[],
        labels={"identifier": "public", "record[]": "internal"},
        fired={contract.tool},
        tool_types={"record[]": contract.tool},
    )

    class FakeEngine:
        def __init__(self, contracts, profile, trust, cfg):
            self.H = graph
            self.composer = SimpleNamespace(model_edges=lambda goals: [])

        def discover(self, spec, policy):
            return SimpleNamespace(
                spec=spec,
                gap=SimpleNamespace(gap=[], rho=0.0),
                compose=SimpleNamespace(
                    reachability=reach, candidates=[contract.tool], regime="exact", stats={}
                ),
                certificate=None,
                counterexample=None,
                toolkit=[contract.tool],
                time_s=0.01,
                abstained=False,
            )

    monkeypatch.setattr(api, "DiscoveryEngine", FakeEngine)
    response = client.post(
        "/api/v1/discover",
        headers={"Authorization": "Bearer test-token"},
        json={
            "goal_spec": {
                "prompt": "List customer orders",
                "prompt_inputs": ["identifier"],
                "goals": [{
                    "id": "g1", "class": "retrieve", "in": ["identifier"],
                    "out": "record[]", "eff": ["read(orders)"],
                    "sigma": "data", "deps": [], "desc": "List orders",
                }],
            },
            "human_review_confirmed": True,
            "tools": [{
                "server": "orders", "name": "list_orders",
                "input_schema": {
                    "type": "object",
                    "properties": {"customer_id": {"type": "string"}},
                    "required": ["customer_id"],
                },
            }],
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "selected"
    assert data["selected_tools"] == [contract.tool]
    assert data["hypergraph_projection_status"] == "available"
    projection = data["hypergraph_projection"]
    assert projection["schema"] == "taas.hypergraph-projection/v1"
    edge = next(item for item in projection["hyperedges"] if item["kind"] == "tool")
    assert edge["tool_id"] == contract.tool
    assert edge["fired_in_reachability"] is True
    assert data["execution_performed"] is False
    assert data["human_review"]["confirmed"] is True


def test_discovery_abstention_does_not_manufacture_hypergraph_projection(monkeypatch):
    from types import SimpleNamespace

    import taas.studio.api as api

    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")

    class FakeEngine:
        def __init__(self, contracts, profile, trust, cfg):
            self.H = object()
            self.composer = SimpleNamespace(model_edges=lambda goals: [])

        def discover(self, spec, policy):
            return SimpleNamespace(
                spec=spec,
                gap=SimpleNamespace(gap=[], rho=0.0),
                compose=SimpleNamespace(reachability=None, candidates=[], regime="", stats={}),
                certificate=None,
                counterexample=None,
                toolkit=None,
                time_s=0.01,
                abstained=True,
            )

    monkeypatch.setattr(api, "DiscoveryEngine", FakeEngine)
    response = client.post(
        "/api/v1/discover",
        headers={"Authorization": "Bearer test-token"},
        json={
            "goal_spec": {
                "prompt": "List customer orders",
                "prompt_inputs": ["identifier"],
                "goals": [{
                    "id": "g1", "class": "retrieve", "in": ["identifier"],
                    "out": "record[]", "eff": ["read(orders)"],
                    "sigma": "data", "deps": [], "desc": "List orders",
                }],
            },
            "human_review_confirmed": True,
            "tools": [{
                "server": "orders", "name": "list_orders",
                "input_schema": {
                    "type": "object",
                    "properties": {"customer_id": {"type": "string"}},
                    "required": ["customer_id"],
                },
            }],
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "abstained"
    assert data["hypergraph_projection_status"] == "unavailable_abstained"
    assert data["hypergraph_projection"] is None
    assert data["execution_performed"] is False



def test_objective_prepare_exposes_v3_contract_and_never_authorizes_discovery(monkeypatch):
    import taas.studio.api as api

    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")

    class FakeRuntime:
        def decompose(self, prompt, context, max_new_tokens):
            return {
                "json_valid": True,
                "text": "{\"goal_spec\": {\"goals\": []}}",
                "model_id": "test-model",
                "latency_seconds": 0.01,
                "goal_spec": {
                    "prompt": prompt,
                    "prompt_inputs": ["text"],
                    "goals": [{
                        "id": "g1", "class": "search", "in": ["text"],
                        "out": "record[]", "eff": ["read(web)"],
                        "sigma": "data", "deps": [], "desc": "Search the web for research papers.",
                    }],
                },
            }

    monkeypatch.setattr(api, "get_model_runtime", lambda: FakeRuntime())
    response = client.post(
        "/api/v1/objectives/prepare",
        headers={"Authorization": "Bearer test-token"},
        json={"provider": "huggingface", "prompt": "Search the web for research papers."},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    contract = data["objective_contract_v3"]
    view = data["objective_intelligence_v3"]
    assert contract["schema"] == "taas.objective-contract/v3"
    assert contract["objective"]["text"] == "Search the web for research papers."
    assert view["structurally_valid"] is True
    assert view["semantic_correctness_verified"] is False
    assert view["discovery_authorized"] is False
    assert data["workflow"]["tool_execution"] == "disabled"


def test_studio_frontend_renders_v3_clarifications_and_blocks_apply():
    response = client.get("/")
    assert response.status_code == 200
    page = response.text
    assert 'id="agent-objective-contract-v3"' in page
    assert "renderObjectiveContractV3" in page
    assert "blocking_clarification_count" in page
    assert "&&!v3Blockers" in page
    assert "v3StructurallyValid=result.objective_intelligence_v3?.structurally_valid===true" in page
    assert "&&!v3Blockers&&v3StructurallyValid" in page

def test_default_profile_is_uncalibrated_and_fail_closed(monkeypatch):
    from taas.studio.api import load_profile

    monkeypatch.delenv("TAAS_MODEL_PROFILE", raising=False)
    profile = load_profile()
    assert profile.model_id == "uncalibrated-default"
    assert profile.strict is True
    assert profile.rho("summarise", 1) == 0.0


def test_ready_does_not_require_calibration(monkeypatch):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    monkeypatch.delenv("TAAS_MODEL_PROFILE", raising=False)
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["calibration"] == "uncalibrated"


def test_studio_home_serves_browser_workspace():
    response = client.get("/")
    assert response.status_code == 200
    assert "<title>TaaS Studio — Tool Intelligence Platform</title>" in response.text
    assert '<strong>TaaS Studio</strong>' in response.text
    assert "/api/v1/objectives/discover" in response.text
    assert response.headers["cache-control"] == "no-store, no-cache, must-revalidate, max-age=0"
    assert response.headers["pragma"] == "no-cache"


def test_studio_frontend_keeps_goal_metrics_disjoint_and_runtime_claims_precise():
    response = client.get("/")
    assert response.status_code == 200
    page = response.text

    # A goal in the toolkit gap must not also be counted as model-delegated.
    assert 'goal.sigma === "native" && !gapGoals.has(goal.id)' in page
    assert 'gapGoals.has(goalId) && selectedTools.has(target)' in page

    # CUDA availability is not evidence of a loaded model or executed inference.
    assert "model not loaded · inference not executed" in page
    assert "model_loaded: false" in page
    assert "inference_executed: false" in page
    assert 'id="discovery-diagnostics-panel"' in page
    assert 'id="discovery-diagnostics-tools"' in page
    assert 'cell.textContent=String(value)' in page
    assert 'discovery_diagnostics' in page

    # Separate mandatory validity gates from non-gating diagnostics.
    assert 'const mandatoryChecks = ["S", "C", "P", "E", "L", "V"]' in page
    assert 'const diagnosticChecks = ["M", "B"]' in page



def test_hardware_diagnostics_requires_token(monkeypatch):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    response = client.get("/api/v1/runtime/hardware")
    assert response.status_code == 401


def test_hardware_diagnostics_returns_probe(monkeypatch):
    from taas.studio import api

    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    expected = {
        "gpu_detected": True,
        "gpu": {
            "name": "Tesla T4",
            "memory_total_mib": 15360,
            "memory_free_mib": 14000,
            "driver_version": "test",
            "compute_capability": "7.5",
        },
        "nvidia_smi_available": True,
        "torch_installed": False,
        "cuda_available": False,
        "inference_ready": False,
        "notes": ["PyTorch is not installed; CUDA inference has not been configured."],
    }
    monkeypatch.setattr(api, "probe_hardware", lambda: expected)
    response = client.get(
        "/api/v1/runtime/hardware",
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200
    assert response.json() == expected


def test_studio_goal_spec_rejects_legacy_field_names():
    from fastapi import HTTPException
    from taas.studio.api import validate_studio_goal_spec

    with pytest.raises(HTTPException) as exc:
        validate_studio_goal_spec({
            "goals": [{
                "id": "g1",
                "class": "read",
                "output": "text",
                "reason": "legacy",
                "dependencies": [],
            }]
        })
    assert exc.value.status_code == 422
    assert "legacy field" in exc.value.detail


def test_studio_goal_spec_accepts_core_contract():
    from taas.studio.api import validate_studio_goal_spec

    validate_studio_goal_spec({
        "prompt": "List orders",
        "goals": [{
            "id": "g1",
            "class": "retrieve",
            "in": [],
            "out": "record[]",
            "eff": ["read(*)"],
            "sigma": "data",
            "desc": "Retrieve orders",
            "deps": [],
        }],
    })


def test_studio_goal_spec_rejects_invalid_class():
    from fastapi import HTTPException
    from taas.studio.api import validate_studio_goal_spec

    with pytest.raises(HTTPException) as exc:
        validate_studio_goal_spec({
            "goals": [{
                "id": "g1",
                "class": "read",
                "out": "text",
            }]
        })
    assert exc.value.status_code == 422
    assert "supported model or external goal classes" in exc.value.detail


def test_studio_goal_spec_preserves_natural_language_prompt():
    from taas.studio.api import parse_studio_goal_spec

    parsed = parse_studio_goal_spec({
        "prompt": "List the available orders",
        "goals": [{
            "id": "g1",
            "class": "retrieve",
            "in": [],
            "out": "record[]",
            "eff": ["read(*)"],
            "sigma": "data",
            "desc": "Retrieve available orders",
            "deps": [],
        }],
    })
    assert parsed.prompt == "List the available orders"


def test_studio_home_explains_model_delegation_and_toolkit_coverage():
    response = client.get("/")
    assert response.status_code == 200
    assert "Model-delegated goals" in response.text
    assert "Toolkit-bound goals" in response.text
    assert "not runtime execution verification" in response.text


def test_model_memory_estimate_endpoint(monkeypatch):
    from taas.studio import api

    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    monkeypatch.setattr(api, "estimate_model_memory", lambda **kwargs: {
        "parameters_billion": kwargs["parameters_billion"],
        "quantization": kwargs["quantization"],
        "estimated_memory_gib": 4.5,
        "fits_observed_free_memory": True,
        "load_guaranteed": False,
    })
    response = client.post(
        "/api/v1/models/estimate-memory",
        headers={"Authorization": "Bearer test-token"},
        json={"parameters_billion": 7, "quantization": "int4"},
    )
    assert response.status_code == 200
    assert response.json()["estimated_memory_gib"] == 4.5
    assert response.json()["load_guaranteed"] is False


def test_model_memory_estimate_requires_authentication(monkeypatch):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    response = client.post(
        "/api/v1/models/estimate-memory",
        json={"parameters_billion": 7, "quantization": "int4"},
    )
    assert response.status_code == 401


def test_model_memory_estimate_rejects_unsupported_quantization(monkeypatch):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    response = client.post(
        "/api/v1/models/estimate-memory",
        headers={"Authorization": "Bearer test-token"},
        json={"parameters_billion": 7, "quantization": "bf16"},
    )
    assert response.status_code == 422


def test_huggingface_model_search_returns_normalized_metadata(monkeypatch):
    from taas.studio import api

    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    monkeypatch.setattr(api, "search_models", lambda *args, **kwargs: [{
        "model_id": "org/example-7b",
        "url": "https://huggingface.co/org/example-7b",
        "pipeline_tag": "text-generation",
        "library_name": "transformers",
        "downloads": 1234,
        "likes": 56,
        "last_modified": "2026-10-01T00:00:00Z",
        "gated": False,
        "private": False,
        "license": "apache-2.0",
        "tags": ["text-generation", "license:apache-2.0"],
        "safetensors": True,
        "parameter_count": 7_000_000_000,
    }])
    response = client.get(
        "/api/v1/models/search",
        params={"q": "example", "limit": 5},
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["models"][0]["model_id"] == "org/example-7b"
    assert data["weights_downloaded"] is False


def test_huggingface_model_search_requires_authentication(monkeypatch):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    response = client.get("/api/v1/models/search", params={"q": "llama"})
    assert response.status_code == 401


def test_huggingface_model_search_bounds_limit(monkeypatch):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    response = client.get(
        "/api/v1/models/search",
        params={"q": "llama", "limit": 100},
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 422


def test_model_catalog_normalizes_parameter_count():
    from taas.studio.models import normalize_model

    model = normalize_model({
        "id": "org/model",
        "tags": ["license:apache-2.0", "text-generation"],
        "safetensors": {"parameters": {"BF16": 6_000_000_000, "F16": 1_000_000_000}},
    })
    assert model["parameter_count"] == 7_000_000_000
    assert model["license"] == "apache-2.0"


def test_model_catalog_does_not_require_parameter_metadata():
    from taas.studio.models import normalize_model

    model = normalize_model({"id": "org/model", "tags": []})
    assert model["parameter_count"] is None
    assert model["safetensors"] is False


def test_kv_cache_memory_estimate_uses_decoder_architecture():
    from taas.studio.runtime import estimate_model_memory

    result = estimate_model_memory(
        parameters_billion=7,
        quantization="int4",
        overhead_fraction=0,
        runtime_reserve_gib=0,
        num_hidden_layers=32,
        num_key_value_heads=8,
        head_dim=128,
        context_length=4096,
        batch_size=1,
        kv_cache_dtype="fp16",
    )
    assert result["kv_cache_memory_gib"] == 0.5
    assert result["estimated_memory_gib"] == round(result["weight_memory_gib"] + 0.5, 3)
    assert result["load_guaranteed"] is False


def test_kv_cache_estimate_requires_complete_architecture():
    from taas.studio.runtime import estimate_model_memory

    with pytest.raises(ValueError, match="all KV-cache dimensions"):
        estimate_model_memory(
            parameters_billion=7,
            num_hidden_layers=32,
        )


def test_kv_cache_estimate_rejects_unsupported_dtype():
    from taas.studio.runtime import estimate_model_memory

    with pytest.raises(ValueError, match="kv_cache_dtype"):
        estimate_model_memory(
            parameters_billion=7,
            num_hidden_layers=32,
            num_key_value_heads=8,
            head_dim=128,
            context_length=4096,
            kv_cache_dtype="bf16",
        )



def test_huggingface_model_detail_endpoint_returns_safe_metadata(monkeypatch):
    from taas.studio import api

    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    monkeypatch.setattr(api, "get_model_details", lambda model_id: {
        "model_id": model_id,
        "architecture": {
            "model_type": "llama",
            "num_hidden_layers": 32,
            "num_key_value_heads": 8,
            "head_dim": 128,
            "max_position_embeddings": 8192,
            "kv_cache_dimensions_complete": True,
            "context_limit_reported": True,
        },
        "architecture_source": "Hugging Face model API config",
        "architecture_complete_for_kv_estimate": True,
        "weights_downloaded": False,
        "model_code_executed": False,
    })
    response = client.get(
        "/api/v1/models/detail",
        params={"model_id": "org/example-7b"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["architecture"]["num_hidden_layers"] == 32
    assert data["architecture_complete_for_kv_estimate"] is True
    assert data["weights_downloaded"] is False
    assert data["model_code_executed"] is False


def test_huggingface_model_detail_requires_authentication(monkeypatch):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    response = client.get(
        "/api/v1/models/detail",
        params={"model_id": "org/example"},
    )
    assert response.status_code == 401


def test_huggingface_model_detail_rejects_invalid_repository_id(monkeypatch):
    from taas.studio.models import get_model_details

    with pytest.raises(ValueError, match="namespace/repository"):
        get_model_details("../../etc/passwd")


def test_huggingface_model_detail_uses_only_reported_architecture(monkeypatch):
    from taas.studio import models

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "id": "org/example",
                "tags": ["license:apache-2.0"],
                "config": {
                    "model_type": "llama",
                    "architectures": ["LlamaForCausalLM"],
                    "num_hidden_layers": 32,
                    "num_attention_heads": 32,
                    "num_key_value_heads": 8,
                    "hidden_size": 4096,
                    "max_position_embeddings": 8192,
                },
            }

    monkeypatch.setattr(models.httpx, "get", lambda *args, **kwargs: FakeResponse())
    details = models.get_model_details("org/example")
    assert details["architecture"]["num_hidden_layers"] == 32
    assert details["architecture"]["num_key_value_heads"] == 8
    # head_dim is deliberately not inferred from hidden_size / attention heads.
    assert "head_dim" not in details["architecture"]
    assert details["architecture_complete_for_kv_estimate"] is False
    assert details["weights_downloaded"] is False


def test_huggingface_artifact_inspection_reports_formats_without_download(monkeypatch):
    from taas.studio import models

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "id": "org/example",
                "siblings": [
                    {"rfilename": "model.safetensors", "size": 1024},
                    {"rfilename": "model-Q4_K_M.gguf", "size": 2048,
                     "lfs": {"size": 2048, "oid": "a" * 64}},
                    {"rfilename": "config.json"},
                ],
            }

    monkeypatch.setattr(models.httpx, "get", lambda *args, **kwargs: FakeResponse())
    result = models.inspect_model_artifacts("org/example")
    assert result["formats"] == ["gguf", "safetensors"]
    assert result["known_artifact_bytes"] == 3072
    assert result["weights_downloaded"] is False
    assert result["model_code_executed"] is False
    assert result["t4_assessment"]["status"] == "not_verified"
    assert {item["backend"] for item in result["backend_candidates"]} == {"llama.cpp", "Transformers"}


def test_huggingface_artifact_inspection_rejects_invalid_repository_id():
    from taas.studio.models import inspect_model_artifacts

    with pytest.raises(ValueError, match="namespace/repository"):
        inspect_model_artifacts("../outside")


def test_huggingface_artifact_endpoint_requires_authentication(monkeypatch):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    response = client.get("/api/v1/models/artifacts", params={"model_id": "org/example"})
    assert response.status_code == 401


def test_huggingface_artifact_endpoint_returns_metadata(monkeypatch):
    from taas.studio import api

    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    monkeypatch.setattr(api, "inspect_model_artifacts", lambda model_id: {
        "model_id": model_id,
        "file_count": 1,
        "formats": ["safetensors"],
        "weights_downloaded": False,
        "t4_assessment": {"status": "not_verified"},
    })
    response = client.get(
        "/api/v1/models/artifacts",
        params={"model_id": "org/example"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200
    assert response.json()["weights_downloaded"] is False


def test_studio_goal_metrics_distinguish_gap_model_and_tool_bindings():
    from pathlib import Path
    from taas.studio import api

    page = Path(api.__file__).parent / "static" / "index.html"
    html = page.read_text(encoding="utf-8")
    assert "Toolkit-required goals" in html
    assert "Model-delegated goals" in html
    assert "Toolkit-bound goals" in html
    assert 'goal.sigma === "native"' in html
    assert "selectedTools.has(target)" in html
    assert "boundGoals.length" not in html


def test_benchmark_dataset_catalog_requires_authentication(monkeypatch):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    assert client.get("/api/v1/bench/datasets").status_code == 401


def test_benchmark_dataset_catalog_uses_local_snapshot(monkeypatch):
    from taas.studio import api
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    monkeypatch.setattr(api, "_bench_data", lambda: {
        "stats": {"merged": {"servers": 76, "tools": 569}},
        "tasks_livemcpbench": [{"category": "Office"}, {"category": "Travel"}],
        "tasks_mcptoolbenchpp": [{"category": "Travel"}],
    })
    response = client.get("/api/v1/bench/datasets", headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 200
    data = response.json()
    assert data["registry"]["merged"]["tools"] == 569
    assert data["upstream_fetch_performed"] is False
    assert {item["id"] for item in data["datasets"]} == {"livemcpbench", "mcptoolbenchpp"}


def test_benchmark_task_browser_hides_gold_labels(monkeypatch):
    from taas.studio import api
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    monkeypatch.setattr(api, "_bench_data", lambda: {
        "tasks_livemcpbench": [
            {"id": "t1", "query": "Create a PDF report", "category": "Office",
             "source": "LiveMCPBench", "n_steps": 3, "gold_tools": ["hidden-tool"]},
            {"id": "t2", "query": "Find a hotel", "category": "Travel",
             "source": "LiveMCPBench", "n_steps": 2, "gold_tools": ["hidden-hotel"]},
        ]
    })
    response = client.get("/api/v1/bench/tasks", params={"dataset": "livemcpbench", "category": "Office"},
                          headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["tasks"][0]["id"] == "t1"
    assert data["gold_labels_exposed"] is False
    assert "gold_tools" not in data["tasks"][0]


def test_benchmark_tool_browser_marks_annotations_untrusted(monkeypatch):
    from taas.studio import api
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    monkeypatch.setattr(api, "_bench_data", lambda: {"registry": [{
        "id": "GitHub::search", "server": "GitHub", "name": "search",
        "description": "Search repositories", "input_schema": {"type": "object"},
        "annotations": {"readOnlyHint": True}, "source": "LiveMCPTool", "hash": "abc123",
    }]})
    response = client.get("/api/v1/bench/tools", params={"source": "LiveMCPTool", "q": "github"},
                          headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 200
    assert response.json()["tools"][0]["id"] == "GitHub::search"
    assert response.json()["annotations_are_trusted_evidence"] is False


def test_studio_frontend_integrates_benchmark_and_tool_registry_workspace():
    response = client.get("/")
    assert response.status_code == 200
    page = response.text
    for marker in (
        'id="workspace"',
        'id="bench-datasets"',
        'id="bench-tasks"',
        'id="bench-tools"',
        'id="bench-use-task"',
        'id="bench-add-tools"',
        'id="discovery"',
        'id="models"',
        'id="runtime"',
        "Gold labels reserved for evaluation",
        "Structural validation does not verify semantic alignment",
    ):
        assert marker in page


def test_studio_frontend_keeps_benchmark_gold_labels_out_of_browser_contract():
    response = client.get("/")
    assert response.status_code == 200
    page = response.text
    # Browser task selection is based only on the prompt and public task metadata.
    assert "gold_tools" not in page
    assert "gold_unresolved" not in page
    assert "/api/v1/bench/tasks?" in page
    assert "/api/v1/bench/tools?" in page


def test_goal_spec_validation_endpoint_requires_authentication(monkeypatch):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    response = client.post("/api/v1/goals/validate", json={
        "prompt": "List orders",
        "goals": [{"id": "g1", "class": "retrieve", "out": "record[]", "eff": ["read(*)"]}],
    })
    assert response.status_code == 401


def test_goal_spec_validation_endpoint_returns_topological_order(monkeypatch):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    response = client.post(
        "/api/v1/goals/validate",
        headers={"Authorization": "Bearer test-token"},
        json={
            "prompt": "Retrieve orders and summarize them",
            "prompt_inputs": ["text"],
            "goals": [
                {"id": "g1", "class": "retrieve", "in": [], "out": "record[]",
                 "eff": ["read(*)"], "sigma": "data", "deps": [], "desc": "Retrieve orders"},
                {"id": "g2", "class": "summarise", "in": ["record[]"], "out": "text",
                 "eff": [], "sigma": "native", "deps": ["g1"], "desc": "Summarise retrieved orders"},
            ],
        },
    )
    assert response.status_code == 200
    assert response.json()["valid"] is True
    assert response.json()["goal_order"] == ["g1", "g2"]
    assert response.json()["semantic_correctness_verified"] is False


@pytest.mark.parametrize(
    ("goals", "message"),
    [
        (
            [
                {"id": "g1", "class": "retrieve", "out": "record[]", "desc": "Retrieve records"},
                {"id": "g1", "class": "answer", "out": "text", "desc": "Answer the question"},
            ],
            "duplicate goal id",
        ),
        (
            [{"id": "g1", "class": "retrieve", "out": "record[]", "deps": ["missing"], "desc": "Retrieve records"}],
            "unknown dependency",
        ),
        (
            [
                {"id": "g1", "class": "retrieve", "out": "record[]", "deps": ["g2"], "desc": "Retrieve records"},
                {"id": "g2", "class": "answer", "out": "text", "deps": ["g1"], "desc": "Answer the question"},
            ],
            "contains a cycle",
        ),
        (
            [{"id": "g1", "class": "retrieve", "out": "record[]", "eff": ["launch rocket"], "desc": "Retrieve records"}],
            "invalid effect",
        ),
        (
            [{"id": "g1", "class": "retrieve", "out": "made_up_type", "desc": "Retrieve records"}],
            "semantic type string",
        ),
    ],
)
def test_goal_spec_validation_rejects_invalid_contracts(monkeypatch, goals, message):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    response = client.post(
        "/api/v1/goals/validate",
        headers={"Authorization": "Bearer test-token"},
        json={"prompt": "Validate this plan", "goals": goals},
    )
    assert response.status_code == 422
    assert message in response.json()["detail"]


def test_studio_frontend_exposes_visual_goalspec_editor_and_server_validation():
    response = client.get("/")
    assert response.status_code == 200
    page = response.text
    for marker in (
        'id="goal-editor"',
        'id="goal-prompt"',
        'id="goal-prompt-inputs"',
        'id="goal-cards"',
        'id="goal-add"',
        'id="goal-validate"',
        'id="goal-reload-json"',
        "/api/v1/goals/validate",
        "semantic correctness is not automatically verified",
        "Dependency graph contains a cycle.",
    ):
        assert marker in page


def test_goal_spec_validation_rejects_missing_goal_description(monkeypatch):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    response = client.post(
        "/api/v1/goals/validate",
        headers={"Authorization": "Bearer test-token"},
        json={"prompt": "Get BBC finance news", "goals": [
            {"id": "g1", "class": "retrieve", "out": "record[]", "desc": ""}
        ]},
    )
    assert response.status_code == 422
    assert ".desc must be a non-empty authored goal description" in response.json()["detail"]


def test_goal_spec_validation_rejects_unknown_prompt_context_type(monkeypatch):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    response = client.post(
        "/api/v1/goals/validate",
        headers={"Authorization": "Bearer test-token"},
        json={
            "prompt": "Inspect records",
            "prompt_inputs": ["imaginary_kind"],
            "goals": [{"id": "g1", "class": "retrieve", "out": "record[]", "desc": "Retrieve records"}],
        },
    )
    assert response.status_code == 422
    assert "prompt_inputs contains invalid semantic type" in response.json()["detail"]


def test_studio_goal_editor_requires_reload_after_advanced_json_edit():
    response = client.get("/")
    assert response.status_code == 200
    page = response.text
    assert "goalJsonManuallyEdited" in page
    assert "Reload the visual editor from the advanced JSON" in page


def test_studio_frontend_renders_structured_certificate_and_goal_coverage_panels():
    response = client.get("/")
    assert response.status_code == 200
    page = response.text
    for marker in (
        'id="certificate-panel"',
        'id="certificate-checks"',
        'id="goal-coverage"',
        'id="counterexample-panel"',
        'id="certificate-witnesses"',
        "Pre-execution certificate valid",
        "M (minimality) and B (bridge ratio) are diagnostics",
        "This certifies the discovery model's pre-execution conditions, not runtime behavior.",
    ):
        assert marker in page


def test_studio_frontend_keeps_counterexample_visible_without_certificate():
    response = client.get("/")
    assert response.status_code == 200
    page = response.text
    assert "certPanel.hidden=!cert&&!data.counterexample" in page
    assert "No certificate produced" in page
    assert "absence of a certificate is not a pass" in page


def test_visual_goal_editor_defaults_missing_cardinality_on_load_and_json_reload():
    response = client.get("/")
    assert response.status_code == 200
    page = response.text
    # Older/hand-authored GoalSpecs may omit n; the visual editor must hydrate
    # the canonical default (1) both at initial load and after JSON reload.
    assert page.count("n:g.n??1") == 2


def test_benchmark_task_import_clears_stale_demo_goal_before_authoring():
    response = client.get("/")
    assert response.status_code == 200
    page = response.text
    handler = page.split('$("bench-use-task").addEventListener("click",()=>{', 1)[1].split(
        '\n  $("bench-add-tools")', 1
    )[0]
    assert "if(goalSpecState.prompt!==prompt){goalSpecState.goals=[]" in handler
    assert "Task prompt copied to GoalSpec" in handler
    assert "Author and review task-specific semantic goal contracts" in handler


def test_benchmark_tool_import_replaces_demo_tools_instead_of_merging():
    response = client.get("/")
    assert response.status_code == 200
    page = response.text
    handler = page.split('$("bench-add-tools").addEventListener("click",()=>{', 1)[1].split(
        '\n  function showBenchError', 1
    )[0]
    assert "syncBenchmarkToolsToRequest()" in handler
    assert "const syncBenchmarkToolsToRequest = () =>" in page
    # Selected tools replace body.tools outright (descriptor mapping, never a merge).
    assert 'body.tools=ordered.map' in page
    assert "bench.selectedTools.entries()" in page
    assert "Demo/sample tools are excluded" in page
    assert "new Map((body.tools||[])" not in handler
    assert "body.tools.concat" not in page
    assert "body.tools.push" not in page


def test_benchmark_task_import_synchronizes_registry_selection_and_clears_demo_tools():
    response = client.get("/")
    assert response.status_code == 200
    page = response.text
    task_handler = page.split('$("bench-use-task").addEventListener("click",()=>{', 1)[1].split(
        '\n  $("bench-add-tools")', 1
    )[0]
    assert "const importedToolCount=syncBenchmarkToolsToRequest()" in task_handler
    assert "selectBenchmarkTask(t)" in page
    assert "goalSpecState.goals=[]" in page
    assert "Structural validation does not verify semantic alignment" in task_handler


def test_benchmark_registry_selection_stays_synchronized_and_blocks_stale_demo_discovery():
    response = client.get("/")
    assert response.status_code == 200
    page = response.text.replace("\r\n", "\n")
    assert "if(bench.selectedTask)" in page
    assert 'if(bench.selectedTask){\n          $("bench-goal-review").checked=false;' in page
    assert "syncBenchmarkToolsToRequest()" in page
    assert "Benchmark discovery blocked: select at least one registry tool" in page
    assert "registry selections are not synchronized with the request" in page
    assert "benchmark task NOT evaluated" in page
    assert "semantic alignment with the task prompt is not verified" in page
    assert "Replace discovery toolset with basket" in page
    assert "Benchmark discovery blocked: review the GoalSpec against the selected task prompt" in page

def test_benchmark_task_switch_invalidates_previous_goal_and_tool_context():
    response = client.get("/")
    assert response.status_code == 200
    page = response.text
    assert 'selectedTaskKey:null' in page
    assert "const invalidateBenchmarkTaskContext = (message) =>" in page
    assert "const selectBenchmarkTask = (task) =>" in page
    assert 'bench.selectedTools.clear()' in page
    assert 'goalSpecState.prompt=task.query||"";goalSpecState.goals=[]' in page
    assert '$("bench-goal-review").checked=false' in page
    assert 'syncBenchmarkToolsToRequest()' in page
    assert 'selectBenchmarkTask(t)' in page
    assert '$("goal-editor").addEventListener("input"' in page
    assert '$("goal-editor").addEventListener("change"' in page
    assert 'if(bench.selectedTask)$("bench-goal-review").checked=false' in page


def test_benchmark_discovery_requires_explicit_goal_spec_review():
    response = client.get("/")
    assert response.status_code == 200
    page = response.text
    assert 'id="bench-goal-review" type="checkbox"' in page
    run_handler = page.split('run.addEventListener("click", async () => {', 1)[1].split(
        '\n  // Integrated benchmark workspace', 1
    )[0]
    assert 'if(!$("bench-goal-review").checked)' in run_handler
    assert "review the GoalSpec against the selected task prompt" in run_handler



def test_api_json_parsing_survives_empty_or_truncated_proxy_responses():
    response = client.get("/")
    assert response.status_code == 200
    page = response.text.replace("\r\n", "\n")
    assert "const readJsonResponse = async (response) =>" in page
    assert "empty response body; the request may have been cut by a proxy timeout" in page
    assert page.count("readJsonResponse(response)") + page.count("readJsonResponse(r)") >= 10
    assert ".json()" not in page


def test_visual_goal_editor_requires_authored_goal_description():
    response = client.get("/")
    assert response.status_code == 200
    assert "goal description is required; describe the intended operation" in response.text



def test_studio_navigation_shell_has_valid_targets_and_accessible_skip_link():
    from pathlib import Path
    from taas.studio import api

    page = Path(api.__file__).parent / "static" / "index.html"
    html = page.read_text(encoding="utf-8")
    ids = set(re.findall(r'id="([^"]+)"', html))
    nav = re.search(r'<nav class="studio-nav".*?</nav>', html, re.DOTALL)
    assert nav is not None
    targets = set(re.findall(r'href="#([^"]+)"', nav.group(0)))
    assert targets <= ids
    assert 'class="skip-link" href="#overview-workspace"' in html
    assert 'id="overview-workspace"' in html
    assert 'id="overview"' in html
    assert 'aria-label="Studio sections"' in html
    assert ".studio-layout" in html
    assert "@media(max-width:900px)" in html


def test_runtime_status_requires_authentication(monkeypatch):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    response = client.get("/api/v1/runtime/status")
    assert response.status_code == 401


def test_runtime_status_reports_host_and_explicit_model_boundary(monkeypatch):
    from taas.studio import api

    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    expected = {
        "service": {
            "status": "running",
            "pid": 123,
            "python_version": "3.12.0",
            "python_executable": "/usr/bin/python",
            "platform": "Linux-test",
        },
        "host": {
            "cpu_count": 2,
            "memory_total_gib": 12.0,
            "memory_available_gib": 8.0,
            "disk_total_gib": 100.0,
            "disk_free_gib": 80.0,
        },
        "hardware": {"gpu_detected": False, "inference_ready": False},
        "model_runtime": {
            "model_loaded": False,
            "inference_executed": False,
            "lifecycle_supported": False,
            "note": "Runtime diagnostics only; model loading and inference are not implemented by this service.",
        },
        "colab": {"detected": True, "ephemeral_storage": True},
    }
    monkeypatch.setattr(api, "probe_runtime", lambda: expected)
    response = client.get(
        "/api/v1/runtime/status",
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200
    assert response.json() == expected



def test_studio_overview_connects_to_authenticated_live_runtime_status():
    response = client.get("/")
    assert response.status_code == 200
    page = response.text
    for marker in (
        'id="runtime-refresh"',
        'id="runtime-overview-state"',
        'id="runtime-cpu"',
        'id="runtime-memory"',
        'id="runtime-disk"',
        'id="runtime-gpu"',
        'id="runtime-colab"',
        'id="runtime-model"',
        'id="runtime-overview-details"',
        'fetch("/api/v1/runtime/status"',
        'cache: "no-store"',
        'displayed values are from an earlier successful snapshot',
        'inference not executed',
    ):
        assert marker in page
    assert 'localStorage.setItem("token"' not in page



def test_model_runtime_status_requires_authentication(monkeypatch):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    response = client.get("/api/v1/models/runtime")
    assert response.status_code == 401


def test_model_runtime_status_reports_actual_process_state(monkeypatch):
    from taas.studio import api

    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")

    class Runtime:
        def status(self):
            return {"model_loaded": True, "model_id": "Qwen/Qwen2.5-0.5B-Instruct",
                    "device": "cpu", "dtype": "float32", "inference_executed": False}

    monkeypatch.setattr(api, "get_model_runtime", lambda: Runtime())
    class Ollama:
        def status(self):
            return {"provider": "ollama", "available": False, "models": []}
    monkeypatch.setattr(api, "get_ollama_runtime", lambda: Ollama())
    response = client.get("/api/v1/models/runtime",
                          headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 200
    assert response.json()["model_loaded"] is True
    assert response.json()["inference_executed"] is False


def test_model_load_endpoint_uses_selected_model_and_device(monkeypatch):
    from taas.studio import api

    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")

    class Runtime:
        def load(self, model_id, device):
            return {"model_loaded": True, "model_id": model_id, "device": device,
                    "dtype": "float32", "trust_remote_code": False}

    monkeypatch.setattr(api, "get_model_runtime", lambda: Runtime())
    response = client.post("/api/v1/models/load",
                           headers={"Authorization": "Bearer test-token"},
                           json={"model_id": "Qwen/Qwen2.5-0.5B-Instruct", "device": "cpu"})
    assert response.status_code == 200
    assert response.json()["model_id"] == "Qwen/Qwen2.5-0.5B-Instruct"
    assert response.json()["device"] == "cpu"
    assert response.json()["trust_remote_code"] is False


def test_model_load_endpoint_rejects_invalid_device(monkeypatch):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    response = client.post("/api/v1/models/load",
                           headers={"Authorization": "Bearer test-token"},
                           json={"model_id": "Qwen/Qwen2.5-0.5B-Instruct", "device": "tpu"},
                           )
    assert response.status_code == 422


def test_model_chat_endpoint_returns_real_runtime_result(monkeypatch):
    from taas.studio import api

    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")

    class Runtime:
        def chat(self, message, system, max_new_tokens, temperature):
            return {"text": "hello", "model_id": "Qwen/Qwen2.5-0.5B-Instruct",
                    "device": "cpu", "latency_seconds": 0.1, "output_tokens": 1}

    monkeypatch.setattr(api, "get_model_runtime", lambda: Runtime())
    response = client.post("/api/v1/models/chat",
                           headers={"Authorization": "Bearer test-token"},
                           json={"message": "hello"})
    assert response.status_code == 200
    assert response.json()["text"] == "hello"
    assert response.json()["device"] == "cpu"


def test_agent_decomposition_endpoint_separates_structure_from_semantics(monkeypatch):
    from taas.studio import api

    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    goal_spec = {
        "prompt": "Explain precision and recall",
        "prompt_inputs": ["text"],
        "goals": [{
            "id": "g1", "class": "answer", "in": ["text"], "out": "text",
            "eff": [], "sigma": "native", "desc": "Explain precision and recall",
            "deps": [], "n": 1, "exactness": "tolerant", "lang": "en", "optional": False,
        }],
    }

    class Runtime:
        def decompose(self, prompt, context, max_new_tokens):
            return {"text": "{}", "goal_spec": goal_spec, "json_valid": True,
                    "semantic_correctness_verified": False}

    monkeypatch.setattr(api, "get_model_runtime", lambda: Runtime())
    response = client.post("/api/v1/agents/decompose",
                           headers={"Authorization": "Bearer test-token"},
                           json={"prompt": "Explain precision and recall"})
    assert response.status_code == 200
    data = response.json()
    assert data["structural_validation"]["valid"] is True
    assert data["semantic_correctness_verified"] is False


def test_huggingface_model_id_validation_is_strict():
    from taas.studio.model_runtime import HuggingFaceModelRuntime

    assert HuggingFaceModelRuntime._validate_model_id("Qwen/Qwen2.5-0.5B-Instruct") == "Qwen/Qwen2.5-0.5B-Instruct"
    with pytest.raises(ValueError):
        HuggingFaceModelRuntime._validate_model_id("../local-code")



def test_mcp_server_registry_lists_only_safe_metadata(monkeypatch):
    from taas.studio import api

    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    monkeypatch.setattr(api, "list_mcp_servers", lambda: {
        "count": 1,
        "servers": [{"id": "local_docs", "name": "Local Docs", "transport": "stdio",
                     "configured": True, "credentials_configured": True}],
    })
    response = client.get("/api/v1/mcp/servers",
                          headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["servers"][0]["id"] == "local_docs"
    assert "command" not in data["servers"][0]
    assert "env" not in data["servers"][0]


def test_mcp_inspection_endpoint_never_executes_tool_calls(monkeypatch):
    from taas.studio import api

    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    monkeypatch.setattr(api, "inspect_mcp_server", lambda server_id: {
        "server_id": server_id, "tool_count": 1,
        "tools": [{"server": server_id, "name": "search", "description": "Search",
                   "input_schema": {"type": "object", "properties": {}},
                   "source": "mcp-live-inspection"}],
        "inspection_only": True, "tool_execution_performed": False,
    })
    response = client.post("/api/v1/mcp/servers/local_docs/inspect",
                           headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 200
    data = response.json()
    assert data["tools"][0]["name"] == "search"
    assert data["inspection_only"] is True
    assert data["tool_execution_performed"] is False


def test_mcp_inspection_unknown_server_returns_404(monkeypatch):
    from taas.studio import api

    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")

    def unknown(_server_id):
        raise ValueError("Unknown MCP server id")

    monkeypatch.setattr(api, "inspect_mcp_server", unknown)
    response = client.post("/api/v1/mcp/servers/missing/inspect",
                           headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 404


def test_mcp_registry_rejects_duplicate_and_invalid_server_ids(monkeypatch):
    from taas.studio.mcp_registry import MCPRegistryError, _load_config

    monkeypatch.setenv("TAAS_MCP_SERVERS_JSON", '[{"id":"bad id","name":"X","command":"python"}]')
    with pytest.raises(MCPRegistryError):
        _load_config()
    monkeypatch.setenv("TAAS_MCP_SERVERS_JSON", '[{"id":"ok","name":"X","command":"python"},{"id":"ok","name":"Y","command":"python"}]')
    with pytest.raises(MCPRegistryError):
        _load_config()


def test_mcp_registry_never_accepts_inline_secret_values(monkeypatch):
    from taas.studio.mcp_registry import MCPRegistryError, _load_config

    monkeypatch.setenv("TAAS_MCP_SERVERS_JSON", '[{"id":"ok","name":"X","command":"python","env":{"API_KEY":"secret"}}]')
    with pytest.raises(MCPRegistryError):
        _load_config()


def _valid_agent_manifest():
    return {
        "apiVersion": "taas.ai/v1alpha1",
        "kind": "Agent",
        "metadata": {
            "id": "support-assistant",
            "name": "Support Assistant",
            "version": "1.0.0",
            "description": "Draft support workflow agent",
        },
        "spec": {
            "model": {"provider": "huggingface", "model_id": "Qwen/Qwen2.5-0.5B-Instruct"},
            "instructions": "Help the operator summarize support requests.",
            "tool_allowlist": [],
            "resources": {"max_new_tokens": 512, "timeout_seconds": 90, "max_tool_calls": 0},
            "approval": {
                "require_human_approval": True,
                "require_assurance": True,
                "allow_side_effects": False,
            },
        },
    }


def test_agent_manifest_validation_is_authenticated_and_non_executing(monkeypatch):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    payload = _valid_agent_manifest()
    unauthorized = client.post("/api/v1/agents/validate", json=payload)
    assert unauthorized.status_code == 401

    response = client.post(
        "/api/v1/agents/validate",
        headers={"Authorization": "Bearer test-token"},
        json=payload,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["manifest"]["metadata"]["id"] == "support-assistant"
    assert data["lifecycle_state"] == "draft"
    assert data["semantic_correctness_verified"] is False
    assert data["tools_authorized"] is False
    assert data["execution_enabled"] is False


def test_agent_manifest_rejects_unknown_fields_and_invalid_model_ids(monkeypatch):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    payload = _valid_agent_manifest()
    payload["spec"]["model"]["model_id"] = "../untrusted-code"
    payload["spec"]["unexpected"] = "must be rejected"
    response = client.post(
        "/api/v1/agents/validate",
        headers={"Authorization": "Bearer test-token"},
        json=payload,
    )
    assert response.status_code == 422


def test_agent_manifest_rejects_duplicate_tool_grants(monkeypatch):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    payload = _valid_agent_manifest()
    payload["spec"]["tool_allowlist"] = [
        {"server_id": "docs", "tool_name": "search"},
        {"server_id": "docs", "tool_name": "search"},
    ]
    payload["spec"]["resources"]["max_tool_calls"] = 2
    response = client.post(
        "/api/v1/agents/validate",
        headers={"Authorization": "Bearer test-token"},
        json=payload,
    )
    assert response.status_code == 422


def test_agent_manifest_requires_human_approval_for_side_effects(monkeypatch):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    payload = _valid_agent_manifest()
    payload["spec"]["approval"]["allow_side_effects"] = True
    payload["spec"]["approval"]["require_human_approval"] = False
    response = client.post(
        "/api/v1/agents/validate",
        headers={"Authorization": "Bearer test-token"},
        json=payload,
    )
    assert response.status_code == 422


def test_agent_manifest_rejects_mutable_or_malformed_model_revision(monkeypatch):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    payload = _valid_agent_manifest()
    payload["spec"]["model"]["revision"] = "main"
    response = client.post(
        "/api/v1/agents/validate",
        headers={"Authorization": "Bearer test-token"},
        json=payload,
    )
    assert response.status_code == 422


def test_agent_manifest_requires_full_model_commit_sha(monkeypatch):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    payload = _valid_agent_manifest()
    payload["spec"]["model"]["revision"] = "1234567"
    response = client.post(
        "/api/v1/agents/validate",
        headers={"Authorization": "Bearer test-token"},
        json=payload,
    )
    assert response.status_code == 422


def _mcp_inspection_fixture():
    return {
        "server_id": "docs",
        "server_name": "Documentation tools",
        "server_info": {"name": "docs-server", "version": "1.2.0"},
        "protocol_version": "2025-06-18",
        "tool_count": 1,
        "tools": [{
            "server": "docs",
            "name": "search",
            "description": "Search documentation",
            "input_schema": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
            "output_schema": None,
            "annotations": {"readOnlyHint": True},
            "source": "mcp-live-inspection",
            "category": "mcp",
        }],
        "inspection_only": True,
        "tool_execution_performed": False,
    }


def test_mcp_registry_snapshot_is_read_only_content_addressed_and_retrievable(monkeypatch, tmp_path):
    from taas.studio import api

    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    monkeypatch.setenv("TAAS_AGENT_REGISTRY_PATH", str(tmp_path / "agents.sqlite3"))
    monkeypatch.setattr(api, "list_mcp_servers", lambda: {
        "count": 1,
        "servers": [{"id": "docs", "name": "Documentation tools", "transport": "stdio"}],
    })
    monkeypatch.setattr(api, "inspect_mcp_server", lambda server_id: _mcp_inspection_fixture())
    headers = {"Authorization": "Bearer test-token"}

    first = client.post("/api/v1/mcp/registry/snapshots/inspect", headers=headers)
    assert first.status_code == 200
    snapshot = first.json()
    assert len(snapshot["snapshot_id"]) == 64
    assert snapshot["server_count"] == 1
    assert snapshot["tool_count"] == 1
    assert snapshot["snapshot"]["servers"][0]["inspection_only"] is True
    assert snapshot["snapshot"]["servers"][0]["tool_execution_performed"] is False
    tool = snapshot["snapshot"]["servers"][0]["tools"][0]
    assert len(tool["definition_sha256"]) == 64

    second = client.post("/api/v1/mcp/registry/snapshots/inspect", headers=headers)
    assert second.status_code == 200
    assert second.json()["snapshot_id"] == snapshot["snapshot_id"]

    fetched = client.get(
        f"/api/v1/mcp/registry/snapshots/{snapshot['snapshot_id']}",
        headers=headers,
    )
    assert fetched.status_code == 200
    assert fetched.json()["snapshot"] == snapshot["snapshot"]

    listing = client.get("/api/v1/mcp/registry/snapshots", headers=headers)
    assert listing.status_code == 200
    assert listing.json()["count"] == 1


def test_mcp_registry_snapshot_rejects_non_read_only_inspection(monkeypatch, tmp_path):
    from taas.studio import api

    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    monkeypatch.setenv("TAAS_AGENT_REGISTRY_PATH", str(tmp_path / "agents.sqlite3"))
    monkeypatch.setattr(api, "list_mcp_servers", lambda: {
        "count": 1,
        "servers": [{"id": "docs", "name": "Documentation tools", "transport": "stdio"}],
    })
    unsafe = _mcp_inspection_fixture()
    unsafe["tool_execution_performed"] = True
    monkeypatch.setattr(api, "inspect_mcp_server", lambda server_id: unsafe)
    headers = {"Authorization": "Bearer test-token"}

    response = client.post("/api/v1/mcp/registry/snapshots/inspect", headers=headers)
    assert response.status_code == 502
    listing = client.get("/api/v1/mcp/registry/snapshots", headers=headers)
    assert listing.json()["count"] == 0


def test_agent_publish_requires_exact_mcp_snapshot_for_tool_grants(monkeypatch, tmp_path):
    from taas.studio import api

    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    monkeypatch.setenv("TAAS_AGENT_REGISTRY_PATH", str(tmp_path / "agents.sqlite3"))
    monkeypatch.setattr(api, "list_mcp_servers", lambda: {
        "count": 1,
        "servers": [{"id": "docs", "name": "Documentation tools", "transport": "stdio"}],
    })
    monkeypatch.setattr(api, "inspect_mcp_server", lambda server_id: _mcp_inspection_fixture())
    headers = {"Authorization": "Bearer test-token"}
    payload = _valid_agent_manifest()
    payload["spec"]["tool_allowlist"] = [{"server_id": "docs", "tool_name": "search"}]
    payload["spec"]["resources"]["max_tool_calls"] = 1

    created = client.post("/api/v1/agents", headers=headers, json=payload)
    assert created.status_code == 201
    path = "/api/v1/agents/support-assistant/versions/1.0.0"
    assert client.post(path + "/validate", headers=headers).status_code == 200

    missing_snapshot = client.post(path + "/publish", headers=headers)
    assert missing_snapshot.status_code == 422

    captured = client.post("/api/v1/mcp/registry/snapshots/inspect", headers=headers)
    snapshot_id = captured.json()["snapshot_id"]
    published = client.post(
        path + "/publish",
        headers=headers,
        json={"registry_snapshot_id": snapshot_id},
    )
    assert published.status_code == 200
    data = published.json()
    assert data["lifecycle_state"] == "published"
    assert data["registry_snapshot_id"] == snapshot_id
    assert data["resolved_tool_grants"][0]["server_id"] == "docs"
    assert data["resolved_tool_grants"][0]["tool_name"] == "search"
    assert len(data["resolved_tool_grants"][0]["tool_definition_sha256"]) == 64
    assert data["tools_authorized"] is False
    assert data["execution_enabled"] is False


def test_agent_publish_rejects_tool_grants_absent_from_snapshot(monkeypatch, tmp_path):
    from taas.studio import api

    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    monkeypatch.setenv("TAAS_AGENT_REGISTRY_PATH", str(tmp_path / "agents.sqlite3"))
    monkeypatch.setattr(api, "list_mcp_servers", lambda: {
        "count": 1,
        "servers": [{"id": "docs", "name": "Documentation tools", "transport": "stdio"}],
    })
    monkeypatch.setattr(api, "inspect_mcp_server", lambda server_id: _mcp_inspection_fixture())
    headers = {"Authorization": "Bearer test-token"}
    payload = _valid_agent_manifest()
    payload["spec"]["tool_allowlist"] = [{"server_id": "docs", "tool_name": "delete_all"}]
    payload["spec"]["resources"]["max_tool_calls"] = 1

    created = client.post("/api/v1/agents", headers=headers, json=payload)
    assert created.status_code == 201
    path = "/api/v1/agents/support-assistant/versions/1.0.0"
    assert client.post(path + "/validate", headers=headers).status_code == 200
    snapshot = client.post("/api/v1/mcp/registry/snapshots/inspect", headers=headers).json()

    rejected = client.post(
        path + "/publish",
        headers=headers,
        json={"registry_snapshot_id": snapshot["snapshot_id"]},
    )
    assert rejected.status_code == 409
    current = client.get(path, headers=headers).json()
    assert current["lifecycle_state"] == "validated"
    assert current["registry_snapshot_id"] is None


def test_agent_registry_snapshot_binding_is_one_time_and_audited(monkeypatch, tmp_path):
    from taas.studio import agent_registry

    monkeypatch.setenv("TAAS_AGENT_REGISTRY_PATH", str(tmp_path / "agents.sqlite3"))
    manifest = _valid_agent_manifest()
    created = agent_registry.create_draft(manifest)
    snapshot = agent_registry.store_mcp_snapshot({
        "schema_version": "taas.mcp.registry/v1",
        "capture_mode": "test",
        "servers": [],
    })
    validated = agent_registry.transition("support-assistant", "1.0.0", "validated")
    published = agent_registry.transition(
        "support-assistant", "1.0.0", "published",
        registry_snapshot_id=snapshot["snapshot_id"],
    )
    assert published["registry_snapshot_id"] == snapshot["snapshot_id"]
    events = agent_registry.list_events("support-assistant")["events"]
    assert events[0]["registry_snapshot_id"] == snapshot["snapshot_id"]


def test_ollama_provider_load_chat_and_status(monkeypatch):
    from taas.studio.ollama_runtime import OllamaModelRuntime

    monkeypatch.setenv("TAAS_OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    runtime = OllamaModelRuntime()
    calls = []

    def fake_request(path, payload=None, timeout=30):
        calls.append((path, payload))
        if path == "/api/show":
            return {"modelfile": "FROM qwen2.5"}
        if path == "/api/tags":
            return {"models": [{"name": "qwen2.5:0.5b", "size": 123}]}
        if path == "/api/chat":
            return {"message": {"content": "hello"}, "prompt_eval_count": 4, "eval_count": 2}
        raise AssertionError(path)

    monkeypatch.setattr(runtime, "_request", fake_request)
    selected = runtime.load("qwen2.5:0.5b")
    assert selected["model_selected"] == "qwen2.5:0.5b"
    assert selected["load_semantics"].startswith("validated")
    assert selected["available"] is True
    result = runtime.chat("hi")
    assert result["text"] == "hello"
    assert result["provider"] == "ollama"
    assert result["device"] == "managed-by-ollama"
    assert calls[0][0] == "/api/show"
    assert calls[-1][0] == "/api/chat"


def test_ollama_provider_rejects_invalid_model_tag():
    from taas.studio.ollama_runtime import OllamaModelRuntime

    with pytest.raises(ValueError):
        OllamaModelRuntime().load("../unsafe model")


def test_ollama_provider_rejects_embedded_credentials_in_endpoint(monkeypatch):
    from taas.studio.ollama_runtime import OllamaModelRuntime, ModelRuntimeError

    monkeypatch.setenv("TAAS_OLLAMA_BASE_URL", "http://user:pass@example.test:11434")
    status = OllamaModelRuntime().status()
    assert status["available"] is False
    assert "without embedded credentials" in status["last_error"]


def test_model_load_endpoint_routes_to_ollama_provider(monkeypatch):
    from taas.studio import api

    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")

    class Ollama:
        def load(self, model_id):
            return {"provider": "ollama", "model_selected": model_id}

    monkeypatch.setattr(api, "get_ollama_runtime", lambda: Ollama())
    response = client.post("/api/v1/models/load",
                           headers={"Authorization": "Bearer test-token"},
                           json={"provider": "ollama", "model_id": "qwen2.5:0.5b"})
    assert response.status_code == 200
    assert response.json()["provider"] == "ollama"


def test_model_chat_endpoint_routes_to_ollama_provider(monkeypatch):
    from taas.studio import api

    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")

    class Ollama:
        def chat(self, message, system, max_new_tokens, temperature):
            return {"provider": "ollama", "text": "response", "device": "managed-by-ollama"}

    monkeypatch.setattr(api, "get_ollama_runtime", lambda: Ollama())
    response = client.post("/api/v1/models/chat",
                           headers={"Authorization": "Bearer test-token"},
                           json={"provider": "ollama", "message": "hello"})
    assert response.status_code == 200
    assert response.json()["provider"] == "ollama"
    assert response.json()["text"] == "response"

def test_ollama_load_rejects_huggingface_device_selection(monkeypatch):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    response = client.post("/api/v1/models/load",
                           headers={"Authorization": "Bearer test-token"},
                           json={"provider": "ollama", "model_id": "qwen2.5:0.5b", "device": "cpu"})
    assert response.status_code == 422
    assert "Ollama manages device placement" in response.json()["detail"]


def test_canonical_objective_prepare_endpoint_runs_goal_decomposition_and_core_analysis(monkeypatch):
    from taas.studio import api

    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    goal_spec = {
        "prompt": "Explain precision and recall",
        "prompt_inputs": ["text"],
        "goals": [{
            "id": "g1", "class": "answer", "in": ["text"], "out": "text",
            "eff": [], "sigma": "native", "desc": "Explain precision and recall",
            "deps": [], "n": 1, "exactness": "tolerant", "lang": "en", "optional": False,
        }],
    }

    class Runtime:
        def decompose(self, prompt, context, max_new_tokens):
            assert "TaaS Core Objective Contract v2" in context
            return {"text": "{}", "goal_spec": goal_spec, "json_valid": True,
                    "model_id": "test/model", "semantic_correctness_verified": False}

    monkeypatch.setattr(api, "get_model_runtime", lambda: Runtime())
    response = client.post("/api/v1/objectives/prepare",
                           headers={"Authorization": "Bearer test-token"},
                           json={"prompt": "Explain precision and recall"})
    assert response.status_code == 200
    data = response.json()
    assert data["structural_validation"]["valid"] is True
    assert data["core_analysis"]["status"] != "not_analyzed"
    assert data["core_analysis"]["goal_order"] == ["g1"]
    assert data["conformance"]["semantic_correctness_verified"] is False
    assert data["conformance"]["auto_applied"] is False
    assert data["objective_contract"]["contract_version"] == "2.0"
    assert data["objective_coverage"]["summary"] == {"required": 1, "covered": 1, "missing": 0}
    assert data["semantic_review_required"] is True
    assert data["workflow"]["objective_interpretation"] == "completed"
    assert data["workflow"]["tool_discovery"] == "awaiting_human_review_and_selected_tool_metadata"
    assert data["workflow"]["tool_execution"] == "disabled"


def test_canonical_objective_prepare_endpoint_requires_studio_authentication():
    response = client.post("/api/v1/objectives/prepare",
                           json={"prompt": "Explain precision and recall"})
    assert response.status_code == 503 or response.status_code == 401


def test_studio_frontend_routes_operational_objectives_through_core_first_workflow():
    response = client.get("/")
    assert response.status_code == 200
    page = response.text
    assert "Objective Engineering · TaaS Core" in page
    assert "Free-form inference only" in page
    assert 'id="agent-route-prompt-core"' in page
    assert "Prepare this prompt with TaaS Core" in page
    assert 'id="goal-semantic-review"' in page
    assert "human_review_confirmed" in page
    assert '$("goal-add").addEventListener("click",invalidateHumanReview)' in page
    assert 'runtimePost("/api/v1/objectives/prepare"' in page
    assert 'id="agent-outcome-coverage"' in page
    assert "renderObjectiveCoverage(result.objective_coverage)" in page
    assert "Coverage shows structural mapping only" in page
    assert "const missingOutcomes=" in page
    assert "!missingOutcomes" in page


def test_canonical_objective_discover_endpoint_runs_existing_core_discovery(monkeypatch):
    from types import SimpleNamespace
    from taas.studio import api

    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")

    class FakeEngine:
        def __init__(self, contracts, profile, trust, cfg):
            self.H = object()
            self.composer = SimpleNamespace(model_edges=lambda goals: [])

        def discover(self, spec, policy):
            return SimpleNamespace(
                spec=spec, gap=SimpleNamespace(gap=[], rho=0.0),
                compose=SimpleNamespace(reachability=None, candidates=[], regime="exact", stats={}),
                certificate=None, counterexample=None, toolkit=None, time_s=0.01, abstained=True,
            )

    monkeypatch.setattr(api, "DiscoveryEngine", FakeEngine)
    response = client.post("/api/v1/objectives/discover",
        headers={"Authorization": "Bearer test-token"},
        json={
            "goal_spec": {
                "prompt": "List customer orders", "prompt_inputs": ["text"],
                "goals": [{"id": "g1", "class": "retrieve", "in": ["query"],
                           "out": "record[]", "eff": ["read(orders)"], "sigma": "data",
                           "deps": [], "desc": "List customer orders"}],
            },
            "human_review_confirmed": True,
            "tools": [{"server": "orders", "name": "list_orders",
                       "input_schema": {"type": "object", "properties": {}}}],
        })
    assert response.status_code == 200
    assert response.json()["status"] == "abstained"
    assert response.json()["execution_performed"] is False


def test_studio_pipeline_ui_orders_core_before_tool_discovery():
    page = client.get("/").text
    labels = [
        "Objective intelligence", "GoalSpec decomposition", "Core validation",
        "Tool intelligence", "Discovery &amp; hypergraph", "Assurance &amp; decision",
        "Governed execution",
    ]
    pipeline_start = page.index('class="pipeline-steps"')
    positions = [page.index(label, pipeline_start) for label in labels]
    assert positions == sorted(positions)
    assert 'fetch("/api/v1/objectives/discover"' in page


def test_core_discovery_requires_explicit_human_review(monkeypatch):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    response = client.post(
        "/api/v1/objectives/discover",
        headers={"Authorization": "Bearer test-token"},
        json={"goal_spec": {}, "tools": [{"server": "s", "name": "t"}]},
    )
    assert response.status_code == 409
    assert "Human review is required" in response.json()["detail"]


def test_discovery_revalidates_objective_conformance_before_core_engine(monkeypatch):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")

    def must_not_run(*args, **kwargs):
        raise AssertionError("DiscoveryEngine must not run for a nonconformant GoalSpec")

    from taas.studio import api
    monkeypatch.setattr(api, "DiscoveryEngine", must_not_run)
    response = client.post(
        "/api/v1/objectives/discover",
        headers={"Authorization": "Bearer test-token"},
        json={
            "human_review_confirmed": True,
            "goal_spec": {
                "prompt": "Count all invoices issued this year.",
                "prompt_inputs": ["text"],
                "goals": [{
                    "id": "g1", "class": "retrieve", "in": ["query"],
                    "out": "record[]", "eff": ["read(*)"], "sigma": "data",
                    "deps": [], "desc": "Retrieve all invoices issued this year",
                }],
            },
            "tools": [{"server": "invoice_source", "name": "list_invoices",
                       "input_schema": {"type": "object", "properties": {}}}],
        },
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "conformance rejected" in detail["message"]
    assert any(item["code"] == "objective_operation_missing"
               for item in detail["diagnostics"])
