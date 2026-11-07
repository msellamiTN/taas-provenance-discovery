from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from taas.experiments.plotting import (
    create_csv_templates,
    iter_figures,
    load_plot_plan,
    render_figure,
    validate_figure_data,
    validate_plot_plan,
)

ROOT = Path(__file__).resolve().parents[1]


def _figure(figure_id: str):
    plan = load_plot_plan(ROOT / "docs/experiment_design/pamcp_plot_plan_v1.json")
    return next(item for item in iter_figures(plan) if item["id"] == figure_id)


def test_plot_plan_covers_all_experiments_and_matches_frozen_baselines():
    result = validate_plot_plan(
        ROOT / "docs/experiment_design/pamcp_plot_plan_v1.json",
        ROOT / "docs/experiment_design/pamcp_experiments_v1.json",
        ROOT / "docs/experiment_design/pamcp_baselines_v1.json",
    )
    assert result["valid"] is True
    assert result["experiments"] == 22
    assert result["figures"] == 80


def test_e18_contains_all_eight_factorial_cells():
    figure = _figure("E18-F1")
    assert set(figure["comparison"]["factorial_cells"]) == {
        "Full_PaMCP", "PaMCP_NoCert", "PaMCP_Declared", "G1_P0_S0",
        "PaMCP_NoGap", "G0_P1_S0", "G0_P0_S1", "G0_P0_S0",
    }


def test_csv_templates_are_header_only(tmp_path):
    plan = load_plot_plan(ROOT / "docs/experiment_design/pamcp_plot_plan_v1.json")
    created = create_csv_templates(tmp_path, plan=plan)
    assert len(created) == 80
    for path in created:
        lines = path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1
        assert lines[0].strip()


def test_forest_data_requires_valid_confidence_interval():
    figure = _figure("E2-F2")
    valid = pd.DataFrame({
        "category": ["structural"],
        "value": [0.8],
        "ci_low": [0.7],
        "ci_high": [0.9],
        "series": ["macro_f1"],
    })
    assert validate_figure_data(figure, valid)["rows"] == 1

    invalid = valid.copy()
    invalid.loc[0, "ci_low"] = 0.85
    with pytest.raises(ValueError, match="lies outside"):
        validate_figure_data(figure, invalid)


def test_requested_facet_must_be_present():
    figure = _figure("E4-F3")
    figure["data_contract"]["required_columns"] = ["category", "series", "value"]
    frame = pd.DataFrame({"category": ["policy"], "series": ["Exp@5"], "value": [0.1]})
    with pytest.raises(ValueError, match="missing CSV columns"):
        validate_figure_data(figure, frame)


def test_pareto_scatter_renders_without_numpy_size_truth_ambiguity(tmp_path):
    figure = _figure("E4-F1")
    frame = pd.DataFrame({
        "util_at_5": [0.8, 0.9],
        "exp_at_5": [0.12, 0.08],
        "series": ["Full_PaMCP", "mcp_default_annotations"],
        "eligible_share": [0.35, 0.55],
        "benchmark": ["MCPToolBench++", "MCPToolBench++"],
    })
    output = render_figure(figure, frame, tmp_path, formats=("png",), dpi=100)
    assert len(output) == 1
    assert output[0].is_file()
    assert output[0].stat().st_size > 1000


def test_heatmap_renders_categorical_axes(tmp_path):
    figure = _figure("E1-F2")
    frame = pd.DataFrame({
        "metadata_field": ["description", "description", "annotations", "annotations"],
        "server": ["srv-a", "srv-b", "srv-a", "srv-b"],
        "value": [0.8, 0.6, 0.5, 0.9],
    })
    output = render_figure(figure, frame, tmp_path, formats=("svg",), dpi=100)
    assert output[0].is_file()
    assert output[0].stat().st_size > 1000


def test_alluvial_requires_nonnegative_flows():
    figure = _figure("E16-F4")
    frame = pd.DataFrame({"source": ["observed"], "target": ["invalidated"], "value": [-1], "benchmark": ["event-replay"]})
    with pytest.raises(ValueError, match="non-negative"):
        validate_figure_data(figure, frame)


def test_unknown_experiment_filter_is_rejected():
    plan = load_plot_plan(ROOT / "docs/experiment_design/pamcp_plot_plan_v1.json")
    with pytest.raises(ValueError, match="Unknown experiment"):
        list(iter_figures(plan, "E99"))


