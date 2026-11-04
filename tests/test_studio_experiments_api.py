import os
from fastapi.testclient import TestClient
from taas.studio.experiments_api import app

client = TestClient(app)


def headers():
    os.environ["TAAS_STUDIO_API_TOKEN"] = "test-token"
    return {"Authorization": "Bearer test-token"}


def test_catalog_api_is_authenticated():
    os.environ["TAAS_STUDIO_API_TOKEN"] = "test-token"
    assert client.get("/api/v1/experiments/catalog").status_code == 401


def test_catalog_api_lists_22_planned_experiments():
    response = client.get("/api/v1/experiments/catalog", headers=headers())
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 22
    assert data["planned_not_run"] == 22
    assert data["results_loaded"] is False


def test_variant_api_exposes_three_leave_one_out_variants_and_factorial():
    response = client.get("/api/v1/experiments/variants", headers=headers())
    assert response.status_code == 200
    data = response.json()
    assert len(data["factorial_design"]["cells"]) == 8
    assert data["variants"]["PaMCP_NoGap"]["G"] == 0
    assert data["variants"]["PaMCP_Declared"]["P"] == 0
    assert data["variants"]["PaMCP_NoCert"]["S"] == 0


def test_validate_requires_frozen_dataset_hash():
    response = client.post("/api/v1/experiments/validate", headers=headers(), json={
        "experiment_id": "E1", "variant": "Full_PaMCP",
        "dataset_snapshot": {"name": "merged_registry", "version_or_hash": ""},
        "split": "all", "parameters": {}, "seeds": [1]
    })
    assert response.status_code == 422


def test_validate_is_validation_only_not_execution():
    response = client.post("/api/v1/experiments/validate", headers=headers(), json={
        "experiment_id": "E1", "variant": "Full_PaMCP",
        "dataset_snapshot": {"name": "merged_registry", "version_or_hash": "sha256:abc"},
        "split": "all", "parameters": {}, "seeds": [1]
    })
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["execution_enabled"] is False
    assert data["evaluator_access_granted"] is False
    assert data["status"] == "validated_not_queued"


def test_workbench_status_does_not_claim_runner_or_sandbox():
    response = client.get("/api/v1/experiments/workbench/status", headers=headers())
    assert response.status_code == 200
    data = response.json()
    assert data["execution_enabled"] is False
    assert data["sequential_runner"] == "not_implemented"
    assert data["mcp_execution_sandbox"] == "not_implemented"


def test_existing_studio_mounts_experiment_catalog(monkeypatch):
    from fastapi.testclient import TestClient
    from taas.studio.api import app
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    response = TestClient(app).get(
        "/api/v1/experiments/catalog",
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200
    assert response.json()["total"] == 22
    assert response.json()["planned_not_run"] == 22
