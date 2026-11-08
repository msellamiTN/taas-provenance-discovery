# PaMCP final evaluation — findings

Branch `research/pamcp-final-evaluation`. Methods: `docs/FINAL_EVALUATION_METHODS.md`; plan, evidence classes and
the preregistered confirmatory family: `docs/FINAL_EVALUATION_PLAN.md`; every number below is in
`docs/FINAL_EVALUATION_TABLES.md` (generated from `results/final/*.json`; raw per-item records in
`results/final/raw/`). Each result file carries a run id, the code commit and content hash, input, label and
LLM-record hashes, and its configuration.

## Summary

* Eligibility (RQ2) is where the approach is strongest: published annotations cover 44 of 569 tools, a fifth of
  the tools are not read-only, and reading missing annotations as safe exposes 42.5% of the requests; verified
  evidence removes that exposure (by construction of the simulation) at a utility cost of 3.6 points, and stays
  better than lexical cues while the verifier's false-accept rate is below 10% (5% with random errors).
* Certified toolkits are small (1.2–1.5 tools) and leave no out-of-scope action reachable offline, mostly through
  eligibility; they do not raise joint feasibility over eligible baselines (F3 n.s.).
* Negative results: typed retrieval from goal contracts collapses on the merged registry (Hit@1 23.0%, F7
  against PaMCP); set-level reasoning costs recall (Shapley −0.060); recall is below retrievers that expose
  more tools, and non-inferiority to per-subtask retrieval is not shown (F1).
* Not run: E13 (execution), observed effects (E3), human typing study (E2), E19 role configurations, E21
  experience reuse.

## Evidence ledger

| Series | Status | Evidence class |
|---|---|---|
| E1 Registry characterisation | run (3 views) | MEASURED; LABELLED for the not-read-only share |
| E2 Semantic typing | proxy run; human study BLOCKED (sheet prepared) | LABELLED (agreement, not accuracy) |
| E3 Declared vs observed effects | declared/lexical vs labels B; observed BLOCKED | LABELLED |
| E4–E7 Exposure, forgery, verifier, trust | run | SIMULATED evidence, LABELLED scoring |
| E8 Single-tool retrieval | run | MEASURED (benchmark gold) |
| E9 Set retrieval | run | MEASURED (benchmark gold) |
| E10 Set validity | run | LABELLED (independent evaluator) |
| E11 Capability gap | partial (task success BLOCKED) | MEASURED (engine) |
| E12 Profile calibration | partial (64-item set, 3 models) | MEASURED |
| E13 End-to-end execution | BLOCKED | — |
| E14 Prompt injection | offline only | LABELLED |
| E15 Scalability | run | SYNTHETIC, MEASURED latency |
| E16 Evolution | run | MEASURED |
| E17 Refinement | partial (LLM-free repairs) | MEASURED |
| E18 Factorial ablation | run (task success BLOCKED) | MEASURED / LABELLED |
| E19 LLM role configurations | not run | — |
| E20 Sensitivity | run | MEASURED / LABELLED |
| E21 Experience reuse (AutoTool) | BLOCKED | — |
| E22 Statistics | run | — |

## Reference labels and reproducibility

The blind second labelling (labels B, Claude Opus) agrees with labels A (Claude Sonnet) on 558 of 569 tools
for state modification (κ = 0.944) and on private output with κ = 0.893. Every tool that is not read-only under
B is also not read-only under A (A marks 131 tools, B 120), so verifier evidence simulated from A excludes every
tool B considers unsafe; the independence of B tests over-exclusion, not under-exclusion. Both labellings come
from one model family. Re-running E4, E11 and E12 from the committed code reproduced every reported metric
exactly (1,920 E4 metrics compared).

## E1–E3 Registry, typing and declared effects

* The three views reproduce Table 1 (76 servers, 569 tools, 44 annotated tools on three servers, all declaring
  `readOnlyHint=true`). The original MCPToolBench++ tool set has 87 tools on 10 servers; 43 of them and 3 of the
  servers coincide with LiveMCPTool. Under labels B, 120 tools (21.1%, 95% CI 17.9–24.6%) are not read-only;
  one annotated tool (`opgg-mcp::lol-summoner-renewal`) declares read-only but is not.
