# TaaS — Provenance-Aware Tool Discovery for LLM Agents in MCP Ecosystems

Research prototype and reference implementation for the TaaS / PaMCP study:

> M. Sellami and H. Mezni, *Tool-as-a-Service: Provenance-Aware Tool Discovery for LLM Agents in Model
> Context Protocol Ecosystems*, IEEE Transactions on Services Computing (manuscript).

The discovery core models MCP tool capabilities, provenance-aware eligibility, model-conditioned goal
gaps, toolkit composition and pre-execution certificates. TaaS Studio exposes the discovery workflow and
the new E1–E22 experimental workbench. This repository is a research prototype: the experiment catalogue
and selected baseline adapters are implemented, but the durable sequential runner, independent evaluator,
live MCP probe/runtime and full E1–E22 execution pipeline are still being built.

## What is here

| Path | Content |
|---|---|
| `src/taas/` | discovery core, provenance/trust, bitmap eligibility, capability hypergraph, model profiles, certificates, refinement, maintenance, Studio APIs and experiment/baseline adapters |
| `src/taas/scenarios.py` | the paper's Figs. 1–3 / Tables 5–6 as executable registries |
| `experiments/` | Legacy E0–E7 scripts plus the new E1–E22 catalogue validator; the legacy runner is not the definitive study runner |
| `tests/` | 40 tests: Props. 1–3, Lemma 1, Obs. 1, Property 1, algorithms, scenarios |
| `data/processed/` | merged 569-tool registry, tasks, type vocabulary Θ, measured model profiles |
| `data/llm_records/` | every LLM output used (recorded once, replayed by the experiments) |
| `docs/PAPER_ANALYSIS.md` | deep analysis: formal model, proof checks, algorithm walk-through, ambiguity log, traceability |
| `docs/ARCHITECTURE.md` | module map, Mermaid class and sequence diagrams |
| `docs/EXPERIMENT_DESIGN.md` | hypotheses, datasets, baselines, metrics, stages, threats to validity |
| `docs/GITHUB_RESEARCH.md` | related open-source code read for this work and what was reused |
| `docs/RESULTS.md` | all results, generated from `results/*.json` |

## Publication visualization framework

The publication plot registry contains 80 figure contracts for E1-E22, with explicit axes, input columns, comparison assignments and uncertainty conventions. The plotting layer does not execute experiments or fabricate result rows.

Install and validate the plotting framework:

```bash
pip install -e ".[visualization,test]"
python experiments/plot_results.py validate
python experiments/plot_results.py init-templates
```

Populate the generated CSVs only from validated experiment outputs. E8 has a separate source-preparation, ranking, task-level export and partial-figure workflow; do not use strict four-figure rendering until its B1/B1m and distractor-sweep inputs are available:

```bash
E8_DEVICE=cuda bash experiments/run_e8_and_plot.sh
```

