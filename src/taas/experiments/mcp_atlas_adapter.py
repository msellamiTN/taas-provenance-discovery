"""Source-specific adapter for the public MCP-Atlas parquet release.

The adapter treats ENABLED_TOOLS as the per-task candidate set. GTFA_CLAIMS and
TRAJECTORY remain evaluator-side references; TRAJECTORY is not assumed to be
an exhaustive set of all valid toolchains.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from taas.experiments.benchmark_io import normalize_tool
from taas.experiments.benchmark_adapters import _sha256, _write_json


def _decode_json_cell(value: Any, field: str, task_id: str) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            # The official harness also accepts comma-separated tool-name strings.
            return [item.strip() for item in value.split(",") if item.strip()]
    raise ValueError(f"MCP-Atlas {field} must be JSON text, object, or list for task {task_id}")


def adapt_mcp_atlas_records(records: Sequence[Mapping[str, Any]], output_dir: str | Path) -> dict[str, Any]:
    out = Path(output_dir)
    all_tools: dict[str, dict[str, Any]] = {}
    task_views, visibility, evaluator = [], [], []
    for row in records:
        task_id = str(row.get("TASK", "")).strip()
        prompt = str(row.get("PROMPT", "")).strip()
        if not task_id or not prompt:
            raise ValueError("MCP-Atlas row requires TASK and PROMPT")
        enabled = _decode_json_cell(row.get("ENABLED_TOOLS"), "ENABLED_TOOLS", task_id)
        if isinstance(enabled, dict):
            enabled = enabled.get("tools", enabled.get("items"))
        if not isinstance(enabled, list):
            raise ValueError(f"ENABLED_TOOLS must decode to a list for task {task_id}")
        task_tool_ids = []
        for source_tool in enabled:
            if isinstance(source_tool, str):
                tool = {"name": source_tool, "server_id": "mcp_atlas_unresolved_server"}
            elif isinstance(source_tool, dict):
                tool = dict(source_tool)
            else:
                raise ValueError(f"Enabled tool must be a name or object in task {task_id}")
            name = str(tool.get("name") or tool.get("tool_name") or "").strip()
            if not name:
                raise ValueError(f"Enabled tool without name in task {task_id}")
            server = tool.get("server_id") or tool.get("server") or tool.get("server_name") or tool.get("provider")
            if not server:
                server = "mcp_atlas_unresolved_server"
            tool["name"] = name
            tool["server_id"] = str(server)
            tool["tool_id"] = str(tool.get("tool_id") or f"{server}::{name}")
            tool["input_schema"] = tool.get("input_schema", tool.get("inputSchema", {}))
            normalized = normalize_tool(tool, "mcp_atlas_public")
            payload = {
                "dataset_id": normalized.dataset_id, "tool_id": normalized.tool_id,
                "server_id": normalized.server_id, "name": normalized.name,
                "description": normalized.description, "input_schema": normalized.input_schema,
                "output_schema": normalized.output_schema, "annotations": normalized.annotations,
                "definition_hash": normalized.definition_hash,
                "identity_resolution": "unresolved_server" if server == "mcp_atlas_unresolved_server" else "source_server_field"
            }
            previous = all_tools.get(normalized.tool_id)
            if previous and previous != payload:
                raise ValueError(f"Conflicting tool definitions for {normalized.tool_id}")
            all_tools[normalized.tool_id] = payload
            task_tool_ids.append(normalized.tool_id)
        task_views.append({"dataset_id": "mcp_atlas_public", "task_id": task_id, "prompt": prompt, "split": "public"})
        visibility.append({"task_id": task_id, "enabled_tool_ids": sorted(set(task_tool_ids))})
        evaluator.append({
            "dataset_id": "mcp_atlas_public", "task_id": task_id,
            "gtfa_claims": row.get("GTFA_CLAIMS"),
            "trajectory_reference": row.get("TRAJECTORY"),
            "reference_semantics": "claims-based answer oracle; trajectory is diagnostic evidence, not exhaustive acceptable-tool-set ground truth"
        })
    _write_json(out / "discovery" / "tools.json", list(all_tools.values()))
    _write_json(out / "discovery" / "tasks.json", task_views)
    _write_json(out / "discovery" / "task_tool_visibility.json", visibility)
    _write_json(out / "evaluator" / "task_references.json", evaluator)
    manifest = {
        "schema_version": "1.0.0", "dataset_id": "mcp_atlas_public",
        "source": "https://huggingface.co/datasets/ScaleAI/MCP-Atlas",
        "license": "CC-BY-4.0 (verify current dataset card at acquisition)",
        "source_files": {},
        "counts": {"tasks": len(task_views), "unique_tools": len(all_tools),
                   "task_tool_visibility_rows": len(visibility),
                   "tasks_with_gtfa_claims": sum(x["gtfa_claims"] is not None for x in evaluator),
                   "tasks_with_trajectory": sum(x["trajectory_reference"] is not None for x in evaluator)},
        "separation": {"discovery_dir": "discovery/", "evaluator_dir": "evaluator/",
                       "gold_labels_exposed_to_discovery": False},
        "limitations": [
            "The public Hugging Face release contains 500 tasks; it is not the full 1,000-task benchmark.",
            "GTFA_CLAIMS supports claims-based answer evaluation, not tool-set correctness by itself.",
            "TRAJECTORY is a successful reference trace, not proof that no alternative valid composition exists.",
            "Some ENABLED_TOOLS rows contain names only; those tool records have no schema/description and unresolved server identity.",
            "Tool identity remains unresolved when the source row does not identify a server.",
            "Live execution requires the benchmark's pinned Docker harness and server configuration.",
        ],
    }
    _write_json(out / "manifest.json", manifest)
    return manifest


def adapt_mcp_atlas_parquet(parquet_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError("Install the experiment extra (pandas and pyarrow) to read MCP-Atlas parquet") from exc
    path = Path(parquet_path)
    frame = pd.read_parquet(path)
    required = {"TASK", "ENABLED_TOOLS", "PROMPT", "GTFA_CLAIMS", "TRAJECTORY"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"MCP-Atlas parquet missing columns: {sorted(missing)}")
    manifest = adapt_mcp_atlas_records(frame.to_dict(orient="records"), output_dir)
    manifest["source_files"] = {"parquet": {"path": str(path), "sha256": _sha256(path)}}
    _write_json(Path(output_dir) / "manifest.json", manifest)
    return manifest


__all__ = ["adapt_mcp_atlas_records", "adapt_mcp_atlas_parquet"]