* Declarations cover 44 tools, one of them wrong; the other 525 tools, including 119 that are not read-only,
  declare nothing. Lexical cues flag 82.5% of the unsafe tools at precision 0.54.
* Typing: the LLM typing τ used by the engine agrees with labels B on 78.9% of output kinds (κ 0.718, macro-F1
  0.704); the engine's structural typer alone agrees on 22.8% (κ 0.070). Agreement on the full type (kind and
  domain) is 35.7% for τ. This is agreement between two LLM labellings, not accuracy; the human study needs the
  prepared sheet to be filled.

## E4 Exposure under policy encodings

394 requests (300 MCPToolBench++ + 94 LiveMCPBench); 273 have only read-only gold tools under B and form the
Exp@5/Util@5 denominator.

* With no filter (and with MCP's default of displaying annotations without enforcing them) 42.5% of the
  requests get an unsafe tool in PaMCP's top-5 (all 120 unsafe tools are eligible). Closed-world annotations
  admit 44 tools and one unsafe tool, but that tool still reaches 31.5% of the top-5 lists because the pool is
  so small, and utility collapses to 0.4%. Lexical filtering admits 21 of the 120 unsafe tools (Exp@5 9.9%,
  Util@5 41.0%); on this registry the positive and closed-world lexical encodings coincide.
* Verified evidence admits none of the unsafe tools (Exp@5 0% for every retriever) and keeps 77.0% of the
  registry eligible; Util@5 is 46.2% for PaMCP's retrieval stage against 49.8% unfiltered, and 72.2% against
  76.6% for MCP-Zero. As the verifier probes fewer tools, exposure stays at zero and utility falls with the
  eligible share (Util@5 34.7%, 26.8% and 16.3% at coverage 0.75, 0.5 and 0.25).
* The zero exposure follows from the simulation (see Reference labels); the measured content is the utility
  cost and the contrast with the metadata encodings.

## E5 Forged and laundered metadata

Attacker servers (fraction δ, 5 seeds) declare all their tools read-only and/or launder their descriptions; the
verifier has a 5% false-accept rate. Exp@5 / Util@5, PaMCP retrieval stage:

* Forged annotations are what break the closed-world annotation encoding: its exposure rises from 31.5% (δ = 0)
  to 56.8% at δ = 0.1 and 62.6% at δ = 0.3, while utility stays at or below 19.2%.
* Laundering alone barely moves any encoding, because the laundered descriptions keep the tool names, from which
  the lexical labeller takes most of its cues (this favours the lexical encodings): lexical Exp@5 stays between
  8.7% and 9.9%.
* Verified evidence is independent of δ; with a 5% false-accept rate its exposure is 5.4–5.6% (0.0% with the
  single seed at δ = 0) at Util@5 46.1–46.9%.

## E6 Imperfect verifier

δ = 0.2, coverage 1, no false rejections; random errors averaged over 5 seeds, look-alike errors deterministic.

* Exposure of verified evidence grows with the false-accept rate φ: 0, 1.1, 1.1, 5.7, 9.3 and 15.8% at φ = 0,
  1, 2, 5, 10 and 20% with random errors; 0, 1.1, 1.8, 4.4, 4.8 and 13.6% when the errors fall on the unsafe
  tools that most resemble safe ones. The lexical encoding is at 9.2%.
* Break-even against the lexical encoding: φ = 10% for random errors, 20% for look-alike errors (verified stays
  below lexical up to 5% and 10% respectively).
* False rejections cost utility: ψ = 0.2 lowers Util@5 from 46.2% to 39.1% (δ = 0); coverage 0.5 gives 26.8%.

## E7 Trust policy and evidence strength

δ = 0.2, both attacks, φ = 5%, probe coverage κ ~ U(0.3, 1), 3 seeds.

* Default policy, ℓmin ≤ 0.55: eligible 78.0%, Exp@5 5.5%, Util@5 45.8%. ℓmin = 0.65 (observed level):
  63.9% / 3.5% / 34.4%. ℓmin ≥ 0.75 (attested only): 25.4% / 10.3% / 23.1%: exposure rises because the few
  falsely accepted attested tools fill many top-5 lists of a small pool.
* A coverage floor κ ≥ 0.8 at ℓmin = 0.65: 21.6% / 0.6% / 14.3%. Signer-weighted trust at 0.65: 31.2% / 6.5% /
  18.4%.
* A stricter threshold does not lower Exp@k by itself; exposure must be read with the eligible pool size.

## E8 Single-tool retrieval

* On the MCPToolBench++ tool set (B1, 81 tools: the tools only in MCPToolBench++ or used as gold) PaMCP's
  goal-contract retrieval ranks the gold tool first for 66.0% of the 300 sampled requests, second to MCP-Zero's
  model-written requests (68.0%) and ahead of raw-text RRF (54.3%).
* On the merged registry (569 tools) it falls to 23.0%, below every other method (raw-text RRF 38.7%, BM25
  39.7%, MCP-Zero 50.0%, COLT 35.0%, ToolScope 36.0%, CMTF 33.3%); the distractor curve shows the drop growing
  with each added block of LiveMCPTool tools. Confirmatory test F7 (goal contract vs raw-text RRF) therefore
  goes against PaMCP (Δ = −0.157).
* Diagnosis (`E8_diagnostic`): the analyst's goal text alone ranks better than the raw request (Hit@1 40.0% vs
  38.7%); adding the structural component of Eq. (5) drops it to 23.0%, because only 50.3% of the gold tools
  are type-compatible with the analyst's goal output type. With coarse or mismatched typing the structural
  ranking promotes type-compatible wrong tools.
