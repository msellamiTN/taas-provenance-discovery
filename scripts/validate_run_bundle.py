#!/usr/bin/env python3
"""Validate the provenance envelope of a TaaS experiment run bundle.

This is a structural/hash validator, not a scientific-validity checker.
It intentionally never modifies a run bundle.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REQUIRED = {
    "schema_version", "run_id", "experiment_id", "status",
    "started_at_utc", "git_commit", "git_branch", "working_tree_clean",
    "environment", "dataset_fingerprints", "config_path", "config_sha256",
    "seed", "command", "exit_code", "artifacts", "limitations",
    "deviations", "costs", "verification",
}
ALLOWED_STATES = {
    "PLANNED", "INSPECTED", "READY", "RUNNING", "BLOCKED", "FAILED",
    "COMPLETED_UNVERIFIED", "VERIFIED", "REJECTED",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    root = args.run_dir.resolve()
    manifest_path = root / "run_manifest.json"
    errors: list[str] = []

    if not root.is_dir():
        print(f"ERROR: run directory does not exist: {root}")
        return 2
    if not manifest_path.is_file():
        print("ERROR: missing run_manifest.json")
        return 2

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"ERROR: invalid JSON manifest: {exc}")
        return 2

    missing = sorted(REQUIRED - manifest.keys())
    if missing:
        errors.append("missing manifest fields: " + ", ".join(missing))
    if manifest.get("status") not in ALLOWED_STATES:
        errors.append(f"invalid status: {manifest.get('status')!r}")

    config_rel = manifest.get("config_path")
    if isinstance(config_rel, str):
        config = (root / config_rel).resolve()
        if root not in config.parents:
            errors.append("config_path escapes run directory")
        elif not config.is_file():
            errors.append(f"config file missing: {config_rel}")
        elif sha256(config) != manifest.get("config_sha256"):
            errors.append(f"config SHA-256 mismatch: {config_rel}")

    artifacts = manifest.get("artifacts", [])
    if not isinstance(artifacts, list):
        errors.append("artifacts must be a list")
        artifacts = []
    seen: set[str] = set()
    for item in artifacts:
        if not isinstance(item, dict) or not {"path", "sha256"} <= item.keys():
            errors.append(f"invalid artifact entry: {item!r}")
            continue
        rel = item["path"]
        if not isinstance(rel, str) or rel in seen:
            errors.append(f"invalid or duplicate artifact path: {rel!r}")
            continue
        seen.add(rel)
        path = (root / rel).resolve()
        if root not in path.parents:
            errors.append(f"artifact path escapes run directory: {rel}")
        elif not path.is_file():
            errors.append(f"artifact missing: {rel}")
        elif sha256(path) != item["sha256"]:
            errors.append(f"artifact SHA-256 mismatch: {rel}")

    verification = manifest.get("verification", {})
    if manifest.get("status") == "VERIFIED":
        required_verification = {"state", "auditor", "date", "commit", "notes"}
        if not isinstance(verification, dict) or not required_verification <= verification.keys():
            errors.append("VERIFIED status requires complete independent verification metadata")
        elif verification.get("state") != "VERIFIED":
            errors.append("verification.state must be VERIFIED when run status is VERIFIED")

    if errors:
        print("RUN BUNDLE: INVALID")
        for error in errors:
            print(f"- {error}")
        return 1

    print("RUN BUNDLE: STRUCTURALLY VALID")
    print(f"run_id={manifest.get('run_id')}")
    print(f"experiment_id={manifest.get('experiment_id')}")
    print(f"status={manifest.get('status')}")
    print(f"artifacts_checked={len(artifacts)}")
    print("NOTE: structural validity does not establish scientific validity.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
