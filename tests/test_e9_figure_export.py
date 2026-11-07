from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd
import pytest

from experiments.export_e9_figures import export_e9_figures
from taas.experiments.plotting import iter_figures, load_plot_plan, render_figure, validate_figure_data

ROOT = Path(__file__).resolve().parents[1]
REGISTERED = [
    "rag_mcp", "mcp_zero", "per_subtask", "colt_adapted",
    "toolscope_adapted", "cmtf_adapted", "all_tools",
]


def _build_run(root: Path) -> Path:
    (root / "discovery").mkdir(parents=True)
    (root / "evaluator").mkdir()
    ranking_rows = []
    visible = ["provider::a", "provider::b", "provider::c"]
    task_data = [
        ("task-1", "Office", "cluster-a", ["provider::a", "provider::b", "provider::c"]),
        ("task-2", "Travel", "cluster-b", ["provider::b", "provider::a", "provider::c"]),
        ("task-3", "Travel", "cluster-b", ["provider::a", "provider::b", "provider::c"]),
        ("task-4", "Office", "cluster-c", ["provider::a", "provider::b", "provider::c"]),
    ]
    for baseline in ("Full_PaMCP", "all_tools", "rag_mcp"):
        for task_id, task_group, _cluster, ranked in task_data:
            ranking_rows.append({
                "task_id": task_id,
                "benchmark": "live_mcpbench_test",
                "baseline": baseline,
                "task_group": task_group,
                "ranked_tool_ids": ranked,
                "visible_tool_ids": visible,
            })
    (root / "discovery" / "rankings.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in ranking_rows), encoding="utf-8"
    )

    refs = [
        {
            "task_id": "task-1", "benchmark": "live_mcpbench_test",
            "reference_semantics": "independently_adjudicated_acceptable_sets",
            "acceptable_tool_sets": [["provider::a", "provider::b"], ["provider::a", "provider::c"]],
            "independent_unit_id": "cluster-a", "source_revision": "fixture",
        },
        {
            "task_id": "task-2", "benchmark": "live_mcpbench_test",
            "reference_semantics": "benchmark_native_acceptable_sets",
            "acceptable_tool_sets": [["provider::b", "provider::c"]],
            "independent_unit_id": "cluster-b", "source_revision": "fixture",
        },
        {
            "task_id": "task-3", "benchmark": "live_mcpbench_test",
            "reference_semantics": "annotated_trace_only",
            "reference_trace_tool_ids": ["provider::a", "provider::b"],
            "independent_unit_id": "cluster-b", "source_revision": "fixture",
        },
        {
            "task_id": "task-4", "benchmark": "live_mcpbench_test",
            "reference_semantics": "independently_adjudicated_acceptable_sets",
            "acceptable_tool_sets": [["provider::a"]],
            "independent_unit_id": "cluster-c", "source_revision": "fixture",
        },
    ]
    (root / "evaluator" / "task_references.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in refs), encoding="utf-8"
    )
    manifest = {
        "experiment_id": "E9",
        "run_id": "E9-test",
        "status": "partial",
        "baseline_ids_registered": REGISTERED,
        "baseline_ids_executed": ["all_tools", "rag_mcp"],
        "primary_configuration_id": "Full_PaMCP",
        "primary_configuration_executed": True,
        "ranking_cutoffs": [1, 3, 5],
    }
    (root / "MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return root


def _figure(figure_id: str):
    plan = load_plot_plan(ROOT / "docs/experiment_design/pamcp_plot_plan_v1.json")
    return next(figure for figure in iter_figures(plan, "E9") if figure["id"] == figure_id)


def test_e9_export_uses_only_acceptable_set_references_and_renders(tmp_path):
    run_dir = _build_run(tmp_path / "run")
    output = tmp_path / "visualization" / "data"
    figures = tmp_path / "visualization" / "figures"
    result = export_e9_figures(run_dir, output, bootstrap_resamples=200, seed=42)

    assert result["source_run_status"] == "partial"
    assert result["figures_exported"] == ["E9-F1", "E9-F2", "E9-F3"]
    assert result["primary_task_metric_rows"] == 27
    assert result["trace_diagnostic_rows"] == 9
    assert result["primary_configuration_executed"] is True
    assert result["primary_configuration_rows"] == 3
    assert result["primary_tasks_without_acceptable_set_reference"] == 2

    f1 = pd.read_csv(output / "E9-F1.csv")
    f2 = pd.read_csv(output / "E9-F2.csv")
    f3 = pd.read_csv(output / "E9-F3.csv")
    assert set(f1["benchmark"]) == {"live_mcpbench_test"}
    assert set(f1["category"]) == {"Full_PaMCP", "all_tools", "rag_mcp"}
    assert set(f1["series"]) == {"Group recall@1", "Group recall@3", "Group recall@5"}
    assert ((f1["ci_low"] <= f1["value"]) & (f1["value"] <= f1["ci_high"])).all()
    assert set(f2["series"]) == {"@1", "@3", "@5"}
    assert set(f2["label"]) == {"Full_PaMCP", "all_tools", "rag_mcp"}
    assert set(f3["task_group"]) == {"Office", "Travel"}
    assert not f3.empty

    for figure_id, frame in [("E9-F1", f1), ("E9-F2", f2), ("E9-F3", f3)]:
        figure = _figure(figure_id)
        validate_figure_data(figure, frame)
        outputs = render_figure(figure, frame, figures, formats=("png",), dpi=90)
        assert outputs[0].is_file()
        assert outputs[0].stat().st_size > 1000

    # Test fixture values are isolated in tmp_path; no experiment result is created.
    assert (run_dir / "MANIFEST.json").is_file()


def test_e9_rejects_evaluator_leakage_in_discovery_rankings(tmp_path):
    run_dir = _build_run(tmp_path / "run")
    path = run_dir / "discovery" / "rankings.jsonl"
    rows = [json.loads(x) for x in path.read_text().splitlines()]
    rows[0]["acceptable_tool_sets"] = [["provider::a"]]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    with pytest.raises(ValueError, match="evaluator-only"):
        export_e9_figures(run_dir, tmp_path / "out", bootstrap_resamples=150)


def test_e9_rejects_reference_tools_outside_task_visibility(tmp_path):
    run_dir = _build_run(tmp_path / "run")
    path = run_dir / "evaluator" / "task_references.jsonl"
    refs = [json.loads(x) for x in path.read_text().splitlines()]
    refs[0]["acceptable_tool_sets"] = [["provider::not-visible"]]
    path.write_text("".join(json.dumps(row) + "\n" for row in refs))
    with pytest.raises(ValueError, match="outside the task visibility"):
        export_e9_figures(run_dir, tmp_path / "out", bootstrap_resamples=150)


def test_e9_does_not_promote_trace_only_data_to_primary_metrics(tmp_path):
    run_dir = _build_run(tmp_path / "run")
    path = run_dir / "evaluator" / "task_references.jsonl"
    refs = [json.loads(x) for x in path.read_text().splitlines()]
    for row in refs:
        row["reference_semantics"] = "mcp_atlas_trajectory_diagnostic"
        row["reference_trace_tool_ids"] = ["provider::a", "provider::b"]
        row.pop("acceptable_tool_sets", None)
    path.write_text("".join(json.dumps(row) + "\n" for row in refs))
    with pytest.raises(ValueError, match="no primary E9 metrics"):
        export_e9_figures(run_dir, tmp_path / "out", bootstrap_resamples=150)
