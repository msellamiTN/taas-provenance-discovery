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
    with pytest.raises(ValueError, match="facet column"):
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
    frame = pd.DataFrame({"source": ["observed"], "target": ["invalidated"], "value": [-1]})
    with pytest.raises(ValueError, match="non-negative"):
        validate_figure_data(figure, frame)


def test_unknown_experiment_filter_is_rejected():
    plan = load_plot_plan(ROOT / "docs/experiment_design/pamcp_plot_plan_v1.json")
    with pytest.raises(ValueError, match="Unknown experiment"):
        list(iter_figures(plan, "E99"))
