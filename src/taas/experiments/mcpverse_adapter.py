"""MCPVerse v1.1 CSV task adapter; preserves native evaluation semantics."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from taas.experiments.benchmark_adapters import _sha256, _write_json


_REQUIRED = {"question_id", "question", "MCP", "tool", "complexity", "answer", "eval_method"}


def adapt_mcpverse_csv(csv_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
    path, out = Path(csv_path), Path(output_dir)
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        missing = _REQUIRED - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"MCPVerse CSV missing columns: {sorted(missing)}")
        rows = list(reader)
    seen = set()
    discovery, evaluator = [], []
    for row in rows:
        task_id = str(row.get("question_id", "")).strip()
        prompt = str(row.get("question", "")).strip()
        server = str(row.get("MCP", "")).strip()
        tool = str(row.get("tool", "")).strip()
        if not task_id or not prompt or not server or not tool:
            raise ValueError("MCPVerse row requires question_id, question, MCP and tool")
        if task_id in seen:
            raise ValueError(f"Duplicate MCPVerse question_id: {task_id}")
        seen.add(task_id)
        discovery.append({
            "dataset_id": "mcpverse_time_invariant_v1_1",
            "task_id": task_id,
            "prompt": prompt,
            "split": "time_invariant",
        })
        evaluator.append({
            "dataset_id": "mcpverse_time_invariant_v1_1",
            "task_id": task_id,
            "annotated_server_id": server,
            "annotated_tool_id": f"{server}::{tool}",
            "complexity": row.get("complexity"),
            "reference_answer": row.get("answer"),
            "native_eval_method": row.get("eval_method"),
            "time_sensitive": row.get("time-sensitive"),
            "reference_semantics": "benchmark-annotated tool/answer reference; not an exhaustive set of all valid toolchains",
        })
    _write_json(out / "discovery" / "tasks.json", discovery)
    _write_json(out / "evaluator" / "task_references.json", evaluator)
    manifest: dict[str, Any] = {
        "schema_version": "1.0.0",
        "dataset_id": "mcpverse_time_invariant_v1_1",
        "source": "https://github.com/hailsham/mcpverse",
        "source_file": {"path": str(path), "sha256": _sha256(path)},
        "counts": {
            "tasks": len(discovery),
            "distinct_annotated_servers": len({x["annotated_server_id"] for x in evaluator}),
            "distinct_annotated_tools": len({x["annotated_tool_id"] for x in evaluator}),
            "native_eval_methods": sorted({str(x["native_eval_method"]) for x in evaluator}),
        },
        "separation": {
            "discovery_dir": "discovery/",
            "evaluator_dir": "evaluator/",
            "gold_labels_exposed_to_discovery": False,
        },
        "limitations": [
            "This CSV contains task prompts and annotated MCP/tool names, not complete tool schemas.",
            "Do not treat this adapter output as a full candidate registry for retrieval evaluation.",
            "Preserve the native eval_method; llm_as_a_judge is not a deterministic oracle.",
            "The annotated tool is a benchmark reference, not proof that alternative valid tools do not exist.",
            "Use the benchmark's pinned native MCPVerse runtime for execution experiments.",
        ],
    }
    _write_json(out / "manifest.json", manifest)
    return manifest


__all__ = ["adapt_mcpverse_csv"]
