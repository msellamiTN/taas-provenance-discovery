#!/usr/bin/env python3
"""Restore the pinned MCPToolBench++ raw benchmark snapshot without model downloads."""
from __future__ import annotations
import argparse, hashlib, json, shutil, subprocess, tempfile
from pathlib import Path

REPOSITORY = "https://github.com/mcp-tool-bench/MCPToolBenchPP.git"
REVISION = "2bd35e58ed5ebe79bbb12df0f9919a34ed2cb037"
CATEGORIES = ("browser", "file_system", "finance", "map", "pay", "search")
EXPECTED_TASKS, EXPECTED_TOOLS, EXPECTED_SERVERS = 1509, 87, 10


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _category_source(directory: Path, category: str) -> Path:
    source_dir = directory / "data" / category
    candidates = sorted(
        p for p in source_dir.glob("*.json")
        if "demo" not in p.name.casefold() and "forqwen" not in p.name.casefold()
    )
    if len(candidates) != 1:
        raise RuntimeError(
            f"{category}: expected exactly one non-demo JSON under {source_dir}; "
            f"found {[p.name for p in candidates]}"
        )
    return candidates[0]


def validate_snapshot(category_files: dict[str, Path]) -> dict:
    task_count, tool_ids, server_ids = 0, set(), set()
    per_category = {}
    for category in CATEGORIES:
        path = category_files[category]
        rows = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(rows, list) or not rows:
            raise ValueError(f"{category}: expected a non-empty JSON array")
        for index, row in enumerate(rows):
            required = {"uuid", "query", "tools", "function_call_label"}
            missing = sorted(required - set(row))
            if missing:
                raise ValueError(f"{category}[{index}] missing required fields: {missing}")
            if not isinstance(row["tools"], list) or not isinstance(row["function_call_label"], list):
                raise ValueError(f"{category}[{index}] tools/function_call_label must be arrays")
            mapping = row.get("mcp_tools_dict") or {}
            server_by_name = {name: server for server, names in mapping.items() for name in names}
            for tool in row["tools"]:
                name = str(tool.get("name") or "").strip()
                if not name:
                    raise ValueError(f"{category}[{index}] contains a tool without a name")
                server = str(server_by_name.get(name) or "unknown")
                tool_ids.add(f"{server}::{name}")
                if server != "unknown":
                    server_ids.add(server)
            task_count += 1
        per_category[category] = len(rows)

    summary = {
        "tasks": task_count, "candidate_tools": len(tool_ids),
        "servers": len(server_ids), "tasks_by_category": per_category,
    }
    expected = {"tasks": EXPECTED_TASKS, "candidate_tools": EXPECTED_TOOLS, "servers": EXPECTED_SERVERS}
    mismatches = {k: {"expected": v, "actual": summary[k]} for k, v in expected.items() if summary[k] != v}
    if mismatches:
        raise ValueError("Pinned MCPToolBench++ cardinality sentinel mismatch: " + json.dumps(mismatches, sort_keys=True))
    return summary


def restore(raw_root: Path) -> dict:
    raw_root = raw_root.resolve()
    raw_root.mkdir(parents=True, exist_ok=True)
    destination = raw_root / "mcptoolbenchpp"
    with tempfile.TemporaryDirectory(prefix="mcp-toolbenchpp-", dir=raw_root.parent) as temp:
        temp_root, checkout = Path(temp), Path(temp) / "checkout"
        staging = temp_root / "mcptoolbenchpp"
        subprocess.run(["git", "clone", "--quiet", REPOSITORY, str(checkout)], check=True)
        subprocess.run(["git", "-C", str(checkout), "checkout", "--quiet", REVISION], check=True)
        actual = subprocess.check_output(["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True).strip()
        if actual != REVISION:
            raise RuntimeError(f"Source revision mismatch: {actual} != {REVISION}")

        staging.mkdir()
        category_files = {}
        for category in CATEGORIES:
            source = _category_source(checkout, category)
            target = staging / f"{category}.json"
            shutil.copy2(source, target)
            category_files[category] = target
        shutil.copy2(checkout / "LICENSE", staging / "LICENSE")
        summary = validate_snapshot(category_files)
        manifest = {
            "dataset": "MCPToolBench++", "repository": REPOSITORY, "revision": REVISION,
            **summary,
            "files": {p.name: {"sha256": _sha256(p), "bytes": p.stat().st_size}
                      for p in sorted(staging.glob("*.json"))},
        }

        # Keep the manifest outside the category glob so the loader never mistakes it for a category.
        manifest_path = raw_root / "MCPTOOLBENCHPP_MANIFEST.json"
        manifest_temp = raw_root / "MCPTOOLBENCHPP_MANIFEST.json.tmp"
        manifest_temp.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        sources = raw_root / "SOURCES.txt"
        existing = sources.read_text(encoding="utf-8").splitlines() if sources.is_file() else []
        retained = [line for line in existing if not line.startswith("MCPToolBenchPP ")]
        retained.append(f"MCPToolBenchPP {REVISION}")
        sources_temp = raw_root / "SOURCES.txt.tmp"
        sources_temp.write_text("\n".join(retained) + "\n", encoding="utf-8")

        backup = raw_root / "mcptoolbenchpp.previous"
        if backup.exists():
            shutil.rmtree(backup)
        if destination.exists():
            destination.rename(backup)
        try:
            staging.rename(destination)
            sources_temp.replace(sources)
            manifest_temp.replace(manifest_path)
        except Exception:
            if destination.exists():
                shutil.rmtree(destination)
            if backup.exists():
                backup.rename(destination)
            for p in (sources_temp, manifest_temp):
                if p.exists(): p.unlink()
            raise
        if backup.exists():
            shutil.rmtree(backup)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw"))
    args = parser.parse_args()
    print(json.dumps(restore(args.raw_root), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
