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


def test_discovery_fails_closed_without_profile(monkeypatch):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "test-token")
    monkeypatch.delenv("TAAS_MODEL_PROFILE", raising=False)
    response = client.post(
        "/api/v1/discover",
        headers={"Authorization": "Bearer test-token"},
        json={
            "goal_spec": {"goals": [{"id": "g1", "class": "search", "in": ["text"], "out": "document", "sigma": "data"}]},
            "tools": [{"server": "s", "name": "search", "description": "search", "input_schema": {}}],
        },
    )
    assert response.status_code == 503


def test_studio_home_serves_browser_workspace():
    response = client.get("/")
    assert response.status_code == 200
    assert "TaaS Core Studio" in response.text
    assert "/api/v1/discover" in response.text
