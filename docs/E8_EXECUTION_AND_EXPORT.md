# E8 — Reproducible single-tool retrieval run and figure export

## Scope and current completion state

E8 evaluates single-tool retrieval. Its frozen protocol is in
\`docs/experiment_design/pamcp_experiments_v1.json\`; the registered baseline IDs are:

\`bm25\`, \`dense_lsa\`, \`rag_mcp\`, \`mcp_zero\`, \`per_subtask\`, \`colt_adapted\`,
\`toolscope_adapted\`, and \`cmtf_adapted\`.

The current campaign is intentionally allowed to finish as **partial**. It records
which methods ran and why the other registered methods were blocked or not comparable.
It must not turn E5, TF-IDF, RRF or Cross-Encoder controls into aliases for a
registered method. It also does not execute Full PaMCP as a single-tool E8 adapter.
See the run's \`MANIFEST.json\` before interpreting any figure.

For an interactive Colab run with Drive-backed persistence, use the
[PaMCP E8 Colab notebook](https://colab.research.google.com/github/msellamiTN/taas-provenance-discovery/blob/feature/pamcp-publication-visualization-v1/experiments/colab/E8_Retrieval_Campaign.ipynb).
It calls the same launcher documented below.

## 1. Install the required extras

\`\`\`bash
pip install -e ".[benchmark-hf,visualization,retrieval,test]"
\`\`\`

## 2. Prepare pinned source data

From the repository root:

\`\`\`bash
python experiments/prepare_e8_data.py
\`\`\`

This downloads the six single-task category files from MCPToolBench++ commit
\`2bd35e58ed5ebe79bbb12df0f9919a34ed2cb037\` and verifies each downloaded file
against its Git blob SHA-1 from the pinned upstream tree. Existing files are reused
only when their blob hashes match; mismatching local files are not overwritten.
The data are stored under \`data/raw/mcptoolbenchpp/\`. The script preserves the
other entries in \`data/raw/SOURCES.txt\`.

To also prepare the heterogeneous ToolRet retrieval track:

\`\`\`bash
python experiments/prepare_e8_data.py --include-toolret
\`\`\`

ToolRet queries and tools are separate Hugging Face dataset repositories with
independent immutable revisions. The preparer resolves both commit SHAs and writes
them, the data split inventory and an artifact hash inventory into
\`data/processed/toolret/manifest.json\`. Query and tool-corpus revisions are not
assumed to be the same. Discovery queries/tools remain in \`discovery/\`; evaluator
qrels remain in \`evaluator/\`.

The MCPToolBench++ loader applies both conditions before scoring:
- \`call_type\` must be single (legacy rows without this field are treated as single).
- Exactly one primary \`function_call_label\` must resolve to a candidate tool ID.

Multi-call, multi-target, ambiguous and unresolved tasks are counted as exclusions.
The complete candidate registry remains the source-specific MCPToolBench++ registry.
\`similar_tools\` are retained as a separately reported sensitivity qrel and are
never substituted for the primary label or described as B1m.

## 3. Pin the retrieval model revisions

The campaign requires immutable model commits. Resolve each repository commit and
pass the values explicitly:

\`\`\`bash
E5_REVISION=$(python -c "from huggingface_hub import HfApi; print(HfApi().model_info('intfloat/e5-small-v2').sha)")
CROSS_ENCODER_REVISION=$(python -c "from huggingface_hub import HfApi; print(HfApi().model_info('cross-encoder/ms-marco-MiniLM-L-6-v2').sha)")
\`\`\`

Record these exact values in the E8 run manifest. If model repositories are unavailable
or the model revisions cannot be resolved, stop instead of using an unpinned
\`main\` revision.

## 4. Run the E8 campaign

For a CPU-only environment:

\`\`\`bash
python experiments/e8_retrieval_campaign.py \
  --root . \
  --output-root results/definitive/E8 \
  --toolret-dir data/processed/toolret \
  --raw-root data/raw \
  --e5-revision "$E5_REVISION" \
  --cross-encoder-revision "$CROSS_ENCODER_REVISION" \
  --device cpu \
  --top-k 10 \
  --seed 20261105
\`\`\`

Use \`--device cuda\` only when a CUDA runtime is available and tested. The campaign
requires \`top_k >= 10\` because E8 includes MRR@10. Use a new run ID for a new
experimental configuration; finalized run directories are immutable.

The campaign materializes rankings before evaluator qrels are loaded. It exports
per-task metrics with \`cluster_id\`:
- ToolRet has no defensible server clustering in this track, so its confidence
  intervals use task-level resampling.
- MCPToolBench++ records the primary target's server for every task. Its confidence
  intervals use target-server cluster resampling.

## One-command execution

After installing the extras, the complete preparation → retrieval campaign → figure export → partial rendering flow is available as:

```bash
E8_DEVICE=cuda bash experiments/run_e8_and_plot.sh
```

Use `E8_DEVICE=cpu` only for a small-scale smoke run or when a GPU is unavailable. The script pins both model commits at the start of each new run, uses a unique immutable run ID, prepares the pinned sources, and does not overwrite an existing ToolRet snapshot. Set `E8_RUN_ID`, `E8_TOP_K`, `E8_SEED`, or `E8_DEVICE` to explicitly control the run. The generated manifest records the model revisions and the true partial/complete status.

## 5. Export publication figure inputs

Select the newly created run directory (do not point to a legacy E0–E7 result):

\`\`\`bash
RUN_DIR=$(find results/definitive/E8 -mindepth 1 -maxdepth 1 -type d | sort | tail -1)
python experiments/export_e8_figures.py \
  --run-dir "$RUN_DIR" \
  --output-dir results/visualization/data \
  --bootstrap-resamples 5000 \
  --seed 20261105
\`\`\`

The exporter verifies the E8 manifest against the frozen registered baseline list,
checks that per-task CSV methods match the run manifest, and creates confidence
intervals from actual per-task observations. Only registered E8 baseline IDs with
observations enter the primary E8 plots. Other executed controls are listed as
supplementary but excluded from the primary comparisons.

Current figure availability is deliberately conditional:

| Figure | Export condition |
|---|---|
| E8-F1 | Registered baselines with observed per-task metrics, faceted by benchmark |
| E8-F2 | Not exported until B1/B1m are provided as verified source conditions with a frozen mapping |
| E8-F3 | Not exported until a predeclared distractor-count sweep has actually been executed |
| E8-F4 | Macro Hit@1 by task category, with independent benchmark facets |

Groups with fewer than two independent MCPToolBench++ target-server clusters are
excluded from confidence-interval figures and listed in \`E8_EXPORT_MANIFEST.json\`.
They are not assigned fabricated or task-independent error bars.

## 6. Validate and render the available E8 figures

Because E8 can legitimately remain partial, do not use \`--strict\` for the full
four-figure E8 specification until the remaining data conditions are met:

\`\`\`bash
python experiments/plot_results.py validate-data --experiment E8
python experiments/plot_results.py render --experiment E8
\`\`\`

The renderer creates only figures with validated populated CSVs and reports missing
E8-F2/E8-F3 inputs as skipped. To require all four E8 figures, use
\`validate-data --experiment E8 --strict\` and \`render --experiment E8 --strict\`
only after their required source conditions and sweep have been implemented.

## 7. Interpretation guardrails

- Do not relabel \`similar_tools\` sensitivity scores as B1/B1m.
- Do not pool the heterogeneous ToolRet track with the MCP-native MCPToolBench++ track.
- Do not include supplementary unregistered controls in primary E8 figures.
- Do not describe a dense-LSA surrogate as a neural embedding model.
- Do not claim the Cross-Encoder has end-to-end corpus recall beyond its BM25 top-100 candidate pool.
- Do not claim task execution success, tool safety or composition correctness from E8 ranking metrics.
- Do not claim E8 complete while any frozen registered baseline or source condition remains blocked.

The E8 run manifest, per-task exports, source revisions, ranking caches, file hashes
and ZIP archive are the provenance record for the campaign.
