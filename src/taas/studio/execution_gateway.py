"""Fail-closed authorization primitives for the Studio MCP execution gateway.

This module deliberately does not start MCP servers or invoke tools. It provides
server-side, one-time approval tokens bound to an exact invocation and policy.
The API layer must obtain policy from trusted operator configuration, never from
the browser, before using these primitives.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import threading
import time
from dataclasses import dataclass
from typing import Any, Iterable

from taas.effects import Effect, parse_effects, within
from taas.policy import Policy


class GatewayDenied(PermissionError):
    """An invocation failed a mandatory gateway authorization check."""


def canonical_hash(value: Any) -> str:
    """Stable SHA-256 digest for JSON-compatible invocation data."""
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise GatewayDenied("Invocation data must be finite JSON-compatible values") from exc
    return hashlib.sha256(encoded).hexdigest()


def policy_fingerprint(policy: Policy) -> str:
    """Bind approvals to the effective policy fields used by the gateway."""
    snapshot = {
        "name": policy.name,
        "allowed": sorted(str(effect) for effect in policy.allowed),
        "required": sorted(policy.required),
        "forbidden": sorted(policy.forbidden),
        "encoding": policy.encoding,
        "lmin": policy.lmin,
        "egress_threshold": policy.egress_threshold,
        "visible": sorted(policy.visible) if policy.visible is not None else None,
        "declass": [{"label_from": r.label_from, "label_to": r.label_to, "tool_classes": sorted(r.tool_classes), "tools": sorted(r.tools), "min_evidence": r.min_evidence, "min_records": r.min_records} for r in policy.declass],
        "forbidden_pairs": sorted([list(pair) for pair in policy.forbidden_pairs]),
        "prompt_label": policy.prompt_label,
        "credentials": sorted(policy.credentials) if policy.credentials is not None else None,
    }
    return canonical_hash(snapshot)


def require_policy_allow(policy: Policy | None, effects: Iterable[str | Effect]) -> frozenset[Effect]:
    """Deny if no trusted policy is supplied or any effect falls outside its allow-set."""
    if policy is None:
        raise GatewayDenied("No trusted server-side policy is configured")
    if isinstance(effects, (str, bytes)):
        raise GatewayDenied("Effects must be a collection of effect declarations")
    try:
        parsed = parse_effects(effects)
    except (TypeError, ValueError) as exc:
        raise GatewayDenied("Invocation contains an invalid effect declaration") from exc
    if not parsed or not within(parsed, policy.allowed):
        raise GatewayDenied("Invocation effects are not fully allowed by the active policy")
    return parsed


@dataclass(frozen=True)
class Approval:
    token: str
    expires_in_seconds: int
    invocation_id: str
    effects: tuple[str, ...]
    approval_required: bool = True


@dataclass
class _ApprovalRecord:
    token_digest: str
    actor: str
    server_id: str
    tool_name: str
    arguments_hash: str
    goal_hash: str
    policy_hash: str
    tool_definition_hash: str
    assurance_evidence_hash: str
    expires_at: float


class ApprovalStore:
    """Thread-safe, process-local, one-time approval store.

    Tokens are returned once and only their keyed digest is retained. A restart
    invalidates all approvals. This is suitable for a single-process prototype,
    not a distributed or multi-tenant production deployment.
    """

    def __init__(self, secret: bytes | None = None, ttl_seconds: int = 120):
        if ttl_seconds < 1 or ttl_seconds > 600:
            raise ValueError("Approval TTL must be between 1 and 600 seconds")
        self._secret = secret or secrets.token_bytes(32)
        self._ttl = ttl_seconds
        self._records: dict[str, _ApprovalRecord] = {}
        self._lock = threading.Lock()

    def issue(
        self, *, actor: str, server_id: str, tool_name: str,
        arguments: dict[str, Any], goal_spec: dict[str, Any],
        policy: Policy | None, effects: Iterable[str | Effect],
        tool_definition_hash: str, assurance_evidence_hash: str,
    ) -> Approval:
        if not all(isinstance(v, str) and v.strip() for v in (actor, server_id, tool_name)):
            raise GatewayDenied("Actor, server and tool identity are required")
        for label, digest in (("tool definition", tool_definition_hash), ("assurance evidence", assurance_evidence_hash)):
            if not isinstance(digest, str) or len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
                raise GatewayDenied("A valid SHA-256 " + label + " hash is required")
        if not isinstance(arguments, dict) or not isinstance(goal_spec, dict):
            raise GatewayDenied("Arguments and GoalSpec must be JSON objects")
        parsed = require_policy_allow(policy, effects)
        args_hash = canonical_hash(arguments)
        goal_hash = canonical_hash(goal_spec)
        policy_hash = policy_fingerprint(policy)
        invocation_id = canonical_hash({
            "actor": actor, "server": server_id, "tool": tool_name,
            "arguments_hash": args_hash, "goal_hash": goal_hash,
            "policy_hash": policy_hash,
            "tool_definition_hash": tool_definition_hash,
            "assurance_evidence_hash": assurance_evidence_hash,
        })
        token = secrets.token_urlsafe(32)
        token_digest = hmac.new(self._secret, token.encode(), hashlib.sha256).hexdigest()
        with self._lock:
            self._purge_expired()
            self._records[token_digest] = _ApprovalRecord(
                token_digest, actor, server_id, tool_name, args_hash,
                goal_hash, policy_hash, tool_definition_hash, assurance_evidence_hash,
                time.monotonic() + self._ttl,
            )
        return Approval(token, self._ttl, invocation_id, tuple(sorted(map(str, parsed))))

    def consume(
        self, token: str, *, actor: str, server_id: str, tool_name: str,
        arguments: dict[str, Any], goal_spec: dict[str, Any],
        policy: Policy | None, tool_definition_hash: str,
        assurance_evidence_hash: str,
    ) -> str:
        """Consume approval exactly once, checking all bound invocation dimensions."""
        if policy is None or not isinstance(token, str) or not token:
            raise GatewayDenied("A valid one-time approval and active policy are required")
        digest = hmac.new(self._secret, token.encode(), hashlib.sha256).hexdigest()
        with self._lock:
            record = self._records.pop(digest, None)
            self._purge_expired()
        if record is None or record.expires_at <= time.monotonic():
            raise GatewayDenied("Approval is missing, expired, or already consumed")
        expected = (
            record.actor == actor
            and record.server_id == server_id
            and record.tool_name == tool_name
            and hmac.compare_digest(record.arguments_hash, canonical_hash(arguments))
            and hmac.compare_digest(record.goal_hash, canonical_hash(goal_spec))
            and hmac.compare_digest(record.policy_hash, policy_fingerprint(policy))
            and hmac.compare_digest(record.tool_definition_hash, tool_definition_hash)
            and hmac.compare_digest(record.assurance_evidence_hash, assurance_evidence_hash)
        )
        if not expected:
            raise GatewayDenied("Approval does not match this actor, invocation, GoalSpec or policy")
        return canonical_hash({
            "actor": actor, "server": server_id, "tool": tool_name,
            "arguments_hash": record.arguments_hash, "goal_hash": record.goal_hash,
            "policy_hash": record.policy_hash,
            "tool_definition_hash": record.tool_definition_hash,
            "assurance_evidence_hash": record.assurance_evidence_hash,
        })

    def _purge_expired(self) -> None:
        now = time.monotonic()
        expired = [key for key, value in self._records.items() if value.expires_at <= now]
        for key in expired:
            self._records.pop(key, None)
