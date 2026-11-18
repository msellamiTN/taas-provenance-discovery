"""MCP proxy HTTP service — the real filtered tools/list data path.

Flow per request:
  1. Bearer opaque token → broker introspection (401 on inactive)
  2. Server record + exposure → signature verify (403 on forged/unsigned
     gateway exposure)
  3. Policy profile → visibility filter (deny wins, hidden tools counted)
  4. Real MCP client → live tools/list against the stdio server
  5. Response in the filtered-tools-list contract shape
  6. gateway.decision audit event (reuses the studio ledger env)

``POST /mcp/{server}/tools/call`` is a hard 403 — Phase C seam, not a route.
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException

from . import policy_profiles

BROKER_URL = os.environ.get("TAAS_BROKER_URL", "http://127.0.0.1:8001")

app = FastAPI(title="TaaS MCP Proxy", version="0.1.0")


def _audit(subject: str, decision: str, detail: dict[str, Any]) -> None:
    try:
        from taas.studio import audit_ledger
        audit_ledger.append_event(
            "policy_verdict",
            {"kind": "gateway.decision", "subject": subject},
            {"decision": decision, **detail})
    except Exception:
        pass  # audit is best-effort locally; the anchored tier is separate


async def _introspect(token: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(f"{BROKER_URL}/introspect",
                              data={"token": token})
    claims = r.json()
    if not claims.get("active"):
        raise HTTPException(status_code=401, detail="token inactive")
    return claims


def _server_record(server_id: str) -> dict[str, Any]:
    from taas.studio import mcp_registry
    try:
        servers = {s["id"]: s for s in mcp_registry._load_config()}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"registry load: {exc}")
    if server_id not in servers:
        raise HTTPException(status_code=404, detail="unknown server")
    return servers[server_id]


def _check_exposure(server: dict[str, Any]) -> dict[str, Any]:
    exposure = server.get("exposure") or {}
    if exposure.get("mode") != "gateway":
        raise HTTPException(status_code=403,
                            detail="server not exposed via gateway mode")
    sig = server.get("exposure_signature")
    from taas.studio.exposure_signing import verify_exposure
    if not sig or not verify_exposure(exposure, sig):
        raise HTTPException(status_code=403,
                            detail="exposure unsigned or signature invalid")
    return exposure


async def _list_tools(server: dict[str, Any], timeout: float = 20.0
                      ) -> list[dict[str, Any]]:
    """Real MCP client — spawns the stdio server, lists tools, exits."""
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ImportError:
        raise HTTPException(status_code=503,
                            detail="mcp package not installed on proxy")
    params = StdioServerParameters(
        command=server["command"], args=server["args"],
        env={k: os.environ[k] for k in server["env"] if k in os.environ})

    async def run() -> list[dict[str, Any]]:
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w) as session:
                await session.initialize()
                res = await session.list_tools()
                return [{"name": t.name, "description": t.description or "",
                         "input_schema": t.inputSchema or {"type": "object"}}
                        for t in res.tools]
    try:
        return await asyncio.wait_for(run(), timeout=timeout)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="backend inspect timeout")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502,
                            detail=f"backend list_tools failed: {exc}")


@app.get("/mcp/{server_id}/tools")
async def list_tools(server_id: str,
                     authorization: str = Header(default="")) -> dict[str, Any]:
    token = authorization.removeprefix("Bearer ").strip()
    if not token or token == authorization:
        raise HTTPException(status_code=401, detail="bearer token required")
    claims = await _introspect(token)
    server = _server_record(server_id)
    exposure = _check_exposure(server)
    profile_name = exposure.get("policy_profile_ref", "default")
    try:
        profile = policy_profiles.get_profile(profile_name)
    except policy_profiles.PolicyProfileError:
        profile = {"default": "allow"}  # no profile = unfiltered (documented)
    raw_tools = await _list_tools(server)
    visible = policy_profiles.visible_tools(profile, raw_tools)
    _audit(claims["sub"], "allow",
           {"server_id": server_id, "profile": profile_name,
            "visible": len(visible), "hidden": len(raw_tools) - len(visible)})
    return {
        "schema": "taas.filtered-tools-list/v1",
        "server_id": server_id,
        "policy_profile": profile_name,
        "tools": visible,
        "filter": {"visible_count": len(visible),
                   "hidden_count": len(raw_tools) - len(visible)},
        "inspection_only": True,
    }


@app.post("/mcp/{server_id}/tools/call")
async def tools_call(server_id: str,
                     authorization: str = Header(default="")) -> None:
    _audit("unknown", "deny", {"server_id": server_id,
                               "reason": "tools/call is Phase C PEP gate"})
    raise HTTPException(
        status_code=403,
        detail="tools/call is not on the data path — Phase C governed execution only")


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "broker": BROKER_URL}
