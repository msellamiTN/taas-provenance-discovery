"""Real E2E tests for the MCP proxy — broker + registry + live stdio server."""
from __future__ import annotations

import hashlib
import hmac
import json
import sys
import textwrap

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("mcp")
pytest.importorskip("httpx")


DEMO_SERVER = textwrap.dedent('''
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("proxy-demo")

    @mcp.tool()
    def public_tool() -> str:
        """Safe tool."""
        return "ok"

    @mcp.tool()
    def admin_wipe() -> str:
        """Dangerous tool that must be filtered."""
        return "wiped"

    if __name__ == "__main__":
        mcp.run()
''')


@pytest.fixture
def proxy_env(tmp_path, monkeypatch):
    secret = "broker-secret-padded-to-32-bytes-ok"
    sign_key = "exposure-key-padded-to-32-bytes-ok"
    monkeypatch.setenv("TAAS_BROKER_DEV_SECRET", secret)
    monkeypatch.setenv("TAAS_BROKER_TOKEN_STORE", str(tmp_path / "tokens.sqlite3"))
    monkeypatch.setenv("TAAS_EXPOSURE_SIGNING_KEY", sign_key)
    monkeypatch.setenv("TAAS_AUDIT_DB_PATH", str(tmp_path / "audit.sqlite3"))
    monkeypatch.delenv("TAAS_BROKER_ISSUER", raising=False)
    monkeypatch.delenv("TAAS_BROKER_JWKS_URI", raising=False)

    server_file = tmp_path / "demo_server.py"
    server_file.write_text(DEMO_SERVER)

    # sign the NORMALIZED block — validate_exposure keeps only these fields
    exposure = {"mode": "gateway", "route_ref": "gateway://demo/mcp",
                "policy_profile_ref": "safe", "backends": ["demo"]}
    body = json.dumps(exposure, sort_keys=True, separators=(",", ":")).encode()
    sig = hmac.new(sign_key.encode(), body, hashlib.sha256).hexdigest()
    config = [{"id": "demo", "name": "Demo",
               "command": sys.executable, "args": [str(server_file)],
               "env": [], "exposure": exposure, "exposure_signature": sig}]
    cfg = tmp_path / "mcp.json"
    cfg.write_text(json.dumps(config))
    monkeypatch.setenv("TAAS_MCP_SERVERS_FILE", str(cfg))

    profiles = tmp_path / "profiles.json"
    profiles.write_text(json.dumps({
        "safe": {"deny_tools": ["admin_wipe"]},
        "unfiltered": {"default": "allow"}}))
    monkeypatch.setenv("TAAS_POLICY_PROFILES_FILE", str(profiles))

    # run broker and proxy on the same TestClient transport
    from taas.broker import api as broker_api
    from taas.proxy import service as proxy_service
    import taas.proxy.service as svc
    monkeypatch.setattr(svc, "BROKER_URL", "")
    broker_client = TestClient(broker_api.app)

    # patch proxy's introspection to hit the in-process broker
    async def fake_introspect(token):
        r = broker_client.post("/introspect", data={"token": token})
        claims = r.json()
        if not claims.get("active"):
            from fastapi import HTTPException
            raise HTTPException(status_code=401, detail="token inactive")
        return claims
    monkeypatch.setattr(svc, "_introspect", fake_introspect)

    return {"broker": broker_client,
            "proxy": TestClient(proxy_service.app)}


def _grant(broker, scope="mcp:tools:list:server:demo"):
    mint = broker.post("/dev/issue", data={"subject": "agent-1", "scope": scope})
    subject = mint.json()["subject_token"]
    exchange = broker.post("/token", data={
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "subject_token": subject, "requested_scope": scope})
    return exchange.json()["access_token"]


def test_full_path_broker_to_proxy(proxy_env):
    token = _grant(proxy_env["broker"])
    r = proxy_env["proxy"].get("/mcp/demo/tools",
                               headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["schema"] == "taas.filtered-tools-list/v1"
    names = [t["name"] for t in body["tools"]]
    assert "public_tool" in names
    assert "admin_wipe" not in names  # filtered by the policy profile
    assert body["filter"]["hidden_count"] == 1


def test_no_token_rejected(proxy_env):
    r = proxy_env["proxy"].get("/mcp/demo/tools")
    assert r.status_code == 401


def test_bogus_token_rejected(proxy_env):
    r = proxy_env["proxy"].get("/mcp/demo/tools",
                               headers={"Authorization": "Bearer bogus"})
    assert r.status_code == 401


def test_tools_call_hard_denied(proxy_env):
    token = _grant(proxy_env["broker"])
    r = proxy_env["proxy"].post("/mcp/demo/tools/call",
                                headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403
    assert "Phase C" in r.json()["detail"]


def test_unknown_server(proxy_env):
    token = _grant(proxy_env["broker"])
    r = proxy_env["proxy"].get("/mcp/ghost/tools",
                               headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 404


def test_forged_exposure_rejected(proxy_env, tmp_path, monkeypatch):
    # tamper backends → signature invalid → proxy must refuse
    cfg = json.loads((tmp_path / "mcp.json").read_text())
    cfg[0]["exposure"]["backends"] = ["evil:8443"]
    (tmp_path / "mcp.json").write_text(json.dumps(cfg))
    token = _grant(proxy_env["broker"])
    r = proxy_env["proxy"].get("/mcp/demo/tools",
                               headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403
