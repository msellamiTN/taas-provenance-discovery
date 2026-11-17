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

## Demo video

End-to-end reviewer walkthrough (~1:45): open the Colab notebook → connect a
runtime → run all → get the Studio proxy URL → tour the lifecycle UI.

https://github.com/user-attachments/assets/cb82ebd6-3736-4438-b343-f67440e2bfdb

▶ **[Open the interactive player](https://msellamitn.github.io/taas-provenance-discovery/studio/reviewer/watch.html)** · [MP4 download](https://github.com/msellamiTN/taas-provenance-discovery/releases/download/studio-reviewer-demo/taas-studio-full-walkthrough.mp4)

Reviewer quickstart: [`docs/studio/reviewer/README.md`](docs/studio/reviewer/README.md)
· Notebook: [`notebooks/colab/taas_studio_reviewer_colab.ipynb`](notebooks/colab/taas_studio_reviewer_colab.ipynb)

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

## How to use

**1 · Python library (local).** Install and drive the engine directly:

```bash
pip install -e .                    # core library only
pip install -e ".[test,studio,hf]"  # tests + Studio UI + HF extras
```

- `DiscoveryEngine(registry, profile, pair_policy=...).discover(spec, policy)` → gap, toolkit, certificate
- Scenario registries live in `taas.scenarios`; real 569-tool registry under `data/processed/`
- `python -m pytest` runs the full suite (751 tests: contract, algorithms, Studio API, lifecycle scenario, browser E2E)

**API keys — when they are needed.**

| Variable | Required when | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | Regenerating `data/llm_records/` live via `taas.llm.backends.AnthropicAnalyst` | Not needed to run experiments — they replay recorded outputs |
| `TAAS_STUDIO_API_TOKEN` | Running TaaS Studio (UI + every `/api/v1` write/read) | Fails closed: 503 if unset, 401 on mismatch. The Colab notebook generates an ephemeral one automatically |
| `TAAS_EVIDENCE_ATTESTATION_KEY` | Evidence signing, signatures, approvals, freshness checks | Persist across restarts or prior signatures invalidate |
| `TAAS_STUDIO_ACTOR` | Optional — actor name attached to writes when using the shared token | Named API keys (`ak_*`) bind the actor per caller; see `docs/deployment/STUDIO_OPERATIONS.md` |

**2 · TaaS Studio (web UI, zero install).** The control-plane UI walks the
agent/tool lifecycle — DEFINE → BUILD → DISCOVER → VERIFY → OPERATE →
EVALUATE & MANAGE. No GPU needed:

- Open [`notebooks/colab/taas_studio_reviewer_colab.ipynb`](notebooks/colab/taas_studio_reviewer_colab.ipynb)
  in Colab → **Runtime → Run all** → copy the printed token → open the proxy
  URL → **Connect**. Step-by-step guide and video in
  [`docs/studio/reviewer/README.md`](docs/studio/reviewer/README.md).
- Studio boundaries (by design): MCP inspection is `tools/list` only — never
  `tools/call`; discovery records are observations, not execution; the audit
  chain is tamper-evident, not proof of truth; unsupported live data shows
  `UNAVAILABLE`.

**3 · Assurance & registry surfaces.** Other Colab notebooks in
[`notebooks/colab/`](notebooks/colab/) cover acceptance (`taas_studio_acceptance_colab`
— 29-check A1→A6 matrix), hypergraph exploration, evidence assurance, and the
PR-27 MCP registry demo.

## Experiments

`experiments/run_all.py` executes the full evaluation plan deterministically
(replaying `data/llm_records/`; no API key required). `experiments/report.py`
regenerates `docs/RESULTS.md`; `experiments/plot.py` regenerates figures;
`./reproduce.sh` runs everything end-to-end.

| Script | What it tests |
|---|---|
| `e0_registry.py` | **E0/H1** — Table 1 registry characterisation on published metadata |
| `e2_eligibility.py` | **E2/H2** — provenance-sound eligibility vs forged/missing metadata |
| `e3_gap.py` | **E3/H3** — gap analysis shrinks toolkits at equal coverage |
| `e3_tune.py` | **E3-tune** — Stage 2 baseline tuning on the dev split only |
| `e4_injection.py` | **E4/H4** — certified toolkits under prompt injection; Property 1 |
| `e5_synthetic.py` | **E5/RQ3** — controlled synthetic typed registries, backward closure |
| `e6_ablations.py` | **E6** — Stage 4 ablations (relevance term, propagation, encoders) |
| `e7_scalability.py` | **E7/RQ4** — eligibility cost, cache invalidation (Prop. 3), Lemma 1, maintenance |

Run one stage directly, e.g. `python experiments/e3_gap.py`. Deviation notes:
see **Deviations and limitations** below before citing numbers.

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
