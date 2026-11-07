"""Validation helpers for the E1-E22 plotting specification."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
PLOT_SPEC_PATH = ROOT / "docs" / "experiment_design" / "pamcp_plot_specs_v1.json"


def load_plot_spec(path: Path = PLOT_SPEC_PATH) -> dict[str, Any]:
    spec = json.loads(path.read_text(encoding="utf-8"))
    if spec.get("schema_version") != "1.0.0":
        raise ValueError("Unsupported plot specification schema")
    plots = spec.get("plots")
    if not isinstance(plots, list) or not plots:
        raise ValueError("Plot specification must contain plots")
    seen = set()
    represented = set()
    for plot in plots:
        pid = plot.get("id")
        eid = plot.get("experiment")
        if not pid or pid in seen:
            raise ValueError(f"Missing or duplicate plot id: {pid}")
        seen.add(pid)
        if eid not in {f"E{i}" for i in range(1, 23)}:
            raise ValueError(f"Unknown experiment in plot {pid}: {eid}")
        represented.add(eid)
        for axis in ("x", "y"):
            item = plot.get(axis)
            if not isinstance(item, dict) or not item.get("field") or not item.get("label"):
                raise ValueError(f"Plot {pid} lacks a labelled {axis} axis")
        if not plot.get("type") or not plot.get("title") or not plot.get("comparison"):
            raise ValueError(f"Plot {pid} lacks type, title or comparison")
    missing = sorted({f"E{i}" for i in range(1, 23)} - represented)
    if missing:
        raise ValueError(f"Experiments without plots: {missing}")
    return spec