* With 66 target tools for 300 requests, CIs that resample target tools are about three times wider than
  request-level CIs (E22).

## E9 Set retrieval (94 LiveMCPBench tasks, open policy)

| Method | \|K\| | tokens | group recall | COMP |
|---|---|---|---|---|
| PaMCP K = 5 | 1.47 | 199 | 0.169 [0.118, 0.223] | 4.3% |
| PaMCP K = 10 / 20 | 1.46 | — | 0.174 | — |
| PaMCP without closure | 1.40 | 195 | 0.168 | 4.3% |
| Per-subtask (analyst) | 2.59 | 346 | 0.249 | 9.6% |
| MCP-Zero | 1.76 | 250 | 0.227 | 8.5% |
| RAG-MCP top-5 / 10 / 20 | 5 / 10 / 20 | 1,244 (top-5) | 0.293 / 0.397 / 0.494 | 13.8% (top-5) |
| COLT top-5 / 10 | 5 / 10 | 1,094 (top-5) | 0.295 / 0.391 | 12.8% (top-5) |
| ToolScope (analyst) top-5 | 5.20 | 976 | 0.361 | 17.0% |
| CMTF path | 0.64 | 105 | 0.072 | 1.1% |

* Size-matched (84 tasks with a non-empty PaMCP toolkit): PaMCP 0.189, RAG-MCP 0.130, per-subtask 0.138, COLT
  0.084, MCP-Zero ranked 0.200.
* PaMCP abstains on 7.4% of the tasks (6 χ1, 1 χ5) and certifies 92.6%. Backward closure changes recall on 3
  of the 94 tasks.
* Decomposition: per-subtask retrieval reaches 0.105 on the raw request, 0.142 with a clause splitter, 0.249
  with the analyst's subgoals.
* Paired tests (exploratory): PaMCP@5 vs RAG@5 −0.124 (p = 0.016), vs COLT@5 −0.126 (p = 0.013), vs
  per-subtask −0.080 (p = 0.063). F1 (non-inferiority to per-subtask, margin 0.05) is not shown; F2 (size-matched
  vs RAG-MCP) +0.060, p_Holm = 0.397.

## E10 Set validity (least-privilege policy per task, independent evaluator)

* PaMCP (K = 10; K = 20 and 40 identical): joint feasibility 67.0% [57.0, 75.7], 72.4% among non-abstained.
  Checks: S 68.1% (abstentions included), C 97.9%, E, L, V 100%, M 87.2%.
