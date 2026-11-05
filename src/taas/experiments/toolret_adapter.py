"""Source-specific adapter for ToolRet query/tool retrieval exports.

ToolRet is heterogeneous tool retrieval, not an MCP execution benchmark.
A full-corpus file is mandatory: deriving the candidate corpus only from each
query's positive labels would create severe candidate-set leakage.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from taas.experiments.benchmark_adapters import _sha256, _write_json
from taas.experiments.benchmark_io import normalize_tool


def _toolret_doc(source_id: str, doc: Mapping[str, Any]) -> dict[str, Any]:
    params = doc.get("parameters", doc.get("input_schema", {})) or {}
    if isinstance(params, list):
        properties = {}
        required = []
        for item in params:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if name:
                properties[str(name)] = {
                    "type": item.get("type", "string"),
                    "description": item.get("description", ""),
                }
                if item.get("required"):
                    required.append(str(name))
        input_schema = {"type": "object", "properties": properties, "required": required}
    elif isinstance(params, dict) and "properties" in params:
        input_schema = params
    elif isinstance(params, dict):
        input_schema = {"type": "object", "properties": params}
    else:
        input_schema = {}
    return {
        "tool_id": f"toolret::{source_id}",
        "name": doc.get("name", source_id),
        "description": doc.get("description", ""),
        "input_schema": input_schema,
        "output_schema": doc.get("output_schema", {}),
        "server_id": "toolret_source_local",
    }


def adapt_toolret_records(
    task_records: Sequence[Mapping[str, Any]],
    corpus_records: Sequence[Mapping[str, Any]],
    output_dir: str | Path,
    task_source_path: str | Path | None = None,
    corpus_source_path: str | Path | None = None,
) -> dict[str, Any]:
    out = Path(output_dir)
    tools_by_id: dict[str, dict[str, Any]] = {}
    for row in corpus_records:
        source_id = str(row.get("id", row.get("tool_id", ""))).strip()
        doc = row.get("doc", row)
        if not source_id or not isinstance(doc, dict):
            raise ValueError("ToolRet corpus rows require id/tool_id and a doc object")
        normalized = normalize_tool(_toolret_doc(source_id, doc), "toolret")
        payload = {
            "dataset_id": normalized.dataset_id, "tool_id": normalized.tool_id,
            "server_id": normalized.server_id, "name": normalized.name,
            "description": normalized.description, "input_schema": normalized.input_schema,
            "output_schema": normalized.output_schema, "annotations": {},
            "definition_hash": normalized.definition_hash,
        }
        previous = tools_by_id.get(normalized.tool_id)
        if previous and previous != payload:
            raise ValueError(f"Conflicting ToolRet corpus document for {source_id}")
        tools_by_id[normalized.tool_id] = payload
    if not tools_by_id:
        raise ValueError("ToolRet adapter requires the complete candidate tool corpus")

    discovery_tasks, evaluator_refs = [], []
    seen_tasks = set()
    missing_labels = set()
    for row in task_records:
        task_id = str(row.get("id", row.get("task_id", ""))).strip()
        query = str(row.get("query", row.get("prompt", ""))).strip()
        if not task_id or not query:
            raise ValueError("ToolRet task requires id and query")
        if task_id in seen_tasks:
            raise ValueError(f"Duplicate ToolRet task ID: {task_id}")
        seen_tasks.add(task_id)
        labels = row.get("labels", []) or []
        judgments = []
        for label in labels:
            if not isinstance(label, dict):
                continue
            source_tool_id = str(label.get("id", "")).strip()
            canonical_id = f"toolret::{source_tool_id}"
            if not source_tool_id:
                continue
            if canonical_id not in tools_by_id:
                missing_labels.add(source_tool_id)
            relevance = label.get("relevance", 1)
            judgments.append({"tool_id": canonical_id, "relevance": relevance})
        discovery_tasks.append({
            "dataset_id": "toolret", "task_id": task_id, "prompt": query,
            "split": row.get("split"),
        })
        evaluator_refs.append({
            "dataset_id": "toolret", "task_id": task_id,
            "relevance_judgments": judgments,
            "instruction": row.get("instruction"),
            "category": row.get("category"),
        })
    if missing_labels:
        preview = ", ".join(sorted(missing_labels)[:5])
        raise ValueError(f"ToolRet qrels refer to tools absent from corpus: {preview}")
    _write_json(out / "discovery" / "tools.json", list(tools_by_id.values()))
    _write_json(out / "discovery" / "tasks.json", discovery_tasks)
    _write_json(out / "evaluator" / "task_references.json", evaluator_refs)
    source_files = {}
    if task_source_path:
        path = Path(task_source_path)
        source_files["tasks"] = {"path": str(path), "sha256": _sha256(path)}
    if corpus_source_path:
        path = Path(corpus_source_path)
        source_files["corpus"] = {"path": str(path), "sha256": _sha256(path)}
    manifest = {
        "schema_version": "1.0.0", "dataset_id": "toolret",
        "source": "https://github.com/mangopy/tool-retrieval-benchmark",
        "source_files": source_files,
        "counts": {"tasks": len(discovery_tasks), "corpus_tools": len(tools_by_id),
                   "tasks_with_qrels": sum(bool(x["relevance_judgments"]) for x in evaluator_refs)},
        "separation": {"discovery_dir": "discovery/", "evaluator_dir": "evaluator/",
                       "gold_labels_exposed_to_discovery": False},
        "limitations": [
            "ToolRet is a heterogeneous retrieval benchmark; results are a separate track from MCP-only tasks.",
            "A full candidate corpus is mandatory; positive qrel documents alone are not a valid corpus.",
            "Tool IDs are source-local and do not imply MCP server identity.",
            "Preserve graded relevance and the original instruction/no-instruction setting.",
            "This adapter does not establish composition correctness, runtime behavior, or safety labels.",
        ],
    }
    _write_json(out / "manifest.json", manifest)
    return manifest


__all__ = ["adapt_toolret_records"]
