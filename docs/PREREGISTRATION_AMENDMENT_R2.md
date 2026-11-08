# Preregistration amendment R2 (2026-11-08)

Amends `docs/FINAL_EVALUATION_PLAN.md` (confirmatory family F1–F7). Written and committed **before** any of the
test-split runs listed below; the commit containing this file precedes every result file it governs.

## What was known when this amendment was written
* All results of the original E1–E22 runs on the test tasks (Section 8 of the manuscript), including F1–F7.
* Revision 1 re-analyses (label overlap, scope-aware E14 for PaMCP-v1, sanitiser audit).
* Revision 2 analyses on existing records: label swap; evaluator audit, including E10 re-scored with the strict
  evaluator **for PaMCP-v1 and the baselines** (PaMCP-v1 27.7%, eligible baselines 5.3–11.7%).
* Development-split results only for every new configuration: X3 retrieval variants and baseline tuning
  (`results/revision_2/R2_X3_dev.json`), and the PaMCP-v2 composition choice (`R2_v2_selection.json`).
No test-split result of PaMCP-v2 or of the tuned baselines has been computed.

## Changes to the family
* **F4 is withdrawn**: its verified-evidence side is zero by construction ($U_B \subseteq U_A$), so it tests nothing.
* F1–F7 remain reported as the paper's original family (historical); the family below is the confirmatory one for
  the revision.

## Configurations fixed on the development split
* PaMCP-v2 single-tool ranking: variant A (lexical ranking of the goal contract text, reach from the prompt), the
  best non-oracle variant on dev (Hit@1 0.417 on 569 tools).
* PaMCP-v2 composition: `components=("lex",)`, `uncertain_ok=True`, other parameters as in the paper (`lex_unc`).
* Tuned baselines (dev): BM25 k1 = 1.5, b = 0.9; RRF k0 = 30; MCP-Zero servers_k = 2; COLT λ = μ = 0; ToolScope
  lexical representative retrieval; CMTF N = 20, depth 4. Dense retrieval has no parameter.

## Confirmatory family R2 (Holm correction over H1–H5, α = 0.05; H6 conditional)
| ID | Data (test) | Comparison | Unit, clusters | Test |
|---|---|---|---|---|
| H1 | E8 300-query sample, 569 tools | Hit@1, PaMCP-v2 ranking vs tuned BM25 on the raw request | request; target-tool clusters | two-sided paired sign-flip on cluster sums; cluster bootstrap CI |
| H2 | same | Hit@1, PaMCP-v2 ranking vs PaMCP-v1 ranking (variant E with prompt reach) | same | same |
| H3 | 94 LiveMCPBench tasks | group recall, PaMCP-v2 vs per-subtask retrieval (analyst subgoals) | task | one-sided non-inferiority, margin 0.05 |
| H4 | 94 LiveMCPBench tasks | joint feasibility under the strict evaluator, PaMCP-v2 vs per-subtask restricted to eligible tools | task | two-sided paired sign-flip |
| H5 | 95 LiveMCPBench tasks, least privilege | scope-aware definite out-of-scope reachability (Revision 1 estimand, attacks nested in tasks), PaMCP-v2 vs per-subtask unfiltered | task | two-sided paired sign-flip; task bootstrap CI |
| H6 | executed benchmark (X5) | task success, PaMCP-v2 vs eligible per-subtask, same agent and budget | task | enters the family only if at least 30 tasks per arm are executed; otherwise reported as exploratory |

Practical significance: differences smaller than 0.05 (proportions) are reported as negligible whatever their p.
Every other comparison of the revision is exploratory. Seeds, exclusions and missing data: tasks without a gold
tool are excluded from recall (n = 94); abstentions count as recall 0 and as infeasible.