* NoCert: 59.6% (C 88.3%, M 74.5%).
* Baselines restricted to eligible tools: ToolScope 73.4%, per-subtask 62.8%, RAG-MCP 60.6%, COLT 59.6%,
  MCP-Zero 57.4%, CMTF 25.5%. As published: 47.9–59.6% (CMTF 23.4%), effect check failed on 4.3–25.5% of the
  tasks; minimality of top-5 retrievers 21.3–41.5%.
* F3 (PaMCP vs per-subtask eligible): +0.043, p_Holm = 1.0.

## E11 Capability gap (review scenario)

On the review scenario of Fig. 1 the gap grows with input size: with tolerant aggregation the toolkit has 2
tools (60% of the goals native) at n = 30 and 300 and 6 tools at n = 3,000 (τ ≥ 0.75), and the engine abstains
at n = 30,000; exact aggregation adds two tools at n = 30 and 300. With τ = 0.6 the engine already abstains at
n = 3,000. The three measured profiles give the same
toolkits, because Sonnet and Opus answered all 64 calibration items correctly and the scenario's native classes
use the same declared priors beyond the measured sizes. Without gap analysis the engine abstains in every
setting (no registry tool serves the native goals). With the 569 public tools added to this scenario's registry,
the engine abstains with a χ1 counterexample because the K = 5 shortlist of the report goal fills with public
document tools.

## E12 Model profile calibration

Sonnet and Opus answered all 64 items correctly (including exact sums of 640 numbers); Haiku 51 of 64 (exact
sums 1/4 at n = 160 and 0/4 at n = 640, counts 0/4 at n = 640). All three models underestimated themselves when
asked beforehand: mean signed error −0.23 (Sonnet), −0.22 (Haiku), −0.30 (Opus); MAE 0.23, 0.24 and 0.30.
Self-assessment alone would therefore have sent work to tools that the model does correctly. The engine's
profile refuted 12 of the 128 native claims of the analyst (9.4%).

## E14 Prompt injection (offline reachability, labels B)

* Least privilege, 712 task × out-of-scope attack pairs: Full PaMCP, NoGap, Declared and all component variants
  0/712 (Wilson upper bound 0.5%); NoCert 1; no mechanism 8 (1.1%). Baselines as published: RAG-MCP 8.1%,
  ToolScope 7.6%, COLT 7.2%, per-subtask 2.7%, MCP-Zero 1.5%, CMTF 0.7%; restricted to eligible tools ≤ 1.4%;
  all tools eligible 36.1%. F5: −0.027, p_Holm < 0.001.
* Strict read-only, 775 pairs: Full PaMCP 0; baselines 8.4–14.7% (CMTF 2.2%).
* Poisoned descriptions (10% / 30% of tools): the sanitised manifest shows none; the raw definitions of PaMCP's
  toolkits contain one in 32.6% of the tasks at 30%; baselines 17.4% (CMTF) to 86.2% (ToolScope).
* Output-borne exposure: 55.5% of PaMCP toolkits contain a tool returning remote content, none also allows an
  out-of-scope action (baselines 3.2–22.6%).

## E18 Factorial ablation (2^3 over G, P, S; 155 tasks, least privilege)

| Cell | \|K\| | tokens | recall | joint | abstain |
|---|---|---|---|---|---|
| Full PaMCP (G P S) | 1.23 | 176 | 0.181 | 56.1% | 10.3% |
| NoCert (G P –) | 1.46 | 229 | 0.253 | 56.8% | 0 |
| Declared (G – S) | 1.25 | 189 | 0.230 | 54.8% | 6.5% |
| NoGap (– P S) | 1.50 | 193 | 0.183 | 55.5% | 20.0% |
| None (– – –) | 2.08 | 297 | 0.270 | 53.5% | 0 |

* Shapley (G / P / S): recall −0.017 / −0.013 / −0.060; tokens −55.3 / +0.8 / −66.3; joint +0.010 / +0.026 /
  −0.010; reachable attack (share of tasks) −0.012 / −0.018 / −0.022. G×S interaction on tokens 32.0
  (p < 0.001). Joint feasibility 52.9–58.1% in every cell.
* F6 (tokens Full vs NoGap): −16.7, p_Holm = 0.269.
* Components: no closure → abstain 12.3%; derivation-only flow → recall 0.236, abstain 5.8%; no relevance term →
  recall 0.167; utility floor identical; no refinement → recall 0.179.

