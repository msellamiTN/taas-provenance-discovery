"""Task-level retrieval and assurance metrics with explicit denominators."""
from __future__ import annotations

import math
import random
from collections import defaultdict
from typing import Mapping, Sequence


def _mean_with_count(values: Sequence[float]) -> dict:
    if not values:
        return {"value": None, "n": 0, "numerator": None, "denominator": 0}
    return {
        "value": sum(values) / len(values),
        "n": len(values),
        "numerator": sum(values),
        "denominator": len(values),
    }


def ranking_metrics(
    rankings: Mapping[str, Sequence[str]],
    relevance: Mapping[str, Mapping[str, float]],
    ks: Sequence[int] = (1, 5, 10),
) -> dict:
    """Compute macro query-level ranking metrics from graded qrels.

    Queries without qrels are excluded and counted. Abstentions remain in the
    evaluated query set as empty rankings, so unconditional metrics penalize them.
    """
    query_ids = sorted(relevance)
    result = {"queries_with_qrels": len(query_ids), "queries_missing_qrels": 0, "metrics": {}}
    for k in ks:
        if k < 1:
            raise ValueError("Every k must be >= 1")
        precision, recall, reciprocal_rank, ndcg, hit = [], [], [], [], []
        for query_id in query_ids:
            qrels = relevance.get(query_id, {})
            if not qrels:
                continue
            ranked = list(rankings.get(query_id, ()))[:k]
            rel_items = {tool for tool, grade in qrels.items() if float(grade) > 0}
            retrieved_relevant = [tool for tool in ranked if tool in rel_items]
            precision.append(len(retrieved_relevant) / k)
            recall.append(len(set(retrieved_relevant)) / len(rel_items) if rel_items else 0.0)
            hit.append(float(bool(retrieved_relevant)))
            first = next((i for i, tool in enumerate(ranked, 1) if tool in rel_items), None)
            reciprocal_rank.append(1.0 / first if first is not None else 0.0)
            gains = [max(0.0, 2.0 ** float(qrels.get(tool, 0.0)) - 1.0) for tool in ranked]
            dcg = sum(gain / math.log2(rank + 1) for rank, gain in enumerate(gains, 1))
            ideal = sorted((max(0.0, 2.0 * float(g) - 1.0) for g in qrels.values()), reverse=True)[:k]
            idcg = sum(gain / math.log2(rank + 1) for rank, gain in enumerate(ideal, 1))
            ndcg.append(dcg / idcg if idcg > 0 else 0.0)
        result["metrics"][str(k)] = {
            f"precision@{k}": _mean_with_count(precision),
            f"recall@{k}": _mean_with_count(recall),
            f"mrr@{k}": _mean_with_count(reciprocal_rank),
            f"ndcg@{k}": _mean_with_count(ndcg),
            f"hit@{k}": _mean_with_count(hit),
        }
    return result


def assurance_error_rates(
    predictions: Mapping[str, bool],
    oracle_validity: Mapping[str, bool] | None,
) -> dict:
    """Compute false assurance/rejection only where an independent oracle exists."""
    if oracle_validity is None:
        return {"false_assurance_rate": None, "false_rejection_rate": None,
                "n": 0, "reason": "independent oracle unavailable"}
    ids = sorted(set(predictions) & set(oracle_validity))
    if not ids:
        return {"false_assurance_rate": None, "false_rejection_rate": None,
                "n": 0, "reason": "no matched predictions and oracle labels"}
    invalid = [i for i in ids if not oracle_validity[i]]
    valid = [i for i in ids if oracle_validity[i]]
    false_assurance = sum(bool(predictions[i]) for i in invalid)
    false_rejection = sum(not bool(predictions[i]) for i in valid)
    return {
        "false_assurance_rate": false_assurance / len(invalid) if invalid else None,
        "false_assurance_numerator": false_assurance,
        "false_assurance_denominator": len(invalid),
        "false_rejection_rate": false_rejection / len(valid) if valid else None,
        "false_rejection_numerator": false_rejection,
        "false_rejection_denominator": len(valid),
        "n": len(ids),
    }


def bootstrap_mean_ci(
    values: Sequence[float],
    confidence: float = 0.95,
    resamples: int = 10000,
    seed: int = 0,
) -> dict:
    """Percentile bootstrap over independent task-level observations."""
    if not values:
        return {"estimate": None, "lower": None, "upper": None, "n": 0}
    if not 0.0 < confidence < 1.0 or resamples < 1:
        raise ValueError("confidence must be in (0,1) and resamples >= 1")
    rng = random.Random(seed)
    samples = sorted(
        sum(rng.choices(values, k=len(values))) / len(values)
        for _ in range(resamples)
    )
    alpha = (1.0 - confidence) / 2.0
    lo = max(0, min(resamples - 1, int(math.floor(alpha * resamples))))
    hi = max(0, min(resamples - 1, int(math.ceil((1.0 - alpha) * resamples)) - 1))
    return {
        "estimate": sum(values) / len(values),
        "lower": samples[lo],
        "upper": samples[hi],
        "n": len(values),
        "confidence": confidence,
        "resamples": resamples,
        "seed": seed,
        "unit": "task",
    }


def paired_cluster_bootstrap_ci(
    left: Mapping[str, float],
    right: Mapping[str, float],
    cluster_by_task: Mapping[str, str],
    confidence: float = 0.95,
    resamples: int = 10000,
    seed: int = 0,
) -> dict:
    """Bootstrap paired right-left differences by resampling whole clusters."""
    tasks = sorted(set(left) & set(right) & set(cluster_by_task))
    if not tasks:
        return {"estimate": None, "lower": None, "upper": None, "n_tasks": 0, "n_clusters": 0}
    groups = defaultdict(list)
    for task in tasks:
        groups[cluster_by_task[task]].append(float(right[task]) - float(left[task]))
    cluster_ids = sorted(groups)
    cluster_means = {key: sum(vals) / len(vals) for key, vals in groups.items()}
    rng = random.Random(seed)
    draws = []
    for _ in range(resamples):
        selected = rng.choices(cluster_ids, k=len(cluster_ids))
        # Equal cluster weighting; avoids letting large clusters dominate by task count.
        draws.append(sum(cluster_means[key] for key in selected) / len(selected))
    draws.sort()
    alpha = (1.0 - confidence) / 2.0
    lo = max(0, min(resamples - 1, int(math.floor(alpha * resamples))))
    hi = max(0, min(resamples - 1, int(math.ceil((1.0 - alpha) * resamples)) - 1))
    return {
        "estimate": sum(float(right[t]) - float(left[t]) for t in tasks) / len(tasks),
        "cluster_weighted_bootstrap_lower": draws[lo],
        "cluster_weighted_bootstrap_upper": draws[hi],
        "n_tasks": len(tasks),
        "n_clusters": len(cluster_ids),
        "confidence": confidence,
        "resamples": resamples,
        "seed": seed,
        "resampling_unit": "cluster",
        "point_estimate_unit": "task",
    }
