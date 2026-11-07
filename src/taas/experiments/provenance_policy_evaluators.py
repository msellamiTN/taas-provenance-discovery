"""Offline E3-E7 provenance and policy evaluators.

All functions consume frozen, independently supplied labels/evidence. They do not
probe MCP servers, call tools, infer ground truth from declarations, or manufacture
verifier outcomes. Missing/unknown labels are retained in explicit denominators.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Mapping, Sequence

from .evaluation_metrics import _ratio, exposure_at_k, retrieval_metrics


def effect_discrepancy(
    declared: Mapping[str, Iterable[str]],
    observed: Mapping[str, Iterable[str] | None],
    definition_hashes: Mapping[str, str],
    observed_hashes: Mapping[str, str],
) -> dict:
    """Compare declared and observed effect classes only on exact definition-hash matches."""
    if set(declared) != set(observed):
        raise ValueError("Declared and observed tool IDs must match exactly")
    comparable, mismatch, missing, hash_mismatch = 0, 0, 0, 0
    per_tool = {}
    for tool in sorted(declared):
        obs = observed[tool]
        if obs is None:
            missing += 1
            per_tool[tool] = "unobserved"
            continue
        if not definition_hashes.get(tool) or definition_hashes.get(tool) != observed_hashes.get(tool):
            hash_mismatch += 1
            per_tool[tool] = "definition_hash_mismatch"
            continue
        comparable += 1
        differs = set(declared[tool]) != set(obs)
        mismatch += int(differs)
        per_tool[tool] = "discrepant" if differs else "matched"
    return {
        "discrepancy_rate": _ratio("effect_discrepancy_rate", mismatch, comparable).to_dict(),
        "comparable_tools": comparable,
        "unobserved_tools": missing,
        "hash_mismatch_tools": hash_mismatch,
        "per_tool": per_tool,
        "scope": "effect-set equality on hash-matched observed records; not semantic equivalence",
    }


def probe_coverage(
    tool_ids: Iterable[str],
    observed: Mapping[str, Iterable[str] | None],
    definition_hashes: Mapping[str, str],
    observed_hashes: Mapping[str, str],
) -> dict:
    ids = set(tool_ids)
    matched = {
        tool for tool in ids
        if observed.get(tool) is not None
        and definition_hashes.get(tool)
        and definition_hashes.get(tool) == observed_hashes.get(tool)
    }
    return {
        "probe_coverage": _ratio("probe_coverage", len(matched), len(ids)).to_dict(),
        "probeable_share": _ratio("probeable_share", len(matched), len(ids)).to_dict(),
        "n_registry_tools": len(ids),
        "n_hash_matched_observations": len(matched),
    }


def policy_encoding_metrics(
    rankings: Mapping[str, Sequence[str]],
    unsafe_reference: Mapping[str, Iterable[str]],
    relevant_read_only: Mapping[str, Iterable[str]],
    eligible_tools: Mapping[str, Iterable[str]],
    k: int = 5,
) -> dict:
    """E4/E5/E6 policy result bundle for one named encoding/method."""
    if set(rankings) != set(unsafe_reference) or set(rankings) != set(relevant_read_only):
        raise ValueError("Request IDs must match across rankings and references")
    visible = {request: set(rankings[request]) for request in rankings}
    eligible = {request: set(eligible_tools.get(request, ())) & visible[request]
                for request in rankings}
    filtered = {request: [tool for tool in rankings[request] if tool in eligible[request]]
                for request in rankings}
    exposure = exposure_at_k(filtered, unsafe_reference, k)
    utility = retrieval_metrics(filtered, relevant_read_only, ks=(5,))["hit@5"]
    return {
        "eligible_share": _ratio(
            "eligible_share",
            sum(len(eligible[r]) for r in eligible),
            sum(len(visible[r]) for r in visible),
        ).to_dict(),
        "Exp@5": exposure.to_dict(),
        "Util@5": utility,
        "k": k,
        "n_requests": len(rankings),
    }


def verifier_error_rates(
    reference_unsafe: Mapping[str, bool | None],
    verifier_unsafe: Mapping[str, bool | None],
) -> dict:
    """FAR = unsafe accepted as safe (FN/unsafe); FRR = safe rejected (FP/safe)."""
    if set(reference_unsafe) != set(verifier_unsafe):
        raise ValueError("Verifier and reference IDs must match exactly")
    fp = fn = tp = tn = abstain = unknown = 0
    for item, truth in reference_unsafe.items():
        pred = verifier_unsafe[item]
        if truth is None:
            unknown += 1
        elif pred is None:
            abstain += 1
        elif truth and pred:
            tp += 1
        elif not truth and pred:
            fp += 1
        elif truth and not pred:
            fn += 1
        else:
            tn += 1
    negatives, positives = tn + fp, tp + fn
    return {
        "false_acceptance_rate": _ratio("FAR", fn, positives).to_dict(),
        "false_rejection_rate": _ratio("FRR", fp, negatives).to_dict(),
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "abstentions": abstain, "unknown_reference": unknown,
    }


def trust_threshold_sweep(
    property_strengths: Mapping[str, Mapping[str, float]],
    required_properties: Iterable[str],
    thresholds: Sequence[float],
) -> list[dict]:
    """Eligibility share as a function of trust threshold using frozen strengths."""
    props = tuple(required_properties)
    n = len(property_strengths)
    out = []
    for threshold in thresholds:
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("Trust thresholds must lie in [0,1]")
        eligible = [
            tool for tool, strengths in property_strengths.items()
            if all(strengths.get(prop, 0.0) >= threshold for prop in props)
        ]
        out.append({
            "threshold": float(threshold),
            "eligible_count": len(eligible),
            "eligible_share": _ratio("eligible_share", len(eligible), n).to_dict(),
            "eligible_tools": sorted(eligible),
        })
    return out


def pareto_frontier(points: Sequence[Mapping[str, float]],
                    maximize: Sequence[str], minimize: Sequence[str]) -> list[int]:
    """Return indices not dominated on explicitly named maximize/minimize dimensions."""
    dimensions = tuple(maximize) + tuple(minimize)
    if not dimensions:
        raise ValueError("At least one objective is required")
    for point in points:
        if any(key not in point for key in dimensions):
            raise ValueError("Every point must contain every declared objective")
    frontier = []
    for i, candidate in enumerate(points):
        dominated = False
        for j, other in enumerate(points):
            if i == j:
                continue
            no_worse = all(
                other[key] >= candidate[key] for key in maximize
            ) and all(other[key] <= candidate[key] for key in minimize)
            strictly_better = any(
                other[key] > candidate[key] for key in maximize
            ) or any(other[key] < candidate[key] for key in minimize)
            if no_worse and strictly_better:
                dominated = True
                break
        if not dominated:
            frontier.append(i)
    return frontier


def policy_threshold_pareto(
    sweep_rows: Sequence[Mapping],
    exposure_by_threshold: Mapping[float, float],
    utility_by_threshold: Mapping[float, float],
) -> dict:
    """E7 eligible-share/Exp@5/Util@5 Pareto points, retaining threshold identity."""
    points = []
    for row in sweep_rows:
        threshold = float(row["threshold"])
        if threshold not in exposure_by_threshold or threshold not in utility_by_threshold:
            continue
        share = row["eligible_share"]["value"]
        if share is None:
            continue
        points.append({
            "threshold": threshold,
            "eligible_share": float(share),
            "Exp@5": float(exposure_by_threshold[threshold]),
            "Util@5": float(utility_by_threshold[threshold]),
        })
    indices = pareto_frontier(points, maximize=("Util@5",), minimize=("Exp@5",))
    return {"points": points, "frontier_indices": indices,
            "frontier": [points[i] for i in indices],
            "objective_note": "eligible share is reported as a coverage dimension, not optimized implicitly"}
