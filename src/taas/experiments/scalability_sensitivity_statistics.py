"""Protocol-oriented offline evaluators for E15, E16, E20 and E22.

These functions summarize supplied measurements and paired outcomes. They do not
generate timing data, execution trajectories, labels, or model calibration records.
"""
from __future__ import annotations

import itertools
import math
import random
from collections.abc import Mapping, Sequence
from statistics import mean
from typing import Any


def _quantile(values: Sequence[float], q: float) -> float | None:
    if not values:
        return None
    xs = sorted(float(x) for x in values)
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def percentile_summary(values: Sequence[float]) -> dict:
    """Return p50/p95 and exact N; empty measurements remain undefined."""
    xs = [float(x) for x in values]
    return {"n": len(xs), "p50": _quantile(xs, .50), "p95": _quantile(xs, .95),
            "mean": mean(xs) if xs else None, "min": min(xs) if xs else None,
            "max": max(xs) if xs else None}


def scalability_summary(records: Sequence[Mapping[str, Any]]) -> dict:
    """E15 grouped per-stage latency/memory summaries by registry size."""
    grouped: dict[tuple[int, str], dict[str, list[float]]] = {}
    for row in records:
        size, stage = int(row["registry_size"]), str(row["stage"])
        key = (size, stage)
        bucket = grouped.setdefault(key, {"latency_ms": [], "memory_mb": []})
        if row.get("latency_ms") is not None:
            bucket["latency_ms"].append(float(row["latency_ms"]))
        if row.get("memory_mb") is not None:
            bucket["memory_mb"].append(float(row["memory_mb"]))
    return {
        "groups": [
            {"registry_size": size, "stage": stage,
             "latency_ms": percentile_summary(vals["latency_ms"]),
             "memory_mb": percentile_summary(vals["memory_mb"])}
            for (size, stage), vals in sorted(grouped.items())
        ],
        "n_records": len(records),
        "scope": "summaries of supplied measurements; no synthetic timing is generated",
    }


def exact_greedy_gap(exact_objective: float, greedy_objective: float,
                     direction: str = "minimize") -> dict:
    """Objective gap relative to exact optimum; validates direction and denominator."""
    if direction not in {"minimize", "maximize"}:
        raise ValueError("direction must be minimize or maximize")
    optimum = float(exact_objective)
    heuristic = float(greedy_objective)
    if optimum == 0:
        gap = 0.0 if heuristic == 0 else None
    elif direction == "minimize":
        gap = (heuristic - optimum) / abs(optimum)
    else:
        gap = (optimum - heuristic) / abs(optimum)
    return {"exact": optimum, "greedy": heuristic, "relative_gap": gap,
            "direction": direction, "undefined_reason": "zero exact objective" if gap is None else None}


def jaccard_similarity(left: Sequence[str], right: Sequence[str]) -> float:
    a, b = set(left), set(right)
    union = a | b
    return len(a & b) / len(union) if union else 1.0


def weight_sensitivity(reference_toolkits: Mapping[str, Sequence[str]], outcomes_by_weight: Mapping[str, Mapping[str, float]] | None = None) -> dict:
    """E20 pairwise toolkit Jaccard similarities, preserving supplied weight IDs."""
    keys = sorted(reference_toolkits)
    rows = []
    for i, left in enumerate(keys):
        for right in keys[i + 1:]:
            rows.append({"left": left, "right": right,
                         "jaccard": jaccard_similarity(reference_toolkits[left], reference_toolkits[right])})
    return {"pairs": rows, "n_settings": len(keys),
            "mean_pairwise_jaccard": mean([r["jaccard"] for r in rows]) if rows else None,
            "outcomes_by_weight": {key: dict(value) for key, value in (outcomes_by_weight or {}).items()},
            "outcome_metrics": ["Exp@5", "task_success", "price", "latency"]}


def evolution_replay_metrics(events: Sequence[Mapping[str, Any]]) -> dict:
    """E16 compare incremental state to full recomputation after each supplied event."""
    stale = invalidated = false_invalidation = incorrect = 0
    rows = []
    for event in events:
        expected = set(event.get("expected_invalidations", ()))
        actual = set(event.get("actual_invalidations", ()))
        stale_now = set(event.get("stale_answers", ()))
        false_now = actual - expected
        missing_now = expected - actual
        invalidated += len(actual)
        false_invalidation += len(false_now)
        stale += len(stale_now)
        incorrect += int(event.get("incremental_state") != event.get("full_recompute_state"))
        rows.append({"event_id": event.get("event_id"), "missing_invalidations": sorted(missing_now),
                     "false_invalidations": sorted(false_now), "stale_answers": sorted(stale_now),
                     "state_matches_recompute": event.get("incremental_state") == event.get("full_recompute_state")})
    return {"events": len(events), "invalidated_entries": invalidated,
            "false_invalidations": false_invalidation, "stale_answers": stale,
            "events_incorrect_vs_recompute": incorrect, "per_event": rows}


