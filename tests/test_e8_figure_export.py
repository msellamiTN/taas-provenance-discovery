from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd
import pytest

from experiments.export_e8_figures import _mean_ci, export_e8_figures
from taas.experiments.plotting import iter_figures, load_plot_plan, render_figure, validate_figure_data

ROOT = Path(__file__).resolve().parents[1]
REGISTERED = [
    "bm25", "dense_lsa", "rag_mcp", "mcp_zero",
    "per_subtask", "colt_adapted", "toolscope_adapted", "cmtf_adapted",
]
EXECUTED = ["bm25", "dense_lsa", "tfidf"]
METRICS = [("hit", 1), ("hit", 5), ("mrr", 10)]


def _build_e8_run(root: Path, *, one_mcp_cluster: bool = False) -> Path:
    root.mkdir(parents=True)
    tracks = {}
    for track_id in ("toolret_heterogeneous", "mcptoolbenchpp_single_target"):
        csv_path = root / f"{track_id}_per_task_metrics.csv"
        if track_id == "toolret_heterogeneous":
            tasks = [
                ("q1", "browser", ""),
                ("q2", "browser", ""),
                ("q3", "search", ""),
                ("q4", "search", ""),
            ]
        else:
            tasks = [
                ("q1", "browser", "server-a"),
                ("q2", "browser", "server-b" if not one_mcp_cluster else "server-a"),
                ("q3", "search", "server-a"),
                ("q4", "search", "server-b" if not one_mcp_cluster else "server-a"),
            ]
        rows = []
        for method_index, baseline in enumerate(EXECUTED):
            for task_index, (task_id, category, cluster) in enumerate(tasks):
                for metric_index, (metric, k) in enumerate(METRICS):
                    value = min(0.95, 0.35 + method_index * 0.08 + task_index * 0.04 + metric_index * 0.03)
                    rows.append({
                        "baseline": baseline,
                        "task_id": task_id,
                        "category": category,
                        "cluster_id": cluster,
                        "metric": metric,
                        "k": k,
                        "value": value,
                    })
        with csv_path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(
                stream,
                fieldnames=["baseline", "task_id", "category", "cluster_id", "metric", "k", "value"],
            )
            writer.writeheader()
            writer.writerows(rows)
        tracks[track_id] = {
            "baseline_ids_executed": EXECUTED,
            "metrics_file": f"{track_id}_metrics.json",
        }

    manifest = {
        "schema_version": "1.0.0",
        "experiment_id": "E8",
        "run_id": "E8-test-run",
        "status": "partial",
        "tracks": tracks,
        "protocol_baseline_status": {"preregistered_catalog_ids": REGISTERED},
        "blocked_or_not_comparable": {
            "mcp_zero": {"status": "BLOCKED_ADAPTATION_INPUTS"},
            "per_subtask": {"status": "BLOCKED_ADAPTATION_INPUTS"},
            "colt_adapted": {"status": "BLOCKED_TRAIN_SPLIT"},
            "toolscope_adapted": {"status": "NOT_COMPARABLE_IN_CURRENT_TRACK"},
            "cmtf_adapted": {"status": "BLOCKED_CONTRACT_ORACLE"},
            "B1": {"status": "BLOCKED_DATA"},
            "B1m": {"status": "BLOCKED_DATA"},
        },
    }
    (root / "MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return root


def _figure(figure_id: str):
    plan = load_plot_plan(ROOT / "docs/experiment_design/pamcp_plot_plan_v1.json")
    return next(f for f in iter_figures(plan) if f["id"] == figure_id)


def test_exporter_creates_only_observed_registered_e8_figures(tmp_path):
    run_dir = _build_e8_run(tmp_path / "run")
    output = tmp_path / "visualization" / "data"
    result = export_e8_figures(run_dir, output, bootstrap_resamples=250, seed=42)

    assert result["figures_exported"] == ["E8-F1", "E8-F4"]
    assert result["primary_pa_mcp_executed"] is False
    assert "mcp_zero" in result["blocked_registered_baselines"]
    assert "B1" in result["other_blocked_or_not_comparable_conditions"]
    assert result["registered_baselines_with_observations"] == {
        "mcptoolbenchpp_single_target": ["bm25", "dense_lsa"],
        "toolret_heterogeneous": ["bm25", "dense_lsa"],
    }
    assert result["supplementary_unregistered_controls_excluded_from_primary_figures"] == {
        "mcptoolbenchpp_single_target": ["tfidf"],
        "toolret_heterogeneous": ["tfidf"],
    }
    assert not (output / "E8-F2.csv").exists()
    assert not (output / "E8-F3.csv").exists()

    f1 = pd.read_csv(output / "E8-F1.csv")
    f4 = pd.read_csv(output / "E8-F4.csv")
    assert set(f1["category"]) == {"bm25", "dense_lsa"}
    assert set(f1["series"]) == {"Hit@1", "Hit@5", "MRR@10"}
    assert set(f1["benchmark"]) == {
        "toolret_heterogeneous", "mcptoolbenchpp_single_target"
    }
    assert set(f4["series"]) == {"browser", "search"}
    assert set(f4["category"]) == {"bm25", "dense_lsa"}
    assert ((f1["ci_low"] <= f1["value"]) & (f1["value"] <= f1["ci_high"])).all()
    assert ((f4["ci_low"] <= f4["value"]) & (f4["value"] <= f4["ci_high"])).all()

    validate_figure_data(_figure("E8-F1"), f1)
    validate_figure_data(_figure("E8-F4"), f4)


def test_exporter_skips_task_category_ci_with_only_one_target_server(tmp_path):
    run_dir = _build_e8_run(tmp_path / "run", one_mcp_cluster=True)
    output = tmp_path / "visualization" / "data"
    result = export_e8_figures(run_dir, output, bootstrap_resamples=150, seed=17)

    exclusions = result["bootstrap_exclusions"]
    assert any(
        item["figure_id"] == "E8-F4"
        and item["benchmark"] == "mcptoolbenchpp_single_target"
        and item["n_clusters"] == 1
        for item in exclusions
    )
    f4 = pd.read_csv(output / "E8-F4.csv")
    assert set(f4["benchmark"]) == {"toolret_heterogeneous"}


def test_exporter_rejects_missing_mcp_target_server_cluster_ids(tmp_path):
    run_dir = _build_e8_run(tmp_path / "run")
    path = run_dir / "mcptoolbenchpp_single_target_per_task_metrics.csv"
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    rows[0]["cluster_id"] = ""
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError, match="lacks target-server cluster IDs"):
        export_e8_figures(run_dir, tmp_path / "out", bootstrap_resamples=150)


