"""Prepare blinded, paired human annotation files for PaMCP E2.

This prepares annotation work only. It does not predict types, label examples,
score models, or claim that E2 has run. The caller must preregister the sample
size, sampling design, seed, and dataset snapshot before running the script.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

KINDS = (
    "text", "document", "table", "record", "media", "credential", "identifier",
    "location", "number", "url", "path", "query", "code", "datetime", "boolean", "none",
)

ANNOTATION_COLUMNS = [
    "annotation_unit_id", "target_role", "field_name", "tool_name", "tool_description",
    "field_schema_json", "tool_input_schema_json", "tool_output_schema_json",
    "is_required_input", "is_target_schema_available", "type_kind", "type_domain",
    "is_collection", "is_uncertain", "confidence_0_1", "rationale",
]
MAPPING_COLUMNS = [
    "annotation_unit_id", "tool_id", "source", "category", "target_role", "field_name",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _proportional_stratified_sample(
    tools: list[dict[str, Any]], sample_size: int, seed: int
) -> list[dict[str, Any]]:
    """Proportional source×category sample; one item per stratum when feasible.

    This is an explicit design option, not silently imposed by the protocol.
    """
    strata: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for tool in tools:
        strata[(str(tool.get("source") or "unknown"),
                str(tool.get("category") or "unspecified"))].append(tool)
    keys = sorted(strata)
    if sample_size < len(keys):
        raise ValueError(
            f"stratified_source_category requires sample_size >= {len(keys)} "
            f"(one per non-empty source/category stratum); got {sample_size}"
        )
    if sample_size > len(tools):
        raise ValueError(f"sample_size {sample_size} exceeds registry size {len(tools)}")

    allocation = {key: 1 for key in keys}
    remaining = sample_size - len(keys)
    capacities = {key: len(strata[key]) - 1 for key in keys}
    total_capacity = sum(capacities.values())
    if remaining:
        if total_capacity == 0:
            raise ValueError("Requested sample size exceeds stratified capacity")
        quotas = {key: remaining * capacities[key] / total_capacity for key in keys}
        floors = {key: min(capacities[key], int(quotas[key])) for key in keys}
        for key in keys:
            allocation[key] += floors[key]
        left = remaining - sum(floors.values())
        order = sorted(keys, key=lambda key: (-(quotas[key] - floors[key]), key))
        for key in order:
            if left == 0:
                break
            if allocation[key] < len(strata[key]):
                allocation[key] += 1
                left -= 1
        if left:
            for key in keys:
                take = min(left, len(strata[key]) - allocation[key])
                allocation[key] += take
                left -= take
                if left == 0:
                    break
        if left:
            raise RuntimeError("Could not allocate the requested stratified sample")

    rng = random.Random(seed)
    selected: list[dict[str, Any]] = []
    for key in keys:
        group = sorted(strata[key], key=lambda tool: str(tool.get("id") or ""))
        selected.extend(rng.sample(group, allocation[key]))
    rng.shuffle(selected)
    return selected


def select_tools(
    tools: list[dict[str, Any]], sample_size: int, seed: int, sampling_design: str
) -> list[dict[str, Any]]:
    if sample_size < 1:
        raise ValueError("sample_size must be >= 1")
    if sample_size > len(tools):
        raise ValueError(f"sample_size {sample_size} exceeds registry size {len(tools)}")
    if sampling_design == "simple_random":
        ordered = sorted(tools, key=lambda tool: str(tool.get("id") or ""))
        return random.Random(seed).sample(ordered, sample_size)
    if sampling_design == "stratified_source_category":
        return _proportional_stratified_sample(tools, sample_size, seed)
    raise ValueError(f"Unsupported sampling design: {sampling_design}")


def _stable_unit_id(seed: int, tool_id: str, role: str, field_name: str) -> str:
    payload = f"{seed}\0{tool_id}\0{role}\0{field_name}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:20]


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def make_units(
    tools: list[dict[str, Any]], seed: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    annotation_rows: list[dict[str, Any]] = []
    mapping_rows: list[dict[str, Any]] = []
    for tool in tools:
        tool_id = str(tool.get("id") or f"{tool.get('server', '')}::{tool.get('name', '')}")
        if not tool_id or tool_id == "::":
            raise ValueError("Every sampled tool must have a stable server::name ID")
        input_schema = tool.get("input_schema") or {}
        output_schema = tool.get("output_schema")
        properties = input_schema.get("properties", {}) if isinstance(input_schema, dict) else {}
        required = set(input_schema.get("required", [])) if isinstance(input_schema, dict) else set()
        if not isinstance(properties, dict):
            properties = {}

        targets: list[tuple[str, str, Any, bool, bool]] = []
        for field_name, field_schema in sorted(properties.items()):
            targets.append(("input", str(field_name), field_schema,
                            field_name in required, isinstance(field_schema, (dict, list))))
        # Retain missing output schemas: uncertainty is a valid annotation outcome.
        targets.append(("output", "$return", output_schema, False,
                        isinstance(output_schema, (dict, list)) and bool(output_schema)))

        for role, field_name, field_schema, is_required, schema_available in targets:
            unit_id = _stable_unit_id(seed, tool_id, role, field_name)
            annotation_rows.append({
                "annotation_unit_id": unit_id,
                "target_role": role,
                "field_name": field_name,
                "tool_name": str(tool.get("name") or ""),
                "tool_description": str(tool.get("description") or ""),
                "field_schema_json": _json(field_schema) if field_schema is not None else "",
                "tool_input_schema_json": _json(input_schema),
                "tool_output_schema_json": _json(output_schema) if output_schema is not None else "",
                "is_required_input": str(bool(is_required)).lower() if role == "input" else "",
                "is_target_schema_available": str(bool(schema_available)).lower(),
                "type_kind": "",
                "type_domain": "",
                "is_collection": "",
                "is_uncertain": "",
                "confidence_0_1": "",
                "rationale": "",
            })
            mapping_rows.append({
                "annotation_unit_id": unit_id,
                "tool_id": tool_id,
                "source": str(tool.get("source") or "unknown"),
                "category": str(tool.get("category") or "unspecified"),
                "target_role": role,
                "field_name": field_name,
            })
    return annotation_rows, mapping_rows


def _write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def prepare_annotation_tasks(
    registry_path: str | Path,
    output_dir: str | Path,
    sample_size: int,
    seed: int,
    sampling_design: str,
) -> Path:
    registry_path, output_dir = Path(registry_path).resolve(), Path(output_dir).resolve()
    if not registry_path.is_file():
        raise FileNotFoundError(registry_path)
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite existing annotation package: {output_dir}")

    data = json.loads(registry_path.read_text(encoding="utf-8"))
    tools = data.get("registry")
    if not isinstance(tools, list) or not tools:
        raise ValueError("Registry input must contain a non-empty 'registry' array")
    if any(not isinstance(tool, dict) for tool in tools):
        raise ValueError("Registry contains non-object tool rows")
    ids = [str(tool.get("id") or f"{tool.get('server', '')}::{tool.get('name', '')}")
           for tool in tools]
    if len(set(ids)) != len(ids):
        raise ValueError("Registry contains duplicate tool IDs; resolve before sampling")

    selected = select_tools(tools, sample_size, seed, sampling_design)
    annotation_rows, mapping_rows = make_units(selected, seed)
    output_dir.mkdir(parents=True)

    # Same units, separately randomized ordering, and no prediction/gold fields.
    rows_a, rows_b = list(annotation_rows), list(annotation_rows)
    random.Random(seed ^ 0xA17A).shuffle(rows_a)
    random.Random(seed ^ 0xB29B).shuffle(rows_b)
    _write_csv(output_dir / "annotator_A.csv", rows_a, ANNOTATION_COLUMNS)
    _write_csv(output_dir / "annotator_B.csv", rows_b, ANNOTATION_COLUMNS)
    _write_csv(output_dir / "restricted_mapping.csv", mapping_rows, MAPPING_COLUMNS)

    strata_counts: dict[str, int] = defaultdict(int)
    for tool in selected:
        key = f"{tool.get('source') or 'unknown'}::{tool.get('category') or 'unspecified'}"
        strata_counts[key] += 1
    manifest = {
        "experiment_id": "E2",
        "artifact_kind": "human_annotation_intake_only",
        "status": "prepared_not_run",
        "input_registry_sha256": sha256_file(registry_path),
        "registry_tool_count": len(tools),
        "sample_size_tools": sample_size,
        "sampled_tool_count": len(selected),
        "annotation_unit_count": len(annotation_rows),
        "sampling_design": sampling_design,
        "seed": seed,
        "strata_tool_counts": dict(sorted(strata_counts.items())),
        "annotators_required": 2,
        "independent_annotation": True,
        "annotation_order_independently_shuffled": True,
        "model_predictions_in_annotation_sheets": False,
        "llm_silver_labels_used_as_gold": False,
        "sampled_tool_ids": sorted(ids[tools.index(tool)] for tool in selected),
        "semantic_type_kinds": list(KINDS),
        "required_model_evidence_conditions": [
            "schema_only", "schema_plus_name_description", "schema_plus_probe_output"
        ],
        "required_certainty_thresholds": [0.5, 0.7, 0.9],
        "notes": [
            "Sample size, seed, and sampling design are explicit preregistration parameters; the source protocol does not prescribe their values.",
            "No type labels are generated; only two blank human annotation sheets are produced.",
            "Keep restricted_mapping.csv from annotators; join only after both annotation files are frozen.",
        ],
    }
    (output_dir / "sample_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    checksums = {
        path.name: sha256_file(path)
        for path in sorted(output_dir.iterdir())
        if path.is_file() and path.name != "SHA256SUMS.json"
    }
    (output_dir / "SHA256SUMS.json").write_text(
        json.dumps(checksums, indent=2) + "\n", encoding="utf-8"
    )
    return output_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare independent human annotation files for E2")
    parser.add_argument("--registry", required=True, help="Path to frozen registry_merged.json")
    parser.add_argument("--output", required=True, help="New output directory; must not exist")
    parser.add_argument("--sample-size", required=True, type=int,
                        help="Number of tools; preregister this before annotation")
    parser.add_argument("--seed", required=True, type=int, help="Frozen sampling seed")
    parser.add_argument("--sampling-design", required=True,
                        choices=["simple_random", "stratified_source_category"])
    args = parser.parse_args()
    output = prepare_annotation_tasks(args.registry, args.output, args.sample_size,
                                      args.seed, args.sampling_design)
    print(json.dumps({"status": "prepared_not_run", "experiment": "E2",
                      "annotation_package": str(output)}, indent=2))


if __name__ == "__main__":
    main()