def percentile_bootstrap(
    values: Sequence[float], *, confidence: float = .95, replicates: int = 10000,
    seed: int = 0,
) -> dict:
    """Percentile bootstrap CI for a mean; resamples the supplied independent units."""
    xs = [float(x) for x in values]
    if not 0 < confidence < 1 or replicates < 1:
        raise ValueError("invalid confidence or replicate count")
    if not xs:
        return {"estimate": None, "ci": [None, None], "ci_width": None, "n": 0, "replicates": replicates}
    rng = random.Random(seed)
    estimates = [mean(rng.choices(xs, k=len(xs))) for _ in range(replicates)]
    alpha = (1 - confidence) / 2
    ci_low, ci_high = _quantile(estimates, alpha), _quantile(estimates, 1-alpha)
    return {"estimate": mean(xs), "ci": [ci_low, ci_high],
            "ci_width": ci_high - ci_low, "n": len(xs), "replicates": replicates, "seed": seed,
            "resampling_unit": "one supplied value; caller must supply request- or target-tool-level units"}


def paired_sign_flip(
    differences: Sequence[float], *, seed: int = 0, monte_carlo_samples: int = 100000,
) -> dict:
    """Two-sided paired sign-flip test; exact through n=20, deterministic MC above."""
    ds = [float(x) for x in differences]
    n = len(ds)
    if not ds:
        return {"statistic": None, "p_value": None, "n": 0, "method": "undefined"}
    observed = abs(mean(ds))
    tolerance = 1e-12
    if n <= 20:
        vals = (abs(sum(s * d for s, d in zip(signs, ds)) / n)
                for signs in itertools.product((-1.0, 1.0), repeat=n))
        count = sum(value >= observed - tolerance for value in vals)
        total = 2 ** n
        method = "exact"
    else:
        rng = random.Random(seed)
        count = 0
        for _ in range(monte_carlo_samples):
            value = abs(mean(d * rng.choice((-1.0, 1.0)) for d in ds))
            count += value >= observed - tolerance
        total = monte_carlo_samples
        method = "monte_carlo"
    p = count / total if method == "exact" else (count + 1) / (total + 1)
    return {"statistic": mean(ds), "absolute_statistic": observed, "p_value": p,
            "n": n, "method": method, "permutations": total, "seed": seed}


def adjust_pvalues(p_values: Mapping[str, float], method: str = "holm") -> dict:
    """Holm family-wise or Benjamini-Hochberg adjusted p-values."""
    if method not in {"holm", "bh"}:
        raise ValueError("method must be holm or bh")
    items = sorted(((key, float(value)) for key, value in p_values.items()), key=lambda item: item[1])
    if any(not 0 <= value <= 1 for _, value in items):
        raise ValueError("p-values must lie in [0,1]")
    m = len(items)
    adjusted = {}
    if method == "holm":
        running = 0.0
        for rank, (key, value) in enumerate(items):
            running = max(running, min(1.0, (m-rank) * value))
            adjusted[key] = running
    else:
        running = 1.0
        for rank in range(m-1, -1, -1):
            key, value = items[rank]
            running = min(running, value * m / (rank+1))
            adjusted[key] = min(1.0, running)
    return {"method": method, "family_size": m, "adjusted": adjusted}


def rank_stability(rankings: Sequence[Mapping[str, int]]) -> dict:
    """Mean pairwise Spearman rank correlation over common tool IDs."""
    pairs = []
    for i in range(len(rankings)):
        for j in range(i + 1, len(rankings)):
            common = sorted(set(rankings[i]) & set(rankings[j]))
            if len(common) < 2:
                rho = None
            else:
                x = [float(rankings[i][tool]) for tool in common]
                y = [float(rankings[j][tool]) for tool in common]
                mx, my = mean(x), mean(y)
                dx = [v-mx for v in x]
                dy = [v-my for v in y]
                denom = math.sqrt(sum(v*v for v in dx) * sum(v*v for v in dy))
                rho = sum(a*b for a, b in zip(dx, dy)) / denom if denom else None
            pairs.append({"left": i, "right": j, "n_common": len(common), "spearman": rho})
    vals = [row["spearman"] for row in pairs if row["spearman"] is not None]
    return {"pairs": pairs, "mean_pairwise_rank_correlation": mean(vals) if vals else None}
