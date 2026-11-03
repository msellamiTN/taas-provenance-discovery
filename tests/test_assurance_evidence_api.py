from fastapi.testclient import TestClient

from taas.studio.api import app

client = TestClient(app)


def test_assurance_evidence_route_requires_authentication(monkeypatch):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    response = client.get("/api/v1/assurance/evidence/" + "1" * 64)
    assert response.status_code == 401


def test_assurance_evidence_route_rejects_malformed_id(monkeypatch):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    response = client.get(
        "/api/v1/assurance/evidence/not-a-digest",
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 422
