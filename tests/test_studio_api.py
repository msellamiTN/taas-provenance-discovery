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
