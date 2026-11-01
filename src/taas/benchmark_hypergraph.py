"""Build a provenance-aware capability hypergraph from the pinned MCP benchmark registry.

The capability graph is derived only from published tool definitions (schemas, descriptions,
annotations) and deterministic lexical/schema typing. Benchmark task gold labels are exported
separately for evaluation and are NEVER used to infer tool capabilities or effects.
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable

from .contracts import CapabilityContract, extract_contract
from .data.registries import RawTool, load_processed, raw_tools_from_processed
from .hypergraph import Hypergraph
from .policy import Policy


SCHEMA_VERSION = "taas-capability-hypergraph/1.0"


def _record(r: Any) -> dict[str, Any]:
    return {"ptype": r.ptype, "signer": r.signer, "kappa": r.kappa, "method": r.method}


def contract_record(c: CapabilityContract) -> dict[str, Any]:
    """Lossless, JSON-safe contract projection with argument names retained."""
    return {
        "tool_id": c.tool,
        "server": c.server,
        "name": c.name,
        "description": c.description,
        "definition_hash": c.h,
        "source": c.srv.get("source", ""),
        "category": c.srv.get("category", ""),
        "arguments": [
            {
                "name": a.name,
                "type": str(a.type),
                "required": a.required,
                "typing_confidence": a.confidence,
                "domain": list(a.domain) if a.domain is not None else None,
            }
            for a in c.args
        ],
        "tail": [{"argument": a.name, "type": str(a.type)} for a in c.args if a.required],
        "tail_types": [str(t) for t in c.tail],
        "head": str(c.head),
        "output_typing": {"type": str(c.out.type), "confidence": c.out.confidence,
                          "source": c.out.source},
        "effects": sorted(str(e) for e in c.eff),
        "effect_provenance": _record(c.eff_record),
        "flow": {"source_label": c.flow.source_label,
                 "narrowed_arguments": sorted(c.flow.narrowed_args)},
        "requirements": list(c.req),
        "qos": asdict(c.qos),
        "tool_class": c.tool_class,
        "tokens": c.tokens,
        "annotations": c.annotations,
        "properties": {
            prop: [_record(r) for r in records]
            for prop, records in sorted(c.props.items())
        },
    }


def _task_record(task: dict[str, Any], known_tool_ids: set[str]) -> dict[str, Any]:
    """Preserve benchmark gold mappings as evaluation-only alternatives.

    A pipe-delimited LiveMCPBench mapping means an ambiguous name resolution. It is
    represented as one alternative set, not incorrectly treated as several required tools.
    """
    raw_gold = task.get("gold_tools") or []
    alternatives: list[list[str]] = []
    unresolved_ids: list[str] = []
    for raw in raw_gold:
        candidates = sorted({x for x in str(raw).split("|") if x})
        if candidates and all(x in known_tool_ids for x in candidates):
            alternatives.append(candidates)
        else:
            unresolved_ids.extend(candidates)
    return {
        "task_id": task.get("id"),
        "query": task.get("query", ""),
        "dataset": task.get("source", ""),
        "category": task.get("category", ""),
        "n_steps": task.get("n_steps", 1),
        "gold_tool_alternatives": alternatives,
        "unresolved_gold_tool_ids": sorted(set(unresolved_ids)),
        "gold_unresolved_names": list(task.get("gold_unresolved") or []),
        "usage": "evaluation_only_not_used_for_capability_inference",
    }


def build_benchmark_hypergraph(
    raw_tools: Iterable[RawTool],
    tasks_by_dataset: dict[str, list[dict[str, Any]]] | None = None,
    dataset_stats: dict[str, Any] | None = None,
    policy: Policy | None = None,
) -> tuple[Hypergraph, dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Construct H=(V,E) and separate benchmark evaluation records.

    Every MCP tool definition contributes one directed hyperedge from its required
    argument types to its output type. Optional arguments remain explicit metadata.
    No benchmark gold label is used in contract extraction.
    """
    tools = list(raw_tools)
    policy = policy or Policy(name="benchmark-build-default")
    contracts = [extract_contract(t, typing=None, store=None) for t in tools]

    H = Hypergraph()
    for c in contracts:
        H.add(c, policy)

    vertices: dict[str, dict[str, Any]] = {}
    hyperedges: list[dict[str, Any]] = []
    for c in contracts:
        for a in c.args:
            key = str(a.type)
            vertices.setdefault(key, {"type": key, "kind": a.type.kind,
                                      "domain": a.type.domain, "collection": a.type.collection})
        key = str(c.head)
        vertices.setdefault(key, {"type": key, "kind": c.head.kind,
                                  "domain": c.head.domain, "collection": c.head.collection})
        hyperedges.append({
            "edge_id": c.tool,
            "edge_kind": "mcp_tool_capability",
            "tail": [{"argument": a.name, "type": str(a.type)}
                     for a in c.args if a.required],
            "tail_types": [str(t) for t in c.tail],
            "head": str(c.head),
            "contract": contract_record(c),
            "definition_hash": c.h,
        })

    known = {c.tool for c in contracts}
    tasks_by_dataset = tasks_by_dataset or {}
    task_records = [
        _task_record(t, known)
        for dataset in sorted(tasks_by_dataset)
        for t in tasks_by_dataset[dataset]
    ]
    server_ids = sorted({c.server for c in contracts})
    source_counts = Counter(c.srv.get("source", "") for c in contracts)
    category_counts = Counter(next((t.category for t in tools if t.id == c.tool), "") for c in contracts)

    graph = {
        "schema_version": SCHEMA_VERSION,
        "construction": {
            "typing_mode": "deterministic_schema_and_lexical",
            "benchmark_gold_labels_used_for_inference": False,
            "llm_silver_typing_used": False,
            "runtime_effect_observations_used": False,
            "effect_semantics": "lexical_cues_plus_published_mcp_annotations",
            "warning": (
                "This is a benchmark-derived static capability model, not proof of runtime "
                "behavior. Lexical effects and MCP annotations are claims, not sandbox observations."
            ),
        },
        "vertices": [vertices[k] for k in sorted(vertices)],
        "hyperedges": hyperedges,
        "forbidden_tool_pairs": [
            {"tools": list(pair), "reason": reason}
            for pair, reason in sorted(H.forbidden.items())
        ],
        "summary": {
            "n_vertices": len(vertices),
            "n_hyperedges": len(hyperedges),
            "n_servers": len(server_ids),
            "n_required_argument_occurrences": sum(len(e["tail"]) for e in hyperedges),
            "n_optional_arguments": sum(
                sum(not a["required"] for a in c.args) for c in contracts
            ),
            "n_forbidden_pairs": len(H.forbidden),
            "servers": server_ids,
            "tools_by_source": dict(sorted(source_counts.items())),
            "tools_by_category": dict(sorted(category_counts.items())),
        },
    }
    benchmark = {
        "schema_version": "taas-benchmark-task-mapping/1.0",
        "usage": "evaluation_only",
        "dataset_stats": dataset_stats or {},
        "tasks": task_records,
        "summary": {
            "n_tasks": len(task_records),
            "n_tasks_by_dataset": dict(sorted(Counter(t["dataset"] for t in task_records).items())),
            "n_tasks_with_resolved_gold": sum(bool(t["gold_tool_alternatives"]) for t in task_records),
            "n_unresolved_gold_mappings": sum(len(t["unresolved_gold_tool_ids"]) +
                                               len(t["gold_unresolved_names"]) for t in task_records),
            "n_ambiguous_gold_groups": sum(
                sum(len(g) > 1 for g in t["gold_tool_alternatives"]) for t in task_records
            ),
        },
    }
    report = {
        "schema_version": "taas-hypergraph-build-report/1.0",
        "graph_summary": graph["summary"],
        "benchmark_summary": benchmark["summary"],
        "data_leakage_controls": {
            "gold_tool_labels_used_to_create_hyperedges": False,
            "silver_effect_labels_used_to_create_effects": False,
            "llm_typing_labels_used": False,
            "gold_mappings_exported_separately": True,
        },
        "interpretation": (
            "Graph structure comes from the merged MCP tool-definition registry. "
            "Task-to-tool gold mappings are evaluation-only and must not be fed back "
            "into capability extraction or model fitting for the same evaluation split."
        ),
    }
    return H, graph, benchmark, report


def build_from_processed_registry() -> tuple[Hypergraph, dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Load the repository's pinned merged benchmark data without rebuilding or overwriting it."""
    data = load_processed()
    tools = raw_tools_from_processed(data)
    tasks = {
        "LiveMCPBench": data.get("tasks_livemcpbench", []),
        "MCPToolBench++": data.get("tasks_mcptoolbenchpp", []),
    }
    return build_benchmark_hypergraph(tools, tasks, data.get("stats", {}))


def write_bundle(out_dir: str | Path, graph: dict[str, Any], benchmark: dict[str, Any],
                 report: dict[str, Any]) -> None:
    """Write a new bundle; refuse to overwrite an existing non-empty directory."""
    out = Path(out_dir)
    if out.exists() and any(out.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty output directory: {out}")
    out.mkdir(parents=True, exist_ok=True)
    for name, payload in (
        ("capability_hypergraph.json", graph),
        ("benchmark_tasks.evaluation-only.json", benchmark),
        ("build_report.json", report),
    ):
        target = out / name
        target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
