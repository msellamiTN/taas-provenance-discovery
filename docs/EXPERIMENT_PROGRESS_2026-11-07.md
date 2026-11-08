# PaMCP experimental progress — 8 November 2026

## Executive status

The dataset, figure and evaluation-export pipelines are materially advanced, but the confirmatory E1–E22 study is **not complete**. The frozen protocol requires accepted E1, E2, E3 and E12 prerequisite artifacts before downstream confirmatory experiments are released. Software tests and prepared dataset packages do not change that gate.

## E1 — Registry characterization

The pinned source snapshots were executed and preserved in the E1 GitHub Actions artifact. The three views contain:

- LiveMCPTool: 525 tools / 69 servers.
- MCPToolBench++: 87 tools / 10 servers.
- Merged source union: 569 unique tool definitions / 76 servers.

The descriptive census and registered E1-F1 category-composition and E1-F2 metadata-availability figures were generated from the actual snapshot. E1-F3 is withheld because independent effect-reference labels are absent. Human reference coverage is 0/569, so the non-read-only reference metric is **not estimable**; it is not zero. The E1 runner remains scientifically incomplete.

Two blinded 569-row annotation sheets are prepared. Annotator A and B packages are separate; the restricted join mapping is owner-only and must not be sent until both annotators freeze their sheets.

## E9 — LiveMCPBench data/reference preparation

The pinned LiveMCPBench source is revision \`36a51a1065dda49c1e503b87edf33a1e0b331a74\`. The strict E9 preparation uses the LiveMCPTool-only candidate pool (525 tools / 69 servers), not the E1 union with MCPToolBench++.

The pinned annotation set has 95 tasks. The protocol-aligned identity audit produced:

| Resolution | Count |
|---|---:|
| Tasks with at least one resolvable gold tool | 94 |
| Tasks with no resolvable gold tool (excluded) | 1 |
| Unique-identity tool mentions | 222 |
| Ambiguous tool-name mentions | 29 |
| Unresolved tool mentions | 5 |

For the 29 ambiguous mentions, every candidate server::tool identity is accepted as an alternative. The five unresolved mentions remain in the audit and are omitted from resolvable gold for those tasks; a task remains eligible when at least one gold tool resolves. Declared tool-count mismatches are audit flags and do not independently remove an otherwise resolvable task. Each reference represents one benchmark-native proposer-completed, validator-scrutinized successful toolchain; it is not an exhaustive list of all possible valid task solutions. MCP-Atlas trajectories remain diagnostic-only; MCPVerse v1.1's single-tool reference is not multi-tool acceptable-set gold.

The prepared package separates discovery tools/tasks/visibility from evaluator references and the 95-row resolution audit. It is marked prepared_not_run: it contains no PaMCP or baseline rankings or performance scores.

[Download protocol-aligned 94-task E9 dataset artifact](https://github.com/msellamiTN/taas-provenance-discovery/actions/runs/42422126446/artifacts/13593902899)

## E9 retrieval runner implementation

A protocol-gated runner now exists at experiments/e9_retrieval_campaign.py. It requires accepted E1/E2/E3/E12 proof artifacts and an approved comparator map; 282 frozen GoalSpecs; accepted hash-bound contracts for all 525 candidates; accepted E12 model profile, policy, composer configuration and local encoder snapshot. It freezes one top-20 ranking per task × method × decomposition before it opens evaluator references. It derives k=5/10/20 from that frozen ranking. Missing COLT training scenes or ToolScope equivalence oracle are explicitly reported as blocked, not replaced.

This is orchestration/software implementation only. No accepted release gate or E9 method result has been generated.

## Software verification

Working branch: \`feature/pamcp-publication-visualization-v1\`.

GitHub Actions run [42421468967](https://github.com/msellamiTN/taas-provenance-discovery/actions/runs/42421468967) completed successfully. It validated the E1–E22 figure registry, E8 launcher syntax, E8 Colab notebook JSON, the real pinned E9 LiveMCPBench preparation, and **44 regression tests**. This proves software/data-preparation behavior, not a PaMCP-versus-baselines experiment.

## Remaining protocol blockers

| Prerequisite | Remaining requirement |
|---|---|
| E1 | Two independent human effect-reference annotations covering all 569 unique definitions; reconciliation, raw agreement and adjudication where needed |
| E2 | Freeze sample size/design/seed and scoring rules; obtain two independent human semantic-type annotations; probe-output condition requires E3 traces |
| E3 | Identify credential-free runnable servers; collect isolated before/after and network/process traces; independently classify observed effects |
| E12 | Complete the registered calibration design: 10 task classes, log-spaced sizes 10–30,000, Latin/Arabic/CJK coverage and three pinned models |
| E8 | Prepare the full pinned benchmark sources and per-task outputs; E8 is downstream of the prerequisite gate |
| E9 | Freeze GoalSpecs and run Full PaMCP plus the feasible frozen baselines on the prepared 64-task subset |

A Hugging Face compute submission was attempted for E8, but the job service returned **402 Payment Required**. No benchmark job started and no compute was billed. The E8 Colab route remains in the repository.

## Immediate human hand-off

1. Send the E1 Annotator A and Annotator B packages to two distinct annotators. Do not share the restricted mapping before both sheets are frozen.
2. Retain the owner-only mapping. Reconcile the two sheets and adjudicate disagreements using the E1 runbook.
3. Confirm E2's preregistered sample size/design/seed before generating its annotation sheets.
4. Build and accept the E3 observation traces and E12 calibration corpus before releasing downstream confirmatory experiments.

No synthetic test rows are presented as empirical observations, and no missing reference values are imputed as zero.
