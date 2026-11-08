# PaMCP final evaluation — plan, evidence classes and confirmatory family

Branch `research/pamcp-final-evaluation`. Protocol: `Experimental_Protocol_PaMCP.docx` (E1–E22) as revised by
the review of 2026-11-04 (factorial design, independent labels, non-inferiority margins, size-matched
comparisons). Code: `experiments/final/`; results: `results/final/`; recorded LLM outputs: `data/llm_records/`.

## Evidence classes

| Class | Meaning |
|---|---|
| MEASURED | deterministic computation on registry/benchmark data and their published gold labels |
| LABELLED | scored against reference labels B (blind second LLM labelling, Claude Opus); not human ground truth |
| SIMULATED | verifier evidence or attackers simulated from labels A (Claude Sonnet) and scored against labels B |
| SYNTHETIC | generated registries or tasks |
| BLOCKED | needs human annotators, executed MCP servers or an execution oracle |

Labels A drive the engine's typing and the simulated verifier; labels B are used only for scoring. Agreement
of A and B (Cohen's κ) is reported in E3. Human annotation sheets for E2 are prepared but not filled.

## Scope per series

| Series | Status | Notes |
|---|---|---|
| E1 | run | three views (LiveMCPTool 525, MCPToolBench++ original 87, merged 569); source-qualified categories |
| E2 | proxy | agreement of τ and of the structural typer with labels B; human study BLOCKED (sheet prepared) |
| E3 | partial | declared and lexical effects vs labels B; observed effects BLOCKED (no runnable servers) |
| E4–E5 | artifacts present | E4 exposure/admitted and E5 forgery outputs are committed; evidence is simulated/labelled as specified |
| E6–E7 | log-only in this snapshot | `results/run_all.log` reports figures, but separate versioned E6/E7 outputs are absent |
| E8 | run | B1 (87), B1m (569), distractor curve; raw text vs goal contract |
| E9–E10 | outputs missing from audited snapshot | runners exist, but versioned E9/E10 outputs were not found; do not use the “run” status as a committed-result claim |
| E11 | partial | toolkit size/native share vs model, τ, n, exactness; task success BLOCKED (E13) |
| E12 | partial | 3 models on the 64-item set, self-assessment, refutation; 10-class/30k/3-script corpus not built |
| E13 | BLOCKED | needs an execution environment and task oracles |
| E14 | output missing from audited snapshot | offline runner exists; worst-case reachable-attack output is not committed; executed actions remain BLOCKED |
| E15–E16 | outputs missing from audited snapshot | historical plan reports these runs; separate versioned outputs were not found |
| E17 | output missing from audited snapshot | LLM-free repair runner/result is not committed; assistant-role variants not run |
| E18 | output and raw rows missing from audited snapshot | factorial runner exists; result and raw rows required by E22 are not committed; task success remains BLOCKED |
| E19 | not run | needs role-configuration runs (assistant role) |
| E20 | output missing from audited snapshot | sensitivity runner exists; versioned output was not found |
| E21 | BLOCKED | needs confirmed execution trajectories (AutoTool comparison) |
| E22 | not reproducible from audited snapshot | E22 requires E9, E10, E18 and raw E18 outputs, which are absent; do not treat “run” as a committed result |


## Artifact completeness and reproducibility

The per-series status above is reconciled against the versioned files in the audited Git tree, not against narrative claims alone. The full path-by-path inventory and execution gates are recorded in `docs/ARTIFACT_COMPLETENESS_AUDIT.md`. In particular, E9/E10/E14/E15/E16/E17/E18/E20 outputs are absent from the audited snapshot, and E22 cannot be reproduced without E9/E10/E18 plus raw E18 rows. Historical logs and narrative result statements are not substitutes for missing versioned experiment outputs.

## Confirmatory family (fixed before E9, E10, E14 and E18 were run; E4 and E8 had started)

Holm correction over the seven tests; all other comparisons are exploratory and reported with CIs.

| ID | Test | Unit | Type |
|---|---|---|---|
| F1 | E9: PaMCP (K=5) group recall non-inferior to per-subtask retrieval with the analyst's subgoals | task | one-sided, margin 0.05 |
| F2 | E9: size-matched group recall, PaMCP vs RAG-MCP | task | two-sided |
| F3 | E10: joint feasibility, PaMCP (K=10) vs per-subtask retrieval restricted to eligible tools | task | two-sided |
| F4 | E4: Exp@5 (PaMCP retrieval stage), verified evidence vs positive lexical encoding, coverage 1 | request | two-sided |
| F5 | E14: reachable out-of-scope attacks, PaMCP vs per-subtask retrieval | task × attack | two-sided |
| F6 | E18: tokens, Full PaMCP vs NoGap | task | two-sided |
| F7 | E8: Hit@1, PaMCP goal-contract retrieval vs raw-text RRF (B1m, sample) | request | two-sided |

Tests: paired sign-flip permutation tests (exact up to 16 non-zero pairs, otherwise 20,000 random sign
vectors), percentile bootstrap CIs (4,000 resamples; clusters = target tools for E8 and E4), Wilson
intervals for proportions.
