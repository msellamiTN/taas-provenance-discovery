"""Studio Governance Policy Engine v1.

A deterministic evaluator that composes the existing governance decision
surfaces — release readiness, skill trust status, authorization preflight and
verified evidence — into one typed verdict per governed subject.

Distinct from ``taas.policy`` (effect/declassification rules for tool
composition) and ``execution_gateway`` (one-time approval tokens). The engine
never grants execution: ``allow`` means governance checks are satisfied as a
diagnostic verdict, not that tools may run. Missing facts degrade to
``needs_review``; contradictory rule outcomes are surfaced as conflicts and
resolve to the safest applicable decision.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping

VERDICT_SCHEMA = "taas.policy-verdict/v1"
POLICY_ENGINE_VERSION = "1.0.0"

_DECISION_ORDER = ("deny", "needs_review", "allow")


def _fingerprint(rules: Iterable[Mapping[str, Any]]) -> str:
    raw = json.dumps(list(rules), sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PolicyRule:
    """One deterministic governance rule evaluated against the fact bundle.

    ``severity`` maps the fired outcome to a candidate decision:
      - "blocking" -> deny when the rule fails
      - "review"   -> needs_review when the rule fails or is unknown
    ``evaluate`` returns True (pass), False (fail) or None (unknown/unavailable).
    """

    rule_id: str
    description: str
    severity: str  # "blocking" | "review"
    evaluate: Callable[[Mapping[str, Any]], bool | None]


def _facts(value: Mapping[str, Any], *path: str) -> Any:
    node: Any = value
    for key in path:
        if not isinstance(node, Mapping):
            return None
        node = node.get(key)
    return node


def _release_ready(facts: Mapping[str, Any]) -> bool | None:
    decision = _facts(facts, "release_readiness", "decision")
    if decision is None:
        return None
    return decision == "READY"


def _skills_not_revoked(facts: Mapping[str, Any]) -> bool | None:
    status = facts.get("skill_trust")
    if status is None:
        return None
    revoked = [s for s in status.get("skills", []) if s.get("revoked")]
    missing = [s for s in status.get("skills", []) if s.get("resolution") == "missing"]
    return not revoked and not missing


def _signatures_verified(facts: Mapping[str, Any]) -> bool | None:
    status = facts.get("skill_trust")
    if status is None:
        return None
    skills = status.get("skills", [])
    if not skills:
        return True
    unverified = [s for s in skills
                  if s.get("signature_verified") is not True and s.get("signature_required")]
    return not unverified


def _preflight_clean(facts: Mapping[str, Any]) -> bool | None:
    preflight = facts.get("authorization_preflight")
    if preflight is None:
        return None
    return preflight.get("authorized") is True


def _evidence_verified(facts: Mapping[str, Any]) -> bool | None:
    summary = facts.get("evidence_summary")
    if summary is None:
        return None
    return summary.get("invalid_records", 0) == 0 and summary.get("verified_records", 0) > 0


def _contract_valid(facts: Mapping[str, Any]) -> bool | None:
    value = facts.get("objective_contract_valid")
    return value if isinstance(value, bool) or value is None else bool(value)


DEFAULT_RULES: tuple[PolicyRule, ...] = (
    PolicyRule("structural_contract_valid", "Objective contract v3 must be structurally valid",
               "blocking", _contract_valid),
    PolicyRule("skills_resolvable_not_revoked", "All bound skills resolvable, published and non-revoked",
               "blocking", _skills_not_revoked),
    PolicyRule("publisher_signatures_verified", "Required publisher signatures verify against attested digests",
               "blocking", _signatures_verified),
    PolicyRule("trusted_evidence_verified", "Verified assurance evidence exists for the subject digest",
               "review", _evidence_verified),
    PolicyRule("release_gate_ready", "Release readiness decision must be READY",
               "review", _release_ready),
    PolicyRule("authorization_preflight_authorized", "Trusted server authorization preflight must authorize",
               "review", _preflight_clean),
)


# Subject kinds that do not exercise every rule surface. Unlisted kinds run all
# rules; excluded rules report "not_applicable" rather than degrading.
SUBJECT_RULE_EXCLUSIONS: dict[str, frozenset[str]] = {
    "agent_version": frozenset({"structural_contract_valid", "authorization_preflight_authorized"}),
    "skill_version": frozenset({
        "structural_contract_valid", "release_gate_ready", "authorization_preflight_authorized",
        "trusted_evidence_verified",
    }),
    "discovery_candidate": frozenset({"structural_contract_valid", "release_gate_ready"}),
}


def rules_for_subject(kind: str, rules: Iterable[PolicyRule]) -> tuple[list[PolicyRule], list[PolicyRule]]:
    active, excluded = [], []
    skip = SUBJECT_RULE_EXCLUSIONS.get(kind, frozenset())
    for rule in rules:
        (excluded if rule.rule_id in skip else active).append(rule)
    return active, excluded


def evaluate_policy(
    subject: Mapping[str, Any],
    facts: Mapping[str, Any] | None = None,
    *,
    rules: Iterable[PolicyRule] = DEFAULT_RULES,
) -> dict[str, Any]:
    """Return a deterministic policy verdict for a governed subject.

    ``subject`` carries ``kind`` (e.g. ``agent_version``, ``skill_version``,
    ``discovery_candidate``) plus identity pins (id, version, digests).
    ``facts`` is the gathered decision-surface bundle; absent surfaces evaluate
    as unknown and degrade to ``needs_review``, never to ``allow``.
    """
    if not isinstance(subject, Mapping) or not subject.get("kind"):
        raise ValueError("policy subject requires a kind")
    facts = dict(facts or {})
    active, excluded = rules_for_subject(str(subject["kind"]), rules)

    fired: list[dict[str, Any]] = [
        {
            "rule_id": rule.rule_id,
            "severity": rule.severity,
            "outcome": "not_applicable",
            "candidate_decision": "allow",
            "description": rule.description,
        }
        for rule in excluded
    ]
    candidates: list[str] = []
    for rule in active:
        try:
            outcome = rule.evaluate(facts)
        except Exception:  # rule evaluation errors are unknown, never pass
            outcome = None
        state = "pass" if outcome is True else "fail" if outcome is False else "unknown"
        candidate = "allow"
        if outcome is False:
            candidate = "deny" if rule.severity == "blocking" else "needs_review"
        elif outcome is None:
            candidate = "needs_review"
        candidates.append(candidate)
        fired.append({
            "rule_id": rule.rule_id,
            "severity": rule.severity,
            "outcome": state,
            "candidate_decision": candidate,
            "description": rule.description,
        })

    decision = "allow"
    for level in _DECISION_ORDER:
        if level in candidates:
            decision = level
            break

    conflicts = []
    blocking_failures = [f["rule_id"] for f in fired
                         if f["severity"] == "blocking" and f["outcome"] == "fail"]
    review_failures = [f["rule_id"] for f in fired
                       if f["severity"] == "review" and f["outcome"] in ("fail", "unknown")]
    gate_ready = _facts(facts, "release_readiness", "decision") == "READY"
    if gate_ready and blocking_failures:
        conflicts.append({
            "kind": "readiness_vs_trust_conflict",
            "detail": "release gate reports READY while blocking trust rules fail",
            "blocking_failures": blocking_failures,
            "resolution": "deny_takes_precedence",
        })
    if gate_ready and review_failures:
        conflicts.append({
            "kind": "stale_facts_warning",
            "detail": "readiness READY but review rules report fail/unknown — facts may be stale or assembled inconsistently",
            "review_failures": review_failures,
            "resolution": "verdict_computed_from_fired_rules_not_gate_label",
        })

    unavailable = [name for name in
                   ("release_readiness", "skill_trust", "authorization_preflight", "evidence_summary")
                   if name not in facts]

    return {
        "schema": VERDICT_SCHEMA,
        "policy_engine_version": POLICY_ENGINE_VERSION,
        "policy_fingerprint": _fingerprint(
            {"rule_id": r.rule_id, "severity": r.severity} for r in rules
        ),
        "subject": dict(subject),
        "decision": decision,
        "fired_rules": fired,
        "conflicts": conflicts,
        "facts_unavailable": unavailable,
        "blocking_failures": blocking_failures,
        "review_findings": review_failures,
        "execution_enabled": False,
        "authorization_granted": False,
        "semantic_correctness_verified": False,
    }
