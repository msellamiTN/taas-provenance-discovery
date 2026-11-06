"""PaMCP core-variant preview for the E18 factorial study.

These previews execute the local discovery/composition logic only. They do not
invoke MCP tools or evaluate benchmark gold labels.
"""
from __future__ import annotations

import os
import hashlib
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Sequence

from taas.baselines import per_subtask
from taas.bitmap_index import BitmapIndex
from taas.composer import ComposerConfig, eligible_set
from taas.contracts import CapabilityContract
from taas.engine import DiscoveryEngine, EngineConfig
from taas.goals import parse_goal_spec
from taas.manifest import manifest_tokens, raw_tokens
from taas.experiments.catalog import FACTORIAL_VARIANTS, get_factorial_variant
from taas.model_profile import ModelProfile
from taas.policy import Policy
from taas.provenance import DEFAULT_TRUST
from taas.provenance import TrustPolicy
from taas.retrieval import HybridRetriever


VARIANT_IDS = set(FACTORIAL_VARIANTS)


def load_preview_profile() -> ModelProfile:
    configured = os.environ.get("TAAS_MODEL_PROFILE", "").strip()
    if not configured:
        return ModelProfile(model_id="uncalibrated-default", strict=True)
    path = Path(configured).expanduser().resolve()
    if not path.is_file():
        raise ValueError("TAAS_MODEL_PROFILE does not point to a readable file")
    return ModelProfile.load(path)


def _policy_with_evidence_floor(policy: Policy, lmin: float) -> Policy:
    return Policy(
        name=policy.name,
        required=policy.required,
        forbidden=policy.forbidden,
        encoding=policy.encoding,
        lmin=lmin,
        visible=policy.visible,
        allowed=policy.allowed,
        declass=policy.declass,
        egress_threshold=policy.egress_threshold,
        forbidden_pairs=policy.forbidden_pairs,
        prompt_label=policy.prompt_label,
        credentials=policy.credentials,
    )


def run_pamcp_variant(
    variant_id: str,
    contracts: Sequence[CapabilityContract],
    goal_spec: dict[str, Any],
    policy: Policy,
    top_k: int = 5,
    refine_k: int = 3,
    model_profile: ModelProfile | None = None,
) -> dict[str, Any]:
    """Run one PaMCP configuration without access to evaluator labels."""
    if variant_id not in VARIANT_IDS:
        raise KeyError(f"Unknown PaMCP variant {variant_id}")
    factors = get_factorial_variant(variant_id)
    if not 1 <= top_k <= 100:
        raise ValueError("top_k must be between 1 and 100")
    profile = model_profile or load_preview_profile()
    spec = parse_goal_spec(goal_spec, prompt=str(goal_spec.get("prompt", "")))

    trust = DEFAULT_TRUST
    effective_policy = policy
    if factors.P == 0:
        # P=0: declarations/lexical assertions remain visible, but there is no
        # obs/att threshold. Lower the evidence floor to the lexical tier.
        effective_policy = _policy_with_evidence_floor(policy, 0.0)
        # All available declarations are treated uniformly. Provenance classes do
        # not receive different trust weights; this is a flat metadata-only control.
        trust = TrustPolicy(
            trusted_signers=frozenset(),
            lex=1.0,
            ann=1.0,
            obs_base=1.0,
            obs_scale=0.0,
            att_trusted=1.0,
            att_unknown=1.0,
            lex_by_property={},
        )

    if not 0 <= refine_k <= 10:
        raise ValueError("refine_k must be between 0 and 10")
    engine_cfg = EngineConfig(composer=ComposerConfig(K=top_k), use_gap=bool(factors.G), refine_k=refine_k)
    engine = DiscoveryEngine(contracts, profile, trust=trust, cfg=engine_cfg)
    if factors.S == 1:
        result = engine.discover(spec, effective_policy)
        toolkit = result.toolkit or []
        certificate = result.certificate.to_dict() if result.certificate is not None else None
        return {
            "variant_id": variant_id,
            "factors": {"G": factors.G, "P": factors.P, "S": factors.S},
            "status": "abstained" if result.abstained else "selected",
            "selected_tool_ids": toolkit,
            "candidate_tool_ids": result.compose.candidates,
            "gap_goal_ids": [g.id for g in result.gap.gap],
            "rho": result.gap.rho,
            "certificate": certificate,
            "certificate_valid": bool(result.certificate and result.certificate.valid),
            "counterexample": result.counterexample.to_dict() if result.counterexample else None,
            "raw_context_tokens": raw_tokens(engine.H, toolkit),
            "sanitized_manifest_tokens": manifest_tokens(result.manifest["tools"]) if result.manifest else 0,
            "discovery_time_seconds": result.time_s,
            "composition_stats": result.compose.stats,
            "model_profile": profile.model_id,
            "model_profile_fingerprint": _canonical_fingerprint(profile),
            "model_profile_strict": profile.strict,
            "refinement_iterations_allowed": refine_k,
            "evaluator_labels_accessed": False,
            "mcp_tools_executed": False,
        }

    # S=0: preserve the model gap and the same per-tool eligibility policy, but
    # retrieve each gap goal independently and union the shortlists. No backward
    # closure, global toolkit search, joint constraints or certificate are applied.
    gap = engine.gap(spec)
    if gap.clarify is not None:
        return {
            "variant_id": variant_id,
            "factors": {"G": factors.G, "P": factors.P, "S": factors.S},
            "status": "abstained_clarification",
            "selected_tool_ids": [],
            "gap_goal_ids": [],
            "clarification": gap.clarify,
            "certificate": None,
            "certificate_valid": False,
            "evaluator_labels_accessed": False,
            "mcp_tools_executed": False,
        }
    eligible = eligible_set(engine.index, effective_policy)
    selected = per_subtask(engine.retriever, gap.spec, eligible, k_per_goal=top_k, include_native=False)
    per_goal = []
    for goal in gap.gap:
        scores = engine.retriever.scores(goal.rendering(), goal.out, eligible, set(),
                                         components=("lex", "den"))
        ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:top_k]
        per_goal.append({"goal_id": goal.id, "tool_ids": [tool for tool, _ in ranked]})
    return {
        "variant_id": variant_id,
        "factors": {"G": factors.G, "P": factors.P, "S": factors.S},
        "status": "selected_uncertified" if selected or not gap.gap else "abstained_no_candidates",
        "selected_tool_ids": selected,
        "per_goal_shortlists": per_goal,
        "gap_goal_ids": [g.id for g in gap.gap],
        "eligible_tool_count": len(eligible),
        "certificate": None,
        "certificate_valid": False,
        "checks_performed": [],
        "composition": "independent per-subgoal retrieval followed by union",
        "backward_closure": False,
        "joint_compatibility_effect_flow_checks": False,
        "raw_context_tokens": raw_tokens(engine.H, selected),
        "sanitized_manifest_tokens": 0,
        "model_profile": profile.model_id,
        "model_profile_strict": profile.strict,
        "refinement_iterations_allowed": refine_k,
        "evaluator_labels_accessed": False,
        "mcp_tools_executed": False,
    }


