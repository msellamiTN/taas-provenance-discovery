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
