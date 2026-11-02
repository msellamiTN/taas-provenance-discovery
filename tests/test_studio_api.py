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
