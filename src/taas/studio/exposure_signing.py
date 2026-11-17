"""Signed exposure records for MCP server entries (E8).

An ``exposure`` block on a registry entry declares *how* a server is exposed
(mode, route reference, policy profile, backends). Because it can redirect a
governed path to an attacker endpoint, it is integrity-protected: the
canonical block is HMAC-signed at publication and verified at resolution.

This is the control-plane half of E8. The data-plane half — the gateway
verifying the signature plus a pinned backend identity (FQDN + TLS chain /
SPIFFE) before honoring a route — is a Phase B seam.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from typing import Any

_KEY_ENV = "TAAS_EXPOSURE_SIGNING_KEY"
_MODES = {"direct", "gateway", "rest-adapter"}


def canonical_exposure(exposure: dict[str, Any]) -> bytes:
    """Deterministic encoding — any key order or whitespace change signs the same bytes."""
    return json.dumps(exposure, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_exposure(exposure: dict[str, Any], key: str | bytes | None = None) -> str:
    """Hex HMAC-SHA256 of the canonical exposure block."""
    key_bytes = _resolve_key(key)
    return hmac.new(key_bytes, canonical_exposure(exposure), hashlib.sha256).hexdigest()


def verify_exposure(exposure: dict[str, Any], signature: str,
                    key: str | bytes | None = None) -> bool:
    """Constant-time check of an exposure signature."""
    try:
        expected = sign_exposure(exposure, key)
    except ValueError:
        return False
    return hmac.compare_digest(expected, signature)


def validate_exposure(exposure: Any, server_id: str) -> dict[str, Any]:
    """Validate and normalize an optional ``exposure`` block from a registry entry."""
    if exposure is None:
        return {}
    if not isinstance(exposure, dict):
        raise ValueError(f"MCP server {server_id} exposure must be an object")
    mode = exposure.get("mode", "direct")
    if mode not in _MODES:
        raise ValueError(
            f"MCP server {server_id} exposure.mode must be one of {sorted(_MODES)}")
    backends = exposure.get("backends", [])
    if not isinstance(backends, list) or len(backends) > 32 or any(
            not isinstance(b, str) or not b.strip() or len(b) > 512 for b in backends):
        raise ValueError(f"MCP server {server_id} exposure.backends must be an array of strings")
    out: dict[str, Any] = {"mode": mode}
    for field in ("route_ref", "policy_profile_ref"):
        val = exposure.get(field)
        if val is not None:
            if not isinstance(val, str) or not val.strip() or len(val) > 512:
                raise ValueError(f"MCP server {server_id} exposure.{field} must be a short string")
            out[field] = val.strip()
    if backends:
        out["backends"] = [b.strip() for b in backends]
    return out


def _resolve_key(key: str | bytes | None) -> bytes:
    if isinstance(key, bytes):
        return key
    raw = key if isinstance(key, str) else os.environ.get(_KEY_ENV, "")
    if not raw.strip():
        raise ValueError(f"Exposure signing requires a key: pass one or set {_KEY_ENV}")
    return raw.strip().encode("utf-8")
