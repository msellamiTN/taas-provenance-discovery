#!/usr/bin/env python3
"""Export validated E8 run artifacts into the frozen publication-figure CSV contracts.

This is an evaluator-side transformation only. It reads a completed E8 run
manifest and its per-task metric export; it does not rerank tools or synthesize
observations. Only baseline IDs registered to E8 in the frozen experiment
catalogue are exported to primary figures. Other campaign controls remain listed
as supplementary and are not relabelled as registered baselines.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "docs" / "experiment_design" / "pamcp_experiments_v1.json"
EXPECTED_TRACKS = {"toolret_heterogeneous", "mcptoolbenchpp_single_target"}
METRICS = {
    ("hit", 1): "Hit@1",
    ("hit", 5): "Hit@5",
    ("mrr", 10): "MRR@10",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _mean_ci(
    values: list[float],
    clusters: list[str],
    seed: int,
    resamples: int,
) -> tuple[float, float, float, int]:
    """Task-weighted mean with a cluster bootstrap when cluster IDs are present.

    Cluster sampling preserves within-target-server dependence while retaining a
    task-weighted estimator: when a cluster is selected, all its task observations
    are copied into the bootstrap sample. ToolRet has no natural shared target-server
    cluster and therefore uses task-level resampling.
    """
    if not values:
        raise ValueError("Cannot bootstrap an empty metric group")
    if resamples < 100:
        raise ValueError("At least 100 bootstrap resamples are required")
    point = sum(values) / len(values)
    if len(clusters) != len(values):
        raise ValueError("Cluster and metric arrays have different lengths")

    has_cluster_ids = any(cluster.strip() for cluster in clusters)
    all_have_cluster_ids = bool(clusters) and all(cluster.strip() for cluster in clusters)
    if has_cluster_ids and not all_have_cluster_ids:
        raise ValueError("A metric group mixes clustered and unclustered observations")
    if all_have_cluster_ids:
        grouped: dict[str, list[float]] = defaultdict(list)
        for value, cluster in zip(values, clusters):
            grouped[cluster].append(value)
        units = [grouped[key] for key in sorted(grouped)]
        unit_count = len(units)
        if unit_count < 2:
            raise ValueError(
                "Cluster bootstrap needs at least two independent target-server clusters"
            )
        rng = random.Random(seed)
        draws = []
        for _ in range(resamples):
            sampled_units = [units[rng.randrange(unit_count)] for _ in range(unit_count)]
            sample = [value for unit in sampled_units for value in unit]
            draws.append(sum(sample) / len(sample))
    else:
        unit_count = len(values)
        rng = random.Random(seed)
        draws = [
            sum((values[index] for index in (rng.randrange(unit_count) for _ in range(unit_count))))
            / unit_count
            for _ in range(resamples)
        ]

    draws.sort()
    lower = draws[max(0, int(0.025 * resamples))]
    upper = draws[min(resamples - 1, int(0.975 * resamples))]
    return point, lower, upper, unit_count


def _read_per_task_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"E8 per-task metric export is missing: {path}")
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"baseline", "task_id", "category", "metric", "k", "value"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path.name}: missing E8 per-task CSV columns {sorted(missing)}")
        return list(reader)


def _group_metrics(
    rows: list[dict[str, str]],
    track_id: str,
    baselines: set[str],
    *,
    by_task_category: bool,
    resamples: int,
    seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str, str], list[tuple[float, str]]] = defaultdict(list)
    for row in rows:
        baseline = row["baseline"]
        if baseline not in baselines:
            continue
        metric_key = (row["metric"].strip().lower(), int(row["k"]))
        metric_name = METRICS.get(metric_key)
        if metric_name is None:
            continue
        category = row["category"] if by_task_category else ""
        value = float(row["value"])
        if not 0.0 <= value <= 1.0:
            raise ValueError(
                f"{track_id}/{baseline}/{metric_name}: expected a [0,1] rate, found {value}"
            )
        grouped[(baseline, metric_name, category)].append(
            (value, row.get("cluster_id", "") or "")
        )

    exported: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for index, ((baseline, metric_name, task_category), observations) in enumerate(sorted(grouped.items())):
        values = [item[0] for item in observations]
        clusters = [item[1] for item in observations]
        cluster_ids = {value for value in clusters if value.strip()}
        if cluster_ids and len(cluster_ids) < 2:
            skipped.append({
                "baseline": baseline,
                "metric": metric_name,
                "task_category": task_category or None,
                "n_tasks": len(values),
                "n_clusters": len(cluster_ids),
                "reason": "fewer than two independent target-server clusters; cluster CI not estimable",
            })
            continue
        point, lower, upper, unit_count = _mean_ci(
            values, clusters, seed + index, resamples
        )
        exported.append({
            "category": baseline,
            "value": point,
            "ci_low": lower,
            "ci_high": upper,
            "series": task_category if by_task_category else metric_name,
            "benchmark": track_id,
            "n": len(values),
            "n_independent_units": unit_count,
        })
    return exported, skipped


def _write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"Refusing to write an empty figure CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "category", "value", "ci_low", "ci_high", "series",
        "benchmark", "n", "n_independent_units",
    ]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def export_e8_figures(
    run_dir: Path,
    output_dir: Path,
    protocol_path: Path = PROTOCOL,
    bootstrap_resamples: int = 5000,
    seed: int = 20261105,
) -> dict[str, Any]:
    """Create E8-F1 and E8-F4 only when real E8 per-task results are present."""
    run_dir = run_dir.resolve()
    output_dir = output_dir.resolve()
    manifest_path = run_dir / "MANIFEST.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"E8 run manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("experiment_id") != "E8":
        raise ValueError("Input run manifest is not an E8 campaign")
    if manifest.get("status") not in {"partial", "complete"}:
        raise ValueError(f"Unexpected E8 run status: {manifest.get('status')!r}")

    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    experiment = next((x for x in protocol["experiments"] if x["id"] == "E8"), None)
    if experiment is None:
        raise ValueError("Frozen protocol contains no E8 definition")
    registered = set(experiment["baseline_ids"])
    manifest_registered = set(
        manifest.get("protocol_baseline_status", {}).get("preregistered_catalog_ids", [])
    )
    if registered != manifest_registered:
        raise ValueError(
            "E8 run baseline registry does not match frozen protocol: "
            f"protocol={sorted(registered)}, run={sorted(manifest_registered)}"
        )

    track_runs = manifest.get("tracks", {})
    missing_tracks = EXPECTED_TRACKS - set(track_runs)
    if missing_tracks:
        raise ValueError(f"E8 run is missing required benchmark tracks: {sorted(missing_tracks)}")

    f1_rows: list[dict[str, Any]] = []
    f4_rows: list[dict[str, Any]] = []
    bootstrap_exclusions: list[dict[str, Any]] = []
    run_hashes: dict[str, str] = {}
    supplementary: dict[str, list[str]] = {}
    executed_registered: dict[str, list[str]] = {}

    for track_index, track_id in enumerate(sorted(EXPECTED_TRACKS)):
        track_meta = track_runs[track_id]
        csv_path = run_dir / f"{track_id}_per_task_metrics.csv"
        run_hashes[csv_path.name] = sha256_file(csv_path)
        rows = _read_per_task_csv(csv_path)
        if track_id == "mcptoolbenchpp_single_target":
            if not rows or any(not row.get("cluster_id", "").strip() for row in rows):
                raise ValueError(
                    "MCPToolBench++ per-task export lacks target-server cluster IDs; "
                    "regenerate E8 using the cluster-preserving exporter before bootstrap."
                )

        csv_baselines = {row["baseline"] for row in rows}
        declared_executed = set(track_meta.get("baseline_ids_executed", []))
        if not csv_baselines.issubset(declared_executed):
            raise ValueError(
                f"{track_id}: per-task CSV contains a method absent from its run manifest"
            )
        actual_registered = csv_baselines & registered
        executed_registered[track_id] = sorted(actual_registered)
        supplementary[track_id] = sorted(csv_baselines - registered)

        f1_part, f1_skipped = _group_metrics(
            rows, track_id, actual_registered,
            by_task_category=False, resamples=bootstrap_resamples,
            seed=seed + 1000 * track_index,
        )
        f4_part, f4_skipped = _group_metrics(
            rows, track_id, actual_registered,
            by_task_category=True, resamples=bootstrap_resamples,
            seed=seed + 2000 * track_index,
        )
        f1_rows.extend(f1_part)
        f4_rows.extend(f4_part)
        bootstrap_exclusions.extend(
            [{"figure_id": "E8-F1", "benchmark": track_id, **item} for item in f1_skipped]
            + [{"figure_id": "E8-F4", "benchmark": track_id, **item} for item in f4_skipped]
        )

    if not f1_rows:
        raise ValueError(
            "No registered E8 baseline has task-level metrics in the run. "
            "No figure CSV was generated."
        )
    _write_rows(output_dir / "E8-F1.csv", f1_rows)
    if f4_rows:
        _write_rows(output_dir / "E8-F4.csv", f4_rows)

    blocked = manifest.get("blocked_or_not_comparable", {})
    figure_manifest = {
        "schema_version": "1.0.0",
        "experiment_id": "E8",
        "source_run_id": manifest.get("run_id"),
        "source_run_status": manifest.get("status"),
        "source_manifest_sha256": sha256_file(manifest_path),
        "source_per_task_csv_sha256": run_hashes,
        "bootstrap": {
            "method": "percentile bootstrap",
            "confidence_level": 0.95,
            "resamples": bootstrap_resamples,
            "seed": seed,
            "ToolRet": "task-level resampling",
            "MCPToolBench++": "target-server cluster resampling; sampled clusters retain their task observations",
        },
        "registered_baseline_ids": sorted(registered),
        "registered_baselines_with_observations": executed_registered,
        "supplementary_unregistered_controls_excluded_from_primary_figures": supplementary,
        "figures_exported": ["E8-F1"] + (["E8-F4"] if f4_rows else []),
        "bootstrap_exclusions": bootstrap_exclusions,
        "figures_not_exported": {
            "E8-F2": (
                "B1/B1m are not included as validated source conditions in the current "
                "campaign; do not relabel primary-qrel and similar_tools sensitivity "
                "metrics as B1/B1m."
            ),
            "E8-F3": (
                "The campaign did not execute a predeclared distractor-count sweep; "
                "the full-corpus retrieval rankings do not define distractor-count observations."
            ),
        },
        "blocked_registered_methods": {
            key: value for key, value in blocked.items()
            if key not in {baseline for values in executed_registered.values() for baseline in values}
        },
        "primary_pa_mcp_executed": any(
            "Full_PaMCP" in values for values in executed_registered.values()
        ),
        "interpretation": (
            "These figures describe the registered retrieval baselines actually executed "
            "in this run. A partial E8 run remains partial; it is not evidence that blocked "
            "methods or Full PaMCP have been evaluated."
        ),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_output = output_dir / "E8_EXPORT_MANIFEST.json"
    manifest_output.write_text(
        json.dumps(figure_manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return figure_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results/visualization/data")
    parser.add_argument("--protocol", type=Path, default=PROTOCOL)
    parser.add_argument("--bootstrap-resamples", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=20261105)
    args = parser.parse_args()
    result = export_e8_figures(
        args.run_dir,
        args.output_dir,
        protocol_path=args.protocol,
        bootstrap_resamples=args.bootstrap_resamples,
        seed=args.seed,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
