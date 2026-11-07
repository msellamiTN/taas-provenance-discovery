#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

E8_RUN_ID="${E8_RUN_ID:-E8-$(date -u +%Y%m%dT%H%M%SZ)}"
E8_OUTPUT_ROOT="${E8_OUTPUT_ROOT:-results/definitive/E8}"
E8_VIS_DATA="${E8_VIS_DATA:-results/visualization/data}"
E8_DEVICE="${E8_DEVICE:-cuda}"
E8_TOP_K="${E8_TOP_K:-10}"
E8_SEED="${E8_SEED:-20261105}"

echo "[E8] Installing the pinned campaign dependencies"
python -m pip install -e ".[benchmark-hf,visualization,retrieval]"

echo "[E8] Preparing pinned MCPToolBench++ sources and immutable ToolRet snapshots"
python experiments/prepare_e8_data.py --include-toolret

resolve_model_sha() {
  python -c 'from huggingface_hub import HfApi; import sys; info=HfApi().model_info(sys.argv[1]); print(info.sha or "")' "$1"
}

E5_MODEL="${E8_E5_MODEL:-intfloat/e5-small-v2}"
CROSS_MODEL="${E8_CROSS_ENCODER_MODEL:-cross-encoder/ms-marco-MiniLM-L-6-v2}"
E5_REVISION="${E8_E5_REVISION:-$(resolve_model_sha "$E5_MODEL")}"
CROSS_REVISION="${E8_CROSS_ENCODER_REVISION:-$(resolve_model_sha "$CROSS_MODEL")}"

[[ "$E5_REVISION" =~ ^[0-9a-f]{40}$ ]] || { echo "E5 revision is not an immutable 40-character commit" >&2; exit 2; }
[[ "$CROSS_REVISION" =~ ^[0-9a-f]{40}$ ]] || { echo "Cross-encoder revision is not an immutable 40-character commit" >&2; exit 2; }
[[ "$E8_TOP_K" -ge 10 ]] || { echo "E8_TOP_K must be >= 10 for MRR@10" >&2; exit 2; }

echo "[E8] Model commits: E5=$E5_REVISION CrossEncoder=$CROSS_REVISION"
echo "[E8] Starting immutable run: $E8_RUN_ID (device=$E8_DEVICE, top_k=$E8_TOP_K)"
CAMPAIGN_OUTPUT="$(
  python experiments/e8_retrieval_campaign.py \
    --root "$ROOT" \
    --output-root "$E8_OUTPUT_ROOT" \
    --toolret-dir "$ROOT/data/processed/toolret" \
    --raw-root "$ROOT/data/raw" \
    --e5-model "$E5_MODEL" \
    --e5-revision "$E5_REVISION" \
    --cross-encoder-model "$CROSS_MODEL" \
    --cross-encoder-revision "$CROSS_REVISION" \
    --device "$E8_DEVICE" \
    --top-k "$E8_TOP_K" \
    --seed "$E8_SEED" \
    --run-id "$E8_RUN_ID"
)"
printf '%s\n' "$CAMPAIGN_OUTPUT"
RUN_DIR="$(printf '%s' "$CAMPAIGN_OUTPUT" | python -c 'import json,sys; print(json.load(sys.stdin)["run_dir"])')"

echo "[E8] Exporting only registered baselines with real task-level results"
python experiments/export_e8_figures.py \
  --run-dir "$RUN_DIR" \
  --output-dir "$E8_VIS_DATA" \
  --bootstrap-resamples "${E8_BOOTSTRAP_RESAMPLES:-5000}" \
  --seed "$E8_SEED"

echo "[E8] Validating and rendering the available E8 figures (partial mode)"
python experiments/plot_results.py validate-data --experiment E8 --input-dir "$E8_VIS_DATA"
python experiments/plot_results.py render \
  --experiment E8 \
  --input-dir "$E8_VIS_DATA" \
  --output-dir "${E8_VIS_FIGURES:-results/visualization/figures}"

echo "[E8] Run complete. The MANIFEST status remains authoritative; blocked E8 figures are not synthesized."