def _fingerprint_value(value: Any) -> Any:
    if is_dataclass(value):
        return _fingerprint_value(asdict(value))
    if isinstance(value, dict):
        return {str(key): _fingerprint_value(item) for key, item in value.items()}
    if isinstance(value, (set, frozenset)):
        normalized = [_fingerprint_value(item) for item in value]
        return sorted(normalized, key=lambda item: json.dumps(item, sort_keys=True, default=str))
    if isinstance(value, (tuple, list)):
        return [_fingerprint_value(item) for item in value]
    return value


def _canonical_fingerprint(value: Any) -> str:
    payload = json.dumps(
        _fingerprint_value(value), sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def run_pamcp_factorial_preview(
    contracts: Sequence[CapabilityContract],
    goal_spec: dict[str, Any],
    policy: Policy,
    top_k: int = 5,
    refine_k: int = 3,
) -> dict[str, Any]:
    """Run all eight frozen E18 cells under one shared preview input/profile.

    This is a software preview only: it never reads evaluator labels or invokes MCP tools.
    It must not be promoted to confirmatory E18 evidence without the independent task and
    composition-oracle package required by the frozen protocol.
    """
    from taas.experiments.catalog import load_catalog

    catalog = load_catalog()
    ordered_names = [cell["name"] for cell in catalog["factorial_design"]["cells"]]
    if len(ordered_names) != 8 or set(ordered_names) != VARIANT_IDS:
        raise RuntimeError("Frozen E18 catalog and implementation variant set differ.")

    profile = load_preview_profile()
    registry_fingerprint = _canonical_fingerprint([
        contract for contract in sorted(contracts, key=lambda item: item.tool)
    ])
    goal_fingerprint = _canonical_fingerprint(goal_spec)
    policy_fingerprint = _canonical_fingerprint(policy)

    results = [
        run_pamcp_variant(
            variant_id, contracts, goal_spec, policy,
            top_k=top_k, refine_k=refine_k, model_profile=profile,
        )
        for variant_id in ordered_names
    ]
    expected = {
        cell["name"]: (cell["G"], cell["P"], cell["S"])
        for cell in catalog["factorial_design"]["cells"]
    }
    for result in results:
        factors = result.get("factors", {})
        observed = (factors.get("G"), factors.get("P"), factors.get("S"))
        if observed != expected[result["variant_id"]]:
            raise RuntimeError(f"E18 factor mismatch for {result['variant_id']}: {observed}")
        if result.get("evaluator_labels_accessed") is not False:
            raise RuntimeError("E18 preview unexpectedly accessed evaluator labels.")
        if result.get("mcp_tools_executed") is not False:
            raise RuntimeError("E18 preview unexpectedly executed MCP tools.")

    return {
        "experiment_id": "E18",
        "status": "preview_only",
        "completion_gate": (
            "Confirmatory E18 requires the same frozen independent task/contract oracle "
            "for all eight cells and matched evaluation conditions."
        ),
        "factorial_design": "GxPxS_full_2^3",
        "variant_order": ordered_names,
        "variant_count": len(results),
        "shared_inputs": {
            "registry_fingerprint": registry_fingerprint,
            "goal_spec_fingerprint": goal_fingerprint,
            "policy_fingerprint": policy_fingerprint,
            "model_profile": profile.model_id,
            "model_profile_fingerprint": _canonical_fingerprint(profile),
            "model_profile_strict": profile.strict,
            "top_k": top_k,
            "refine_k": refine_k,
        },
        "results": results,
        "evaluator_labels_accessed": False,
        "mcp_tools_executed": False,
    }
