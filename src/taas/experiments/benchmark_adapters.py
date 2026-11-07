"""Dataset export adapter with a hard discovery/evaluator data boundary.

Example:
  python -m taas.experiments.benchmark_adapters --dataset-id example \
    --tools tools.json --tasks tasks.json --output data/processed/example \
    --tool-collection tools --task-collection tasks

Collection keys are explicit because benchmark releases use different schemas.
No source is downloaded automatically and no labels are inferred.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from taas.experiments.benchmark_io import (
    discovery_task_view,
    discovery_view,
    load_json_records,
    normalize_task,
    normalize_tool,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def adapt_json_export(
    dataset_id: str,
    tools_path: str | Path,
    tasks_path: str | Path,
    output_dir: str | Path,
    tool_collection: tuple[str, ...] = ("tools", "data", "items"),
    task_collection: tuple[str, ...] = ("tasks", "data", "items"),
) -> dict[str, Any]:
    """Create separated discovery and evaluator artifacts from two source exports."""
    tools_file, tasks_file = Path(tools_path), Path(tasks_path)
    out = Path(output_dir)
    raw_tools = load_json_records(tools_file, tool_collection)
    raw_tasks = load_json_records(tasks_file, task_collection)
    tools = [normalize_tool(row, dataset_id) for row in raw_tools]
    tasks = [normalize_task(row, dataset_id) for row in raw_tasks]

    tool_ids = [row.tool_id for row in tools]
    task_ids = [row.task_id for row in tasks]
    if len(tool_ids) != len(set(tool_ids)):
        raise ValueError("Duplicate normalized tool_id values; resolve identity collisions explicitly")
    if len(task_ids) != len(set(task_ids)):
        raise ValueError("Duplicate normalized task_id values; resolve task collisions explicitly")

    _write_json(out / "discovery" / "tools.json", [discovery_view(row) for row in tools])
    _write_json(out / "discovery" / "tasks.json", [discovery_task_view(row) for row in tasks])
    _write_json(out / "evaluator" / "task_references.json", [
        {
            "dataset_id": row.dataset_id,
            "task_id": row.task_id,
            "target_tool_ids": list(row.target_tool_ids),
            "acceptable_tool_sets": [list(group) for group in row.acceptable_tool_sets],
            "oracle_ref": row.oracle_ref,
            "source_record_id": row.source_record_id,
        }
        for row in tasks
    ])
    manifest = {
        "schema_version": "1.0.0",
        "dataset_id": dataset_id,
        "source_files": {
            "tools": {"path": str(tools_file), "sha256": _sha256(tools_file)},
            "tasks": {"path": str(tasks_file), "sha256": _sha256(tasks_file)},
        },
        "counts": {
            "tools": len(tools),
            "tasks": len(tasks),
            "tasks_with_target_tools": sum(bool(row.target_tool_ids) for row in tasks),
            "tasks_with_acceptable_sets": sum(bool(row.acceptable_tool_sets) for row in tasks),
            "tasks_with_oracle_reference": sum(bool(row.oracle_ref) for row in tasks),
        },
        "separation": {
            "discovery_tools": "discovery/tools.json",
            "discovery_tasks": "discovery/tasks.json",
            "evaluator_references": "evaluator/task_references.json",
            "gold_labels_exposed_to_discovery": False,
        },
        "limitations": [
            "This adapter performs schema normalization only; it does not verify benchmark semantics.",
            "Tool IDs must be mapped to stable server::tool identities before cross-dataset merging.",
            "Original licenses, splits, evaluator implementations and task validity must be checked separately.",
            "Missing references remain missing; they are not interpreted as negative labels.",
        ],
    }
    _write_json(out / "manifest.json", manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--tools", required=True)
    parser.add_argument("--tasks", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--tool-collection", action="append", default=[])
    parser.add_argument("--task-collection", action="append", default=[])
    args = parser.parse_args()
    result = adapt_json_export(
        args.dataset_id, args.tools, args.tasks, args.output,
        tuple(args.tool_collection or ("tools", "data", "items")),
        tuple(args.task_collection or ("tasks", "data", "items")),
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
