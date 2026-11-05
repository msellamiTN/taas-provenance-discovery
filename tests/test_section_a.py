"""PaMCP Section A: read-only inventory, protocol checks, and annotation readiness.

This module deliberately does not execute E0/E1/E2 legacy experiments. It creates
an auditable preflight report and never overwrites source data or historical results.
Compatible with Python 3.10+ and the standard library only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROTOCOL_MARKERS = (
    "## 1. Research question",
    "## 2. PaMCP Core feature model",
    "## 3. Dataset portfolio and track separation",
    "## 4. Baseline protocol",
    "## 5. Ablations and factorial design",
    "## 6. Metrics and contracts",
)
DEFAULT_ANNOTATION_CANDIDATES = (
    "data/annotations",
    "data/processed/annotations",
    "data/reference_labels",
    "data/processed/reference_labels.json",
)
HISTORICAL_RESULT_GLOBS = ("results/e0*.json", "results/e1*.json", "results/e2*.json")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def git_value(root: Path, *args: str) -> str | None:
    try:
        return subprocess.check_output(
            ["git", *args], cwd=root, stderr=subprocess.DEVNULL, text=True
        ).strip() or None
    except (OSError, subprocess.CalledProcessError):
        return None


def file_record(path: Path, root: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": path.relative_to(root).as_posix(),
        "size_bytes": stat.st_size,
        "sha256": sha256_file(path),
    }


def scan_files(root: Path, patterns: tuple[str, ...]) -> list[dict[str, Any]]:
    found: dict[str, Path] = {}
    for pattern in patterns:
        for path in root.glob(pattern):
            if path.is_file():
                found[path.relative_to(root).as_posix()] = path
    return [file_record(found[key], root) for key in sorted(found)]


def protocol_check(protocol_path: Path) -> dict[str, Any]:
    if not protocol_path.is_file():
        return {"status": "BLOCKED_DATA", "path": str(protocol_path), "missing_markers": list(PROTOCOL_MARKERS)}
    content = protocol_path.read_text(encoding="utf-8")
    missing = [marker for marker in PROTOCOL_MARKERS if marker not in content]
    return {
        "status": "PASS" if not missing else "PARTIAL",
        "path": protocol_path.as_posix(),
        "sha256": sha256_file(protocol_path),
        "required_sections": len(PROTOCOL_MARKERS),
        "present_sections": len(PROTOCOL_MARKERS) - len(missing),
        "missing_markers": missing,
    }


def annotation_readiness(root: Path) -> dict[str, Any]:
    candidates = []
    for item in DEFAULT_ANNOTATION_CANDIDATES:
        path = root / item
        if path.is_dir():
            files = sorted(p for p in path.rglob("*") if p.is_file())
            candidates.append({"path": item, "kind": "directory", "file_count": len(files),
                               "files": [p.relative_to(root).as_posix() for p in files[:50]]})
        elif path.is_file():
            candidates.append({"path": item, "kind": "file", "sha256": sha256_file(path)})
    return {
        "status": "REVIEW_REQUIRED" if candidates else "BLOCKED_DATA",
        "candidate_locations": candidates,
        "independence_verified": False,
        "adjudication_verified": False,
        "note": "Presence is only an intake signal; source independence, annotator protocol and adjudication require manual/schema validation.",
    }


def registry_readiness(root: Path) -> dict[str, Any]:
    candidates = ["data/processed/registry_merged.json", "data/raw/livemcpbench/all_annotations.json"]
    rows = []
    for rel in candidates:
        path = root / rel
        rows.append({"path": rel, "exists": path.is_file(),
                     "sha256": sha256_file(path) if path.is_file() else None,
                     "size_bytes": path.stat().st_size if path.is_file() else None})
    available = sum(row["exists"] for row in rows)
    return {"status": "PASS" if available == len(rows) else ("PARTIAL" if available else "BLOCKED_DATA"),
            "sources": rows}


def build_report(root: Path, protocol: Path | None = None) -> dict[str, Any]:
    root = root.resolve()
    protocol = (protocol or root / "docs/experiment_design/PAMCP_CORE_PROTOCOL_V2.md").resolve()
    tracked = git_value(root, "ls-files")
    tracked_paths = tracked.splitlines() if tracked else []
    suffix_counts = Counter(Path(p).suffix.lower() or "[no extension]" for p in tracked_paths)
    historical = scan_files(root, HISTORICAL_RESULT_GLOBS)
    return {
        "schema_version": "pamcp-section-a-preflight/1.0",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "campaign_section": "A",
        "experiments": ["E0", "E1", "E2"],
        "mode": "READ_ONLY_PREFLIGHT",
        "repository": {
            "root": str(root), "git_commit": git_value(root, "rev-parse", "HEAD"),
            "git_branch": git_value(root, "branch", "--show-current"),
            "tracked_file_count": len(tracked_paths),
            "tracked_suffix_counts": dict(sorted(suffix_counts.items())),
        },
        "protocol": protocol_check(protocol),
        "registry": registry_readiness(root),
        "semantic_typing": annotation_readiness(root),
        "historical_results": {
            "files": historical,
            "classification": "HISTORICAL_ONLY",
            "reuse_policy": "Do not reuse as confirmatory results until dataset, code, protocol, config and oracle provenance are validated.",
        },
        "safety": {
            "source_files_modified": False,
            "historical_results_modified": False,
            "legacy_experiments_executed": False,
            "external_model_calls": 0,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root")
    parser.add_argument("--protocol", type=Path, default=None, help="Protocol markdown path")
    parser.add_argument("--output", type=Path, default=None, help="Optional report path; must not exist")
    args = parser.parse_args(argv)
    report = build_report(args.root, args.protocol)
    rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        output = args.output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists():
            parser.error(f"Refusing to overwrite existing report: {output}")
        output.write_text(rendered, encoding="utf-8")
        print(f"Report written: {output}")
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
