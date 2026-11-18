"""Token broker HTTP API — RFC 8693-style exchange + introspection.

Endpoints:
- ``POST /token`` — exchange a subject token for an opaque downscoped token
- ``POST /introspect`` — resolve an opaque handle (used by the proxy)
- ``POST /dev/issue`` — mint a dev-mode subject token (dev mode only)

Denials are normalized RFC 6750-style responses — never a per-layer shape.
"""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Form
from fastapi.responses import JSONResponse

from . import jwt_service, tokens

app = FastAPI(title="TaaS Token Broker", version="0.1.0")


def _deny(error: str, description: str, status: int = 400) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": error, "error_description": description})


@app.post("/token")
def token_exchange(
    grant_type: str = Form(...),
    subject_token: str = Form(...),
    subject_token_type: str = Form("urn:ietf:params:oauth:token-type:access_token"),
    requested_scope: str = Form(...),
    audience: str = Form("taas-mcp"),
) -> Any:
    """Exchange a subject token for an opaque, downscoped access token."""
    if grant_type != "urn:ietf:params:oauth:grant-type:token-exchange":
        return _deny("unsupported_grant_type", "only token-exchange is supported")
    try:
        claims = jwt_service.validate_subject_token(subject_token)
    except jwt_service.BrokerError as exc:
        return _deny("invalid_grant", str(exc), status=401)
    try:
        scope = jwt_service.downscope(
            claims.get("scope", ""), _server_from_scope(requested_scope),
            _capability_from_scope(requested_scope))
    except jwt_service.BrokerError as exc:
        return _deny("insufficient_scope", str(exc), status=403)
    issued = tokens.issue(subject=claims["sub"], scope=scope, audience=audience)
    return JSONResponse(status_code=200, content=issued)


@app.post("/introspect")
def introspect(token: str = Form(...)) -> dict[str, Any]:
    """Resolve an opaque handle; ``active: false`` for unknown/expired."""
    return tokens.introspect(token) or {"active": False}


@app.post("/dev/issue")
def dev_issue(subject: str = Form(...), scope: str = Form(...),
              ttl_seconds: int = Form(300)) -> Any:
    """Mint a dev-mode subject token — disabled in prod mode."""
    try:
        return {"subject_token": jwt_service.mint_dev_token(
            subject=subject, scope=scope, ttl_seconds=ttl_seconds)}
    except jwt_service.BrokerError as exc:
        return _deny("unauthorized_client", str(exc), status=403)


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "mode": "prod" if jwt_service.prod_mode() else "dev"}


def _server_from_scope(scope: str) -> str:
    # format: mcp:<capability>:server:<server_id>, e.g. mcp:tools:list:server:demo
    parts = scope.split(":")
    return parts[4] if len(parts) > 4 else ""


def _capability_from_scope(scope: str) -> str:
    parts = scope.split(":")
    return ":".join(parts[1:3]) if len(parts) > 3 else "tools:list"
