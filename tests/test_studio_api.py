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
    assert "TaaS Core Studio" in response.text
    assert "/api/v1/discover" in response.text


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
        "no automatic LLM interpretation is available in this build",
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
                {"id": "g1", "class": "retrieve", "in": [], "out": "record:order[]",
                 "eff": ["read(*)"], "sigma": "data", "deps": []},
                {"id": "g2", "class": "summarise", "in": ["record:order[]"], "out": "text",
                 "eff": [], "sigma": "native", "deps": ["g1"]},
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
                {"id": "g1", "class": "retrieve", "out": "record[]"},
                {"id": "g1", "class": "answer", "out": "text"},
            ],
            "duplicate goal id",
        ),
        (
            [{"id": "g1", "class": "retrieve", "out": "record[]", "deps": ["missing"]}],
            "unknown dependency",
        ),
        (
            [
                {"id": "g1", "class": "retrieve", "out": "record[]", "deps": ["g2"]},
                {"id": "g2", "class": "answer", "out": "text", "deps": ["g1"]},
            ],
            "contains a cycle",
        ),
        (
            [{"id": "g1", "class": "retrieve", "out": "record[]", "eff": ["launch rocket"]}],
            "invalid effect",
        ),
        (
            [{"id": "g1", "class": "retrieve", "out": "made_up_type"}],
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
            "goals": [{"id": "g1", "class": "retrieve", "out": "record[]"}],
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
    assert "goalSpecState.goals=[]" in handler
    assert "example goals were cleared" in handler
    assert "author semantic goal contracts" in handler


def test_benchmark_tool_import_replaces_demo_tools_instead_of_merging():
    response = client.get("/")
    assert response.status_code == 200
    page = response.text
    handler = page.split('$("bench-add-tools").addEventListener("click",()=>{', 1)[1].split(
        '\n  function showBenchError', 1
    )[0]
    assert "body.tools=[...bench.selectedTools.values()]" in handler
    assert "Demo/sample tools were removed" in handler
    assert "new Map((body.tools||[])" not in handler


def test_visual_goal_editor_requires_authored_goal_description():
    response = client.get("/")
    assert response.status_code == 200
    assert "goal description is required; describe the intended operation" in response.text
