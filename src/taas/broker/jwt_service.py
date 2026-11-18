"""JWT validation and issuance for the token broker.

Two modes, both real:

- **Prod mode** — validate subject tokens against a real OIDC issuer's JWKS
  (``TAAS_BROKER_ISSUER`` + ``TAAS_BROKER_JWKS_URI``; Entra ID, Okta, Keycloak
  all work). Audience + expiry + signature enforced.
- **Dev mode** — a local issuer (``TAAS_BROKER_DEV_SECRET``, HS256) that mints
  and validates subject tokens for Colab/test environments. A real JWT
  issuer, just local — not a simulation.

Issued tokens are always opaque outward: a random handle backed by the
token store, never a JWT carrying internal claims to consumers.
"""
from __future__ import annotations

import os
import time
from typing import Any

import jwt
from jwt import PyJWKClient


class BrokerError(RuntimeError):
    """Token validation/issuance failure — maps to normalized deny responses."""


def _issuer() -> str:
    return os.environ.get("TAAS_BROKER_ISSUER", "").strip()


def _audience() -> str:
    return os.environ.get("TAAS_BROKER_AUDIENCE", "taas-mcp").strip()


def _jwks_client() -> PyJWKClient:
    uri = os.environ.get("TAAS_BROKER_JWKS_URI", "").strip()
    if not uri and _issuer():
        uri = _issuer().rstrip("/") + "/.well-known/jwks.json"
    if not uri:
        raise BrokerError("Prod mode requires TAAS_BROKER_JWKS_URI or TAAS_BROKER_ISSUER")
    return PyJWKClient(uri, cache_keys=True)


def _dev_secret() -> str:
    raw = os.environ.get("TAAS_BROKER_DEV_SECRET", "").strip()
    if not raw:
        raise BrokerError("Dev mode requires TAAS_BROKER_DEV_SECRET")
    return raw


def prod_mode() -> bool:
    """True when a real OIDC issuer is configured; False → dev issuer."""
    return bool(_issuer() or os.environ.get("TAAS_BROKER_JWKS_URI", "").strip())


def validate_subject_token(token: str) -> dict[str, Any]:
    """Validate an inbound subject token; returns its claims.

    Prod: RS256/ES256 signature checked against issuer JWKS + iss/aud/exp.
    Dev: HS256 signature checked against TAAS_BROKER_DEV_SECRET.
    """
    try:
        if prod_mode():
            signing_key = _jwks_client().get_signing_key_from_jwt(token)
            return jwt.decode(token, signing_key.key, algorithms=["RS256", "ES256"],
                              audience=_audience(), issuer=_issuer() or None,
                              options={"verify_iss": bool(_issuer())})
        return jwt.decode(token, _dev_secret(), algorithms=["HS256"],
                          audience=_audience(),
                          options={"verify_iss": False})
    except jwt.PyJWTError as exc:
        raise BrokerError(f"subject token invalid: {type(exc).__name__}") from exc


def mint_dev_token(subject: str, scope: str, ttl_seconds: int = 300,
                   extra: dict[str, Any] | None = None) -> str:
    """Mint a dev-mode subject token (test/Colab only — a real JWT issuer)."""
    if prod_mode():
        raise BrokerError("dev token minting disabled in prod mode")
    now = int(time.time())
    claims = {"sub": subject, "aud": _audience(), "scope": scope,
              "iat": now, "exp": now + ttl_seconds, **(extra or {})}
    return jwt.encode(claims, _dev_secret(), algorithm="HS256")


def downscope(scope: str, server_id: str, capability: str) -> str:
    """RFC 8693-style scope narrowing: only ever shrink, never widen."""
    requested = f"mcp:{capability}:server:{server_id}"
    granted = scope.split()
    if requested in granted or "*" in granted or "mcp:*" in granted:
        return requested
    raise BrokerError(
        f"subject scope does not grant {requested} (downscope is shrink-only)")
