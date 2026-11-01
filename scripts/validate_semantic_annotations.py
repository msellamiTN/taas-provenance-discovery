#!/usr/bin/env python3
"""Validate and reconcile independent GPT semantic annotations against their blind workpack."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def read_jsonl(path: Path):
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                yield line_no, json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc


def validate(workpack_dir: Path, annotation_files: list[Path], out: Path) -> dict[str, Any]:
    manifest = json.loads((workpack_dir / "workpack_manifest.json").read_text(encoding="utf-8"))
    expected: dict[str, dict[str, Any]] = {}
    for shard in sorted(workpack_dir.glob("worker_*.jsonl")):
        for _, item in read_jsonl(shard):
            expected[item["task_id"]] = item

    required = {
        "task_id", "tool_id", "definition_hash", "annotator_session_id", "model_id",
        "perspective", "primary_capability", "secondary_capabilities", "domain", "operation",
        "input_semantics", "output_semantics", "effect_claims", "state_mutation",
        "data_sensitivity", "prerequisites", "composition", "confidence", "evidence", "uncertainties",
    }
    seen: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for path in annotation_files:
        for line_no, row in read_jsonl(path):
            label = f"{path}:{line_no}"
            missing = sorted(required - set(row))
            if missing:
                errors.append(f"{label}: missing fields {missing}")
                continue
            task_id = row["task_id"]
            if task_id not in expected:
                errors.append(f"{label}: unknown task_id {task_id}")
                continue
            if task_id in seen:
                errors.append(f"{label}: duplicate task_id {task_id}")
                continue
            work = expected[task_id]
            if row["tool_id"] != work["tool_id"]:
                errors.append(f"{label}: tool_id mismatch for {task_id}")
            if row["definition_hash"] != work["definition_hash"]:
                errors.append(f"{label}: stale or mismatched definition hash for {task_id}")
            if row["perspective"] != work["perspective"]:
                errors.append(f"{label}: perspective mismatch for {task_id}")
            if row["state_mutation"] not in {"yes", "no_explicitly_claimed", "unknown"}:
                errors.append(f"{label}: invalid state_mutation")
            if row["primary_capability"] not in {
                "retrieve", "search", "create", "update", "delete", "execute", "transform",
                "analyze", "communicate", "plan", "render", "monitor", "configure", "manage",
                "authenticate", "other", "unknown",
            }:
                errors.append(f"{label}: invalid primary_capability")
            if not isinstance(row["confidence"], (int, float)) or not 0 <= row["confidence"] <= 1:
                errors.append(f"{label}: confidence must be in [0,1]")
            if not row["evidence"]:
                errors.append(f"{label}: evidence must not be empty; use an uncertainty if ungrounded")
            # Validate exact quoted evidence against the corresponding tool definition.
            definition = work["definition"]
            for ev in row["evidence"]:
                field = ev.get("source_field")
                span = ev.get("verbatim_span", "")
                source_value = {
                    "name": definition.get("name", ""),
                    "description": definition.get("description", ""),
                    "input_schema": json.dumps(definition.get("input_schema") or {}, ensure_ascii=False),
                    "output_schema": json.dumps(definition.get("output_schema"), ensure_ascii=False),
                    "annotations": json.dumps(definition.get("annotations"), ensure_ascii=False),
                    "category": definition.get("category", ""),
                }.get(field)
                if source_value is None or not span or span not in source_value:
                    errors.append(f"{label}: evidence span is not present in source field {field!r}")
            seen[task_id] = row

    missing_tasks = sorted(set(expected) - set(seen))
    by_tool: dict[str, list[dict[str, Any]]] = {}
    for row in seen.values():
        by_tool.setdefault(row["tool_id"], []).append(row)
    disagreements = []
    for tool_id, rows in sorted(by_tool.items()):
        if len(rows) == 2:
            a, b = rows
            if a["primary_capability"] != b["primary_capability"]:
                disagreements.append({
                    "tool_id": tool_id,
                    "capability_A": a["primary_capability"],
                    "capability_B": b["primary_capability"],
                    "task_ids": [a["task_id"], b["task_id"]],
                    "status": "requires_adjudication",
                })
    report = {
        "schema_version": "taas-semantic-annotation-validation/1.0",
        "registry_sha256": manifest["registry_sha256"],
        "expected_annotation_tasks": len(expected),
        "received_annotation_tasks": len(seen),
        "missing_annotation_tasks": missing_tasks,
        "n_errors": len(errors),
        "errors": errors,
        "n_tools_with_two_annotations": sum(len(v) == 2 for v in by_tool.values()),
        "n_primary_capability_disagreements": len(disagreements),
        "disagreements": disagreements,
        "perspective_counts": dict(Counter(r["perspective"] for r in seen.values())),
        "validation_passed": not errors and not missing_tasks,
        "merge_policy": "No majority vote. Disagreements and uncertainty remain explicit; adjudication is a separate stage.",
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workpack-dir", type=Path, required=True)
    parser.add_argument("--annotations", type=Path, nargs="+", required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result = validate(args.workpack_dir, args.annotations, args.report)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["validation_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
