"""E1: metadata-only characterization of the frozen merged MCP registry.

This module does not load task labels, silver labels, model outputs, policy decisions,
or evaluation helpers. It reads only the merged registry and pinned source manifest.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import os
import platform
import shutil
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

KNOWN_HINTS = ("readOnlyHint", "destructiveHint", "openWorldHint")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_definition_hash(tool: dict[str, Any]) -> str:
    payload = {
        "server": tool.get("server", ""),
        "name": tool.get("name", ""),
        "description": tool.get("description", ""),
        "inputSchema": tool.get("input_schema") or {},
        "outputSchema": tool.get("output_schema"),
        "annotations": tool.get("annotations"),
        "extra": tool.get("extra"),
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:32]


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    position = (len(ordered) - 1) * p
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    return float(ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower))


def summarize_numeric(values: Iterable[float]) -> dict[str, float | int | None]:
    vals = [float(value) for value in values]
    return {
        "n": len(vals),
        "mean": (sum(vals) / len(vals)) if vals else None,
        "median": percentile(vals, 0.5),
        "p90": percentile(vals, 0.9),
        "min": min(vals) if vals else None,
        "max": max(vals) if vals else None,
    }


def schema_type_counts(schema: Any, counts: Counter[str]) -> None:
    """Count declared JSON Schema types recursively; never infer semantic types."""
    if isinstance(schema, list):
        for item in schema:
            schema_type_counts(item, counts)
        return
    if not isinstance(schema, dict):
        return
    declared = schema.get("type")
    if isinstance(declared, str):
        counts[declared] += 1
    elif isinstance(declared, list):
        counts.update(item for item in declared if isinstance(item, str))
    for key in ("properties", "patternProperties", "definitions", "$defs"):
        child = schema.get(key)
        if isinstance(child, dict):
            for value in child.values():
                schema_type_counts(value, counts)
    for key in ("items", "additionalProperties", "not", "if", "then", "else"):
        if isinstance(schema.get(key), (dict, list)):
            schema_type_counts(schema[key], counts)
    for key in ("oneOf", "anyOf", "allOf", "prefixItems"):
        if isinstance(schema.get(key), list):
            schema_type_counts(schema[key], counts)


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str] | None = None) -> None:
    columns = columns or (list(rows[0]) if rows else [])
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        if columns:
            writer.writeheader()
            writer.writerows(rows)


def git_value(root: Path, *args: str) -> str | None:
    try:
        return subprocess.check_output(
            ["git", *args], cwd=root, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def hint_state(annotations: Any, key: str) -> str:
    if not isinstance(annotations, dict):
        return "no_annotations"
    if key not in annotations:
        return "missing_key"
    value = annotations[key]
    if value is True:
        return "true"
    if value is False:
        return "false"
    return "null" if value is None else "other"


def run_e1(root: str | Path, output_dir: str | Path, run_id: str | None = None) -> Path:
    root, output_dir = Path(root).resolve(), Path(output_dir).resolve()
    registry_path = root / "data/processed/registry_merged.json"
    sources_path = root / "data/raw/SOURCES.txt"
    catalog_path = root / "docs/experiment_design/pamcp_experiments_v1.json"
    for required in (registry_path, sources_path, catalog_path):
        if not required.is_file():
            raise FileNotFoundError(f"Required E1 input is missing: {required}")

    data = json.loads(registry_path.read_text(encoding="utf-8"))
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    spec = next((item for item in catalog.get("experiments", []) if item.get("id") == "E1"), None)
    if not spec or spec.get("title") != "Registry characterization":
        raise ValueError("The frozen catalogue does not contain the expected E1 definition")
    if spec.get("status") != "planned_not_run":
        raise ValueError("E1 is not planned_not_run; refusing to overwrite or rerun a completed entry")

    tools = data.get("registry")
    if not isinstance(tools, list) or not tools:
        raise ValueError("Merged registry must contain a non-empty registry array")

    registry_sha = sha256_file(registry_path)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = run_id or f"{stamp}_{registry_sha[:12]}"
    run_dir = output_dir / "E1" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    input_dir = run_dir / "inputs"
    input_dir.mkdir()

    frozen_registry = input_dir / "registry_merged.json.gz"
    with registry_path.open("rb") as source, gzip.open(frozen_registry, "wb", compresslevel=9) as target:
        shutil.copyfileobj(source, target)
    shutil.copy2(sources_path, input_dir / "SOURCES.txt")

    sources: Counter[str] = Counter()
    categories: Counter[tuple[str, str]] = Counter()
    servers: Counter[tuple[str, str]] = Counter()
    annotation_keys: Counter[str] = Counter()
    hint_values: Counter[tuple[str, str]] = Counter()
    schema_types: Counter[str] = Counter()
    description_lengths: list[int] = []
    input_property_counts: list[int] = []
    required_property_counts: list[int] = []
    description_present = input_schema_present = output_schema_present = annotations_present = 0
    malformed_rows: list[int] = []
    ids: Counter[str] = Counter()
    name_servers: dict[str, set[str]] = defaultdict(set)
    hash_mismatches: list[str] = []
    hashes_present = 0

    for index, tool in enumerate(tools):
        if not isinstance(tool, dict):
            malformed_rows.append(index)
            continue
        server = str(tool.get("server") or "").strip()
        name = str(tool.get("name") or "").strip()
        tool_id = str(tool.get("id") or (f"{server}::{name}" if server and name else "")).strip()
        if not server or not name or not tool_id:
            malformed_rows.append(index)
        if tool_id:
            ids[tool_id] += 1
        if name and server:
            name_servers[name].add(server)

        source = str(tool.get("source") or "unknown")
        category = str(tool.get("category") or "unspecified")
        sources[source] += 1
        categories[(source, category)] += 1
        servers[(source, server or "missing_server")] += 1

        description = str(tool.get("description") or "")
        description_lengths.append(len(description))
        description_present += bool(description.strip())

        input_schema, output_schema = tool.get("input_schema"), tool.get("output_schema")
        input_schema_present += isinstance(input_schema, dict) and bool(input_schema)
        output_schema_present += isinstance(output_schema, dict) and bool(output_schema)
        properties = input_schema.get("properties", {}) if isinstance(input_schema, dict) else {}
        required = input_schema.get("required", []) if isinstance(input_schema, dict) else []
        input_property_counts.append(len(properties) if isinstance(properties, dict) else 0)
        required_property_counts.append(len(required) if isinstance(required, list) else 0)
        schema_type_counts(input_schema, schema_types)
        schema_type_counts(output_schema, schema_types)

        annotations = tool.get("annotations")
        annotations_present += isinstance(annotations, dict) and bool(annotations)
        if isinstance(annotations, dict):
            annotation_keys.update(str(key) for key in annotations)
        for hint in KNOWN_HINTS:
            hint_values[(hint, hint_state(annotations, hint))] += 1

        if tool.get("hash"):
            hashes_present += 1
            if str(tool["hash"]) != canonical_definition_hash(tool):
                hash_mismatches.append(tool_id or f"row_{index}")

    n = len(tools)
    duplicate_ids = sorted(tool_id for tool_id, count in ids.items() if count > 1)
    name_collisions = [
        {"tool_name": name, "server_count": len(server_set), "servers": sorted(server_set)}
        for name, server_set in sorted(name_servers.items()) if len(server_set) > 1
    ]
    source_rows = [
        {"source": source, "tools": count, "share_of_registry": count / max(1, n)}
        for source, count in sorted(sources.items())
    ]
    category_rows = [
        {"source": source, "category": category, "tools": count,
         "share_within_source": count / max(1, sources[source])}
        for (source, category), count in sorted(categories.items())
    ]
    server_rows = [
        {"source": source, "server": server, "tools": count}
        for (source, server), count in sorted(servers.items())
    ]
    annotation_rows = [
        {"annotation_key": key, "tools_with_key": count, "share_of_registry": count / max(1, n)}
        for key, count in annotation_keys.most_common()
    ]
    hint_rows = [
        {"hint": hint, "value_state": state, "tools": count, "share_of_registry": count / max(1, n)}
        for (hint, state), count in sorted(hint_values.items())
    ]
    schema_rows = [{"json_schema_type": kind, "occurrences": count}
                   for kind, count in schema_types.most_common()]

    summary = {
        "experiment_id": "E1",
        "experiment_title": spec["title"],
        "interpretation": "Descriptive metadata characterization only; no safety or effectiveness claims.",
        "registry": {
            "tool_rows": n,
            "unique_tool_ids": len(ids),
            "duplicate_tool_ids": duplicate_ids,
            "source_server_pairs": len(servers),
            "source_count": len(sources),
            "source_distribution": source_rows,
        },
        "metadata_completeness": {
            "description_present": description_present,
            "description_missing_or_empty": n - description_present,
            "input_schema_present": input_schema_present,
            "input_schema_missing_or_empty": n - input_schema_present,
            "output_schema_present": output_schema_present,
            "output_schema_missing_or_empty": n - output_schema_present,
            "annotations_present": annotations_present,
            "annotations_missing_or_empty": n - annotations_present,
            "tools_with_published_hash": hashes_present,
            "published_hash_mismatches": len(hash_mismatches),
        },
        "annotation_hints": {
            "known_hints": list(KNOWN_HINTS),
            "values": {hint: {state: count for (key, state), count in hint_values.items() if key == hint}
                       for hint in KNOWN_HINTS},
            "key_frequency": dict(annotation_keys.most_common()),
        },
        "schema": {
            "description_characters": summarize_numeric(description_lengths),
            "top_level_input_properties": summarize_numeric(input_property_counts),
            "required_input_properties": summarize_numeric(required_property_counts),
            "declared_json_schema_types": dict(schema_types.most_common()),
        },
        "name_collisions_across_servers": name_collisions,
        "data_quality": {
            "rows_with_missing_server_name_or_id_zero_based": malformed_rows,
            "duplicate_tool_ids": duplicate_ids,
            "published_hash_mismatch_ids": hash_mismatches,
        },
        "guardrails": {
            "task_gold_labels_read": False,
            "silver_labels_read": False,
            "llm_records_read": False,
            "policy_decisions_made": False,
            "mcp_servers_executed": False,
            "semantics_inferred_from_names": False,
        },
    }

    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv(run_dir / "source_distribution.csv", source_rows)
    write_csv(run_dir / "category_by_source.csv", category_rows)
    write_csv(run_dir / "server_tool_counts.csv", server_rows)
    write_csv(run_dir / "annotation_key_frequency.csv", annotation_rows)
    write_csv(run_dir / "annotation_hint_distribution.csv", hint_rows)
    write_csv(run_dir / "schema_type_frequency.csv", schema_rows)
    write_csv(run_dir / "duplicate_names_across_servers.csv", name_collisions,
              ["tool_name", "server_count", "servers"])

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        category_names, source_names = sorted({row["category"] for row in category_rows}), sorted(sources)
        fig, ax = plt.subplots(figsize=(max(8, len(source_names) * 2.3), 5.5))
        bottom = [0] * len(source_names)
        for category in category_names:
            values = [categories[(source, category)] for source in source_names]
            ax.bar(source_names, values, bottom=bottom, label=category)
            bottom = [bottom[i] + values[i] for i in range(len(values))]
        ax.set(title="E1 — Registry tools by source and category",
               ylabel="Number of tool definitions", xlabel="Registry source")
        ax.legend(title="Category", bbox_to_anchor=(1.02, 1), loc="upper left")
        fig.tight_layout()
        fig.savefig(run_dir / "category_by_source.png", dpi=180)
        plt.close(fig)
    except ImportError:
        summary["plot_status"] = "matplotlib_not_installed"
        (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    artifacts = []
    for path in sorted(run_dir.rglob("*")):
        if path.is_file() and path.name != "MANIFEST.json":
            artifacts.append({"path": str(path.relative_to(run_dir)), "bytes": path.stat().st_size,
                              "sha256": sha256_file(path)})
    manifest = {
        "manifest_schema": "taas-experiment-run/1.0",
        "run_id": run_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "experiment": {"id": "E1", "title": spec["title"], "catalog_status_before_run": spec["status"]},
        "execution": {
            "execution_environment": "Google Colab" if "COLAB_RELEASE_TAG" in os.environ else "Python runtime",
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "git_branch": git_value(root, "rev-parse", "--abbrev-ref", "HEAD"),
            "git_commit": git_value(root, "rev-parse", "HEAD"),
        },
        "inputs": {
            "registry_path": "data/processed/registry_merged.json",
            "registry_sha256": registry_sha,
            "registry_gzip_snapshot_sha256": sha256_file(frozen_registry),
            "source_manifest_sha256": sha256_file(sources_path),
            "experiment_catalog_sha256": sha256_file(catalog_path),
            "runner_script_sha256": sha256_file(Path(__file__).resolve()),
        },
        "guardrails": summary["guardrails"],
        "artifacts": artifacts,
    }
    (run_dir / "MANIFEST.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return run_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Execute metadata-only E1 registry characterization")
    parser.add_argument("--root", default=".", help="Repository root")
    parser.add_argument("--output", default="results/colab", help="Artifact output directory")
    parser.add_argument("--run-id", default=None, help="Optional unique run identifier")
    args = parser.parse_args()
    path = run_e1(args.root, args.output, args.run_id)
    print(json.dumps({"status": "completed", "experiment": "E1", "artifact_dir": str(path)}, indent=2))


if __name__ == "__main__":
    main()