def test_bootstrap_rejects_mixed_cluster_and_task_level_rows():
    with pytest.raises(ValueError, match="mixes clustered and unclustered"):
        _mean_ci([0.2, 0.8], ["server-a", ""], seed=5, resamples=150)


def test_e8_export_to_publication_plotter_integration(tmp_path):
    run_dir = _build_e8_run(tmp_path / "run")
    data_dir = tmp_path / "visualization" / "data"
    output_dir = tmp_path / "visualization" / "figures"

    export_manifest = export_e8_figures(
        run_dir, data_dir, bootstrap_resamples=250, seed=20261105
    )
    plan = load_plot_plan(ROOT / "docs/experiment_design/pamcp_plot_plan_v1.json")
    figures = {figure["id"]: figure for figure in iter_figures(plan, "E8")}

    assert export_manifest["source_run_status"] == "partial"
    assert export_manifest["primary_pa_mcp_executed"] is False
    assert set(export_manifest["figures_exported"]) == {"E8-F1", "E8-F4"}

    for figure_id in export_manifest["figures_exported"]:
        frame = pd.read_csv(data_dir / f"{figure_id}.csv")
        validation = validate_figure_data(figures[figure_id], frame)
        assert validation["rows"] > 0
        assert set(frame["benchmark"]) == {
            "toolret_heterogeneous", "mcptoolbenchpp_single_target"
        }
        outputs = render_figure(
            figures[figure_id], frame, output_dir, formats=("png",), dpi=100
        )
        assert len(outputs) == 1
        assert outputs[0].is_file()
        assert outputs[0].stat().st_size > 1000

    # Exporter and renderer must not alter experiment status or claim PaMCP ran.
    assert json.loads((run_dir / "MANIFEST.json").read_text())["status"] == "partial"
