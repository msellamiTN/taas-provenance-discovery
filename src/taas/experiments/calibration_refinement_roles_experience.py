"""Offline evaluators for E12, E17, E19 and E21 from frozen records."""
from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Mapping, Sequence

from .scalability_sensitivity_statistics import percentile_bootstrap


def model_profile_calibration(records: Sequence[Mapping], *, tau: float = .9,
                              replicates: int = 10000, seed: int = 0) -> dict:
    """E12 measured reliability CIs, claimed-vs-measured and refutation rates."""
    groups = defaultdict(list)
    for row in records:
        key = (str(row["class"]), int(row["n"]), str(row.get("lang", "en")),
               str(row.get("exactness", "tolerant")))
        groups[key].append(row)
    cells = []
    cell_gaps, refuted_cells, claim_cells = [], 0, 0
    for key, rows in sorted(groups.items()):
        outcomes = [float(bool(row["correct"])) for row in rows]
        estimate = mean(outcomes)
        ci = percentile_bootstrap(outcomes, replicates=replicates,
                                  seed=seed + len(cells))
        paired = [(float(row["claimed_rho"]), float(bool(row["correct"])))
                  for row in rows if row.get("claimed_rho") is not None]
        claim_values = [pair[0] for pair in paired]
        claim = mean(claim_values) if claim_values else None
        if paired:
            claim_cell = mean(value for value, _ in paired)
            measured_cell = mean(outcome for _, outcome in paired)
            cell_gaps.append(abs(claim_cell - measured_cell))
            claim_cells += 1
            refuted_cells += int(claim_cell >= tau and measured_cell < tau)
        cells.append({"class": key[0], "n": key[1], "lang": key[2], "exactness": key[3],
                      "count": len(rows), "measured_reliability": estimate,
                      "reliability_ci": ci["ci"], "claimed_rho": claim})
    return {
        "cells": cells, "n_records": len(records),
        "mean_absolute_calibration_gap": mean(cell_gaps) if cell_gaps else None,
        "refuted_claim_cells": refuted_cells, "claim_cell_denominator": claim_cells,
        "refutation_rate": refuted_cells / claim_cells if claim_cells else None,
        "tau": tau,
        "note": "claims are compared only where claimed_rho is supplied; no prior is treated as measured",
    }


def refinement_metrics(records: Sequence[Mapping]) -> dict:
    """E17 repair success, iteration count, abstention and token use by χ and iteration."""
    by_chi = defaultdict(list)
    by_iteration = defaultdict(list)
    for row in records:
        chi = str(row.get("chi", "unknown"))
        by_chi[chi].append(row)
        if row.get("iterations") is not None:
            by_iteration[int(row["iterations"])].append(row)
    groups = {}
    for chi, rows in sorted(by_chi.items()):
        n = len(rows)
        groups[chi] = {
            "n": n,
            "repair_success_rate": sum(bool(r.get("repair_success")) for r in rows) / n,
            "abstention_rate": sum(bool(r.get("abstained")) for r in rows) / n,
            "iterations": _summary([r.get("iterations") for r in rows]),
            "tokens": _summary([r.get("tokens") for r in rows]),
        }
    success_by_iteration = {
        str(iteration): {
            "n": len(rows),
            "repair_success_rate": sum(bool(r.get("repair_success")) for r in rows) / len(rows),
            "abstention_rate": sum(bool(r.get("abstained")) for r in rows) / len(rows),
        }
        for iteration, rows in sorted(by_iteration.items())
    }
    return {"by_chi": groups, "success_by_iteration": success_by_iteration,
            "n_records": len(records)}


def _summary(values):
    xs = [float(x) for x in values if x is not None]
    if not xs:
        return {"n": 0, "mean": None, "p50": None, "p95": None}
    xs.sort()
    def q(p):
        pos = (len(xs)-1)*p
        lo, hi = int(pos), min(int(pos)+1, len(xs)-1)
        return xs[lo] + (xs[hi]-xs[lo])*(pos-lo)
    return {"n": len(xs), "mean": mean(xs), "p50": q(.5), "p95": q(.95)}


def role_configuration_metrics(records: Sequence[Mapping]) -> dict:
    """E19 validity, repair, success, token and latency outcomes by role configuration."""
    by_role = defaultdict(list)
    for row in records:
        by_role[str(row["role_configuration"])].append(row)
    out = {}
    for role, rows in sorted(by_role.items()):
        n = len(rows)
        out[role] = {
            "n": n,
            "goalspec_validity_rate": sum(bool(r.get("goalspec_valid")) for r in rows) / n,
            "repair_rate": sum(bool(r.get("repaired")) for r in rows) / n,
            "task_success_rate": sum(bool(r.get("task_success")) for r in rows) / n,
            "tokens": _summary([r.get("tokens") for r in rows]),
            "latency_ms": _summary([r.get("latency_ms") for r in rows]),
        }
    return {"roles": out, "n_records": len(records)}


def experience_reuse_metrics(records: Sequence[Mapping]) -> dict:
    """E21 reuse rate, latency saved and stale-evidence detection from confirmed trajectories."""
    n = len(records)
    reused = [r for r in records if r.get("reused") is True]
    saved = [
        float(r["cold_latency_ms"]) - float(r["reuse_latency_ms"])
        for r in reused
        if r.get("cold_latency_ms") is not None and r.get("reuse_latency_ms") is not None
    ]
    stale = [r for r in records if r.get("stale_evidence") is True]
    caught = sum(bool(r.get("stale_error_caught")) for r in stale)
    return {
        "n_trajectories": n,
        "reuse_rate": len(reused) / n if n else None,
        "reused_trajectories": len(reused),
        "latency_saved_ms": _summary(saved),
        "stale_cases": len(stale),
        "stale_errors_caught": caught,
        "stale_errors_uncaught": len(stale) - caught,
        "stale_error_detection_rate": caught / len(stale) if stale else None,
        "note": "requires confirmed trajectory repository; no trajectory is generated by this evaluator",
    }
