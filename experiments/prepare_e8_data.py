#!/usr/bin/env python3
"""Prepare pinned source inputs for the definitive E8 retrieval campaign.

MCPToolBench++ JSON files are downloaded from one immutable Git commit and
verified against their Git blob SHA-1 values. ToolRet is optional because its
query and tool corpora live in separate Hugging Face repositories; when requested,
both immutable Hub commit SHAs are resolved and recorded independently.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
MCPTOOLBENCH_REPO = "mcp-tool-bench/MCPToolBenchPP"
MCPTOOLBENCH_REVISION = "2bd35e58ed5ebe79bbb12df0f9919a34ed2cb037"
MCPTOOLBENCH_FILES = {
    "browser/browser_0724_single_v3.json": "35fcd12b3c631127b08112f4139e4878bc0ede60",
    "file_system/filesystem_0723_single.json": "f07d602ef59d9c49f0e6b4b39a6c04c94d632e70",
    "finance/finance_0724_single_v3.json": "01192f6f3a55e1b09fca6567c06dd3742dcdcdd7",
    "map/map_0717_single_multi_lang_500.json": "a48b93fffe136749c080c2d048b7c6c2b6ba3e49",
    "pay/pay_0723_single.json": "20a54197a2a1d700262b428da7b2a9f43039cf9d",
    "search/search_0725_single_v2.json": "49a075fb2847f610e21acb23995f99b5eaf8bb61",
}
TOOLRET_QUERY_REPO = "mangopy/ToolRet-Queries"
TOOLRET_TOOLS_REPO = "mangopy/ToolRet-Tools"


def git_blob_sha1(payload: bytes) -> str:
    """Return the Git object SHA-1 (blob header + content), not plain-file SHA-1."""
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _download(url: str, timeout: int = 120) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "PaMCP-E8-pinned-data-preparer/1.0"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if getattr(response, "status", 200) != 200:
            raise RuntimeError(f"Download returned HTTP {response.status}: {url}")
        return response.read()


def prepare_mcptoolbenchpp(
    raw_root: Path,
    downloader: Callable[[str], bytes] = _download,
) -> dict:
    """Fetch six frozen single-task category files; verify exact Git blob SHAs."""
    root = raw_root / "mcptoolbenchpp"
    root.mkdir(parents=True, exist_ok=True)
    downloaded, reused = [], []
    for relative_path, expected_sha in MCPTOOLBENCH_FILES.items():
        destination = root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.is_file():
            actual = git_blob_sha1(destination.read_bytes())
            if actual != expected_sha:
                raise ValueError(
                    f"Pinned MCPToolBench++ file mismatch for {relative_path}: "
                    f"expected {expected_sha}, found {actual}. Move the file aside; "
                    "the preparer will not silently overwrite untrusted inputs."
                )
            reused.append(relative_path)
            continue
        url = (
            f"https://raw.githubusercontent.com/{MCPTOOLBENCH_REPO}/"
            f"{MCPTOOLBENCH_REVISION}/data/{relative_path}"
        )
        payload = downloader(url)
        actual = git_blob_sha1(payload)
        if actual != expected_sha:
            raise ValueError(
                f"Pinned MCPToolBench++ download mismatch for {relative_path}: "
                f"expected Git blob {expected_sha}, found {actual}"
            )
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.write_bytes(payload)
        if git_blob_sha1(temporary.read_bytes()) != expected_sha:
            temporary.unlink(missing_ok=True)
            raise RuntimeError(f"Temporary-file integrity check failed for {relative_path}")
        temporary.replace(destination)
        downloaded.append(relative_path)

    sources_path = raw_root / "SOURCES.txt"
    source_line = f"MCPToolBenchPP {MCPTOOLBENCH_REVISION}"
    existing_lines = []
    if sources_path.exists():
        existing_lines = [
            line.strip() for line in sources_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    existing_mcp = [line for line in existing_lines if line.split(maxsplit=1)[0] == "MCPToolBenchPP"]
    if existing_mcp and existing_mcp != [source_line]:
        raise ValueError(
            "data/raw/SOURCES.txt has a different MCPToolBench++ revision: "
            f"{existing_mcp}; expected {source_line}"
        )
    if source_line not in existing_lines:
        existing_lines.append(source_line)
        sources_path.parent.mkdir(parents=True, exist_ok=True)
        sources_path.write_text("\n".join(existing_lines) + "\n", encoding="utf-8")

    return {
        "dataset": "MCPToolBench++",
        "repository": MCPTOOLBENCH_REPO,
        "revision": MCPTOOLBENCH_REVISION,
        "downloaded": downloaded,
        "reused_verified": reused,
        "file_count": len(MCPTOOLBENCH_FILES),
        "files": {
            relative: {
                "git_blob_sha1": MCPTOOLBENCH_FILES[relative],
                "sha256": sha256_file(root / relative),
                "bytes": (root / relative).stat().st_size,
            }
            for relative in MCPTOOLBENCH_FILES
        },
    }


def prepare_toolret(
    output_dir: Path,
    query_revision: str | None = None,
    tool_revision: str | None = None,
) -> dict:
    """Prepare the heterogeneous ToolRet track with independent immutable revisions."""
    try:
        from huggingface_hub import HfApi
        from taas.experiments.toolret_adapter import adapt_toolret_hf
    except ImportError as exc:
        raise RuntimeError(
            'ToolRet preparation requires: pip install -e ".[benchmark-hf]"'
        ) from exc

    api = HfApi()
    query_info = api.dataset_info(TOOLRET_QUERY_REPO, revision=query_revision)
    tools_info = api.dataset_info(TOOLRET_TOOLS_REPO, revision=tool_revision)
    query_sha = str(getattr(query_info, "sha", "") or "")
    tools_sha = str(getattr(tools_info, "sha", "") or "")
    if len(query_sha) != 40 or len(tools_sha) != 40:
        raise RuntimeError("Could not resolve immutable 40-character ToolRet Hub revisions")

    manifest = adapt_toolret_hf(
        output_dir=output_dir,
        query_revision=query_sha,
        tool_revision=tools_sha,
    )
    source_revisions = manifest.get("source_revisions", {})
    if source_revisions.get("query_revision") != query_sha:
        raise RuntimeError("ToolRet query revision was not preserved by the adapter")
    if source_revisions.get("tool_revision") != tools_sha:
        raise RuntimeError("ToolRet tool-corpus revision was not preserved by the adapter")

    inventory = {}
    for path in sorted(output_dir.rglob("*")):
        if path.is_file() and path.name != "manifest.json":
            inventory[str(path.relative_to(output_dir))] = {
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
    manifest["prepared_artifact_inventory"] = inventory
    manifest["preparation_policy"] = {
        "query_repository_revision": query_sha,
        "tool_repository_revision": tools_sha,
        "query_and_instruction_are_not_interchanged": True,
        "discovery_and_evaluator_files_are_separate": True,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return {
        "dataset": "ToolRet",
        "query_revision": query_sha,
        "tool_revision": tools_sha,
        "counts": manifest.get("counts", {}),
        "artifact_count": len(inventory),
        "output_dir": str(output_dir),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--include-toolret", action="store_true",
                        help="also prepare the two independent ToolRet Hub datasets")
    parser.add_argument("--toolret-query-revision",
                        help="optional immutable query dataset commit; default resolves current commit")
    parser.add_argument("--toolret-tools-revision",
                        help="optional immutable tool dataset commit; default resolves current commit")
    args = parser.parse_args()

    root = args.root.resolve()
    raw_root = root / "data" / "raw"
    result = {
        "mcp_tool_bench_pp": prepare_mcptoolbenchpp(raw_root),
        "toolret": None,
    }
    if args.include_toolret:
        result["toolret"] = prepare_toolret(
            root / "data" / "processed" / "toolret",
            query_revision=args.toolret_query_revision,
            tool_revision=args.toolret_tools_revision,
        )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
