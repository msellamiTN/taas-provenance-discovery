# Experiment design

The paper ends with an evaluation plan (§8): four hypotheses tested "on the registries of Table 1 and
on runnable reference servers", with ablations of the dual LLM roles, the cost weights and manifest
sanitisation. This design implements that plan with the four-stage progression of the
`experiment-design` skill. `docs/experiment_design.json` is the machine-readable form.

## Data

| Dataset | Content | Role |
|---|---|---|
| LiveMCPTool / LiveMCPBench (Apache-2.0, `36a51a1`) | 69 servers, 525 tools, 95 tasks with annotated tool chains | registry; **test** split for H3/H4 |
| MCPToolBench++ (MIT, `2bd35e5`) | 10 servers, 87 tools, 1,509 single-call requests | registry; 60-query **dev** split (10/category) for tuning; all 1,509 for retrieval ablation |
| Merged registry | 76 servers, 569 tools by `server::name` | Table 1 |
| Paper scenarios | Figs. 1–3, Tables 5–6 as contracts | acceptance tests |
| Synthetic typed registries | hidden chains, 5 distractor kinds, brute-force optimum | RQ3 under control |

## LLM roles and recorded outputs (session-based)

No API key exists in the build environment, so every LLM output was produced once by Claude models
through sub-agents of the build session and recorded in `data/llm_records/`; experiments replay them.

| Output | Model | Use |
|---|---|---|
| silver effect labels J (effects, modifies_state, private_source) | Claude Sonnet | ground truth for H1/H2/H4 — never used as evidence |
| LLM-assisted typing τ (in/out types, class) | Claude Sonnet (same pass) | contract extraction (§6.1) |
| analyst goal contracts, 158 prompts | Claude Sonnet | H3/H4 request path |
| analyst goal contracts, 98 prompts | Claude Haiku | analyst ablation |
| ρ_LLM calibration answers, 64 items × 2 models | Claude Haiku, Claude Sonnet | measured profiles |

Calibration items were answered with the Read tool only (verified from the agents' tool logs) and the
gold answers were held outside the workspace until scoring.

## Hypotheses, metrics, baselines

| Exp. | Hypothesis (paper §8) | Metrics | Baselines / variants | Seeds |
|---|---|---|---|---|
| E0 | registry characterisation (Table 1, §2.2); H1 at registry level | counts, shares, lexical-vs-silver P/R | — | — |
| E2 | **H2** provenance-sound eligibility removes unsafe tools under forged/missing metadata; exposure grows with the verifier's FAR | exposure, unsafe share of Elig, safe retention | ann+ (MCP default), ann-cw, lex+, lex-cw, **obs+**, att+; α ∈ {0,.1,.25,.5}, FAR ∈ {0,.01,.05,.1,.2}, coverage sweep | 5 |
| E3 | **H3** gap analysis shrinks toolkits without loss of task coverage; bridge ratio reported | |K|, tokens, gold recall, boundary recall, precision, abstention, validity, β | ours, ours-nogap, ours-strict, per-subtask, per-subtask-gap, RAG top-3/5, MCP-Zero, all-tools | deterministic |
| E3-tune | Stage 2 tuning on dev only | recall, |K| | K ∈ {3,5,10} × w_rel ∈ {0,1,3,10} | — |
| E4 | **H4** certified toolkits reduce executed unsafe actions under injection; Property 1 | worst-case and stochastic ASR (out-of-scope), recall; runtime effect/flow violations | certified (conservative / derivation flow, FAR 0/.05), per-subtask, RAG top-5, MCP-Zero, all-tools | 3 |
| E5 | RQ3 composition: closure, sharing, optimality | validity (independent checker), optimal rate, cost/opt, time | exact, greedy, no-closure, per-subtask; L ∈ {2,3,4}, distractors ∈ {3,5} | 8 |
| E6 | ablations (§8) | as E3; retrieval R@k; injection leakage, tokens | relevance off, structural off, Alg.1 literal, rule 1 off, strict profile, Haiku profile, Haiku analyst, no refinement, derivation flow, depth 0; lex/den/RRF; sanitised vs raw manifest | — |
| E7 | RQ4 evolution and cost | eligibility µs, Prop. 3 confusion, Lemma 1, incremental vs rebuild, rug pull | bitmap vs scan; n ∈ {10³,10⁴,10⁵} | 1–3 |

## Stages

1. **Initial implementation** — scenarios of Figs. 1–3 reproduce Γ and K exactly (tests).
2. **Baseline tuning** — E3-tune on the dev split selects K = 5, w_rel = 10, applied unchanged on test.
3. **Creative research** — the relevance term, conservative flow propagation with the χ5 split,
   uncertain-match repair, effect-purpose matching; each traced to a failure observed on real data.
4. **Ablations** — E6.

## Threats to validity (stated up front)

* Silver labels are LLM judgements, not sandbox traces; H2/H4 measure soundness *relative to J*.
* The verifier is simulated with a controlled FAR; no MCP server was executed in this study.
* Gold tool lists in LiveMCPBench include alternatives, so gold recall penalises minimal toolkits;
  task success was not executed end to end.
* The dense retriever is an LSA stand-in for BGE-M3 (blocked download); E6-A shows it is weaker
  than BM25 alone.
* The analyst and labeller are from one model family (Claude); the Haiku analyst is the only
  cross-model ablation.
