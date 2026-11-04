"""PaMCP core-variant preview for the E18 factorial study.

These previews execute the local discovery/composition logic only. They do not
invoke MCP tools or evaluate benchmark gold labels.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Sequence

from taas.baselines import per_subtask
from taas.bitmap_index import BitmapIndex
from taas.composer import ComposerConfig, eligible_set
from taas.contracts import CapabilityContract
from taas.engine import DiscoveryEngine, EngineConfig
from taas.goals import parse_goal_spec
from taas.manifest import manifest_tokens, raw_tokens
from taas.model_profile import ModelProfile
from taas.policy import Policy
from taas.provenance import DEFAULT_TRUST
from taas.provenance import TrustPolicy
from taas.retrieval import HybridRetriever


VARIANT_IDS = {"Full_PaMCP", "PaMCP_NoGap", "PaMCP_Declared", "PaMCP_NoCert"}


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
) -> dict[str, Any]:
    """Run one PaMCP configuration without access to evaluator labels."""
    if variant_id not in VARIANT_IDS:
        raise KeyError(f"Unknown PaMCP variant {variant_id}")
    if not 1 <= top_k <= 100:
        raise ValueError("top_k must be between 1 and 100")
    profile = load_preview_profile()
    spec = parse_goal_spec(goal_spec, prompt=str(goal_spec.get("prompt", "")))

    trust = DEFAULT_TRUST
    effective_policy = policy
    if variant_id == "PaMCP_Declared":
        # P=0: declarations/lexical assertions remain visible, but there is no
        # obs/att threshold. Lower the evidence floor to the lexical tier.
        effective_policy = _policy_with_evidence_floor(policy, 0.25)
        trust = TrustPolicy(
            trusted_signers=frozenset(),
            lex=0.25,
            ann=0.50,
            obs_base=0.55,
            obs_scale=0.20,
            att_trusted=0.60,
            att_unknown=0.60,
        )

    engine_cfg = EngineConfig(composer=ComposerConfig(K=top_k), use_gap=(variant_id != "PaMCP_NoGap"))
    engine = DiscoveryEngine(contracts, profile, trust=trust, cfg=engine_cfg)
    if variant_id != "PaMCP_NoCert":
        result = engine.discover(spec, effective_policy)
        toolkit = result.toolkit or []
        certificate = result.certificate.to_dict() if result.certificate is not None else None
        return {
            "variant_id": variant_id,
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
            "model_profile_strict": profile.strict,
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
        "evaluator_labels_accessed": False,
        "mcp_tools_executed": False,
    }
