#!/usr/bin/env bash
# Re-download the raw benchmark files at the pinned commits (only needed to rebuild
# data/processed/registry_merged.json from scratch; the processed file is committed).
set -euo pipefail
cd "$(dirname "$0")/.."
tmp=$(mktemp -d)
git clone -q https://github.com/icip-cas/LiveMCPBench.git "$tmp/live" && git -C "$tmp/live" checkout -q 36a51a1065dda49c1e503b87edf33a1e0b331a74
git clone -q https://github.com/mcp-tool-bench/MCPToolBenchPP.git "$tmp/pp" && git -C "$tmp/pp" checkout -q 2bd35e58ed5ebe79bbb12df0f9919a34ed2cb037
mkdir -p data/raw/livemcpbench data/raw/mcptoolbenchpp
cp "$tmp/live/tools/LiveMCPTool/tools.json" "$tmp/live/annotated_data/all_annotations.json" "$tmp/live/LICENSE" data/raw/livemcpbench/
for c in browser file_system finance map pay search; do
  f=$(ls "$tmp/pp/data/$c/"*.json | grep -v demo | grep -v forqwen); cp "$f" "data/raw/mcptoolbenchpp/$c.json"
done
cp "$tmp/pp/LICENSE" data/raw/mcptoolbenchpp/LICENSE
rm -rf "$tmp"
PYTHONPATH=src python3 -m taas.data.registries
