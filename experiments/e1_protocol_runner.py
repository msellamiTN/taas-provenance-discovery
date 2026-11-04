"""Protocol-conformant E1 registry characterization.

Rebuilds LiveMCPTool, MCPToolBench++ and merged views from the pinned raw
sources. Silver LLM labels are never read. Without a complete independent
reference-label file, descriptive outputs are preserved but the run status is
"failed"; the experiment is not declared complete.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import random
import shutil
import subprocess
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any

import jsonschema
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from taas.data.registries import (
    RawTool, build_all, load_livemcptool, load_mcptoolbenchpp, merge_registries
)

EXPECTED = {
    "LiveMCPTool": {"tools": 525, "servers": 69},
    "MCPToolBench++": {"tools": 87, "servers": 10},
    "merged": {"tools": 569, "servers": 76},
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def hash_json(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    x = sorted(values)
    pos = (len(x) - 1) * p
    lo, hi = int(pos), int(-(-pos // 1))
    return float(x[lo] + (x[hi] - x[lo]) * (pos - lo))


def stats(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0, "mean": None, "median": None, "p90": None, "min": None, "max": None}
    return {
        "n": len(values), "mean": float(mean(values)), "median": float(median(values)),
        "p90": percentile(values, .90), "min": float(min(values)), "max": float(max(values))
    }


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    fields = fields or (list(rows[0]) if rows else [])
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if fields:
            w.writeheader()
            w.writerows(rows)


def tool_key(tool: RawTool) -> tuple[str, str]:
    return tool.id, tool.definition_hash()


def load_reference_labels(path: Path | None) -> dict[tuple[str, str], bool] | None:
    if path is None:
        return None
    d = json.loads(path.read_text(encoding="utf-8"))
    if d.get("schema_version") != "1.0.0":
        raise ValueError("Reference label schema_version must be 1.0.0")
    if d.get("label_source") != "independent_human_reference":
        raise ValueError("Only independent human reference labels are admissible")
    if d.get("independent_of_silver_labels") is not True or d.get("generated_by_model") is not False:
        raise ValueError("Reference labels must be explicitly independent of model/silver labels")
    rows = d.get("labels")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Reference label file has no labels")
    result: dict[tuple[str, str], bool] = {}
    for row in rows:
        key = (str(row.get("tool_id") or ""), str(row.get("definition_hash") or ""))
        if not key[0] or len(key[1]) != 64 or not isinstance(row.get("non_read_only"), bool):
            raise ValueError("Each label requires tool_id, full SHA-256 definition_hash and boolean non_read_only")
        if key in result:
            raise ValueError(f"Duplicate reference label for {key[0]}")
        result[key] = row["non_read_only"]
    return result


def summarize_view(name: str, tools: list[RawTool],
                   labels: dict[tuple[str, str], bool] | None) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    by_server: dict[str, list[RawTool]] = defaultdict(list)
    categories: Counter[str] = Counter()
    annotated = ro_true = ro_false = ro_missing = ro_null = 0
    desc_lengths = []
    labelled = non_read_only = 0
    for t in tools:
        by_server[t.server].append(t)
        categories[t.category or "unspecified"] += 1
        desc_lengths.append(len(t.description or ""))
        ann = t.annotations or {}
        annotated += bool(ann)
        if "readOnlyHint" not in ann:
            ro_missing += 1
        elif ann.get("readOnlyHint") is None:
            ro_null += 1
        elif ann.get("readOnlyHint") is True:
            ro_true += 1
        elif ann.get("readOnlyHint") is False:
            ro_false += 1
        if labels is not None and tool_key(t) in labels:
            labelled += 1
            non_read_only += int(labels[tool_key(t)])
    n = len(tools)
    full = labels is not None and labelled == n
    per_server = [len(v) for v in by_server.values()]
    s = {
        "registry": name, "tool_count": n, "server_count": len(by_server),
        "category_count": len(categories), "category_distribution": dict(sorted(categories.items())),
        "annotated_tool_count": annotated, "annotated_tool_share": annotated / n,
        "declared_read_only_true_count": ro_true,
        "declared_read_only_share_of_all_tools": ro_true / n,
        "declared_read_only_share_of_annotated_tools": ro_true / annotated if annotated else None,
        "declared_read_only_false_count": ro_false, "read_only_hint_missing_count": ro_missing,
        "read_only_hint_null_count": ro_null,
        "tools_per_server": stats([float(x) for x in per_server]),
        "description_length_chars": stats([float(x) for x in desc_lengths]),
        "reference_labels": {
            "labelled_tool_definitions": labelled, "unlabelled_tool_definitions": n - labelled,
            "coverage": labelled / n, "non_read_only_count": non_read_only if full else None,
            "non_read_only_share": non_read_only / n if full else None,
            "metric_status": "complete" if full else "blocked_incomplete_independent_reference_labels",
        },
    }
    cat_rows = [
        {"registry": name, "category": cat, "tools": count, "share_of_registry": count / n}
        for cat, count in sorted(categories.items())
    ]
    server_rows = [
        {"registry": name, "server": server, "tool_count": len(server_tools),
         "category": server_tools[0].category or "unspecified"}
        for server, server_tools in sorted(by_server.items())
    ]
    return s, cat_rows, server_rows


def write_reference_intake(views: dict[str, list[RawTool]], run_dir: Path) -> int:
    unique: dict[tuple[str, str], RawTool] = {}
    view_names: dict[tuple[str, str], set[str]] = defaultdict(set)
    for view, tools in views.items():
        for tool in tools:
            key = tool_key(tool)
            unique.setdefault(key, tool)
            view_names[key].add(view)
    rows, mapping = [], []
    for (tool_id, definition_hash), tool in sorted(unique.items()):
        unit = hashlib.sha256((tool_id + "\0" + definition_hash).encode()).hexdigest()[:24]
        rows.append({
            "annotation_unit_id": unit, "server": tool.server, "tool_name": tool.name,
            "description": tool.description or "",
            "input_schema_json": json.dumps(tool.input_schema or {}, sort_keys=True, ensure_ascii=False),
            "output_schema_json": json.dumps(tool.output_schema, sort_keys=True, ensure_ascii=False)
                                 if tool.output_schema is not None else "",
            "annotations_json": json.dumps(tool.annotations, sort_keys=True, ensure_ascii=False)
                                if tool.annotations is not None else "",
            "non_read_only": "", "effect_classes": "", "confidence_0_1": "", "rationale": "",
        })
        mapping.append({
            "annotation_unit_id": unit, "tool_id": tool_id, "definition_hash": definition_hash,
            "registry_views": ";".join(sorted(view_names[(tool_id, definition_hash)])),
        })
    fields = list(rows[0])
    write_csv(run_dir / "reference_effect_annotator_A.csv", rows, fields)
    shuffled = list(rows)
    random.Random(20261104).shuffle(shuffled)
    write_csv(run_dir / "reference_effect_annotator_B.csv", shuffled, fields)
    write_csv(run_dir / "restricted_reference_mapping.csv", mapping)
    return len(unique)


def git_value(root: Path, *args: str) -> str | None:
    try:
        return subprocess.check_output(["git", *args], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def render_report(rows: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    out = [
        "# E1 — Registry characterization", "",
        "Protocol: PaMCP Experimental Specification v1.0.0", "",
        f"Run metric gate: {summary['reference_labels']['status']}", "",
        "| Registry | Tools | Servers | Categories | Annotated share | Declared read-only share | Reference non-read-only share |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        ref = "BLOCKED" if r["reference_non_read_only_share"] is None else f"{r['reference_non_read_only_share']:.4f}"
        out.append(
            f"| {r['registry']} | {r['tools']} | {r['servers']} | {r['categories']} | "
            f"{r['annotated_share']:.4f} | {r['declared_read_only_share']:.4f} | {ref} |"
        )
    out += [
        "", "## Reference-label gate", "",
        f"Status: {summary['reference_labels']['status']}.",
        f"Human reference labels: {summary['reference_labels']['labelled_definition_count']} / "
        f"{summary['reference_labels']['required_definition_count']} unique source definitions.",
        "No LLM silver labels, lexical effect guesses or MCP annotation claims were substituted.",
        "", "## Interpretation", "",
        "Annotation and read-only metadata are declarations, not evidence of actual tool behavior.",
        "The reference non-read-only share is only reported with complete independent human labels.",
        "",
    ]
    return "\n".join(out)


def run_e1(root: str | Path, output_root: str | Path,
           reference_labels_path: str | Path | None = None, run_id: str | None = None) -> Path:
    root, output_root = Path(root).resolve(), Path(output_root).resolve()
    raw = root / "data" / "raw"
    sources_path = raw / "SOURCES.txt"
    schema_path = root / "docs" / "experiment_design" / "run_manifest.schema.json"
    for p in (raw / "livemcpbench" / "tools.json",
              raw / "livemcpbench" / "all_annotations.json",
              raw / "mcptoolbenchpp", sources_path, schema_path):
        if not p.exists():
            raise FileNotFoundError(p)
    sources = sources_path.read_text(encoding="utf-8")
    if "36a51a1065dda49c1e503b87edf33a1e0b331a74" not in sources:
        raise ValueError("LiveMCPBench source commit is not pinned to the specified revision")
    if "2bd35e58ed5ebe79bbb12df0f9919a34ed2cb037" not in sources:
        raise ValueError("MCPToolBench++ source commit is not pinned to the specified revision")

    live = load_livemcpptool(raw)
    pp, _ = load_mcptoolbenchpp(raw)
    merged = merge_registries(live, pp)
    views = {"LiveMCPTool": live, "MCPToolBench++": pp, "merged": merged}
    for name, tools in views.items():
        actual = {"tools": len(tools), "servers": len({t.server for t in tools})}
        if actual != EXPECTED[name]:
            raise ValueError(f"{name} view mismatch: expected {EXPECTED[name]}, found {actual}")

    labels_path = Path(reference_labels_path).resolve() if reference_labels_path else None
    labels = load_reference_labels(labels_path)
    unique_source_definitions = {tool_key(t) for t in live + pp}
    if labels is not None:
        missing, extra = unique_source_definitions - set(labels), set(labels) - unique_source_definitions
        if missing or extra:
            raise ValueError(f"Reference label coverage mismatch: missing={len(missing)}, extra={len(extra)}")

    built = build_all(write=True)
    if len(built["registry"]) != 569:
        raise ValueError("Canonical registry build did not yield 569 tools")

    run_id = run_id or f"E1-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-protocol-v1"
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    input_dir = run_dir / "inputs"
    input_dir.mkdir()
    shutil.copytree(raw, input_dir / "data" / "raw")
    proc = input_dir / "data" / "processed"
    proc.mkdir(parents=True)
    shutil.copy2(root / "data" / "processed" / "registry_merged.json", proc / "registry_merged.json")
    if labels_path:
        shutil.copy2(labels_path, input_dir / "independent_reference_labels.json")

    views_summary, categories, servers = [], [], []
    for name, tools in views.items():
        s, c, sv = summarize_view(name, tools, labels)
        views_summary.append(s)
        categories.extend(c)
        servers.extend(sv)
    category_names = sorted({t.category for t in live + pp if t.category})
    if len(category_names) != 14:
        raise ValueError(f"Expected 14 source categories, observed {len(category_names)}: {category_names}")

    published = {r["id"]: r for r in built["registry"]}
    hash_mismatches = []
    for tool in merged:
        if published[tool.id].get("hash") != tool.definition_hash():
            hash_mismatches.append({
                "tool_id": tool.id, "published_hash": published[tool.id].get("hash"),
                "recomputed_hash": tool.definition_hash(),
            })

    input_hash_rows = []
    for p in sorted(x for x in raw.rglob("*") if x.is_file()):
        input_hash_rows.append({
            "path": str(p.relative_to(root)), "bytes": p.stat().st_size, "sha256": sha256_file(p)
        })
    input_hash_rows.append({
        "path": "data/processed/registry_merged.json",
        "bytes": (root / "data/processed/registry_merged.json").stat().st_size,
        "sha256": sha256_file(root / "data/processed/registry_merged.json"),
    })
    dataset_hash = hash_json(input_hash_rows)

    registry_rows = []
    for s in views_summary:
        ref = s["reference_labels"]
        registry_rows.append({
            "registry": s["registry"], "tools": s["tool_count"], "servers": s["server_count"],
            "categories": s["category_count"], "annotated_tools": s["annotated_tool_count"],
            "annotated_share": s["annotated_tool_share"],
            "declared_read_only_true": s["declared_read_only_true_count"],
            "declared_read_only_share": s["declared_read_only_share_of_all_tools"],
            "reference_labelled_tools": ref["labelled_tool_definitions"],
            "reference_label_coverage": ref["coverage"],
            "reference_non_read_only_tools": ref["non_read_only_count"],
            "reference_non_read_only_share": ref["non_read_only_share"],
            "tools_per_server_mean": s["tools_per_server"]["mean"],
            "tools_per_server_median": s["tools_per_server"]["median"],
            "description_length_mean_chars": s["description_length_chars"]["mean"],
            "description_length_median_chars": s["description_length_chars"]["median"],
            "description_length_p90_chars": s["description_length_chars"]["p90"],
        })
    write_csv(run_dir / "registry_summary.csv", registry_rows)
    write_csv(run_dir / "category_distribution.csv", categories)
    write_csv(run_dir / "server_distribution.csv", servers)
    write_csv(run_dir / "description_length_summary.csv", [
        {"registry": s["registry"], **s["description_length_chars"]} for s in views_summary
    ])
    write_csv(run_dir / "reference_label_coverage.csv", [
        {"registry": s["registry"], **s["reference_labels"]} for s in views_summary
    ])
    write_csv(run_dir / "definition_hash_validation.csv", hash_mismatches,
              ["tool_id", "published_hash", "recomputed_hash"])

    intake_count = 0
    if labels is None:
        intake_count = write_reference_intake(views, run_dir)

    summary = {
        "experiment_id": "E1", "title": "Registry characterization", "protocol_version": "1.0.0",
        "datasets": views_summary,
        "server_categories": {"expected": 14, "observed": len(category_names), "labels": category_names},
        "definition_hash_validation": {
            "implementation": "RawTool.definition_hash()",
            "validated_merged_tool_count": len(merged), "mismatch_count": len(hash_mismatches),
            "mismatches": hash_mismatches,
        },
        "reference_labels": {
            "provided": labels is not None,
            "labelled_definition_count": len(labels) if labels is not None else 0,
            "required_definition_count": len(unique_source_definitions),
            "status": "complete" if labels is not None else "blocked_missing_independent_reference_labels",
            "prohibited_sources_excluded": ["data/llm_records/silver_labels.json", "silver_labels_part*.jsonl"],
        },
        "reference_intake_unique_definitions": intake_count,
        "interpretation": "Descriptive registry census; metadata hints are declarations, not observed behavior.",
        "guardrails": {
            "silver_labels_read": False, "task_gold_labels_read": False,
            "llm_records_read": False, "reference_labels_reused_for_contract_construction": False,
            "mcp_servers_executed": False, "policy_decisions_made": False,
        },
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Protocol output: stacked bars for 14 categories and the three registry views.
    registry_names = ["LiveMCPTool", "MCPToolBench++", "merged"]
    cats = sorted({r["category"] for r in categories})
    lookup = {(r["registry"], r["category"]): r["tools"] for r in categories}
    fig, ax = plt.subplots(figsize=(max(12, len(cats) * .9), 6))
    bottom = [0] * len(registry_names)
    for cat in cats:
        values = [lookup.get((name, cat), 0) for name in registry_names]
        ax.bar(registry_names, values, bottom=bottom, label=cat)
        bottom = [bottom[i] + values[i] for i in range(len(bottom))]
    ax.set_title("E1 — Registry views by server category")
    ax.set_ylabel("Tool definitions")
    ax.set_xlabel("Registry view")
    ax.legend(title="Server category (14)", bbox_to_anchor=(1.02, 1), loc="upper left")
    fig.tight_layout()
    fig.savefig(run_dir / "registry_category_stacked.png", dpi=180)
    plt.close(fig)
    (run_dir / "E1_REPORT.md").write_text(render_report(registry_rows, summary), encoding="utf-8")

    artifact_paths = [
        str(p.relative_to(run_dir)) for p in sorted(run_dir.rglob("*"))
        if p.is_file() and p.name not in {"MANIFEST.json", "ARTIFACTS_SHA256.json", "E1_run.zip"}
    ]
    checksums = {p: sha256_file(run_dir / p) for p in artifact_paths}
    (run_dir / "ARTIFACTS_SHA256.json").write_text(json.dumps(checksums, indent=2) + "\n", encoding="utf-8")
    artifact_paths.append("ARTIFACTS_SHA256.json")

    status = "completed" if labels is not None and not hash_mismatches else "failed"
    notes = "Full independent reference labels supplied." if labels is not None else (
        "Partial descriptive census only. Reference non-read-only share is blocked because "
        "the repository has no independent human reference label set. Silver LLM labels were excluded."
    )
    if hash_mismatches:
        notes += f" Canonical definition hash mismatch count: {len(hash_mismatches)}."
    manifest = {
        "spec_version": "1.0.0", "experiment_id": "E1", "run_id": run_id,
        "status": status, "configuration": "descriptive_measurement",
        "dataset_snapshot": {
            "name": "LiveMCPTool+MCPToolBench+++merged",
            "version_or_hash": "sha256:" + dataset_hash,
            "split": "all three protocol registry views",
            "sample_count": sum(len(x) for x in views.values()),
            "label_snapshot_hash": sha256_file(labels_path) if labels_path else None,
        },
        "code": {
            "repository": "https://github.com/msellamiTN/taas-provenance-discovery",
            "commit": git_value(root, "rev-parse", "HEAD") or "unknown",
            "dirty_worktree": bool(git_value(root, "status", "--porcelain")),
        },
        "environment": {
            "os": platform.platform(), "python": platform.python_version(),
            "hardware": platform.processor() or platform.machine(), "container_image_digest": None,
        },
        "models": [],
        "parameters": {
            "registry_views": registry_names, "expected_counts": EXPECTED,
            "server_categories": 14, "description_length_unit": "Unicode characters",
            "annotated_definition": "non-empty annotations object",
            "declared_read_only_definition": "annotations.readOnlyHint is true",
            "reference_non_read_only_definition": "complete independent human reference labels keyed by tool_id + definition_hash",
            "source_revisions": sources.splitlines(),
        },
        "seeds": [], "metrics": {
            "registry_summary": registry_rows,
            "reference_metric_status": summary["reference_labels"]["status"],
            "definition_hash_mismatch_count": len(hash_mismatches),
        },
        "statistical_analysis": {
            "design": "descriptive census", "confidence_intervals": "not applicable to registry census",
            "bootstrap_unit": None,
        },
        "artifacts": artifact_paths, "notes": notes,
    }
    schema = json.loads((root / "docs/experiment_design/run_manifest.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(manifest, schema)
    (run_dir / "MANIFEST.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    archive = run_dir / "E1_run.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for p in sorted(run_dir.rglob("*")):
            if p.is_file() and p != archive:
                zf.write(p, Path(run_id) / p.relative_to(run_dir))
    return run_dir


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--root", default=".")
    p.add_argument("--output", default="results/definitive/E1")
    p.add_argument("--reference-labels")
    p.add_argument("--run-id")
    a = p.parse_args()
    d = run_e1(a.root, a.output, a.reference_labels, a.run_id)
    m = json.loads((d / "MANIFEST.json").read_text(encoding="utf-8"))
    print(json.dumps({
        "experiment_id": "E1", "run_id": m["run_id"], "status": m["status"],
        "reference_metric_status": m["metrics"]["reference_metric_status"],
        "archive": str(d / "E1_run.zip"),
    }, indent=2))


if __name__ == "__main__":
    main()
