#!/usr/bin/env python3
"""Prepare evaluator-separated E9 LiveMCPBench data from the pinned snapshot.

The source paper describes task proposers completing tasks with the toolset and
validators scrutinizing the associated toolchain invocations. For a strict,
resolvable subset, each such toolchain is one benchmark-native successful
reference set. It is not an exhaustive enumeration of all valid alternatives.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_REVISION = "36a51a1065dda49c1e503b87edf33a1e0b331a74"
EXPECTED_TOOL_COUNT = 525
EXPECTED_SERVER_COUNT = 69


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def source_revision(path: Path) -> str:
    pins: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if len(fields) >= 2:
            pins[fields[0].casefold()] = fields[1]
    revision = pins.get("livemcpbench")
    if revision != EXPECTED_REVISION:
        raise ValueError(
            f"LiveMCPBench source revision mismatch: expected {EXPECTED_REVISION}, "
            f"got {revision!r}"
        )
    return revision


def parse_tool_names(value: str) -> list[str]:
    names: list[str] = []
    for line in (value or "").splitlines():
        name = re.sub(r"^\s*\d+\s*[\.\)]\s*", "", line.strip())
        name = name.strip().strip('"').strip("'").strip()
        if name:
            names.append(name)
    return names


def resolve_name(name: str, by_name: dict[str, list[str]]) -> list[str]:
    candidates = sorted(by_name.get(name, []))
    browser_ids = [
        tool_id for tool_id in candidates
        if tool_id.startswith(("puppeteer::", "playwright::"))
    ]
    non_browser = [tool_id for tool_id in candidates if tool_id not in browser_ids]
    return non_browser or candidates


def build_acceptable_sets(
    reference_choices: list[dict[str, Any]],
    max_alternatives: int = 256,
) -> list[list[str]]:
    """Expand ambiguous names so every candidate identity is accepted."""
    candidate_lists = [
        sorted(set(str(tool_id) for tool_id in choice["candidate_tool_ids"]))
        for choice in reference_choices
        if choice.get("candidate_tool_ids")
    ]
    if not candidate_lists:
        return []
    product_size = 1
    for candidates in candidate_lists:
        product_size *= len(candidates)
        if product_size > max_alternatives:
            raise ValueError(
                f"Reference identity expansion exceeds {max_alternatives}; "
                "manual source review is required."
            )
    alternatives = {
        tuple(sorted(set(combination)))
        for combination in itertools.product(*candidate_lists)
        if combination
    }
    return [list(group) for group in sorted(alternatives)]


def prepare(
    registry_path: Path,
    annotations_path: Path,
    sources_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    registry_path = registry_path.resolve()
    annotations_path = annotations_path.resolve()
    sources_path = sources_path.resolve()
    output_dir = output_dir.resolve()

    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite existing E9 preparation directory: {output_dir}")
    for path in (registry_path, annotations_path, sources_path):
        if not path.is_file():
            raise FileNotFoundError(path)

    revision = source_revision(sources_path)
    registry_doc = json.loads(registry_path.read_text(encoding="utf-8"))
    registry_all = registry_doc.get("registry")
    if not isinstance(registry_all, list):
        raise ValueError("registry_merged.json must contain a registry array")

    # E9 LiveMCPBench uses its own LiveMCPTool registry, not the 569-tool E1
    # union that additionally contains MCPToolBench++ definitions.
    registry = [row for row in registry_all if row.get("source") == "LiveMCPTool"]
    ids = [str(row.get("id") or "") for row in registry]
    servers = {str(row.get("server") or "") for row in registry}

    if not registry or any(not item for item in ids) or len(ids) != len(set(ids)):
        raise ValueError("LiveMCPTool registry contains missing or duplicate stable tool IDs")
    if "" in servers:
        raise ValueError("LiveMCPTool registry contains a tool without server identity")
    if len(registry) != EXPECTED_TOOL_COUNT or len(servers) != EXPECTED_SERVER_COUNT:
        raise ValueError(
            f"Pinned registry drift: expected {EXPECTED_TOOL_COUNT} tools/"
            f"{EXPECTED_SERVER_COUNT} servers, got {len(registry)}/{len(servers)}"
        )

    by_name: dict[str, list[str]] = {}
    for row in registry:
        by_name.setdefault(str(row.get("name") or ""), []).append(str(row["id"]))

    annotations = json.loads(annotations_path.read_text(encoding="utf-8"))
    if not isinstance(annotations, list) or len(annotations) != 95:
        count = len(annotations) if isinstance(annotations, list) else "non-list"
        raise ValueError(f"Expected 95 pinned LiveMCPBench tasks; found {count}")

    discovery_tools: list[dict[str, Any]] = []
    for row in registry:
        discovery_tools.append({
            "dataset_id": "livemcpbench",
            "tool_id": row["id"],
            "server_id": row["server"],
            "name": row.get("name") or "",
            "description": row.get("description") or "",
            "input_schema": row.get("input_schema") or {},
            "output_schema": row.get("output_schema") or {},
            "annotations": row.get("annotations") or {},
            "definition_hash": row.get("hash") or "",
        })

    visible_ids = sorted(ids)
    discovery_tasks: list[dict[str, Any]] = []
    visibility_rows: list[dict[str, Any]] = []
    evaluator_refs: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    counts = {
        "tasks_total": len(annotations),
        "tasks_primary_eligible": 0,
        "tasks_excluded_no_resolvable_gold": 0,
        "tasks_with_ambiguous_tool_mentions": 0,
        "tasks_with_unresolved_tool_mentions": 0,
        "tasks_with_declared_tool_count_mismatch": 0,
        "tool_mentions_total": 0,
        "tool_mentions_unique_identity": 0,
        "tool_mentions_ambiguous_identity": 0,
        "tool_mentions_unresolved": 0,
        "tool_identity_candidates_from_ambiguous_mentions": 0,
        "acceptable_set_alternatives_total": 0,
        "maximum_alternatives_per_task": 0,
    }
    seen: set[str] = set()
    annotations_hash = sha256_file(annotations_path)

    for row in annotations:
        task_id = str(row.get("task_id") or "").strip()
        prompt = str(row.get("Question") or "").strip()
        category = str(row.get("category") or "unspecified")
        metadata = row.get("Annotator Metadata") or {}
        names = parse_tool_names(str(metadata.get("Tools") or ""))
        try:
            declared_count = int(metadata.get("Number of tools") or len(names))
        except (TypeError, ValueError):
            declared_count = -1

        if not task_id or not prompt or task_id in seen:
            raise ValueError(f"Empty, invalid or duplicate task ID: {task_id!r}")
        seen.add(task_id)
        counts["tool_mentions_total"] += len(names)

        reference_choices: list[dict[str, Any]] = []
        unique_ids: list[str] = []
        ambiguous: list[dict[str, Any]] = []
        unresolved: list[str] = []

        for name in names:
            candidates = resolve_name(name, by_name)
            if len(candidates) == 1:
                unique_ids.append(candidates[0])
                counts["tool_mentions_unique_identity"] += 1
                reference_choices.append({
                    "tool_name": name,
                    "candidate_tool_ids": candidates,
                    "identity_status": "unique",
                })
            elif candidates:
                ambiguous.append({
                    "tool_name": name,
                    "candidate_tool_ids": candidates,
                })
                counts["tool_mentions_ambiguous_identity"] += 1
                counts["tool_identity_candidates_from_ambiguous_mentions"] += len(candidates)
                reference_choices.append({
                    "tool_name": name,
                    "candidate_tool_ids": candidates,
                    "identity_status": "ambiguous_any_candidate_accepted",
                })
            else:
                unresolved.append(name)
                counts["tool_mentions_unresolved"] += 1

        if ambiguous:
            counts["tasks_with_ambiguous_tool_mentions"] += 1
        if unresolved:
            counts["tasks_with_unresolved_tool_mentions"] += 1

        count_matches = declared_count == len(names)
        if not count_matches:
            counts["tasks_with_declared_tool_count_mismatch"] += 1

        # Protocol denominator: retain every task with at least one resolvable gold
        # tool mention. For an ambiguous mention, any candidate identity is accepted.
        # Missing names remain disclosed in the audit but are not fabricated as tools.
        acceptable_sets = build_acceptable_sets(reference_choices)
        if acceptable_sets:
            visible_set = set(visible_ids)
            if any(not set(group).issubset(visible_set) for group in acceptable_sets):
                raise ValueError(f"{task_id}: acceptable reference includes a tool outside the candidate registry")

            discovery_tasks.append({
                "dataset_id": "livemcpbench",
                "task_id": task_id,
                "prompt": prompt,
                "task_group": category,
                "split": "benchmark_evaluation",
            })
            visibility_rows.append({
                "dataset_id": "livemcpbench",
                "task_id": task_id,
                "visible_tool_ids": visible_ids,
            })
            evaluator_refs.append({
                "dataset_id": "livemcpbench",
                "benchmark": "live_mcpbench",
                "task_id": task_id,
                "reference_semantics": "benchmark_native_acceptable_sets",
                "acceptable_tool_sets": acceptable_sets,
                "reference_tool_choices": reference_choices,
                "reference_tool_names": names,
                "unresolved_gold_names": unresolved,
                "declared_tool_count": declared_count,
                "parsed_tool_mention_count": len(names),
                "declared_tool_count_matches_parsed_mentions": count_matches,
                "reference_source": (
                    "LiveMCPBench proposer-completed task/toolchain, validator-scrutinized"
                ),
                "reference_source_revision": revision,
                "reference_source_sha256": annotations_hash,
                "reference_scope": (
                    "One benchmark-validated successful toolchain, with any candidate "
                    "server::tool identity accepted for ambiguous annotated names; "
                    "unresolved names are omitted. Not an exhaustive list of all "
                    "alternative valid toolchains."
                ),
                "independent_unit_id": task_id,
            })
            counts["tasks_primary_eligible"] += 1
            counts["acceptable_set_alternatives_total"] += len(acceptable_sets)
            counts["maximum_alternatives_per_task"] = max(
                counts["maximum_alternatives_per_task"], len(acceptable_sets)
            )
            if ambiguous:
                status = "primary_eligible_with_identity_alternatives"
            elif unresolved:
                status = "primary_eligible_with_missing_mentions"
            else:
                status = "primary_eligible_unique_identity"
        else:
            counts["tasks_excluded_no_resolvable_gold"] += 1
            status = "excluded_no_resolvable_gold"

        audit_rows.append({
            "task_id": task_id,
            "category": category,
            "declared_tool_count": declared_count,
            "parsed_tool_mentions": len(names),
            "resolved_tool_mentions": len(reference_choices),
            "unique_identity_mentions": len(unique_ids),
            "ambiguous_tool_mentions": json.dumps(ambiguous, ensure_ascii=False),
            "unresolved_tool_names": json.dumps(unresolved, ensure_ascii=False),
            "count_matches": str(count_matches).lower(),
            "acceptable_set_alternative_count": len(acceptable_sets),
            "status": status,
        })

    expected = {
        "tasks_total": 95,
        "tasks_primary_eligible": 94,
        "tasks_excluded_no_resolvable_gold": 1,
        "tool_mentions_total": 256,
        "tool_mentions_unique_identity": 222,
        "tool_mentions_ambiguous_identity": 29,
        "tool_mentions_unresolved": 5,
    }
    for key, value in expected.items():
        if counts[key] != value:
            raise ValueError(
                f"LiveMCPBench protocol-scope drift for {key}: expected {value}, got {counts[key]}"
            )

    output_dir.mkdir(parents=True)
    write_json(output_dir / "discovery" / "tools.json", discovery_tools)
    write_jsonl(output_dir / "discovery" / "tasks.jsonl", discovery_tasks)
    write_jsonl(output_dir / "discovery" / "task_visibility.jsonl", visibility_rows)
    write_jsonl(output_dir / "evaluator" / "task_references.jsonl", evaluator_refs)
    write_csv(
        output_dir / "evaluator" / "reference_resolution_audit.csv",
        audit_rows,
        [
            "task_id", "category", "declared_tool_count", "parsed_tool_mentions",
            "resolved_tool_mentions", "unique_identity_mentions", "ambiguous_tool_mentions",
            "unresolved_tool_names", "count_matches", "acceptable_set_alternative_count", "status",
        ],
    )

    manifest = {
        "schema_version": "1.0.0",
        "experiment_id": "E9",
        "artifact_kind": "dataset_preparation_not_experiment_run",
        "status": "prepared_not_run",
        "benchmark": "LiveMCPBench",
        "source_revision": revision,
        "source_files": {
            "annotations": {
                "path": str(annotations_path),
                "sha256": annotations_hash,
            },
            "registry": {
                "path": str(registry_path),
                "sha256": sha256_file(registry_path),
            },
            "source_pins": {
                "path": str(sources_path),
                "sha256": sha256_file(sources_path),
            },
        },
        "candidate_registry_view": (
            "LiveMCPTool only; MCPToolBench++ is not merged into E9 candidates"
        ),
        "candidate_tool_count": len(discovery_tools),
        "candidate_server_count": len(servers),
        "primary_reference_semantics": (
            "one benchmark-validated successful toolchain per eligible task; ambiguous "
            "annotated names expand to all candidate server::tool identities"
        ),
        "protocol_denominator": (
            "94 tasks with at least one resolvable gold tool mention, from the 95-task public set"
        ),
        "not_claimed": [
            "All possible valid toolchains are enumerated.",
            "A positive reference chain is the only acceptable solution.",
            "LiveMCPEval task success is equivalent to retrieval set precision.",
        ],
        "resolution": counts,
        "exclusion_policy": {
            "ambiguous_tool_names": (
                "include all candidate server::tool identities as acceptable alternatives; any candidate counts"
            ),
            "unresolved_tool_names": (
                "retain names in the evaluator audit; omit unresolved mentions from the resolvable reference set"
            ),
            "declared_tool_count_mismatch": (
                "record as an audit flag; do not exclude a task when at least one gold tool resolves"
            ),
            "no_resolvable_gold": "exclude only tasks with no resolvable gold tool mention",
        },
        "separation": {
            "discovery_tools": "discovery/tools.json",
            "discovery_tasks": "discovery/tasks.jsonl",
            "discovery_visibility": "discovery/task_visibility.jsonl",
            "evaluator_acceptable_sets": "evaluator/task_references.jsonl",
            "resolution_audit": "evaluator/reference_resolution_audit.csv",
            "gold_labels_exposed_to_discovery": False,
        },
        "limitations": [
            "This prepares tasks/references only; it contains no method rankings or E9 scores.",
            "Each eligible task has one successful benchmark-validated reference toolchain; alternatives may exist.",
            "Ambiguous tool names are represented by Cartesian acceptable-set alternatives over all candidate identities; this does not claim alternative task solutions beyond those identity ambiguities.",
            "Five source tool mentions do not resolve to a candidate tool; they remain in the audit and are omitted from the resolvable reference sets.",
            "Declared Number of tools mismatches remain visible in the audit and do not independently exclude otherwise resolvable tasks.",
            "Native LiveMCPBench task-success evaluation requires its runtime and LiveMCPEval judge.",
        ],
    }
    write_json(output_dir / "PREPARATION_MANIFEST.json", manifest)
    hashes = {
        path.relative_to(output_dir).as_posix(): sha256_file(path)
        for path in sorted(output_dir.rglob("*"))
        if path.is_file()
    }
    write_json(output_dir / "SHA256SUMS.json", hashes)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=ROOT / "data/processed/registry_merged.json")
    parser.add_argument("--annotations", type=Path, default=ROOT / "data/raw/livemcpbench/all_annotations.json")
    parser.add_argument("--sources", type=Path, default=ROOT / "data/raw/SOURCES.txt")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.registry, args.annotations, args.sources, args.output)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
