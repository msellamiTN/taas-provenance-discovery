# TaaS — Provenance-Aware Tool Discovery for LLM Agents in MCP Ecosystems

Reference implementation and full experimental study of

> M. Sellami and H. Mezni, *Tool-as-a-Service: Provenance-Aware Tool Discovery for LLM Agents in Model
> Context Protocol Ecosystems*, IEEE Transactions on Services Computing (manuscript).

The paper reframes MCP tool discovery as **closing the capability gap** of the deployed model: find the
lowest-cost *evidenced* toolkit that makes a dynamically generated goal achievable under the principal's
policy, and deliver it with a **pre-execution certificate** that holds for any call order. This
repository implements every definition, proposition and algorithm of the paper, reproduces its three
scenarios exactly, and tests the four hypotheses of its evaluation plan on the public registries of
Table 1 (LiveMCPTool + MCPToolBench++, 76 servers, 569 tools).

## What is here

| Path | Content |
|---|---|
| `src/taas/` | the library: contracts, provenance & trust policy, bitmap eligibility, capability hypergraph, model profile ρ_LLM, Algorithms 1–3, certificate, refinement, maintenance, sanitised manifest, LLM roles |
| `src/taas/scenarios.py` | the paper's Figs. 1–3 / Tables 5–6 as executable registries |
| `experiments/` | E0–E7 (H1–H4, RQ3, ablations, scalability), `run_all.py`, `plot.py`, `report.py` |
| `tests/` | 40 tests: Props. 1–3, Lemma 1, Obs. 1, Property 1, algorithms, scenarios |
| `data/processed/` | merged 569-tool registry, tasks, type vocabulary Θ, measured model profiles |
| `data/llm_records/` | every LLM output used (recorded once, replayed by the experiments) |
| `docs/PAPER_ANALYSIS.md` | deep analysis: formal model, proof checks, algorithm walk-through, ambiguity log, traceability |
| `docs/ARCHITECTURE.md` | module map, Mermaid class and sequence diagrams |
| `docs/EXPERIMENT_DESIGN.md` | hypotheses, datasets, baselines, metrics, stages, threats to validity |
| `docs/GITHUB_RESEARCH.md` | related open-source code read for this work and what was reused |
| `docs/RESULTS.md` | all results, generated from `results/*.json` |

## Quick start

```bash
pip install -r requirements.txt
python -m pytest -q                      # 40 tests
python experiments/run_all.py            # all experiments + figures (~30 min on 2 CPUs)
python experiments/report.py             # regenerate docs/RESULTS.md
./reproduce.sh                           # all of the above
```

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

## Headline results

See `docs/RESULTS.md` for every number with confidence intervals and `docs/PAPER_ANALYSIS.md` §6 for
what they imply for the manuscript.

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
  exact (Prop. 3) with no stale answers. Incremental maintenance is about 150× faster than a rebuild, and
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