## E15 Cost and scalability

30 LiveMCPBench tasks, least privilege, two vCPUs; registries of n cloned contracts (n > 569). Latency per
request, p50 / p95: 45 / 164 ms (569, real registry), 55 / 787 ms (1,000), 252 ms / 5.8 s (10,000), 2.6 / 13.5 s
(100,000). Separately timed stages, p50: eligibility 0.08, 0.16, 5.2 and 327 ms (listing the eligible tools);
per-goal retrieval 42, 50, 256 ms and 2.5 s; one dense ranking (RAG-MCP) 12, 12, 33 and 212 ms. Bitmap eligibility
test over 10^6 contracts: 0.025 ms (index built in 123 s). Engine build: 2.0, 2.9, 31.6 and 2,078 s, dominated by
the eager, quadratic materialisation of the pairwise risk relation; peak memory 3.1 GB at 100,000. Exact search in
26–28 of 30 tasks at every size; abstentions 2, 3, 9, 10 (χ1, one χ5 at 100,000); no failures.

Optimality gap (generated cover instances, 10 per size, node budget 20,000 = engine default): greedy / exact cost
1.008, 1.027, 1.157 on average (max 1.039, 1.219, 1.395) for 1, 3, 5 goals; exact search 3 ms, 21 ms, 1.06 s. With
8 and 12 goals the exact search exhausts the budget in 10/10 instances (11.6 s, 17.6 s) and falls back to greedy
(28 ms, 66 ms); the gap is not measurable there.

## E16 Evolution

152 events (remove and re-insert each server): incremental update p50 13.5 ms, p95 565 ms vs rebuild 4.22 s;
exact invalidation 1.09% of 35 cached toolkits per event vs 100% for a flush; 33 of 35 recomputed toolkits
identical; 20/20 rug pulls detected and restored; model change 0.012 ms; MCP-Zero index rebuild 0.060 s, COLT
graph 0.019 s.

## E17 Refinement (deterministic operators)

* K = 5: 138 of 155 certified at k = 0 (89.0%) → 89.7% at k ≥ 1; χ1 1 of 9 repaired, χ5 0 of 8.
* Induced χ1 (K = 1): 73.5% → 83.9% (k = 1) → 85.8% (k ≥ 3); repaired χ1 46.4%, χ5 30%, χ2 3 of 3; mean 1.3
  iterations.
* Revenue scenario: χ5 at k = 0, repaired by split at k = 3.

## E20 Sensitivity

β, η, ζ ∈ {0, 0.25, 1} and u_min ∈ {0.4, 0.6} change no toolkit; u_min = 0.8 changes 0.7%. γ changes 7.2–20.1%
of the toolkits (γ = 0: Jaccard 0.844), δ 2.9–7.2%; recall 0.197–0.215 (default 0.202). Only γ = 1 with
β ≤ 0.25 admits a tool forbidden under labels B (0.014 per toolkit). The registries publish no prices or
latencies, so η and ζ cannot act.

## E22 Statistics

| ID | Comparison | Δ | p | p_Holm |
|---|---|---|---|---|
| F1 | E9 recall, PaMCP vs per-subtask (non-inferiority, margin 0.05) | −0.080 | 0.763 | 1.0 |
| F2 | E9 recall at equal size, PaMCP vs RAG-MCP | +0.060 | 0.132 | 0.397 |
| F3 | E10 joint feasibility, PaMCP vs per-subtask (eligible) | +0.043 | 0.641 | 1.0 |
| F4 | E4 Exp@5, verified vs lexical | −0.099 | < 0.001 | < 0.001 |
| F5 | E14 reach, PaMCP vs per-subtask | −0.027 | < 0.001 | < 0.001 |
| F6 | E18 tokens, Full vs NoGap | −16.7 | 0.067 | 0.269 |
| F7 | E8 Hit@1, goal contract vs raw-text RRF | −0.157 | < 0.001 | < 0.001 |

Target-tool clustered intervals are 2.7–3.3 times wider than request-level ones (300 requests, 66 targets).
Method ranking: stratified half splits Kendall τ 0.68, same best method in 200/200; tool-disjoint τ 0.43, same
best 87.5%.
