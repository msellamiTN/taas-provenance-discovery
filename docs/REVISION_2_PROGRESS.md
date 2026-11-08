# Revision 2 — progress log

Plan: `docs/REVISION_PLAN_TSC.md`. Outputs of new analyses: `results/revision_2/`. Reference results regenerated in
`results/final/` keep their file names (manifests record commit and run id).

## Step 1 — validity repairs
* Alias manifest integrated in `src/taas/manifest.py` (tool and argument aliases, server-side bindings, type strings
  restricted to a safe alphabet); test `test_alias_manifest_hides_provider_identifiers`. 116 tests pass.
* E14 poisoning exposure is now measured by a canary scan of what each method shows the model (description, name,
  argument keys); the legacy sanitiser is scanned on the same toolkits for comparison.
* E14/E18 report `by_split` (test = 95 LiveMCPBench tasks, dev = the 60 tuning prompts); E17/E20 `--split test`.
* E5 runs five seeds at every delta, including 0.
* Label swap (`results/revision_2/R2_label_swap.json`): verifier from J_B scored on J_A admits the 11 A-only-unsafe
  tools; verified Exp@5 2.3–3.9% (paper direction 0%); lexical 9.9% under the paper's scoring.
* Evaluator audit (`R2_evaluator_audit.json`): ten hand-built cases with ground truth fixed beforehand; paper evaluator
  2/10 correct, strict variant 7/10 (the three misses need scope, credential or declassification information the
  labels lack). E10 re-scored strictly (exploratory): PaMCP joint 27.7%, eligible baselines 5.3–11.7%, NoCert 13.8%.
* Reruns in progress: E14/E18, E4–E7, E17/E20 test.

## Step 1 (continued) — committed reruns
* Reference E4, E6, E7 identical after rerun; E5 at δ = 0 now five seeds (verified Exp@5 5.4%, flat over δ);
  E14/E18 identical except the alias manifest's shorter `manifest_tokens` and the new canary and split fields.
  Canary scan: alias manifest shows no canary; the legacy sanitiser would show one in as many tasks as raw
  definitions (tool name channel).
* Revision 1 scope-aware E14: regex bug fixed (`r"^\\s*"` never matched, so a bare class became a blanket
  permission; no number changed because analyst requirements are scoped); test split added (`PAMCP_SPLIT=test`).
  Test split, PaMCP-v1: definite 0%, indeterminate 32.6%; per-subtask unfiltered definite 20.0%.

## Step 2 — dev selection (60 development prompts only)
* X3 (`R2_X3_dev.json`): PaMCP variants on 569 tools: A lexical 0.417, C lex+den 0.383, E Eq. (5) 0.283, oracle goal
  and tool types together (IJ) 0.450; either oracle alone does not help. Tuned baselines: BM25 0.450, MCP-Zero 0.683,
  RRF 0.400, ToolScope 0.400, COLT 0.367 (λ = μ = 0, i.e. dense), CMTF 0.300. The first selection rule did not
  exclude oracle variants; corrected (oracles are diagnostic only), PaMCP-v2 ranking = A.
* Composition (`R2_v2_selection.json`): `lex_unc` (lexical candidates, kind-level matching recorded as uncertain).
* E8 bug found: the paper's E8 computed the structural score with an empty reach set; the engine uses the
  prompt's types. Dev effect small (0.267 → 0.283).

## Step 3 — amendment committed before test runs (`docs/PREREGISTRATION_AMENDMENT_R2.md`, eb4e111)

## Step 4 — test results
* X3 test (300 queries, 569 tools; `R2_X3_test.json`): PaMCP-v2 ranking 0.413, tuned BM25 0.410, PaMCP-v1 with prompt
  reach 0.297, MCP-Zero 0.667, oracle IJ 0.583, oracle I 0.437.
* PaMCP-v2 composition on the test tasks (`R2_v2_eval.json`): recall 0.161 (v1 0.169), |K| 1.22, 146 tokens; joint
  feasibility 54.7% paper evaluator (v1 67.0%), 15.8% strict (v1 27.7%); definite out-of-scope 0%. v2 does not
  improve on v1 (negative result of the dev selection).
* Family R2 (`R2_family.json`, Holm): H1 +0.003 (p_H 1.0); H2 +0.117 [0.03, 0.226] (p_H 0.070); H3 non-inferiority
  not shown (−0.088); H4 +0.074 [0.0, 0.149] (p_H 0.277); H5 −0.200 [−0.284, −0.126] (p_H 0.0005).