def test_renderer_smoke_covers_all_chart_families(tmp_path):
    # Synthetic rows below are renderer fixtures only. They are never written to
    # results/visualization/data and are not experimental observations.
    fixtures = {
        "E1-F1": pd.DataFrame({
            "registry": ["reg-a", "reg-a", "reg-b", "reg-b"],
            "category": ["read", "write", "read", "write"],
            "value": [8, 3, 6, 5],
        }),
        "E1-F3": pd.DataFrame({
            "registry": ["reg-a", "reg-a", "reg-b", "reg-b"],
            "series": ["read", "write", "read", "write"],
            "value": [8, 3, 6, 5],
        }),
        "E2-F1": pd.DataFrame({
            "actual": ["read", "read", "write", "write"],
            "predicted": ["read", "write", "read", "write"],
            "count": [8, 1, 2, 7],
        }),
        "E2-F2": pd.DataFrame({
            "category": ["structural", "LLM"],
            "value": [0.7, 0.85],
            "ci_low": [0.6, 0.78],
            "ci_high": [0.8, 0.92],
            "series": ["macro_f1", "macro_f1"],
        }),
        "E2-F3": pd.DataFrame({
            "threshold": [0.3, 0.6, 0.9],
            "value": [0.65, 0.78, 0.82],
            "series": ["LLM", "LLM", "LLM"],
        }),
        "E4-F1": pd.DataFrame({
            "util_at_5": [0.8, 0.9],
            "exp_at_5": [0.15, 0.07],
            "series": ["Full_PaMCP", "control"],
            "eligible_share": [0.4, 0.6],
            "benchmark": ["native", "native"],
        }),
        "E4-F2": pd.DataFrame({
            "category": ["annotation", "lexical"],
            "reference": [0.5, 0.4],
            "candidate": [0.2, 0.25],
        }),
        "E4-F3": pd.DataFrame({
            "category": ["PaMCP", "control"],
            "series": ["Full", "control"],
            "value": [0.08, 0.3],
            "metric": ["Exp@5", "Exp@5"],
            "benchmark": ["native", "native"],
        }),
        "E10-F3": pd.DataFrame({
            "category": ["PaMCP", "baseline", "baseline"],
            "segment": ["interface", "interface", "flow"],
            "value": [2, 3, 1],
        }),
        "E11-F1": pd.DataFrame({
            "input_size": [10, 20, 40],
            "value": [2, 3, 5],
            "series": ["Full_PaMCP"] * 3,
            "benchmark": ["review-tasks"] * 3,
        }),
        "E11-F3": pd.DataFrame({
            "tau": [0.2, 0.5, 0.8],
            "value": [5, 4, 3],
            "series": ["calibrated"] * 3,
        }),
        "E12-F2": pd.DataFrame({
            "claimed": [0.3, 0.7, 0.9],
            "measured": [0.25, 0.65, 0.82],
            "ci_low": [0.20, 0.60, 0.78],
            "ci_high": [0.30, 0.70, 0.86],
            "series": ["model-a"] * 3,
        }),
        "E13-F3": pd.DataFrame({
            "group": ["PaMCP"] * 3 + ["baseline"] * 3,
            "value": [2, 3, 4, 4, 5, 6],
            "benchmark": ["Toolathlon-Verified"] * 6,
        }),
        "E15-F1": pd.DataFrame({
            "registry_size": [100, 1000, 10000],
            "latency_ms": [1, 4, 18],
            "series": ["PaMCP"] * 3,
            "benchmark": ["synthetic-registry"] * 3,
        }),
        "E16-F4": pd.DataFrame({
            "source": ["observed", "observed", "attested"],
            "target": ["retained", "invalidated", "retained"],
            "value": [6, 2, 3],
            "benchmark": ["mutation-replay"] * 3,
        }),
        "E18-F1": pd.DataFrame({
            "metric": ["success", "success"],
            "configuration": ["Full_PaMCP", "PaMCP_NoGap"],
            "value": [0.8, 0.7],
            "benchmark": ["LiveMCPBench", "LiveMCPBench"],
        }),
        "E22-F3": pd.DataFrame({
            "rank": [1, 2, 3, 1, 2, 3],
            "probability": [0.7, 0.2, 0.1, 0.3, 0.4, 0.3],
            "series": ["PaMCP"] * 3 + ["baseline"] * 3,
            "benchmark": ["tool-disjoint"] * 6,
        }),
        "E22-F4": pd.DataFrame({
            "effect": [0.15, -0.04],
            "adjusted_p": [0.02, 0.4],
            "series": ["baseline-a", "baseline-b"],
            "benchmark": ["tool-disjoint", "tool-disjoint"],
        }),
    }
    for figure_id, frame in fixtures.items():
        figure = _figure(figure_id)
        rendered = render_figure(figure, frame, tmp_path, formats=("png",), dpi=80)
        assert len(rendered) == 1
        assert rendered[0].is_file(), figure_id


def test_multi_field_facets_render_independent_panels(tmp_path):
    figure = _figure("E4-F3")
    frame = pd.DataFrame({
        "category": ["PaMCP", "baseline", "PaMCP", "baseline"],
        "series": ["Full", "control", "Full", "control"],
        "value": [0.08, 0.3, 0.09, 0.28],
        "metric": ["Exp@5", "Exp@5", "Util@5", "Util@5"],
        "benchmark": ["MCPToolBench++"] * 4,
    })
    outputs = render_figure(figure, frame, tmp_path, formats=("png",), dpi=80)
    assert len(outputs) == 1
    assert outputs[0].is_file()
    assert outputs[0].stat().st_size > 1000
