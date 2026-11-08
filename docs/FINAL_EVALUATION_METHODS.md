# PaMCP final evaluation — methods

Companion to `docs/FINAL_EVALUATION.md` (findings) and `docs/FINAL_EVALUATION_TABLES.md` (generated tables).
Plan, evidence classes and the preregistered confirmatory family: `docs/FINAL_EVALUATION_PLAN.md`.

## Data

* Registry: LiveMCPTool (525 tools, 69 servers) and the original MCPToolBench++ tool set (87 tools, 10 servers;
  pinned release `2bd35e5`, raw files hashed in `results/final/E1_registry.json`) merged by `server::name` into
  569 tools on 76 servers.
* Tasks: 95 LiveMCPBench test tasks (94 with a resolvable gold tool); the 60-query MCPToolBench++ development
  split; a 300-query MCPToolBench++ evaluation sample (50 distinct queries per category, excluding the
  development split, seed 7); all 1,509 MCPToolBench++ requests for methods without LLM inputs.

## Labels

* **Labels A** (`silver_labels.json`, Claude Sonnet): effects, state modification, private output, types and
  tool class. They provide the engine's typing τ and drive the simulated verifier.
* **Labels B** (`reference_labels_opus_part*.jsonl`, Claude Opus): a blind second labelling under a separately
  written guide (`docs/REFERENCE_LABELING_GUIDE.md`); the labelling agents were instructed not to open labels A,
  their guide or any result. Labels B are used only for scoring. Agreement with A: κ = 0.944 (state
  modification), 0.893 (private output). Both are LLM labels from one model family; neither is human ground
  truth. A blank, stratified two-annotator sheet (150 tools, disagreements over-sampled) is in
  `docs/annotation/E2_human_annotation_sheet.csv`.

## Recorded LLM inputs (all replayed; no LLM call at evaluation time)

| Role | Model | File(s) | Items |
|---|---|---|---|
| Analyst goal contracts | Sonnet | `analyst_sonnet_A/B.jsonl`, `analyst_sonnet_e8_part*.jsonl` | 158 + 300 |
| MCP-Zero active requests | Sonnet | `mcpzero_requests_sonnet_part*.jsonl` | 455 tasks |
| MCP-Zero server summaries | Sonnet | `mcpzero_server_summaries_sonnet.jsonl` | 76 servers |
| COLT training queries (ToolLens-style) | Sonnet | `colt_train_queries_sonnet_part*.jsonl` | 450 scenes |
| ToolScope equivalence judgements | Sonnet | `toolscope_equiv_sonnet_part*.jsonl` | 638 pairs |
| Reference labels B | Opus | `reference_labels_opus_part*.jsonl` | 569 tools |
| Calibration answers | Opus (new), Sonnet, Haiku | `calibration_answers_*.json` | 64 items each |
| Calibration self-assessment | Sonnet, Haiku, Opus | `calibration_self_assessment_*.json` | 16 cells each |

Prompts for the new roles: `docs/llm_protocols/`. Exact model version strings were not exposed to the session
and are not recorded.

## Methods compared (protocol baseline ids)

All methods share the registry, the contracts and the dense encoder (a TF-IDF + truncated-SVD stand-in; no
neural encoder could be installed offline). None of the baselines was tuned.

| Id | Implementation |
|---|---|
| `bm25`, `dense_lsa`, `rrf` | lexical, dense and reciprocal-rank fusion over raw tool text |
| `rag_mcp` | dense top-k over the whole request (RAG-MCP); identical to `dense_lsa` for single-tool ranking |
| `mcp_zero` | recorded model-written requests (server, tool); routing to the top-3 servers by the max of summary and description similarity, tools ranked by (s_srv·s_tool)·max(s_srv, s_tool); top-1 per request; one round (the paper's refinement round is not replayed) |
| `per_subtask` | one tool per analyst subgoal (lexical + dense), union |
| `colt_adapted` | semantic stage = shared encoder (no PLM fine-tuning); collaborative stage = parameter-free LightGCN over a query–scene–tool graph built from training queries only (450 generated multi-tool scenes + MCPToolBench++ requests outside every evaluation split); score = sim(q,t) + 0.5·sim(q,t̃) + 0.5·scene completion |
| `toolscope_adapted` | merger: top-5 neighbours with cosine ≥ 0.7 → 638 candidate pairs → recorded LLM equivalence → 17 equivalent pairs, 16 multi-tool clusters, representative = shortest name; member identities, hashes and effects preserved; retriever: dense (α = 1), analyst subqueries top-1 then filled to k; a merged tool counts as each of its members; no cross-encoder reranker |
| `cmtf_adapted` | breadth-first search over sets of available semantic types; actions = top-40 relevant tools per goal whose required inputs are available; goal = output types of all non-optional goals (no model coverage); unit cost; ties by relevance; depth ≤ 6, ≤ 5,000 expanded states; frontier = first tool, path = all tools on the plan |
| `all_tools` | the whole visible registry |
| PaMCP cells | G (capability gap) × P (provenance-sound eligibility) × S (set-level reasoning and certification); S = 0 is per-subgoal retrieval over the eligible pool with no closure, cover or certificate; P = 0 accepts published metadata (annotations, lexical cues) at face value (ℓmin = lex) |

Policy encodings (E4–E7): no filter; MCP defaults (annotations displayed, not enforced; identical exposure to
no filter); closed-world annotations (readOnlyHint = true required); positive and closed-world lexical (on this
registry the engine's lexical labeller gives a read cue to every tool without a write cue, so the two
coincide); verified evidence (observed or attested evidence at ℓobs from the simulated verifier); observed
with lexical fallback for unprobed tools; attested only.

## Metrics

Exp@k (share of requests whose top-k contains a tool that is not read-only under labels B; primary
denominator: requests whose gold tools are all read-only under B), Util@k (gold tool in top-k on the same
requests), Hit@k, MRR@10, tool-macro Hit@1, group recall (share of gold groups hit; alternatives count once),
complete-set share (COLT's COMP), set precision, toolkit size, tokens of the raw definitions
(characters/4), joint feasibility and per-check pass rates from the independent set evaluator
(`experiments/final/set_evaluator.py`), reachable out-of-scope actions (worst case under labels B),
description- and output-borne exposure, latency percentiles, and for refinement the repair rate by first
counterexample type.

## Statistics

Paired sign-flip permutation tests (exact up to 16 non-zero pairs, otherwise 20,000 random sign vectors),
percentile bootstrap CIs (4,000 resamples; target-tool clusters for request-level metrics), Wilson intervals for
proportions, Holm correction over the preregistered family F1–F7, non-inferiority margin 0.05 for recall.
Seeds are replicates, not independent observations.

## Not run in this environment

E13 (end-to-end execution), E21 (experience reuse vs AutoTool), E3's observed effects and E14's executed
actions need executed MCP servers and task oracles; E2's human study needs annotators; E19 and E17's
assistant-role variants need further role-configuration runs; E12's 10-class, 30k-item, three-script corpus
and E10's distractor-server dimension were not built.