For an interactive Colab run with Google Drive persistence, open the [PaMCP E8 Colab notebook](https://colab.research.google.com/github/msellamiTN/taas-provenance-discovery/blob/feature/pamcp-publication-visualization-v1/experiments/colab/E8_Retrieval_Campaign.ipynb). The current source/result readiness boundary is recorded in [docs/E8_EXECUTION_READINESS.md](docs/E8_EXECUTION_READINESS.md).

Full workflow and per-figure axes are documented in [docs/VISUALIZATION_FRAMEWORK.md](docs/VISUALIZATION_FRAMEWORK.md), the [E8 execution runbook](docs/E8_EXECUTION_AND_EXPORT.md), the [E8 readiness report](docs/E8_EXECUTION_READINESS.md), the [E9 execution runbook](docs/experiment_design/E9_EXECUTION_RUNBOOK.md), the [E9 readiness report](docs/experiment_design/E9_EXECUTION_READINESS.md), the [80-figure catalogue](docs/FIGURE_CATALOG.md), , the [dataset-led execution sequence](docs/experiment_design/DATASET_LED_EXECUTION_SEQUENCE.md), and [docs/experiment_design/pamcp_plot_plan_v1.json](docs/experiment_design/pamcp_plot_plan_v1.json).

## Definitive PaMCP experimental workbench

The definitive E1–E22 design is versioned in `docs/experiment_design/pamcp_experiments_v1.json`. Its 31 method cards and experiment-specific baseline assignments are in `docs/experiment_design/pamcp_baselines_v1.json`.

The primary TaaS Studio app (`taas.studio.api:app`) mounts:
- `/api/v1/experiments` for E1–E22, the four named PaMCP variants, the complete eight-cell factorial and run-draft validation.
- `/api/v1/baselines` for baseline method cards and controlled adapter previews.
- The browser workspace contains an **Experiments & baselines** section. E18 presents all eight G×P×S cells; other experiments show only their assigned baseline methods.

The baseline preview executes local retrieval, policy-control and PaMCP variant adapters over a supplied GoalSpec/tool snapshot. It is **not** a persisted experiment run and does not read evaluator labels, invoke MCP tools or measure task success. Methods requiring live probes, runtime security hooks, confirmed trajectories, or external profile calibration return blocked/not-implemented states until those dependencies exist.

Install and launch the primary Studio:

```bash
pip install -e ".[studio,experiment,test]"
export TAAS_STUDIO_API_TOKEN='replace-with-a-strong-random-token'
uvicorn taas.studio.api:app --host 127.0.0.1 --port 8000
```

All E1–E22 definitions begin as `planned_not_run`. Historical E0–E7 outputs and Claude-session replay artifacts are retained for provenance only; they are **superseded exploratory material and are not evidence for the definitive E1–E22 study**.

## Quick start

```bash
python -m pytest -q
python experiments/catalog_cli.py validate
python experiments/catalog_cli.py baselines
```

The legacy `python experiments/run_all.py` pipeline still runs the superseded E0–E7 programme. Do not use it to generate results for the definitive E1–E22 manuscript.

Minimal use on the paper's motivating scenario:

```python
from taas.scenarios import reviews_registry, reviews_spec, reviews_policy, illustrative_profile
from taas.engine import DiscoveryEngine

eng = DiscoveryEngine(reviews_registry(), illustrative_profile(), pair_policy=reviews_policy())
r = eng.discover(reviews_spec(), reviews_policy())
print([g.id for g in r.gap.gap], r.toolkit, r.certificate.checks)
# ['g1', 'g5'] ['db::query_reviews', 'report::generate'] {'S': True, 'C': True, 'P': True, 'E': True, 'L': True, ...}
```

## How the LLM was used

The build environment had no API key, so the LLM roles were played by **Claude models through
sub-agents of the build session**, and every output was recorded to `data/llm_records/`:

* silver effect labels and LLM-assisted typing of all 569 tools (Claude Sonnet; guide in `docs/LABELING_GUIDE.md`);
* analyst-role goal contracts for 158 prompts (Claude Sonnet) and 98 prompts (Claude Haiku; guide in `docs/ANALYST_GUIDE.md`);
* a ρ_LLM calibration run, 64 items × 2 models, answered by reading only (tool logs checked).

Experiments replay these records, so results are deterministic. `taas.llm.backends.AnthropicAnalyst`
regenerates them live when `ANTHROPIC_API_KEY` is set.

## Legacy exploratory results — superseded, not used by E1–E22

These values belong to the superseded E0–E7 exploratory pipeline. They are retained for historical traceability only and must not be cited as results of the definitive E1–E22 protocol.

* **Table 1 replicates exactly** (76 / 569 / 44; one annotated tool is not read-only; 7.7% kept by
  required hints).
* **H2 holds.** MCP's default annotation reading is unsound under forgery, and reading missing hints as
  safe filters nothing. Verified-evidence eligibility has zero exposure at FAR = 0 for every forgery
  rate, and its exposure grows roughly linearly with the verifier's false-accept rate.
* **H4 holds.** Certified toolkits leave no out-of-scope injected action executable, against a few
  percent for retrieval baselines and all of them for the full registry. The effect bound held in every
  simulated call order.
* **Property 1 needs the conservative reading of (L).** If labels are propagated only along the
  composition's derivations, about one simulated call sequence in six realises a forbidden flow. With
  context-wide propagation none does, and the χ5 split repairs the revenue scenario.
* **H3 holds in part.** Gap analysis shrinks toolkits by about 28% at equal recall and gives the most
  precise, smallest toolkits. On real registries, though, gold-tool recall stays below per-subtask and
  RAG retrieval. Most of the shortfall comes from Eq. 6 having no relevance term and from type-vocabulary
  mismatches. Adding a relevance term, tuned on dev, doubles test recall over pure Eq. 6.
* **Composition (RQ3).** On synthetic typed registries the exact regime is always valid and optimal.
  Without backward closure only 6% of tasks are solved; per-subtask retrieval solves 67%.
* **Evolution (RQ4).** Bitmap eligibility answers in microseconds at 10⁵ tools. Cache invalidation is
  exact (Prop. 3) with no stale answers. Incremental maintenance is about 100× faster than a full rebuild (32 ms vs 3.0 s), and
  rug-pulled definitions lose their evidence.

## Deviations and limitations (read before citing numbers)

* **Relevance term** in the cost (w_rel·(1 − retrieval score)); `relevance=0.0` restores Eq. 6. Tuned on
  the MCPToolBench++ dev sample only.
* **Conservative flow propagation** is the default; the derivation reading is available as an ablation.
* **Dense retrieval** uses a local LSA encoder because BGE-M3 could not be downloaded; it is weaker than
  BM25 alone (E6).
* **Ground truth J** is an LLM silver labelling, not sandbox traces; the verifier is simulated with a
  controlled false-accept rate. No MCP server was executed.
* **Task success** was not executed end to end; gold-tool recall penalises minimal toolkits when gold
  lists alternative tools.
* All other open points of the paper and their resolutions are listed in `docs/PAPER_ANALYSIS.md` §5.

## Data and licences

LiveMCPBench / LiveMCPTool (Apache-2.0, commit `36a51a1`) and MCPToolBench++ (MIT, commit `2bd35e5`);
see `data/raw/SOURCES.txt` and `scripts/fetch_data.sh`. No licence has been chosen yet for this
repository's own code.
