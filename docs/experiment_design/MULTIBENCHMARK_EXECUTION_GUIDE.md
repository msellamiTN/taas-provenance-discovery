# PaMCP MultiBenchmark v1 — acquisition and execution guide

## Status

This branch adds a dataset registry, a schema-explicit JSON/JSONL adapter, discovery/evaluator separation, metric contracts, E3 effect-label rules, and regression tests.

It does **not** claim that external datasets have been downloaded, licensed for redistribution, normalized, or evaluated. Each external entry remains a candidate until its exact release and license are pinned.

## 1. Acquire and pin sources

For each benchmark, create a local acquisition record containing:
- upstream URL and exact repository commit / dataset revision;
- license text and intended-use permission;
- archive checksum;
- original split and evaluator version;
- source schema and mapping decisions;
- server/tool availability and credentials required (never store credentials in the dataset);
- whether the source exposes an independent oracle or only trajectories/model judgments.

Recommended first wave:

| Dataset | Use in PaMCP | Important boundary |
|---|---|---|
| MCP-Atlas public release | Cross-server multi-step discovery and execution | Public HF release has 500 tasks; full benchmark describes 1,000 including 500 private tasks |
| ToolRet | Large-scale heterogeneous retrieval | Not MCP execution or safety ground truth |
| MCPVerse time-invariant v1.1 | MCP task and registry scale/evolution | Pin snapshot; original live servers may be unavailable |
| Toolathlon-Verified | Long-horizon composition and execution | Use verified final release and native evaluator |
| MCPTox | MCP tool-description poisoning | Attack outcomes are not operational-effect labels |
| InjecAgent | Indirect prompt injection | Not specifically an MCP registry benchmark |
| BFCL V4 | Function-call correctness and multi-turn behavior | Function-call benchmark, not provenance assurance |
| τ³-bench | Stateful policy compliance | Use current fixed tasks; not MCP tool discovery |
| MCP-Universe | Real-world MCP execution | Pin environment, task version and evaluator |

## 2. Normalize a source export

The adapter requires explicit collection keys rather than guessing source schemas.

```bash
python -m pip install -e ".[test,experiment]"
python -m taas.experiments.benchmark_adapters \
  --dataset-id mcp_atlas_public \
  --tools /content/source/tools.json \
  --tasks /content/source/tasks.json \
  --output /content/processed/mcp_atlas_public \
  --tool-collection tools \
  --task-collection tasks
```

For ToolRet, adapt the upstream export to the adapter's minimal source shape first, preserving original IDs and relevance grades. Do not flatten multiple relevance grades to a binary label without recording that transformation.

## 3. Output layout and leakage boundary

The adapter creates:

```text
processed/<dataset>/
  manifest.json
  discovery/
    tools.json
    tasks.json
  evaluator/
    task_references.json
```

Only discovery/ is passed to the retrieval/discovery system. The evaluator reads evaluator/ after predictions have been materialized.

Never mount evaluator references into the discovery process, prompt, index, model profile, or baseline training unless the data is explicitly part of the training split.

## 4. Identity mapping

Before merging datasets, build an explicit identity crosswalk:

`(dataset_id, source_tool_id) -> (server_id, canonical_tool_id, definition_hash)`

Do not merge tools by name alone. If server identity cannot be resolved, preserve the source-local identity and mark it unresolved. Do not guess provider identity.

## 5. Required split checks

For every source that supports it:
- task-disjoint train/test;
- tool-disjoint train/test;
- server-disjoint train/test for generalization claims;
- near-duplicate prompt detection across datasets;
- duplicate definition detection by canonical hash.

ToolRet and MCP-specific tasks must be reported as separate evaluation tracks. Cross-dataset overlap must be reported, not silently deduplicated from test sets.

## 6. E3 independent effect references

Use E3_EFFECT_REFERENCE_PROTOCOL.md. MCP annotations remain declarations. A false readOnlyHint is not a positive write label. Missing hints remain unknown.

E3 is blocked until isolated runtime traces and adjudicated effect labels exist. Synthetic fixtures only validate the software pipeline.

## 7. Metrics

Use metric_contracts_v2.json. Publish both Exposure@k and UnsafeShare@k; if no independent unsafe reference exists, the safety metric is null. Always report retrieval coverage and unconditional utility with conditional utility.

## 8. Run tests

```bash
python -m pytest -q \
  tests/test_pamcp_benchmark_io.py \
  tests/test_pamcp_benchmark_adapters.py \
  tests/test_declared_effects_are_not_observations.py
```

The GitHub Actions PaMCP workbench workflow includes these tests and validates the benchmark and metric registries.

## 9. Publication rule

A benchmark adapter passing unit tests proves schema-handling behavior only. It does not prove benchmark fidelity, successful task execution, independent ground truth, or PaMCP superiority. Those claims require a pinned acquisition, source-specific validation, independent oracle, and completed experiment run.
## 2.1 MCP-Atlas public parquet adapter

The public dataset card specifies a parquet row with TASK, ENABLED_TOOLS, PROMPT, GTFA_CLAIMS, and TRAJECTORY. It contains 500 public tasks under CC-BY-4.0. Install the parquet dependency already declared by the experiment extra.

```bash
hf download ScaleAI/MCP-Atlas --repo-type dataset --local-dir data/raw/mcp_atlas
python - <<'PY'
from pathlib import Path
from taas.experiments.mcp_atlas_adapter import adapt_mcp_atlas_parquet

files = sorted(Path("data/raw/mcp_atlas").glob("*.parquet"))
if len(files) != 1:
    raise RuntimeError(f"Expected one parquet file, found {len(files)}")
print(adapt_mcp_atlas_parquet(files[0], "data/processed/mcp_atlas_public"))
PY
```

The adapter keeps per-task ENABLED_TOOLS visibility separate from the global union of definitions. It puts GTFA_CLAIMS and TRAJECTORY only in the evaluator directory. A successful trajectory is not assumed to be the only valid toolchain.

## 2.2 ToolRet adapter

ToolRet requires the complete candidate corpus in addition to query records with graded qrels. Do not construct the corpus from positive labels. Convert the upstream source files to two JSON arrays with these shapes:

- Corpus: `{ "id": "source-tool-id", "doc": { "name": "...", "description": "...", "parameters": {} } }`
- Task: `{ "id": "query-id", "query": "...", "labels": [{ "id": "source-tool-id", "relevance": 2 }] }`

Preferred: use adapt_toolret_hf(output_dir, revision, query_configs=None, tool_configs=None) from taas.experiments.toolret_adapter after installing the benchmark-hf extra. The revision is mandatory and must be an immutable Hugging Face commit, not main. The adapter loads mangopy/ToolRet-Queries and mangopy/ToolRet-Tools using the upstream dataset configs. For offline exports, use adapt_toolret_records(tasks, corpus, output_dir, task_source_path, corpus_source_path). The adapter preserves graded relevance judgments in evaluator-only files and keeps ToolRet IDs source-local; it does not fabricate MCP server identities.