# PaMCP final evaluation (protocol E1–E22) — results and manuscript section (Nov 2026)

Repository: https://github.com/msellamiTN/taas-provenance-discovery, branch `research/pamcp-final-evaluation`.
Section 8 (IEEEtran compsoc, ~5 pages): `paper/sections/evaluation_final.tex` (+ `evaluation_final_e15.tex`),
tables `paper/tables_final/`, figures `results/final/figures/paper_*.pdf`, bib `paper/evaluation_final.bib`,
preview `paper/evaluation_final_preview.pdf`, integration notes `paper/INTEGRATION_FINAL.md`.
Findings in full: `docs/FINAL_EVALUATION.md`; methods `docs/FINAL_EVALUATION_METHODS.md`; preregistered family
`docs/FINAL_EVALUATION_PLAN.md`. Every result file carries a manifest (run id, commit, code hash, input/label/LLM
record hashes, config); raw per-item records in `results/final/raw/`.

## Design
- Labels A (Claude Sonnet) for typing and simulated verifier; labels B (Claude Opus, blind) for scoring only.
  κ = 0.944 (state), 0.893 (private); B's 120 unsafe tools ⊂ A's 131 → error-free verified exposure is 0 by
  construction.
- Mechanisms G (gap), P (provenance-sound eligibility), S (set-level reasoning + certificate); 2^3 factorial with
  Shapley. Baselines: RAG-MCP, MCP-Zero (recorded requests), COLT (adapted), ToolScope (adapted), CMTF (adapted),
  per-subtask, all tools. LSA encoder for all. Confirmatory family F1–F7 fixed before E9/E10/E14/E18; Holm.

## Main results
- E1/E3: 44 of 569 tools annotated (1 wrong); 120 (21.1%) not read-only; lexical cues recall 0.825, precision 0.54.
- E4: no filter Exp@5 42.5%; closed-world annotations 31.5% (Util 0.4%); lexical 9.9% (21 unsafe admitted);
  verified 0% at Util 46.2% vs 49.8% unfiltered. F4 significant.
- E5–E7: forged hints push closed-world exposure to 57.1% (δ = 0.1); verified 5.4–5.6% at FAR 5% (0–14.7% per
  seed); break-even vs lexical φ = 10% random, 20% look-alike; stricter ℓmin is non-monotone (pool size).
- E8 (negative): goal-contract Hit@1 66.0% on B1 but 23.0% on the 569-tool registry, lowest of all; F7 against
  PaMCP; cause: structural score, only 50.3% of gold tools type-compatible with the analyst's goal type.
- E9/E10: PaMCP 1.47 tools, recall 0.169 (below retrievers exposing more tools); F1 non-inferiority not shown,
  F2 n.s.; joint feasibility 67.0% (ToolScope eligible 73.4%), F3 n.s.; certification adds C and M.
- E14: 0/712 reachable out-of-scope attacks for Full/NoGap/Declared vs 1.5–8.1% published baselines; ≤1.4% when
  baselines are restricted to eligible tools (eligibility does most of the work); F5 significant.
- E18: Shapley recall −0.017/−0.013/−0.060 (G/P/S), tokens −55.3/+0.8/−66.3, no mechanism moves joint feasibility;
  F6 n.s.
- E16: incremental update 13.5 ms p50 vs 4.22 s rebuild; invalidation 1.09%; 20/20 rug pulls detected.
- E17: deterministic repairs: 89.0 → 89.7% (natural), 73.5 → 85.8% (induced χ1).
- E15: see the section (latency per stage up to 10^5 cloned tools; greedy vs exact gap).
- Not run: E13, observed effects (E3), human E2, E19, E21.

## Issues for the manuscript (from the evaluation)
1. Structural retrieval score (Eq. 5) hurts on the merged registry; weight it down or apply after relevance.
2. Eq. 6 needs the relevance term used in all experiments (w_rel = 10).
3. Recall cost of set-level reasoning; certified toolkits do not raise joint feasibility over eligible baselines.
4. Five "evaluation plan" sentences and the Conclusion's last paragraph need replacing (texts in INTEGRATION_FINAL.md).
5. Model version strings were not recorded; AI-use disclosure needed.
