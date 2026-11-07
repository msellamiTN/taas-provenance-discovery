"""Offline E1 registry characterization and E2 semantic-typing evaluators."""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Mapping, Sequence


def registry_characterization(rows: Sequence[Mapping]) -> dict:
    """E1 counts and metadata coverage from one frozen registry snapshot."""
    def distribution(field):
        counts = Counter(str(row.get(field) or "unknown") for row in rows)
        return dict(sorted(counts.items()))
    n = len(rows)
    tool_ids = [row.get("tool_id") for row in rows if row.get("tool_id")]
    unique_tools = len(set(tool_ids))
    missing_tool_ids = n - len(tool_ids)
    duplicate_tool_rows = len(tool_ids) - unique_tools
    unique_servers = len({row.get("server") for row in rows if row.get("server")})
    hashes_present = sum(bool(row.get("definition_hash")) for row in rows)
    hashes_unique = len({row.get("definition_hash") for row in rows if row.get("definition_hash")})
    annotation_present = sum(row.get("annotations") not in (None, {}, "") for row in rows)
    descriptions_present = sum(bool(row.get("description")) for row in rows)
    return {
        "n_rows": n, "n_unique_tool_ids": unique_tools, "n_unique_servers": unique_servers,
        "duplicate_tool_rows": duplicate_tool_rows,
        "missing_tool_id_rows": missing_tool_ids,
        "category_distribution": distribution("category"),
        "source_distribution": distribution("source"),
        "transport_distribution": distribution("transport"),
        "definition_hash_coverage": {"numerator": hashes_present, "denominator": n,
                                     "rate": hashes_present/n if n else None},
        "unique_definition_hashes": hashes_unique,
        "annotation_coverage": {"numerator": annotation_present, "denominator": n,
                                "rate": annotation_present/n if n else None},
        "description_coverage": {"numerator": descriptions_present, "denominator": n,
                                 "rate": descriptions_present/n if n else None},
    }


def semantic_typing_metrics(
    reference: Mapping[str, str | None],
    predictions: Mapping[str, Mapping | str | None],
    *,
    confidence_threshold: float = 0.0,
) -> dict:
    """E2 multiclass typing scores and Cohen kappa on independently labelled items."""
    if set(predictions) - set(reference):
        raise ValueError("Predictions contain IDs absent from the reference set")
    labels = sorted({str(v) for v in reference.values() if v is not None})
    confusion = {truth: {pred: 0 for pred in labels + ["__abstain__"]} for truth in labels}
    unknown, abstain = 0, 0
    scored = 0
    for item, truth in reference.items():
        if truth is None:
            unknown += 1
            continue
        raw = predictions.get(item)
        if isinstance(raw, Mapping):
            pred = raw.get("label")
            confidence = float(raw.get("confidence", 0.0))
            if confidence < confidence_threshold:
                pred = None
        else:
            pred = raw
        if pred is None:
            pred = "__abstain__"
            abstain += 1
        pred = str(pred)
        if pred not in labels and pred != "__abstain__":
            pred = "__abstain__"
            abstain += 1
        confusion[str(truth)][pred] += 1
        scored += 1
    per_class = {}
    total = sum(sum(row.values()) for row in confusion.values())
    correct = sum(confusion[label][label] for label in labels)
    for label in labels:
        tp = confusion[label][label]
        fp = sum(confusion[other][label] for other in labels if other != label)
        fn = sum(confusion[label][other] for other in labels + ["__abstain__"] if other != label)
        precision = tp/(tp+fp) if tp+fp else None
        recall = tp/(tp+fn) if tp+fn else None
        f1 = 2*precision*recall/(precision+recall) if precision is not None and recall is not None and precision+recall else None
        per_class[label] = {"support": sum(confusion[label].values()), "precision": precision,
                            "recall": recall, "f1": f1}
    observed = correct/total if total else None
    row_marginals = [sum(confusion[label].values()) for label in labels]
    col_marginals = [sum(confusion[row][label] for row in labels) for label in labels]
    expected = (sum(a*b for a,b in zip(row_marginals, col_marginals))/(total*total)
                if total else None)
    kappa = ((observed-expected)/(1-expected) if observed is not None and expected is not None and expected < 1
             else (1.0 if observed == 1.0 else None))
    f1s = [v["f1"] for v in per_class.values() if v["f1"] is not None]
    return {
        "confusion_matrix": confusion, "per_class": per_class,
        "macro_f1": sum(f1s)/len(f1s) if f1s else None,
        "accuracy": observed, "cohen_kappa": kappa,
        "reference_unknown": unknown, "prediction_abstentions": abstain,
        "scored_denominator": scored, "labelled_denominator": len(reference)-unknown,
        "confidence_threshold": confidence_threshold,
    }


def typing_threshold_curve(reference: Mapping[str, str | None],
                           predictions: Mapping[str, Mapping | str | None],
                           thresholds: Sequence[float]) -> list[dict]:
    """E2 F1/coverage operating points without changing the reference set."""
    return [
        {"threshold": float(threshold),
         **semantic_typing_metrics(reference, predictions, confidence_threshold=float(threshold))}
        for threshold in thresholds
    ]
