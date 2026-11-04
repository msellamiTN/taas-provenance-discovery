"""Baseline catalogue loader and experiment-to-baseline compatibility checks."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
BASELINE_CATALOG_PATH = ROOT / "docs" / "experiment_design" / "pamcp_baselines_v1.json"
EXPERIMENT_CATALOG_PATH = ROOT / "docs" / "experiment_design" / "pamcp_experiments_v1.json"


def load_baseline_catalog(path: Path = BASELINE_CATALOG_PATH) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != "1.0.0":
        raise ValueError("Unsupported baseline catalog schema")
    items = data.get("baselines")
    if not isinstance(items, list) or not items:
        raise ValueError("Baseline catalogue must contain at least one baseline")
    ids = [x.get("id") for x in items]
    if any(not isinstance(x, str) or not x for x in ids) or len(ids) != len(set(ids)):
        raise ValueError("Baseline IDs must be non-empty and unique")
    allowed_status = {"ready", "ready_surrogate", "ready_adaptation", "partial_adapter",
                      "adapter_to_build", "pipeline_to_build", "planned", "ready_policy_control",
                      "core_method", "ready_control"}
    for item in items:
        if item.get("implementation") not in allowed_status:
            raise ValueError(f"Unknown implementation maturity for baseline {item.get('id')}")
        if not isinstance(item.get("experiments"), list):
            raise ValueError(f"Baseline {item.get('id')} must declare supported experiments")
    return data


def load_experiment_catalog(path: Path = EXPERIMENT_CATALOG_PATH) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != "1.0.0":
        raise ValueError("Unsupported experiment catalog schema")
    return data


def baseline_index(data: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    data = data or load_baseline_catalog()
    return {item["id"]: item for item in data["baselines"]}


def baselines_for_experiment(experiment_id: str) -> list[dict[str, Any]]:
    experiments = load_experiment_catalog()["experiments"]
    experiment = next((x for x in experiments if x["id"] == experiment_id.upper()), None)
    if experiment is None:
        raise KeyError(f"Unknown experiment {experiment_id}")
    index = baseline_index()
    ids = experiment.get("baseline_ids", [])
    missing = sorted(set(ids) - set(index))
    if missing:
        raise ValueError(f"{experiment_id} refers to unknown baselines: {missing}")
    return [index[x] for x in ids]


def validate_baseline_selection(experiment_id: str, baseline_ids: list[str]) -> list[dict[str, Any]]:
    available = {x["id"]: x for x in baselines_for_experiment(experiment_id)}
    unknown = sorted(set(baseline_ids) - set(available))
    if unknown:
        raise ValueError(f"Baseline(s) {unknown} are not registered for {experiment_id}")
    if len(baseline_ids) != len(set(baseline_ids)):
        raise ValueError("Baseline selections must be unique")
    return [available[x] for x in baseline_ids]
