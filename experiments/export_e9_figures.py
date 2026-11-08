#!/usr/bin/env python3
"""Export E9 multi-tool set metrics from frozen rankings and evaluator-only references.

The discovery ranking file must be materialized before evaluator references are read.
Only independently adjudicated or benchmark-native acceptable tool sets contribute
to primary group-recall / set-precision / complete-set figures. A strictly resolved
LiveMCPBench proposer-completed, validator-scrutinized chain is one benchmark-native
successful reference set, not an exhaustive enumeration of alternatives. MCP-Atlas
trajectories remain diagnostics unless the benchmark supplies exhaustive set labels.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random

import numpy as np

from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "docs" / "experiment_design" / "pamcp_experiments_v1.json"
PRIMARY_REFERENCE_SEMANTICS = {
    "independently_adjudicated_acceptable_sets",
    "benchmark_native_acceptable_sets",
}
TRACE_REFERENCE_SEMANTICS = {
    "annotated_trace_only",
    "positive_trace_only",
    "mcp_atlas_trajectory_diagnostic",
}
FORBIDDEN_DISCOVERY_KEYS = {
    "acceptable_tool_sets", "target_tool_ids", "qrels", "labels",
    "gtfa_claims", "trajectory_reference", "reference_trace_tool_ids",
    "answer", "reference_answer",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    rows = []
    with path.open(encoding="utf-8") as stream:
        for line_no, raw in enumerate(stream, start=1):
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSONL: {exc}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_no}: each JSONL record must be an object")
            rows.append(row)
    return rows


def _write_csv(path: Path, columns: list[str], rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _normalize_sets(value: Any, task_id: str) -> list[tuple[str, ...]]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{task_id}: primary acceptable_tool_sets must be a non-empty list")
    normalized: set[tuple[str, ...]] = set()
    for group in value:
        if not isinstance(group, list) or not group:
            raise ValueError(f"{task_id}: each acceptable tool set must be a non-empty list")
        tools = tuple(sorted({str(item).strip() for item in group if str(item).strip()}))
        if not tools:
            raise ValueError(f"{task_id}: empty acceptable tool set after normalization")
        normalized.add(tools)
    return sorted(normalized)


def _best_reference(predicted: set[str], alternatives: list[tuple[str, ...]]) -> tuple[float, float, tuple[str, ...]]:
    """Choose one alternative by Jaccard; derive precision and recall from that same set."""
    best = None
    for reference in alternatives:
        reference_set = set(reference)
        intersection = len(predicted & reference_set)
        precision = intersection / len(predicted) if predicted else 0.0
        recall = intersection / len(reference_set)
        union = len(predicted | reference_set)
        jaccard = intersection / union if union else 0.0
        candidate = (jaccard, precision, recall, reference)
        if best is None or candidate[0] > best[0] or (
            candidate[0] == best[0] and candidate[3] < best[3]
        ):
            best = candidate
    assert best is not None
    return best[1], best[2], best[3]


def _bootstrap_ci(
    observations: list[tuple[float, str]],
    seed: int,
    resamples: int,
) -> tuple[float, float, float, int]:
    """Percentile bootstrap of task means, clustered when independent-unit IDs are supplied."""
    if resamples < 100:
        raise ValueError("At least 100 bootstrap resamples are required")
    if not observations:
        raise ValueError("Cannot bootstrap an empty group")
    by_unit: dict[str, list[float]] = defaultdict(list)
    for value, unit in observations:
        by_unit[unit].append(value)
    units = [by_unit[key] for key in sorted(by_unit)]
    if len(units) < 2:
        raise ValueError("At least two independent task/cluster units are required for a CI")
    values = [value for value, _ in observations]
    point = sum(values) / len(values)
    rng = random.Random(seed)
    draws = []
    for _ in range(resamples):
        sampled = [units[rng.randrange(len(units))] for _ in range(len(units))]
        flat = [value for unit in sampled for value in unit]
        draws.append(sum(flat) / len(flat))
    draws.sort()
    lower = draws[max(0, int(0.025 * resamples))]
    upper = draws[min(resamples - 1, int(0.975 * resamples))]
    return point, lower, upper, len(units)


def _stable_seed(seed: int, key: str) -> int:
    digest = hashlib.sha256(f"{seed}\0{key}".encode("utf-8")).hexdigest()
    return seed + int(digest[:12], 16)


def _paired_inference(
    observations: list[tuple[float, str]],
    seed: int,
    bootstrap_resamples: int = 10000,
    sign_flip_resamples: int = 100000,
) -> dict[str, Any]:
    """Cluster-paired task bootstrap CI and sign-flip test.

    Each independent_unit_id is one exchangeable unit. Tasks sharing a cluster
    are resampled together and receive one common sign in the sign-flip test.
    The point estimate remains the task-weighted mean paired difference.
    """
    if bootstrap_resamples < 100 or sign_flip_resamples < 100:
        raise ValueError("Paired inference requires at least 100 resamples")
    by_unit: dict[str, list[float]] = defaultdict(list)
    for difference, independent_unit_id in observations:
        unit = str(independent_unit_id).strip()
        if not unit:
            raise ValueError("Paired inference requires non-empty independent_unit_id values")
        by_unit[unit].append(float(difference))

    n_tasks = sum(len(values) for values in by_unit.values())
    unit_ids = sorted(by_unit)
    n_units = len(unit_ids)
    if n_units < 2:
        return {
            "status": "insufficient_independent_units",
            "n": n_tasks,
            "n_independent_units": n_units,
        }

    clusters = [np.asarray(by_unit[unit], dtype=float) for unit in unit_ids]
    cluster_sums = np.asarray([float(values.sum()) for values in clusters], dtype=float)
    point = float(cluster_sums.sum() / n_tasks)

    # Resample whole independent units, retaining every paired task in each draw.
    rng = np.random.default_rng(seed)
    draws = np.empty(bootstrap_resamples, dtype=float)
    for index in range(bootstrap_resamples):
        sampled_indices = rng.integers(0, n_units, size=n_units)
        sampled_values = [clusters[int(i)] for i in sampled_indices]
        draws[index] = float(np.concatenate(sampled_values).mean())
    ci_low, ci_high = np.quantile(draws, [0.025, 0.975]).tolist()

    # Sign flips are applied per independent unit, not per task within a cluster.
    observed = abs(point)
    if n_units <= 16:
        total = 1 << n_units
        extreme = 0
        for mask in range(total):
            signed_sum = sum(
                float(cluster_sums[index]) if (mask >> index) & 1 else -float(cluster_sums[index])
                for index in range(n_units)
            )
            if abs(signed_sum / n_tasks) >= observed - 1e-15:
                extreme += 1
        p_value = extreme / total
        test_method = "exact_cluster_paired_sign_flip"
        actual_resamples = total
    else:
        extreme = 0
        offset = 0
        batch = 2000
        while offset < sign_flip_resamples:
            count = min(batch, sign_flip_resamples - offset)
            signs = rng.choice(np.array([-1.0, 1.0]), size=(count, n_units))
            permuted = np.abs((signs @ cluster_sums) / n_tasks)
            extreme += int(np.count_nonzero(permuted >= observed - 1e-15))
            offset += count
        p_value = (extreme + 1) / (sign_flip_resamples + 1)
        test_method = "monte_carlo_cluster_paired_sign_flip"
        actual_resamples = sign_flip_resamples

    return {
        "status": "tested",
        "n": n_tasks,
        "n_independent_units": n_units,
        "mean_paired_difference": point,
        "ci_low": float(ci_low),
        "ci_high": float(ci_high),
        "p_value": float(p_value),
        "test_method": test_method,
        "sign_flip_resamples": actual_resamples,
        "bootstrap_resamples": bootstrap_resamples,
    }

def _holm_adjust(rows: list[dict[str, Any]]) -> None:
    tested = [row for row in rows if row.get("status") == "tested" and row.get("p_value") is not None]
    ordered = sorted(tested, key=lambda row: (float(row["p_value"]), str(row["comparison_id"])))
    family_size = len(ordered)
    adjusted_running = 0.0
    tested_ids = {id(row) for row in tested}
    for rank, row in enumerate(ordered):
        adjusted_running = max(
            adjusted_running,
            min(1.0, (family_size - rank) * float(row["p_value"])),
        )
        row["holm_adjusted_p"] = adjusted_running
        row["holm_family_size"] = family_size
    for row in rows:
        if id(row) not in tested_ids:
            row["holm_adjusted_p"] = ""
            row["holm_family_size"] = family_size



def export_e9_figures(
    run_dir: Path,
    output_dir: Path,
    protocol_path: Path = PROTOCOL,
    bootstrap_resamples: int = 10000,
    seed: int = 20261108,
    sign_flip_resamples: int = 100000,
) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    output_dir = output_dir.resolve()
    manifest_path = run_dir / "MANIFEST.json"
    ranking_path = run_dir / "discovery" / "rankings.jsonl"
    reference_path = run_dir / "evaluator" / "task_references.jsonl"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("experiment_id") != "E9":
        raise ValueError("Input run manifest is not an E9 campaign")
    if manifest.get("status") not in {"partial", "complete"}:
        raise ValueError(f"Unexpected E9 run status: {manifest.get('status')!r}")

    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    experiment = next((item for item in protocol["experiments"] if item["id"] == "E9"), None)
    if experiment is None:
        raise ValueError("Frozen protocol contains no E9 definition")
    registered = set(experiment["baseline_ids"])
    declared_registered = set(manifest.get("baseline_ids_registered", []))
    if registered != declared_registered:
        raise ValueError(
            "E9 run baseline registry differs from the frozen protocol: "
            f"protocol={sorted(registered)}, run={sorted(declared_registered)}"
        )
    executed = set(manifest.get("baseline_ids_executed", []))
    if not executed.issubset(registered):
        raise ValueError(f"E9 run declares unregistered baselines as executed: {sorted(executed - registered)}")
    plot_plan_path = ROOT / "docs" / "experiment_design" / "pamcp_plot_plan_v1.json"
    plot_plan = json.loads(plot_plan_path.read_text(encoding="utf-8"))
    e9_plot_spec = next(item for item in plot_plan["experiments"] if item["id"] == "E9")
    primary_id = next(
        (figure["comparison"].get("primary_configuration")
         for figure in e9_plot_spec["figures"] if figure["comparison"].get("primary_configuration")),
        None,
    )
    primary_executed = bool(manifest.get("primary_configuration_executed", False))
    manifest_primary_id = manifest.get("primary_configuration_id")
    if primary_executed and (not primary_id or manifest_primary_id != primary_id):
        raise ValueError(
            f"E9 primary configuration mismatch: plot plan={primary_id!r}, "
            f"run manifest={manifest_primary_id!r}"
        )
    if not primary_executed and manifest_primary_id not in {None, primary_id}:
        raise ValueError(f"E9 manifest declares an unexpected primary configuration {manifest_primary_id!r}")
    executable_methods = executed | ({primary_id} if primary_executed and primary_id else set())
    cutoffs = sorted({int(k) for k in manifest.get("ranking_cutoffs", [1, 3, 5, 10, 20])})
    if cutoffs != [1, 3, 5, 10, 20]:
        raise ValueError("E9 ranking_cutoffs must match the protocol values [1, 3, 5, 10, 20]")

    ranking_rows = _read_jsonl(ranking_path)
    reference_rows = _read_jsonl(reference_path)
    if not ranking_rows:
        raise ValueError("E9 discovery rankings are empty")
    if not reference_rows:
        raise ValueError("E9 evaluator reference file is empty")

    refs: dict[tuple[str, str], dict[str, Any]] = {}
    trace_only = []
    for row in reference_rows:
        task_id = str(row.get("task_id", "")).strip()
        benchmark = str(row.get("benchmark", "")).strip()
        if not task_id or not benchmark:
            raise ValueError("E9 evaluator records require task_id and benchmark")
        key = (benchmark, task_id)
        if key in refs:
            raise ValueError(f"Duplicate E9 evaluator reference: {key}")
        semantics = str(row.get("reference_semantics", "")).strip()
        if semantics in PRIMARY_REFERENCE_SEMANTICS:
            alternatives = _normalize_sets(row.get("acceptable_tool_sets"), task_id)
            refs[key] = {
                "alternatives": alternatives,
                "semantics": semantics,
                "independent_unit_id": str(row.get("independent_unit_id") or task_id),
                "source_revision": row.get("source_revision"),
            }
        elif semantics in TRACE_REFERENCE_SEMANTICS:
            trace = row.get("reference_trace_tool_ids", [])
            if trace and not isinstance(trace, list):
                raise ValueError(f"{task_id}: reference_trace_tool_ids must be a list")
            trace_only.append({
                "benchmark": benchmark,
                "task_id": task_id,
                "reference_semantics": semantics,
                "reference_trace_tool_ids": sorted({str(x) for x in (trace or [])}),
                "source_revision": row.get("source_revision"),
            })
        else:
            raise ValueError(
                f"{task_id}: unsupported/unspecified reference_semantics {semantics!r}; "
                "declare an accepted reference class explicitly"
            )

    seen: set[tuple[str, str, str, str, int]] = set()
    per_task: list[dict[str, Any]] = []
    task_meta: dict[tuple[str, str], dict[str, Any]] = {}
    diagnostic_rows: list[dict[str, Any]] = []
    baseline_rows: dict[str, int] = defaultdict(int)
    invalid_reference_visibility: list[dict[str, Any]] = []
    skipped_no_reference = 0
    skipped_no_reference_task_keys: set[tuple[str, str]] = set()

    trace_ref_map = {(r["benchmark"], r["task_id"]): r for r in trace_only}
    for row in ranking_rows:
        leaked = sorted(FORBIDDEN_DISCOVERY_KEYS.intersection(row))
        if leaked:
            raise ValueError(
                f"Discovery ranking contains evaluator-only fields for {row.get('task_id')}: {leaked}"
            )
        task_id = str(row.get("task_id", "")).strip()
        benchmark = str(row.get("benchmark", "")).strip()
        baseline = str(row.get("baseline", "")).strip()
        task_group = str(row.get("task_group") or "unspecified")
        decomposition = str(row.get("decomposition") or "").strip()
        ranking_k = int(row.get("ranking_k", -1))
        prediction_kind = str(row.get("prediction_kind") or "top_k_retrieved_tools")
        key = (benchmark, task_id)
        if not task_id or not benchmark or not baseline or not decomposition:
            raise ValueError("E9 discovery rows require task_id, benchmark, baseline and decomposition")
        if decomposition not in {"none", "clause_splitter", "llm_analyst"}:
            raise ValueError(f"{benchmark}/{task_id}: unknown decomposition condition {decomposition!r}")
        if ranking_k not in cutoffs:
            raise ValueError(f"{benchmark}/{task_id}/{baseline}: ranking_k={ranking_k} is outside {cutoffs}")
        if prediction_kind not in {"selected_toolkit", "top_k_retrieved_tools"}:
            raise ValueError(f"{benchmark}/{task_id}/{baseline}: unsupported prediction_kind={prediction_kind!r}")
        if baseline not in executable_methods:
            raise ValueError(f"{benchmark}/{task_id}: method {baseline!r} absent from executed baseline/primary-configuration manifest")
        pair = (benchmark, task_id, baseline, decomposition, ranking_k)
        if pair in seen:
            raise ValueError(f"Duplicate E9 discovery ranking: {pair}")
        seen.add(pair)
        ranked_raw = row.get("ranked_tool_ids")
        visible_raw = row.get("visible_tool_ids")
        if not isinstance(ranked_raw, list) or not isinstance(visible_raw, list):
            raise ValueError(f"{benchmark}/{task_id}/{baseline}: ranked_tool_ids and visible_tool_ids must be lists")
        ranked = [str(x).strip() for x in ranked_raw]
        visible = {str(x).strip() for x in visible_raw}
        if any(not x for x in ranked) or len(ranked) != len(set(ranked)):
            raise ValueError(f"{benchmark}/{task_id}/{baseline}: prediction has empty or duplicate tool IDs")
        if prediction_kind == "top_k_retrieved_tools" and len(ranked) > ranking_k:
            raise ValueError(f"{benchmark}/{task_id}/{baseline}: top-k retrieval output exceeds ranking_k")
        if len(visible) != len(set(str(x).strip() for x in visible_raw)) or any(not x for x in visible):
            raise ValueError(f"{benchmark}/{task_id}/{baseline}: visibility contains duplicate/empty IDs")
        if not set(ranked).issubset(visible):
            raise ValueError(f"{benchmark}/{task_id}/{baseline}: prediction includes tools outside task visibility")
        if key not in refs:
            skipped_no_reference += 1
            skipped_no_reference_task_keys.add(key)
            trace = trace_ref_map.get(key)
            if trace:
                ref_tools = set(trace["reference_trace_tool_ids"])
                predicted = set(ranked)
                intersection = len(predicted & ref_tools)
                diagnostic_rows.append({
                    "task_id": task_id, "benchmark": benchmark, "baseline": baseline,
                    "task_group": task_group, "decomposition": decomposition, "k": ranking_k,
                    "prediction_size": len(predicted),
                    "trace_coverage": intersection / len(ref_tools) if ref_tools else "",
                    "reference_trace_size": len(ref_tools),
                    "reference_semantics": trace["reference_semantics"],
                })
            continue

        ref = refs[key]
        for alternative in ref["alternatives"]:
            if not set(alternative).issubset(visible):
                invalid_reference_visibility.append({
                    "benchmark": benchmark, "task_id": task_id,
                    "acceptable_set": list(alternative),
                    "missing_from_visibility": sorted(set(alternative) - visible),
                })
        if invalid_reference_visibility and invalid_reference_visibility[-1]["benchmark"] == benchmark and invalid_reference_visibility[-1]["task_id"] == task_id:
            continue
        task_meta[key] = {"task_group": task_group}
        predicted = set(ranked)
        precision, recall, selected_reference = _best_reference(predicted, ref["alternatives"])
        complete = any(set(alternative).issubset(predicted) for alternative in ref["alternatives"])
        per_task.append({
            "task_id": task_id,
            "benchmark": benchmark,
            "baseline": baseline,
            "task_group": task_group,
            "decomposition": decomposition,
            "k": ranking_k,
            "prediction_kind": prediction_kind,
            "group_recall": recall,
            "set_precision": precision,
            "complete_set": int(complete),
            "coverage": int(bool(predicted)),
            "reference_size": len(selected_reference),
            "predicted_size": len(predicted),
            "reference_semantics": ref["semantics"],
            "independent_unit_id": ref["independent_unit_id"],
        })
        baseline_rows[baseline] += 1

    if invalid_reference_visibility:
        raise ValueError(
            "One or more acceptable tool sets contain IDs outside the task visibility set; "
            f"examples={invalid_reference_visibility[:3]}"
        )
    if not per_task:
        if diagnostic_rows:
            output_dir.mkdir(parents=True, exist_ok=True)
            _write_csv(
                output_dir / "E9_TRACE_DIAGNOSTICS.csv",
                ["task_id", "benchmark", "baseline", "task_group", "decomposition", "k",
                 "trace_coverage", "reference_trace_size", "reference_semantics"],
                diagnostic_rows,
            )
            trace_manifest = {
                "schema_version": "1.0.0",
                "experiment_id": "E9",
                "source_run_id": manifest.get("run_id"),
                "source_run_status": manifest.get("status"),
                "source_manifest_sha256": sha256_file(manifest_path),
                "source_rankings_sha256": sha256_file(ranking_path),
                "source_evaluator_references_sha256": sha256_file(reference_path),
                "baseline_ids_registered": sorted(registered),
                "baseline_ids_executed": sorted(executable_methods),
                "primary_configuration_id": primary_id,
                "primary_configuration_executed": primary_executed,
                "primary_task_metric_rows": 0,
                "primary_tasks_without_acceptable_set_reference": len(skipped_no_reference_task_keys),
                "primary_ranking_rows_without_acceptable_set_reference": skipped_no_reference,
                "trace_diagnostic_rows": len(diagnostic_rows),
                "figures_exported": [],
                "figures_not_exported": {
                    "E9-F1": "No independently adjudicated or benchmark-native acceptable-set references.",
                    "E9-F2": "No independently adjudicated or benchmark-native acceptable-set references.",
                    "E9-F3": "No independently adjudicated or benchmark-native acceptable-set references.",
                },
                "interpretation": (
                    "Only positive-trace diagnostics were available. No primary multi-tool "
                    "set-quality figure was produced; traces are not treated as exhaustive "
                    "acceptable tool sets."
                ),
            }
            (output_dir / "E9_EXPORT_MANIFEST.json").write_text(
                json.dumps(trace_manifest, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            return trace_manifest
        raise ValueError(
            "No primary E9 metrics can be computed: no discovery rankings match "
            "independently adjudicated/benchmark-native acceptable-set references, "
            "and no trace-only diagnostic rows are available."
        )

    # Paired comparisons use the same task IDs, condition and K.
    paired_index: dict[tuple[str, str, int], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in per_task:
        key = (str(row["benchmark"]), str(row["decomposition"]), int(row["k"]))
        paired_index[key].setdefault(str(row["baseline"]), {})[str(row["task_id"])] = row

    paired_rows: list[dict[str, Any]] = []
    for benchmark, decomposition, k in sorted(paired_index):
        methods_by_task = paired_index[(benchmark, decomposition, k)]
        full_rows = methods_by_task.get("Full_PaMCP", {})
        for comparator in sorted(registered):
            comparator_rows = methods_by_task.get(comparator, {})
            common = sorted(set(full_rows) & set(comparator_rows))
            comparison_id = f"{benchmark}/{decomposition}/k={k}/Full_PaMCP-vs-{comparator}"
            paired_observations = []
            independent_unit_ids = []
            for task_id in common:
                full_row = full_rows[task_id]
                comparator_row = comparator_rows[task_id]
                full_unit = str(full_row.get("independent_unit_id") or "").strip()
                comparator_unit = str(comparator_row.get("independent_unit_id") or "").strip()
                if not full_unit or full_unit != comparator_unit:
                    raise ValueError(
                        f"{comparison_id}/{task_id}: paired methods have missing or mismatched "
                        "independent_unit_id values"
                    )
                independent_unit_ids.append(full_unit)
                paired_observations.append((
                    float(full_row["group_recall"]) - float(comparator_row["group_recall"]),
                    full_unit,
                ))
            inference = _paired_inference(
                paired_observations,
                _stable_seed(seed, comparison_id),
                bootstrap_resamples=bootstrap_resamples,
                sign_flip_resamples=sign_flip_resamples,
            )
            paired_rows.append({
                "comparison_id": comparison_id,
                "benchmark": benchmark,
                "decomposition": decomposition,
                "k": k,
                "primary_method": "Full_PaMCP",
                "comparator": comparator,
                "metric": "group_recall",
                "n_common_tasks": len(common),
                "n_independent_units": len(set(independent_unit_ids)),
                "common_task_ids_sha256": hashlib.sha256(
                    "\n".join(common).encode("utf-8")
                ).hexdigest(),
                "independent_unit_ids_sha256": hashlib.sha256(
                    "\n".join(sorted(set(independent_unit_ids))).encode("utf-8")
                ).hexdigest(),
                **inference,
            })
    _holm_adjust(paired_rows)
    if paired_rows:
        _write_csv(
            output_dir / "E9_PAIRED_TESTS.csv",
            [
                "comparison_id", "benchmark", "decomposition", "k",
                "primary_method", "comparator", "metric", "status", "n_common_tasks",
                "n_independent_units", "independent_unit_ids_sha256",
                "mean_paired_difference", "ci_low", "ci_high", "p_value", "test_method",
                "sign_flip_resamples", "bootstrap_resamples", "holm_adjusted_p",
                "holm_family_size", "common_task_ids_sha256",
            ],
            paired_rows,
        )

    # Preserve per-task evidence so later paired analyses can be reconstructed.
    per_task_columns = [
        "task_id", "benchmark", "baseline", "decomposition", "task_group", "k", "prediction_kind",
        "group_recall", "set_precision", "complete_set", "coverage",
        "reference_size", "predicted_size", "reference_semantics", "independent_unit_id",
    ]
    _write_csv(output_dir / "E9_per_task_metrics.csv", per_task_columns, per_task)

    grouped: dict[tuple[str, str, str, int], list[dict[str, Any]]] = defaultdict(list)
    group_by_task: dict[tuple[str, str, str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in per_task:
        grouped[(row["benchmark"], row["decomposition"], row["baseline"], row["k"])].append(row)
        group_by_task[
            (row["benchmark"], row["decomposition"], row["baseline"], row["task_group"], row["k"])
        ].append(row)

    f1_rows, f2_rows, f3_rows, f4_rows, ci_exclusions = [], [], [], [], []
    for (benchmark, decomposition, baseline, k), observations in sorted(grouped.items()):
        unit_obs = [
            (float(row["group_recall"]), str(row["independent_unit_id"]))
            for row in observations
        ]
        try:
            mean, low, high, n_units = _bootstrap_ci(
                unit_obs,
                _stable_seed(seed, f"{benchmark}/{decomposition}/{baseline}/{k}/group_recall"),
                bootstrap_resamples,
            )
        except ValueError as exc:
            ci_exclusions.append({
                "figure_id": "E9-F1",
                "benchmark": benchmark,
                "decomposition": decomposition,
                "baseline": baseline,
                "k": k,
                "reason": str(exc),
                "n_tasks": len(observations),
            })
            continue

        f1_rows.append({
            "category": baseline,
            "series": f"Group recall@{k}",
            "value": mean,
            "ci_low": low,
            "ci_high": high,
            "benchmark": benchmark,
            "decomposition": decomposition,
            "n": len(observations),
            "n_independent_units": n_units,
        })
        p_mean = sum(float(row["set_precision"]) for row in observations) / len(observations)
        r_mean = sum(float(row["group_recall"]) for row in observations) / len(observations)
        c_mean = sum(float(row["complete_set"]) for row in observations) / len(observations)
        f2_rows.append({
            "set_precision": p_mean,
            "group_recall": r_mean,
            "series": f"@{k}",
            "label": baseline,
            "complete_set_share": c_mean,
            "benchmark": benchmark,
            "decomposition": decomposition,
            "n": len(observations),
            "n_independent_units": n_units,
        })

    for row in per_task:
        f4_rows.append({
            "group": row["baseline"],
            "value": row["predicted_size"],
            "benchmark": row["benchmark"],
            "decomposition": row["decomposition"],
            "k": row["k"],
        })

    for (benchmark, decomposition, baseline, task_group, k), observations in sorted(group_by_task.items()):
        complete_share = (
            sum(int(row["complete_set"]) for row in observations) / len(observations)
        )
        f3_rows.append({
            "task_group": task_group,
            "method": baseline,
            "value": complete_share,
            "benchmark": benchmark,
            "decomposition": decomposition,
            "k": k,
            "n": len(observations),
        })

    if f1_rows:
        _write_csv(output_dir / "E9-F1.csv",
                   ["category", "series", "value", "ci_low", "ci_high", "benchmark", "decomposition", "n", "n_independent_units"],
                   f1_rows)
    if f2_rows:
        _write_csv(output_dir / "E9-F2.csv",
                   ["set_precision", "group_recall", "series", "label", "complete_set_share", "benchmark", "decomposition", "n", "n_independent_units"],
                   f2_rows)
    if f3_rows:
        _write_csv(output_dir / "E9-F3.csv",
                   ["task_group", "method", "value", "benchmark", "decomposition", "k", "n"],
                   f3_rows)
    if f4_rows:
        _write_csv(
            output_dir / "E9-F4.csv",
            ["group", "value", "benchmark", "decomposition", "k"],
            f4_rows,
        )
    if diagnostic_rows:
        _write_csv(output_dir / "E9_TRACE_DIAGNOSTICS.csv",
                   ["task_id", "benchmark", "baseline", "task_group", "decomposition", "k",
                    "prediction_size", "trace_coverage", "reference_trace_size", "reference_semantics"],
                   diagnostic_rows)

    exported = [figure_id for figure_id, rows in [
        ("E9-F1", f1_rows), ("E9-F2", f2_rows), ("E9-F3", f3_rows), ("E9-F4", f4_rows)
    ] if rows]
    export_manifest = {
        "schema_version": "1.0.0",
        "experiment_id": "E9",
        "source_run_id": manifest.get("run_id"),
        "source_run_status": manifest.get("status"),
        "source_manifest_sha256": sha256_file(manifest_path),
        "source_rankings_sha256": sha256_file(ranking_path),
        "source_evaluator_references_sha256": sha256_file(reference_path),
        "ranking_cutoffs": cutoffs,
        "decomposition_conditions_expected": ["none", "clause_splitter", "llm_analyst"],
        "decomposition_conditions_observed": sorted({row["decomposition"] for row in ranking_rows}),
        "bootstrap": {
            "method": "percentile bootstrap over independent task/cluster units",
            "confidence_level": 0.95,
            "resamples": bootstrap_resamples,
            "seed": seed,
        },
        "paired_inference": {
            "task_matching_unit": "matched task ID",
            "independent_resampling_unit": "independent_unit_id cluster",
            "point_estimator": "task-weighted mean paired difference",
            "bootstrap": "cluster bootstrap; all paired task differences in a sampled cluster stay together",
            "primary_metric": "group_recall@k",
            "test": "cluster-level paired sign-flip",
            "sign_flip_resamples": sign_flip_resamples,
            "exact_when_independent_units_at_most": 16,
            "multiple_testing": "Holm across available Full_PaMCP-versus-registered-comparator tests",
            "paired_test_rows": len(paired_rows),
        },
        "paired_test_file": "E9_PAIRED_TESTS.csv" if paired_rows else None,
        "primary_reference_semantics": sorted(PRIMARY_REFERENCE_SEMANTICS),
        "trace_only_reference_semantics_excluded_from_primary": sorted(TRACE_REFERENCE_SEMANTICS),
        "baseline_ids_registered": sorted(registered),
        "baseline_ids_executed_with_primary_reference_rows": sorted(
            method for method in baseline_rows if method in registered
        ),
        "primary_configuration_id": primary_id,
        "primary_configuration_executed": primary_executed,
        "primary_configuration_rows": baseline_rows.get(primary_id, 0) if primary_id else 0,
        "primary_task_metric_rows": len(per_task),
        "primary_tasks_without_acceptable_set_reference": len(skipped_no_reference_task_keys),
        "primary_ranking_rows_without_acceptable_set_reference": skipped_no_reference,
        "trace_diagnostic_rows": len(diagnostic_rows),
        "ci_exclusions": ci_exclusions,
        "figures_exported": exported,
        "figures_not_exported": {
            figure: "No primary acceptable-set observations satisfy the figure's required grouping/uncertainty contract."
            for figure, rows in [("E9-F1", f1_rows), ("E9-F2", f2_rows), ("E9-F3", f3_rows), ("E9-F4", f4_rows)]
            if not rows
        },
        "interpretation": (
            "Primary E9 set metrics use only independently adjudicated or benchmark-native "
            "acceptable tool sets. Strictly resolved, validator-scrutinized LiveMCPBench "
            "chains are one benchmark-native successful reference set per task, not an "
            "exhaustive enumeration of alternatives. MCP-Atlas trajectories remain "
            "diagnostic-only. Single-tool MCPVerse references are not promoted to "
            "multi-tool set gold."
        ),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "E9_EXPORT_MANIFEST.json").write_text(
        json.dumps(export_manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return export_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results/visualization/data")
    parser.add_argument("--protocol", type=Path, default=PROTOCOL)
    parser.add_argument("--bootstrap-resamples", type=int, default=10000)
    parser.add_argument("--sign-flip-resamples", type=int, default=100000)
    parser.add_argument("--seed", type=int, default=20261108)
    args = parser.parse_args()
    result = export_e9_figures(
        args.run_dir, args.output_dir, args.protocol,
        args.bootstrap_resamples, args.seed, args.sign_flip_resamples,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
