"""Policy profiles for the MCP proxy (E3 exposure_rules).

Loaded from ``TAAS_POLICY_PROFILES_FILE`` (JSON). A profile decides which
tools a consumer sees — hidden tools are counted, never listed.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class PolicyProfileError(RuntimeError):
    pass


def _profiles_path() -> Path | None:
    raw = os.environ.get("TAAS_POLICY_PROFILES_FILE", "").strip()
    return Path(raw).expanduser().resolve() if raw else None


def load_profiles() -> dict[str, Any]:
    path = _profiles_path()
    if path is None or not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PolicyProfileError("policy profiles file must be valid JSON") from exc
    if not isinstance(data, dict):
        raise PolicyProfileError("policy profiles file must be an object")
    return data


def get_profile(name: str) -> dict[str, Any]:
    profiles = load_profiles()
    if name not in profiles:
        raise PolicyProfileError(f"unknown policy profile: {name}")
    return profiles[name]


def visible_tools(profile: dict[str, Any], tools: list[dict[str, Any]]
                  ) -> list[dict[str, Any]]:
    """Apply allow/deny lists; deny wins. Default = allow all not denied."""
    allow = set(profile.get("allow_tools") or [])
    deny = set(profile.get("deny_tools") or [])
    default_allow = profile.get("default", "allow") == "allow"
    out = []
    for t in tools:
        name = t.get("name", "")
        if name in deny:
            continue
        if allow and name not in allow:
            continue
        if not allow and not default_allow:
            continue
        out.append(t)
    return out
