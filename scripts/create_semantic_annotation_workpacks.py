#!/usr/bin/env python3
"""Create blind, hash-bound GPT annotation work packages from the MCP tool registry.

Benchmark task queries and gold tool mappings are deliberately never loaded by this script.
Each tool is assigned to two independent annotation sessions using different perspectives.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "data" / "processed" / "registry_merged.json"
SCHEMA_VERSION = "taas-semantic-annotation-workpack/1.0"
PERSPECTIVES = ("capability_semantics", "operational_security")


def canonical_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_tools(path: Path) -> list[dict[str, Any]]:
    # Read only registry definitions. Never load task arrays or gold labels.
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data["registry"]
    tools = []
    for row in rows:
        definition = {
            "server": row["server"],
            "name": row["name"],
            "description": row.get("description") or "",
            "input_schema": row.get("input_schema") or {},
            "output_schema": row.get("output_schema"),
            "annotations": row.get("annotations"),
            "source": row.get("source", ""),
            "category": row.get("category", ""),
            "extra": row.get("extra"),
        }
        payload = json.dumps(
            {"server": definition["server"], "name": definition["name"],
             "description": definition["description"],
             "inputSchema": definition["input_schema"],
             "outputSchema": definition["output_schema"],
             "annotations": definition["annotations"], "extra": definition["extra"]},
            sort_keys=True, ensure_ascii=False, separators=(",", ":"),
        )
        definition_hash = hashlib.sha256(payload.encode()).hexdigest()[:32]
        tool_id = f'{definition["server"]}::{definition["name"]}'
        tools.append({
            "tool_id": tool_id,
            "definition_hash": definition_hash,
            "definition": definition,
        })
    return sorted(tools, key=lambda x: x["tool_id"])


def build_workpacks(registry_path: Path, outdir: Path, workers: int = 8) -> dict[str, Any]:
    if workers < 2:
        raise ValueError("workers must be >= 2 for independent annotation sessions")
    if outdir.exists() and any(outdir.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty directory: {outdir}")
    tools = load_tools(registry_path)
    snapshot_hash = canonical_hash(registry_path)
    outdir.mkdir(parents=True, exist_ok=True)
    tasks = []
    for tool in tools:
        for perspective in PERSPECTIVES:
            task_id = f'{tool["tool_id"]}@{perspective}'
            tasks.append({
                "task_id": task_id,
                "tool_id": tool["tool_id"],
                "definition_hash": tool["definition_hash"],
                "perspective": perspective,
                "definition": tool["definition"],
                "instructions": {
                    "benchmark_queries_included": False,
                    "gold_tool_labels_included": False,
                    "do_not_infer_unstated_behavior": True,
                    "unknown_is_not_absent": True,
                },
            })
    # Stable round-robin sharding; each worker/session receives a balanced workload.
    shards: list[list[dict[str, Any]]] = [[] for _ in range(workers)]
    for i, task in enumerate(tasks):
        shards[i % workers].append(task)
    for i, shard in enumerate(shards):
        path = outdir / f"worker_{i + 1:02d}.jsonl"
        with path.open("w", encoding="utf-8") as f:
            for task in shard:
                f.write(json.dumps(task, ensure_ascii=False, sort_keys=True) + "\n")
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "registry_path": str(registry_path.relative_to(ROOT)),
        "registry_sha256": snapshot_hash,
        "n_tools": len(tools),
        "n_perspectives": len(PERSPECTIVES),
        "n_annotation_tasks": len(tasks),
        "n_workers": workers,
        "assignment": "stable_round_robin",
        "perspectives": list(PERSPECTIVES),
        "worker_task_counts": [len(s) for s in shards],
        "leakage_controls": {
            "benchmark_task_queries_loaded": False,
            "benchmark_gold_tool_labels_loaded": False,
            "gold_labels_used_for_annotation": False,
        },
        "tool_definition_hashes": {t["tool_id"]: t["definition_hash"] for t in tools},
    }
    (outdir / "workpack_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=REGISTRY)
    parser.add_argument("--outdir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    print(json.dumps(build_workpacks(args.registry, args.outdir, args.workers),
                     indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
