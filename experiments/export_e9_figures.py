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


def export_e9_figures(
    run_dir: Path,
    output_dir: Path,
    protocol_path: Path = PROTOCOL,
    bootstrap_resamples: int = 5000,
    seed: int = 20261107,
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
    cutoffs = sorted({int(k) for k in manifest.get("ranking_cutoffs", [5, 10, 20])})
    if cutoffs != [5, 10, 20]:
        raise ValueError("E9 ranking_cutoffs must match the protocol values [5, 10, 20]")

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

    seen: set[tuple[str, str, str, str]] = set()
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
        key = (benchmark, task_id)
        if not task_id or not benchmark or not baseline or not decomposition:
            raise ValueError("E9 discovery rows require task_id, benchmark, baseline and decomposition")
        if decomposition not in {"none", "clause_splitter", "llm_analyst"}:
            raise ValueError(f"{benchmark}/{task_id}: unknown decomposition condition {decomposition!r}")
        if baseline not in executable_methods:
            raise ValueError(f"{benchmark}/{task_id}: method {baseline!r} absent from executed baseline/primary-configuration manifest")
        pair = (benchmark, task_id, baseline, decomposition)
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
            raise ValueError(f"{benchmark}/{task_id}/{baseline}: ranking has empty or duplicate tool IDs")
        if len(visible) != len(set(str(x).strip() for x in visible_raw)) or any(not x for x in visible):
            raise ValueError(f"{benchmark}/{task_id}/{baseline}: visibility contains duplicate/empty IDs")
        if not set(ranked).issubset(visible):
            raise ValueError(f"{benchmark}/{task_id}/{baseline}: ranking includes tools outside task visibility")
        if key not in refs:
            skipped_no_reference += 1
            skipped_no_reference_task_keys.add(key)
            trace = trace_ref_map.get(key)
            if trace:
                ref_tools = set(trace["reference_trace_tool_ids"])
                for k in cutoffs:
                    predicted = set(ranked[:k])
                    intersection = len(predicted & ref_tools)
                    diagnostic_rows.append({
                        "task_id": task_id, "benchmark": benchmark, "baseline": baseline,
                        "task_group": task_group, "decomposition": decomposition, "k": k,
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
        for k in cutoffs:
            predicted_list = ranked[:k]
            predicted = set(predicted_list)
            precision, recall, selected_reference = _best_reference(predicted, ref["alternatives"])
            complete = any(set(alternative).issubset(predicted) for alternative in ref["alternatives"])
            per_task.append({
                "task_id": task_id,
                "benchmark": benchmark,
                "baseline": baseline,
                "task_group": task_group,
                "decomposition": decomposition,
                "k": k,
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

    # Preserve per-task evidence so later paired analyses can be reconstructed.
    per_task_columns = [
        "task_id", "benchmark", "baseline", "decomposition", "task_group", "k",
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

    f1_rows, f2_rows, f3_rows, ci_exclusions = [], [], [], []
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
    if diagnostic_rows:
        _write_csv(output_dir / "E9_TRACE_DIAGNOSTICS.csv",
                   ["task_id", "benchmark", "baseline", "task_group", "decomposition", "k", "trace_coverage",
                    "reference_trace_size", "reference_semantics"], diagnostic_rows)

    exported = [figure_id for figure_id, rows in [
        ("E9-F1", f1_rows), ("E9-F2", f2_rows), ("E9-F3", f3_rows)
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
            for figure, rows in [("E9-F1", f1_rows), ("E9-F2", f2_rows), ("E9-F3", f3_rows)]
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
    parser.add_argument("--bootstrap-resamples", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=20261107)
    args = parser.parse_args()
    result = export_e9_figures(
        args.run_dir, args.output_dir, args.protocol,
        args.bootstrap_resamples, args.seed,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
