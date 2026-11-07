"""Source-specific adapter for ToolRet query/tool retrieval exports.

ToolRet is heterogeneous tool retrieval, not an MCP execution benchmark.
A full-corpus file is mandatory: deriving the candidate corpus only from each
query's positive labels would create severe candidate-set leakage.
"""
from __future__ import annotations

from pathlib import Path
import json
from typing import Any, Mapping, Sequence

from taas.experiments.benchmark_adapters import _sha256, _write_json
from taas.experiments.benchmark_io import normalize_tool


def _toolret_doc(source_id: str, doc: Mapping[str, Any]) -> dict[str, Any]:
    documentation = doc.get("documentation")
    if documentation is not None and not doc.get("description"):
        doc = dict(doc) | {"description": str(documentation)}
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
        "name": doc.get("name", doc.get("tool_name", source_id)),
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
        if not source_id:
            raise ValueError("ToolRet corpus rows require id/tool_id")
        if isinstance(doc, str):
            doc = {"documentation": doc, "name": row.get("name", source_id)}
        if not isinstance(doc, dict):
            raise ValueError("ToolRet corpus doc must be an object or documentation string")
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
        query_value = row.get("query", row.get("prompt", ""))
        query = str(query_value).strip() if query_value is not None else ""
        if not task_id or not query:
            context = {
                "row_index": len(discovery_tasks),
                "available_fields": sorted(str(k) for k in row.keys()),
                "id": row.get("id", row.get("task_id")),
                "query_preview": query[:120],
                "query_is_null": query_value is None,
                "category": row.get("category"),
                "task": row.get("task"),
            }
            raise ValueError(
                "Malformed ToolRet query record (expected non-empty id/task_id and query/prompt). "
                f"Record context: {context}. Check the source config and pinned HF revision."
            )
        if task_id in seen_tasks:
            raise ValueError(f"Duplicate ToolRet task ID: {task_id}")
        seen_tasks.add(task_id)
        labels = row.get("labels", []) or []
        # Hugging Face exposes the nested qrels as a JSON-encoded string.
        # Decode explicitly; iterating a string would silently discard every label.
        if isinstance(labels, str):
            try:
                labels = json.loads(labels) if labels.strip() else []
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON in ToolRet labels for task {task_id}: {exc}"
                ) from exc
        if isinstance(labels, dict):
            labels = labels.get("labels", labels.get("relevance_judgments", []))
        if not isinstance(labels, list):
            raise ValueError(
                f"ToolRet labels for task {task_id} must decode to a list; "
                f"got {type(labels).__name__}"
            )
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
            "category": row.get("category") or row.get("task") or "unspecified",
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


def adapt_toolret_hf(
    output_dir: str | Path,
    query_revision: str,
    tool_revision: str,
    query_configs: Sequence[str] | None = None,
    tool_configs: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Load official ToolRet HF query/tool repositories at an immutable revision.

    Both repository revisions are mandatory because the query and tool corpora
    are separate Hugging Face repositories with independent commit histories.
    """
    for revision in (query_revision, tool_revision):
        if not revision or revision.lower() in {"main", "master", "latest"}:
            raise ValueError("Pass immutable Hugging Face commits for both repositories")
    try:
        from datasets import get_dataset_config_names, load_dataset
    except ImportError as exc:
        raise RuntimeError("Install the benchmark-hf extra to load ToolRet from Hugging Face") from exc

    query_repo = "mangopy/ToolRet-Queries"
    tool_repo = "mangopy/ToolRet-Tools"
    q_configs = list(query_configs or get_dataset_config_names(query_repo, revision=query_revision))
    t_configs = list(tool_configs or get_dataset_config_names(tool_repo, revision=tool_revision))
    if not q_configs or not t_configs:
        raise ValueError("ToolRet query and tool config lists must both be non-empty")

    task_records, corpus_records = [], []
    excluded_query_rows = []
    raw_query_rows = 0
    for config in q_configs:
        dataset = load_dataset(query_repo, config, revision=query_revision)
        split_name = "queries" if "queries" in dataset else next(iter(dataset.keys()))
        for row_index, row in enumerate(dataset[split_name]):
            raw_query_rows += 1
            record = dict(row) | {"task": config}
            # Dataset IDs are only guaranteed unique inside their source config.
            raw_id = str(record.get("id", record.get("task_id", "")) or "").strip()
            query_value = record.get("query", record.get("prompt"))
            query = str(query_value).strip() if query_value is not None else ""
            if not query:
                # Do not substitute the retrieval instruction for the user query:
                # they are distinct benchmark conditions in the ToolRet paper.
                excluded_query_rows.append({
                    "config": config, "row_index": row_index,
                    "source_id": raw_id or None,
                    "reason": "missing_or_empty_query",
                })
                continue
            if not raw_id:
                raw_id = f"row_{row_index}"
            record["id"] = f"{config}::{raw_id}"
            record["category"] = record.get("category") or config
            task_records.append(record)
    for config in t_configs:
        dataset = load_dataset(tool_repo, config, revision=tool_revision)
        split_name = "tools" if "tools" in dataset else next(iter(dataset.keys()))
        for row in dataset[split_name]:
            corpus_records.append(dict(row) | {"category": config})

    manifest = adapt_toolret_records(task_records, corpus_records, output_dir)
    manifest["source_revisions"] = {
        "query_repository": query_repo,
        "tool_repository": tool_repo,
        "query_revision": query_revision,
        "tool_revision": tool_revision,
        "query_configs": q_configs,
        "tool_configs": t_configs,
    }
    manifest["counts"]["query_configs"] = len(q_configs)
    manifest["counts"]["tool_configs"] = len(t_configs)
    manifest["counts"]["raw_query_rows"] = raw_query_rows
    manifest["counts"]["excluded_query_rows"] = len(excluded_query_rows)
    manifest["counts"]["qrel_tasks"] = manifest["counts"]["tasks_with_qrels"]
    manifest["data_quality"] = {
        "excluded_query_rows": excluded_query_rows,
        "policy": "Rows without a non-empty query are excluded and reported; instruction is never substituted for query.",
    }
    manifest["source_revisions"]["query_config_row_counts"] = {
        config: sum(1 for row in task_records if row.get("task") == config)
        for config in q_configs
    }
    _write_json(Path(output_dir) / "manifest.json", manifest)
    return manifest


__all__ = ["adapt_toolret_records", "adapt_toolret_hf"]
