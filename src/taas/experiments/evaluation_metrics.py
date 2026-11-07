"""Protocol-faithful, execution-free evaluation metrics for PaMCP.

This module computes metrics from frozen rankings and independently supplied
reference labels. It never imports discovery-time gold labels or invokes MCP tools.
Unknown labels and abstentions remain explicit in the returned denominators.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable, Mapping, Sequence


@dataclass(frozen=True)
class Metric:
    name: str
    value: float | None
    numerator: float
    denominator: int
    details: dict

    def to_dict(self) -> dict:
        return asdict(self)


def _ratio(name: str, numerator: float, denominator: int, **details) -> Metric:
    return Metric(name, numerator / denominator if denominator else None,
                  numerator, denominator, details)


def binary_classification_metrics(
    reference: Mapping[str, bool | None],
    predictions: Mapping[str, bool | None],
) -> dict:
    """Binary metrics with abstentions/unknown reference labels reported, not imputed."""
    if set(predictions) - set(reference):
        raise ValueError("Predictions contain IDs absent from the reference set")
    tp = fp = tn = fn = abstained = unknown = 0
    for item_id, truth in reference.items():
        pred = predictions.get(item_id)
        if truth is None:
            unknown += 1
            continue
        if pred is None:
            abstained += 1
        elif bool(truth) and bool(pred):
            tp += 1
        elif not bool(truth) and bool(pred):
            fp += 1
        elif not bool(truth) and not bool(pred):
            tn += 1
        else:
            fn += 1
    labelled = len(reference) - unknown
    scored = tp + fp + tn + fn
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = (2 * precision * recall / (precision + recall)
          if precision is not None and recall is not None and precision + recall else None)
    return {
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "unknown_reference": unknown, "abstentions": abstained,
        "reference_coverage": _ratio("reference_coverage", labelled, len(reference)).to_dict(),
        "prediction_coverage": _ratio("prediction_coverage", scored, labelled).to_dict(),
        "precision": precision, "recall": recall, "f1": f1,
        "scored_denominator": scored, "labelled_denominator": labelled,
    }


def retrieval_metrics(
    rankings: Mapping[str, Sequence[str]],
    relevant: Mapping[str, Iterable[str]],
    ks: Sequence[int] = (1, 5),
) -> dict:
    """Hit@k, MRR@max(k), and macro Hit@1 over requests with non-empty qrels."""
    if set(rankings) != set(relevant):
        raise ValueError("Ranking and relevance request IDs must match exactly")
    if any(k < 1 for k in ks):
        raise ValueError("k must be positive")
    rows = []
    for request_id, ranking in rankings.items():
        gold = set(relevant[request_id])
        if not gold:
            continue
        ordered = list(ranking)
        first = next((i + 1 for i, tool in enumerate(ordered) if tool in gold), None)
        rows.append((request_id, first))
    n = len(rows)
    out = {"requests_scored": n, "requests_total": len(rankings)}
    for k in ks:
        hits = sum(rank is not None and rank <= k for _, rank in rows)
        out[f"hit@{k}"] = _ratio(f"hit@{k}", hits, n).to_dict()
    mrr_k = max(ks) if ks else 0
    rr = sum(1 / rank for _, rank in rows if rank is not None and rank <= mrr_k)
    out[f"mrr@{mrr_k}"] = _ratio(f"mrr@{mrr_k}", rr, n).to_dict()
    by_request = {rid: (1.0 if rank == 1 else 0.0) for rid, rank in rows}
    out["macro_hit@1"] = _ratio("macro_hit@1", sum(by_request.values()), n).to_dict()
    out["first_relevant_rank"] = {rid: rank for rid, rank in rows}
    return out


def exposure_at_k(
    rankings: Mapping[str, Sequence[str]],
    independently_unsafe: Mapping[str, Iterable[str] | None],
    k: int = 5,
) -> Metric:
    """Exp@k: request share whose top-k contains >=1 independently labelled unsafe tool."""
    if set(rankings) != set(independently_unsafe):
        raise ValueError("Ranking and unsafe-reference request IDs must match exactly")
    if k < 1:
        raise ValueError("k must be positive")
    known = [request for request, unsafe in independently_unsafe.items() if unsafe is not None]
    exposed = sum(bool(set(rankings[request][:k]) & set(independently_unsafe[request] or ()))
                  for request in known)
    unknown = len(rankings) - len(known)
    return _ratio(f"Exp@{k}", exposed, len(known),
                  definition="fraction of requests whose top-k contains >=1 independently reference-labelled unsafe tool",
                  unknown_reference_requests=unknown, total_requests=len(rankings))


def multi_tool_set_metrics(
    selected: Mapping[str, Iterable[str]],
    required_groups: Mapping[str, Sequence[Iterable[str]]],
) -> dict:
    """Group recall, set precision and complete-set share for multi-tool requests.

    A required group is covered when at least one acceptable tool from that group
    is selected. This does not assert task success or runtime feasibility.
    """
    if set(selected) != set(required_groups):
        raise ValueError("Selected sets and required-group request IDs must match exactly")
    group_total = group_hit = 0
    precision_sum = 0.0
    precision_n = 0
    complete = 0
    for request_id, groups_raw in required_groups.items():
        groups = [set(g) for g in groups_raw]
        chosen = set(selected[request_id])
        if not groups:
            continue
        hits = sum(bool(chosen & group) for group in groups)
        group_hit += hits
        group_total += len(groups)
        acceptable_union = set().union(*groups)
        precision_sum += len(chosen & acceptable_union) / len(chosen) if chosen else 0.0
        precision_n += 1
        complete += int(hits == len(groups))
    return {
        "group_recall": _ratio("group_recall", group_hit, group_total).to_dict(),
        "set_precision_macro": _ratio("set_precision_macro", precision_sum, precision_n).to_dict(),
        "complete_set_share": _ratio("complete_set_share", complete, precision_n).to_dict(),
        "requests_scored": precision_n,
        "interpretation_limit": "retrieval/set coverage only; not independent joint-feasibility or task success",
    }


def qos_evidence_record(
    *, metric: str, value: float, unit: str, evidence_kind: str,
    source: str, observed_at: str | None = None, definition_hash: str | None = None,
) -> dict:
    """Normalize a QoS datum without upgrading its evidence status.

    evidence_kind is one of declared, observed, attested, or unknown.
    No value is inferred, benchmarked, or treated as measured by this function.
    """
    allowed = {"declared", "observed", "attested", "unknown"}
    if evidence_kind not in allowed:
        raise ValueError(f"evidence_kind must be one of {sorted(allowed)}")
    if not metric or not unit or not source:
        raise ValueError("metric, unit and source are required")
    if evidence_kind in {"observed", "attested"} and not definition_hash:
        raise ValueError("observed/attested QoS evidence must be bound to a definition hash")
    return {
        "metric": metric, "value": float(value), "unit": unit,
        "evidence_kind": evidence_kind, "source": source,
        "observed_at": observed_at, "definition_hash": definition_hash,
        "measured": evidence_kind == "observed",
    }


def certificate_check_metrics(audits: Sequence[Mapping]) -> dict:
    """E10 certificate pass rates by mandatory check and overall conjunction.

    Each input is an independent-audit dictionary with a recomputed mapping.
    Missing checks fail closed and remain in the denominator; no certificate is
    silently dropped. Empty input yields undefined rates with denominator zero.
    """
    checks = ("S", "C", "P", "E", "L", "V")
    n = len(audits)
    counts = {
        key: sum(
            1 for audit in audits
            if isinstance(audit.get("recomputed"), Mapping)
            and audit["recomputed"].get(key) is True
        )
        for key in checks
    }
    complete = sum(
        1 for audit in audits
        if audit.get("valid") is True
        and isinstance(audit.get("recomputed"), Mapping)
        and all(audit["recomputed"].get(key) is True for key in checks)
    )
    return {
        "n_certificates": n,
        "by_check": {
            key: _ratio(f"certificate_pass_{key}", counts[key], n).to_dict()
            for key in checks
        },
        "failure_counts_by_check": {key: n - counts[key] for key in checks},
        "overall_conjunction": _ratio("certificate_all_mandatory_checks", complete, n).to_dict(),
        "denominator_policy": "all submitted audit records; missing or non-true checks count as failures",
    }
