"""Publication-grade plotting for the frozen PaMCP E1-E22 study.

The plotting layer consumes one CSV per figure contract. It never creates observations,
never imports evaluator labels, and never changes experiment status or protocol metadata.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[3]
PLOT_PLAN_PATH = ROOT / "docs" / "experiment_design" / "pamcp_plot_plan_v1.json"
EXPERIMENT_CATALOG_PATH = ROOT / "docs" / "experiment_design" / "pamcp_experiments_v1.json"
BASELINE_CATALOG_PATH = ROOT / "docs" / "experiment_design" / "pamcp_baselines_v1.json"

SUPPORTED_CHARTS = {
    "grouped_bar", "stacked_bar", "heatmap", "confusion_matrix",
    "horizontal_forest", "grouped_dot", "dose_response", "line",
    "pareto_scatter", "dumbbell", "stacked_horizontal", "violin",
    "alluvial", "interaction_plot", "calibration_scatter", "rankogram",
    "loglog_scaling", "scatter", "significance_scatter", "factorial_heatmap",
}
NUMERIC_FIELDS_BY_CHART = {
    "grouped_bar": ("value",), "stacked_bar": ("value",),
    "heatmap": ("value",), "factorial_heatmap": ("value",),
    "confusion_matrix": ("count",), "horizontal_forest": ("value", "ci_low", "ci_high"),
    "grouped_dot": ("value",), "dose_response": ("x", "value"),
    "line": ("x", "value"), "pareto_scatter": ("x", "y"),
    "dumbbell": ("reference", "candidate"), "stacked_horizontal": ("value",),
    "violin": ("value",), "alluvial": ("value",),
    "interaction_plot": ("x", "value"), "calibration_scatter": ("claimed", "measured"),
    "rankogram": ("rank", "probability"), "loglog_scaling": ("x", "y"),
    "scatter": ("x", "y"), "significance_scatter": ("effect", "adjusted_p"),
}
CHART_ALIASES = {"factorial_heatmap": "heatmap"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_plot_plan(path: Path = PLOT_PLAN_PATH) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Plot plan not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def validate_plot_plan(
    plan_path: Path = PLOT_PLAN_PATH,
    experiment_path: Path = EXPERIMENT_CATALOG_PATH,
    baseline_path: Path = BASELINE_CATALOG_PATH,
) -> dict[str, Any]:
    """Check figure coverage and ensure comparisons match frozen protocol assignments."""
    plan = load_plot_plan(plan_path)
    experiments = json.loads(experiment_path.read_text(encoding="utf-8"))["experiments"]
    baselines = json.loads(baseline_path.read_text(encoding="utf-8"))["baselines"]
    expected_ids = [f"E{i}" for i in range(1, 23)]
    protocol_by_id = {item["id"]: item for item in experiments}
    baseline_ids = {item["id"] for item in baselines}

    if plan.get("schema_version") != "1.0.0":
        raise ValueError("Unsupported plotting-plan schema version")
    planned = plan.get("experiments", [])
    if [item.get("id") for item in planned] != expected_ids:
        raise ValueError("Plot plan must contain E1-E22 in protocol order")

    seen_figures: set[str] = set()
    figure_count = 0
    for experiment in planned:
        exp_id = experiment["id"]
        protocol_item = protocol_by_id.get(exp_id)
        if protocol_item is None:
            raise ValueError(f"Unknown experiment in plot plan: {exp_id}")
        if not experiment.get("figures"):
            raise ValueError(f"{exp_id} has no figure specifications")
        if experiment.get("protocol_metrics") != protocol_item.get("metrics"):
            raise ValueError(f"{exp_id} metrics differ from frozen protocol")
        assigned = set(protocol_item.get("baseline_ids", []))
        for figure in experiment["figures"]:
            figure_id = figure.get("id", "")
            if not figure_id or figure_id in seen_figures:
                raise ValueError(f"Missing or duplicate figure id: {figure_id!r}")
            seen_figures.add(figure_id)
            figure_count += 1
            chart = figure.get("chart_type")
            if chart not in SUPPORTED_CHARTS:
                raise ValueError(f"{figure_id}: unsupported chart type {chart!r}")
            required = figure.get("data_contract", {}).get("required_columns", [])
            if len(required) != len(set(required)):
                raise ValueError(f"{figure_id}: duplicate required CSV columns")
            if not required:
                raise ValueError(f"{figure_id}: no required CSV columns")
            for axis in ("x_axis", "y_axis"):
                axis_field = figure.get(axis, {}).get("field")
                if axis_field and axis_field not in required:
                    # Dumbbell and alluvial use two plotted measures/flow columns.
                    if chart not in {"dumbbell", "alluvial"}:
                        raise ValueError(f"{figure_id}: {axis_field!r} missing from required columns")
            if chart == "horizontal_forest" and not {"ci_low", "ci_high"}.issubset(required):
                raise ValueError(f"{figure_id}: forest plot requires ci_low and ci_high")
            used = set(figure.get("comparison", {}).get("baseline_ids", []))
            unknown = used - baseline_ids
            unassigned = used - assigned
            if unknown:
                raise ValueError(f"{figure_id}: unknown baseline ids {sorted(unknown)}")
            if unassigned:
                raise ValueError(f"{figure_id}: baselines not assigned to {exp_id}: {sorted(unassigned)}")
            if exp_id == "E18":
                expected_factorial = {
                    "Full_PaMCP", "PaMCP_NoCert", "PaMCP_Declared", "G1_P0_S0",
                    "PaMCP_NoGap", "G0_P1_S0", "G0_P0_S1", "G0_P0_S0",
                }
                cells = set(figure.get("comparison", {}).get("factorial_cells", []))
                if cells != expected_factorial:
                    raise ValueError(f"{figure_id}: incomplete E18 factorial comparison")
    return {
        "valid": True,
        "experiments": len(planned),
        "figures": figure_count,
        "chart_types": sorted({f["chart_type"] for e in planned for f in e["figures"]}),
        "plot_plan_sha256": _sha256(plan_path),
    }


def iter_figures(plan: dict[str, Any], experiment_id: str | None = None) -> Iterable[dict[str, Any]]:
    for experiment in plan["experiments"]:
        if experiment_id is None or experiment["id"] == experiment_id.upper():
            for figure in experiment["figures"]:
                yield figure


def create_csv_templates(
    input_dir: Path,
    plan: dict[str, Any] | None = None,
    overwrite: bool = False,
) -> list[Path]:
    """Create header-only CSV templates. No example observations are inserted."""
    plan = plan or load_plot_plan()
    created: list[Path] = []
    input_dir.mkdir(parents=True, exist_ok=True)
    for figure in iter_figures(plan):
        path = input_dir / f'{figure["id"]}.csv'
        if path.exists() and not overwrite:
            continue
        columns = list(figure["data_contract"]["required_columns"])
        with path.open("w", encoding="utf-8", newline="") as stream:
            csv.writer(stream).writerow(columns)
        created.append(path)
    return created


def _numeric_columns(figure: dict[str, Any]) -> set[str]:
    chart = figure["chart_type"]
    columns = set(NUMERIC_FIELDS_BY_CHART[chart])
    columns.add(figure.get("value_field", "value"))
    categorical_axes = {
        "grouped_bar": {"x_axis"},
        "stacked_bar": {"x_axis"},
        "heatmap": set(),
        "factorial_heatmap": set(),
        "confusion_matrix": {"x_axis", "y_axis"},
        "horizontal_forest": {"y_axis"},
        "grouped_dot": {"y_axis"},
        "dose_response": set(),
        "line": set(),
        "pareto_scatter": set(),
        "dumbbell": {"y_axis"},
        "stacked_horizontal": {"y_axis"},
        "violin": {"x_axis"},
        "alluvial": {"x_axis", "y_axis"},
        "interaction_plot": set(),
        "calibration_scatter": set(),
        "rankogram": set(),
        "loglog_scaling": set(),
        "scatter": set(),
        "significance_scatter": set(),
    }
    for axis in ("x_axis", "y_axis"):
        if axis not in categorical_axes.get(chart, set()):
            field = figure.get(axis, {}).get("field")
            if field:
                columns.add(field)
    options = figure.get("render_options", {})
    size_field = options.get("size_field")
    if size_field:
        columns.add(size_field)
    if chart == "dumbbell":
        columns.update(("reference", "candidate"))
    if chart == "alluvial":
        columns.add("value")
    return columns


def validate_figure_data(figure: dict[str, Any], frame: Any) -> dict[str, Any]:
    """Validate CSV shape and numeric constraints before plotting."""
    required = figure["data_contract"]["required_columns"]
    missing = sorted(set(required) - set(frame.columns))
    if missing:
        raise ValueError(f'{figure["id"]}: missing CSV columns {missing}')
    if frame.empty:
        raise ValueError(f'{figure["id"]}: CSV contains a header but no observations')
    for column in required:
        if frame[column].isna().any() or (frame[column].astype(str).str.strip() == "").any():
            raise ValueError(f'{figure["id"]}: missing values in required column {column!r}')

    numeric = _numeric_columns(figure)
    for column in numeric.intersection(frame.columns):
        converted = __import__("pandas").to_numeric(frame[column], errors="coerce")
        if converted.isna().any() or not converted.map(math.isfinite).all():
            raise ValueError(f'{figure["id"]}: column {column!r} must contain finite numeric values')

    if {"ci_low", "ci_high", "value"}.issubset(frame.columns):
        low = frame["ci_low"].astype(float)
        high = frame["ci_high"].astype(float)
        value = frame["value"].astype(float)
        if (low > high).any():
            raise ValueError(f'{figure["id"]}: ci_low exceeds ci_high')
        if ((value < low) | (value > high)).any():
            raise ValueError(f'{figure["id"]}: point estimate lies outside its confidence interval')
    if figure["chart_type"] == "alluvial" and (frame["value"].astype(float) < 0).any():
        raise ValueError(f'{figure["id"]}: alluvial flow values must be non-negative')
    if figure["chart_type"] == "confusion_matrix" and (frame[figure.get("value_field", "count")].astype(float) < 0).any():
        raise ValueError(f'{figure["id"]}: confusion counts must be non-negative')
    return {"rows": int(len(frame)), "columns": list(frame.columns)}


def _series_field(frame: Any, options: dict[str, Any]) -> str | None:
    candidate = options.get("series_field", "series")
    return candidate if candidate in frame.columns else None


def _groups(frame: Any, field: str | None) -> list[tuple[str, Any]]:
    if field is None:
        return [("All observations", frame)]
    return [(str(value), subset) for value, subset in frame.groupby(field, sort=False, dropna=False)]


def _apply_axis_options(ax: Any, figure: dict[str, Any]) -> None:
    options = figure.get("render_options", {})
    for axis_name, attr in (("x_axis", "set_xlabel"), ("y_axis", "set_ylabel")):
        getattr(ax, attr)(figure[axis_name]["label"])
    if options.get("log_x"):
        ax.set_xscale("log")
    if options.get("log_y"):
        ax.set_yscale("log")
    if "x_min" in options or "x_max" in options:
        ax.set_xlim(options.get("x_min"), options.get("x_max"))
    if "y_min" in options or "y_max" in options:
        ax.set_ylim(options.get("y_min"), options.get("y_max"))
    if options.get("x_format") == "percent" or options.get("y_format") == "percent":
        from matplotlib.ticker import PercentFormatter
        if options.get("x_format") == "percent":
            ax.xaxis.set_major_formatter(PercentFormatter(1.0))
        if options.get("y_format") == "percent":
            ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    if options.get("zero_reference"):
        if figure["chart_type"] == "horizontal_forest":
            ax.axvline(0, color="0.35", linewidth=1, linestyle="--", zorder=0)
    for value in options.get("reference_y", []):
        ax.axhline(value, color="0.45", linewidth=0.9, linestyle="--", zorder=0)


def _draw(ax: Any, figure: dict[str, Any], frame: Any) -> None:
    import numpy as np
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch, PathPatch
    from matplotlib.path import Path as MplPath

    chart = figure["chart_type"]
    options = figure.get("render_options", {})
    x_field = figure["x_axis"]["field"]
    y_field = figure["y_axis"]["field"]
    value_field = figure.get("value_field", "value")
    series_field = _series_field(frame, options)

    if chart == "grouped_bar":
        groups = _groups(frame, options.get("series_field") or series_field)
        categories = list(dict.fromkeys(frame[x_field].astype(str)))
        y = np.arange(len(categories))
        height = 0.82 / max(1, len(groups))
        for index, (label, subset) in enumerate(groups):
            indexed = subset.set_index(x_field)
            values = indexed[y_field].astype(float).reindex(categories)
            offset = (index - (len(groups) - 1) / 2) * height
            if options.get("orientation") == "horizontal":
                positions = y + offset
                ax.barh(positions, values.values, height=height * 0.9, label=label)
                if {"ci_low", "ci_high"}.issubset(subset.columns):
                    low = indexed["ci_low"].astype(float).reindex(categories)
                    high = indexed["ci_high"].astype(float).reindex(categories)
                    ax.errorbar(values, positions, xerr=np.vstack([values-low, high-values]), fmt="none", ecolor="0.2", capsize=2)
            else:
                positions = np.arange(len(categories)) + offset
                ax.bar(positions, values.values, width=height * 0.9, label=label)
                if {"ci_low", "ci_high"}.issubset(subset.columns):
                    low = indexed["ci_low"].astype(float).reindex(categories)
                    high = indexed["ci_high"].astype(float).reindex(categories)
                    ax.errorbar(positions, values, yerr=np.vstack([values-low, high-values]), fmt="none", ecolor="0.2", capsize=2)
        if options.get("orientation") == "horizontal":
            ax.set_yticks(y, categories)
        else:
            ax.set_xticks(np.arange(len(categories)), categories, rotation=25, ha="right")
    elif chart == "stacked_bar":
        pivot = frame.pivot(index=x_field, columns=series_field or "series", values=y_field)
        if options.get("normalize"):
            pivot = pivot.div(pivot.sum(axis=1).replace(0, np.nan), axis=0).fillna(0)
        pivot.plot(kind="bar", stacked=True, ax=ax, width=0.82)
        ax.tick_params(axis="x", rotation=25)
    elif chart in {"heatmap", "factorial_heatmap", "confusion_matrix"}:
        if chart == "confusion_matrix":
            value = figure.get("value_field", "count")
            matrix = frame.pivot(index=y_field, columns=x_field, values=value).fillna(0)
            if options.get("normalize") == "true":
                matrix = matrix.div(matrix.sum(axis=1).replace(0, np.nan), axis=0).fillna(0)
        else:
            matrix = frame.pivot(index=y_field, columns=x_field, values=value_field)
        image = ax.imshow(matrix.values.astype(float), aspect="auto", interpolation="nearest",
                          vmin=options.get("vmin", options.get("x_min")), vmax=options.get("vmax", options.get("x_max")))
        ax.set_xticks(np.arange(len(matrix.columns)), [str(x) for x in matrix.columns], rotation=35, ha="right")
        ax.set_yticks(np.arange(len(matrix.index)), [str(x) for x in matrix.index])
        for row in range(matrix.shape[0]):
            for col in range(matrix.shape[1]):
                value = matrix.iloc[row, col]
                if not np.isnan(value):
                    label = f"{value:.2f}" if chart == "confusion_matrix" and options.get("normalize") == "true" else f"{value:g}"
                    ax.text(col, row, label, ha="center", va="center", fontsize=8)
        plt.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    elif chart in {"horizontal_forest", "grouped_dot"}:
        categories = list(dict.fromkeys(frame[figure["y_axis"]["field"]].astype(str)))
        groups = _groups(frame, series_field)
        offsets = np.linspace(-0.22, 0.22, len(groups)) if len(groups) > 1 else [0.0]
        positions = np.arange(len(categories))
        for offset, (label, subset) in zip(offsets, groups):
            indexed = subset.set_index(figure["y_axis"]["field"])
            values = indexed[figure["x_axis"]["field"]].astype(float).reindex(categories)
            ypos = positions + offset
            if chart == "horizontal_forest":
                low = indexed["ci_low"].astype(float).reindex(categories)
                high = indexed["ci_high"].astype(float).reindex(categories)
                xerr = np.vstack([values - low, high - values])
                ax.errorbar(values, ypos, xerr=xerr, fmt="o", capsize=3, markersize=5, label=label)
            elif {"ci_low", "ci_high"}.issubset(subset.columns):
                low = indexed["ci_low"].astype(float).reindex(categories)
                high = indexed["ci_high"].astype(float).reindex(categories)
                ax.errorbar(values, ypos, xerr=np.vstack([values-low, high-values]), fmt="o", capsize=3, label=label)
            else:
                ax.scatter(values, ypos, label=label, s=34)
        ax.set_yticks(positions, categories)
        ax.invert_yaxis()
    elif chart in {"dose_response", "line", "interaction_plot", "loglog_scaling"}:
        groups = _groups(frame, series_field)
        for label, subset in groups:
            subset = subset.sort_values(x_field)
            x = subset[x_field].astype(float).to_numpy()
            y = subset[y_field].astype(float).to_numpy()
            ax.plot(x, y, marker="o", linewidth=1.8, markersize=4, label=label)
            if {"ci_low", "ci_high"}.issubset(subset.columns):
                ax.fill_between(x, subset["ci_low"].astype(float), subset["ci_high"].astype(float), alpha=0.16)
    elif chart in {"pareto_scatter", "scatter", "significance_scatter"}:
        groups = _groups(frame, series_field)
        size_field = options.get("size_field")
        for label, subset in groups:
            sizes = None
            if size_field and size_field in subset.columns:
                raw = subset[size_field].astype(float).to_numpy()
                span = raw.max() - raw.min()
                sizes = 35 + (raw - raw.min()) / (span if span else 1) * 125
            ax.scatter(subset[x_field].astype(float), subset[y_field].astype(float), s=48 if sizes is None else sizes, alpha=0.82, label=label)
            if "label" in subset.columns:
                for _, row in subset.iterrows():
                    ax.annotate(str(row["label"]), (float(row[x_field]), float(row[y_field])), xytext=(4, 3), textcoords="offset points", fontsize=7)
    elif chart == "dumbbell":
        cat = figure["y_axis"]["field"]
        categories = list(dict.fromkeys(frame[cat].astype(str)))
        positions = np.arange(len(categories))
        reference = frame.set_index(cat)["reference"].astype(float).reindex(categories)
        candidate = frame.set_index(cat)["candidate"].astype(float).reindex(categories)
        for y, a, b in zip(positions, reference, candidate):
            ax.plot([a, b], [y, y], color="0.65", linewidth=2, zorder=1)
        ax.scatter(reference, positions, marker="o", label="Reference", zorder=2)
        ax.scatter(candidate, positions, marker="D", label="Candidate", zorder=3)
        ax.set_yticks(positions, categories)
        ax.invert_yaxis()
    elif chart == "stacked_horizontal":
        pivot = frame.pivot(index=figure["y_axis"]["field"], columns="segment", values=value_field).fillna(0)
        if options.get("normalize"):
            pivot = pivot.div(pivot.sum(axis=1).replace(0, np.nan), axis=0).fillna(0)
        pivot.plot(kind="barh", stacked=True, ax=ax, width=0.78)
    elif chart == "violin":
        groups = _groups(frame, figure["x_axis"]["field"])
        data = [subset[y_field].astype(float).to_numpy() for _, subset in groups]
        positions = np.arange(1, len(groups) + 1)
        if all(len(values) >= 2 for values in data):
            ax.violinplot(data, positions=positions, showmeans=False, showmedians=True, showextrema=True)
        else:
            ax.boxplot(data, positions=positions, showfliers=False)
        ax.set_xticks(positions, [label for label, _ in groups], rotation=25, ha="right")
    elif chart == "alluvial":
        sources = list(dict.fromkeys(frame["source"].astype(str)))
        targets = list(dict.fromkeys(frame["target"].astype(str)))
        edges = [(str(row["source"]), str(row["target"]), float(row["value"])) for _, row in frame.iterrows()]
        total = sum(value for _, _, value in edges)
        if total <= 0:
            raise ValueError(f'{figure["id"]}: alluvial total flow must be positive')
        left_totals = {key: sum(v for s, _, v in edges if s == key) for key in sources}
        right_totals = {key: sum(v for _, t, v in edges if t == key) for key in targets}
        scale = 0.82 / max(max(left_totals.values()), max(right_totals.values()))
        left_y, right_y = {}, {}
        cursor = 0.08
        for key in sources:
            height = left_totals[key] * scale
            left_y[key] = [cursor, cursor + height]
            cursor += height + 0.035
        cursor = 0.08
        for key in targets:
            height = right_totals[key] * scale
            right_y[key] = [cursor, cursor + height]
            cursor += height + 0.035
        left_offset, right_offset = {k: 0.0 for k in sources}, {k: 0.0 for k in targets}
        for source, target, value in edges:
            h = value * scale
            y0 = left_y[source][0] + left_offset[source]
            y1 = right_y[target][0] + right_offset[target]
            left_offset[source] += h
            right_offset[target] += h
            verts = [(0.12, y0), (0.48, y0), (0.52, y1), (0.88, y1),
                     (0.88, y1 + h), (0.52, y1 + h), (0.48, y0 + h), (0.12, y0 + h), (0.12, y0)]
            codes = [MplPath.MOVETO, MplPath.CURVE4, MplPath.CURVE4, MplPath.CURVE4,
                     MplPath.LINETO, MplPath.CURVE4, MplPath.CURVE4, MplPath.CURVE4, MplPath.CLOSEPOLY]
            ax.add_patch(PathPatch(MplPath(verts, codes), facecolor="C0", edgecolor="none", alpha=0.22))
        for key, (low, high) in left_y.items():
            ax.add_patch(FancyBboxPatch((0.06, low), 0.06, high-low, boxstyle="round,pad=0.004", facecolor="C0", alpha=0.85))
            ax.text(0.045, (low+high)/2, key, ha="right", va="center", fontsize=8)
        for key, (low, high) in right_y.items():
            ax.add_patch(FancyBboxPatch((0.88, low), 0.06, high-low, boxstyle="round,pad=0.004", facecolor="C1", alpha=0.85))
            ax.text(0.955, (low+high)/2, key, ha="left", va="center", fontsize=8)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_xticks([0.09, 0.91], [figure["x_axis"]["label"], figure["y_axis"]["label"]])
        ax.set_yticks([])
    elif chart == "calibration_scatter":
        groups = _groups(frame, series_field)
        for label, subset in groups:
            x = subset["claimed"].astype(float).to_numpy()
            y = subset["measured"].astype(float).to_numpy()
            ax.scatter(x, y, label=label, alpha=0.82)
            if {"ci_low", "ci_high"}.issubset(subset.columns):
                ax.errorbar(x, y, yerr=np.vstack([y-subset["ci_low"].astype(float), subset["ci_high"].astype(float)-y]), fmt="none", alpha=0.45)
        lo = min(float(frame["claimed"].min()), float(frame["measured"].min()), 0.0)
        hi = max(float(frame["claimed"].max()), float(frame["measured"].max()), 1.0)
        ax.plot([lo, hi], [lo, hi], linestyle="--", color="0.4", linewidth=1, label="Ideal calibration")
    elif chart == "rankogram":
        groups = _groups(frame, "series")
        for label, subset in groups:
            subset = subset.sort_values("rank")
            ax.plot(subset["rank"].astype(float), subset["probability"].astype(float), marker="o", label=label)
    else:
        raise ValueError(f"Unsupported chart type {chart!r}")

    _apply_axis_options(ax, figure)
    ax.grid(True, axis="x", alpha=0.22)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    if series_field or chart in {"dumbbell", "rankogram"}:
        handles, labels = ax.get_legend_handles_labels()
        if handles:
            ax.legend(handles, labels, loc="best", frameon=False, fontsize=8)


def render_figure(
    figure: dict[str, Any],
    frame: Any,
    output_dir: Path,
    formats: tuple[str, ...] = ("pdf", "svg", "png"),
    dpi: int = 300,
) -> list[Path]:
    """Render one validated figure contract to vector and raster formats."""
    import matplotlib
    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt

    validate_figure_data(figure, frame)
    options = figure.get("render_options", {})
    facet_field = options.get("facet_field")
    if figure["chart_type"] == "confusion_matrix" and not facet_field and "series" in frame.columns:
        facet_field = "series"
    if facet_field and facet_field in frame.columns:
        facet_values = list(dict.fromkeys(frame[facet_field].astype(str)))
        ncols = min(3, max(1, len(facet_values)))
        nrows = math.ceil(len(facet_values) / ncols)
        fig, axes = plt.subplots(nrows, ncols, figsize=(4.9 * ncols, 4.4 * nrows), squeeze=False)
        for ax, value in zip(axes.flat, facet_values):
            subset = frame[frame[facet_field].astype(str) == value]
            _draw(ax, figure, subset)
            ax.set_title(f"{facet_field}: {value}", fontsize=10)
        for ax in list(axes.flat)[len(facet_values):]:
            ax.set_visible(False)
    else:
        fig, ax = plt.subplots(figsize=(8.4, 5.4))
        _draw(ax, figure, frame)
    fig.suptitle(figure["title"], fontsize=13, fontweight="semibold", y=0.99)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    for fmt in formats:
        if fmt not in {"pdf", "svg", "png"}:
            raise ValueError(f"Unsupported output format: {fmt}")
        path = output_dir / f'{figure["id"]}.{fmt}'
        fig.savefig(path, format=fmt, dpi=dpi, bbox_inches="tight", metadata={"Title": figure["title"]})
        outputs.append(path)
    plt.close(fig)
    return outputs


def _read_frame(path: Path) -> Any:
    import pandas as pd
    if not path.is_file():
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def render_experiments(
    experiment_id: str | None = None,
    input_dir: Path = ROOT / "results" / "visualization" / "data",
    output_dir: Path = ROOT / "results" / "visualization" / "figures",
    formats: tuple[str, ...] = ("pdf", "svg", "png"),
    dpi: int = 300,
    strict: bool = False,
    plan_path: Path = PLOT_PLAN_PATH,
) -> dict[str, Any]:
    plan = load_plot_plan(plan_path)
    rendered, skipped, errors = [], [], []
    manifest_figures = []
    for figure in iter_figures(plan, experiment_id):
        data_path = input_dir / f'{figure["id"]}.csv'
        if not data_path.exists():
            message = f'{figure["id"]}: data file missing ({data_path})'
            if strict:
                errors.append(message)
            else:
                skipped.append(message)
            continue
        try:
            frame = _read_frame(data_path)
            validation = validate_figure_data(figure, frame)
            paths = render_figure(figure, frame, output_dir, formats=formats, dpi=dpi)
            rendered.extend(str(path) for path in paths)
            manifest_figures.append({
                "figure_id": figure["id"], "experiment_id": figure["id"].split("-")[0],
                "source_csv": str(data_path), "source_sha256": _sha256(data_path),
                "rows": validation["rows"], "outputs": [str(path) for path in paths],
            })
        except Exception as exc:
            errors.append(f'{figure["id"]}: {type(exc).__name__}: {exc}')
    manifest = {
        "schema_version": "1.0.0", "plan_sha256": _sha256(plan_path),
        "rendered_figure_count": len(manifest_figures), "figures": manifest_figures,
        "skipped": skipped, "errors": errors,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "figure_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if strict and (skipped or errors):
        raise RuntimeError(f"Strict render incomplete: {len(skipped)} missing, {len(errors)} invalid")
    return {"rendered": len(manifest_figures), "files": rendered, "skipped": skipped, "errors": errors, "manifest": str(output_dir / "figure_manifest.json")}


def plan_summary(plan_path: Path = PLOT_PLAN_PATH) -> dict[str, Any]:
    plan = load_plot_plan(plan_path)
    validation = validate_plot_plan(plan_path)
    counts: dict[str, int] = {}
    for exp in plan["experiments"]:
        for figure in exp["figures"]:
            counts[figure["chart_type"]] = counts.get(figure["chart_type"], 0) + 1
    return {**validation, "figures_by_chart_type": counts}
