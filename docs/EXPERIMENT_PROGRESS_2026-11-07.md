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

## E9 — LiveMCPBench dataset and retrieval pipeline

The pinned LiveMCPBench source is revision \`36a51a1065dda49c1e503b87edf33a1e0b331a74\`. E9 uses the LiveMCPTool-only candidate pool (525 tools / 69 servers), not the E1 union with MCPToolBench++.

The protocol-aligned audit of 95 public tasks produced:

| Resolution | Count |
|---|---:|
| Tasks with at least one resolvable gold tool | 94 |
| Tasks with no resolvable gold tool (excluded) | 1 |
| Unique-identity tool mentions | 222 |
| Ambiguous tool-name mentions (all candidate identities accepted) | 29 |
| Unresolved tool mentions retained in the audit | 5 |
| Tasks flagged for declared-tool-count mismatch | 4 |

The 94-task package separates discovery tools/tasks/visibility from evaluator acceptable-set alternatives and the 95-row resolution audit. Each reference is one benchmark-native proposer-completed, validator-scrutinized successful toolchain, not an exhaustive list of every valid solution. The package is explicitly \`prepared_not_run\`; it contains no PaMCP or comparator rankings/scores.

The latest CI package is preserved as artifact [PaMCP-E9-LiveMCPBench-Prepared, run 42451849668](https://github.com/msellamiTN/taas-provenance-discovery/actions/runs/42451849668/artifacts/13605144489). The artifact manifest's internal SHA-256 checks were verified after download.

## E9 retrieval runner and metrics

\`experiments/e9_retrieval_campaign.py\` now enforces the E1/E2/E3/E12 release gate, approved comparator map, 282 frozen GoalSpecs (94 × 3 decomposition conditions), 525 hash-bound contracts, accepted E12 model profile, policy, composer config, and local offline model encoder.

The confirmatory E9 comparison is aligned to the explicit protocol:
- Full PaMCP with backward closure is the separate primary configuration.
- Comparators are COLT, MCP-Zero, ToolScope, CMTF using common accepted contracts, and PaMCP without backward closure.
- NoBackwardClosure changes only closure depth to zero; \`per_subtask\` is not used as a proxy.
- Decomposition conditions are \`none\`, \`clause_splitter\`, \`llm_analyst\`.
- Candidate budgets are independent runs at \(k=\{1,3,5,10,20\}\).
- The exporter creates F1 group recall, F2 set-precision/recall, F3 complete-set share, F4 retrieved-set-size distribution, and matched-task paired tests with bootstrap intervals, sign-flip tests and Holm adjustment.

MCP-Zero remains blocked until its official iterative active-request loop exists. COLT requires the accepted MCPToolBench++ dev/server-membership scenes and frozen crosswalk. ToolScope requires an independent equivalence oracle. CMTF requires the accepted common contract bundle. Missing methods are recorded as blocked; the runner does not fabricate their scores.

No E9 method campaign has been run. The E9 runner is implemented and CI-tested, but cannot pass its execution gate until accepted E1/E2/E3/E12 artifacts and the frozen input bundles are supplied.\n\nA subsequent hardening pass now requires explicit non-empty acceptance IDs for every accepted release-gate prerequisite; the local encoder bundle must cover the exact complete file inventory and rejects symlinks, traversal paths and unlisted files; and the ToolScope oracle rejects duplicate/reversed/conflicting pairs and requires both positive and negative examples. Regression tests for these checks are committed. The prepared E9 package now receives exact-inventory and discovery-file SHA-256 verification, while evaluator-reference hashing/parsing is deferred until rankings are frozen. The last confirmed CI run above predates these additions; their CI result has not yet been verified, and they are not included in the 58-test count. The E9 exporter’s paired inference was also hardened to resample/sign-flip at `independent_unit_id` cluster level, with task-weighted paired mean differences and explicit independent-unit counts.

## E2 — proposed annotation sample (not frozen)

A 120-tool stratified sample from the 569-tool merged registry has been generated using seed \`20261107\` and 12 non-empty source × category strata. The sample expands to 481 semantic-type annotation units. It is explicitly \`proposed_not_frozen\`; the finite-population 95%/±8-point calculation is only a planning reference, not a power guarantee for rare classes or macro-F1.

The CI workflow now builds three separate artifacts: Annotator A (no restricted mapping), Annotator B (no restricted mapping), and an owner-only restricted mapping/control package. Do not distribute the annotator files until the study owner accepts the sample design and freezes the E2 scoring rules. Never send the owner-only mapping to annotators.

The latest workflow exposes three separate packages: [Annotator A (no restricted mapping)](https://github.com/msellamiTN/taas-provenance-discovery/actions/runs/42451849668/artifacts/13606051625), [Annotator B (no restricted mapping)](https://github.com/msellamiTN/taas-provenance-discovery/actions/runs/42451849668/artifacts/13605024802), and [owner-only restricted control](https://github.com/msellamiTN/taas-provenance-discovery/actions/runs/42451849668/artifacts/13605338589). Both annotator archives contain 481 rows and no mapping; the owner archive is restricted and must not be distributed.

## Software verification

Working branch: \`feature/pamcp-publication-visualization-v1\`.

GitHub Actions run [42451849668](https://github.com/msellamiTN/taas-provenance-discovery/actions/runs/42451849668) completed successfully. It validated the 81-figure E1–E22 registry, E8 launcher and notebook, regenerated the pinned 94-task E9 package, generated the proposed E2 sample, compiled the E9 runner, split E2 into annotator-only/owner-only archives and passed **58 regression tests**. The packaging step verified SHA-256 values and asserted that A/B archives do not contain the restricted mapping. This proves software and dataset-preparation behavior, not a PaMCP-versus-baselines experiment.

## Remaining protocol blockers

| Prerequisite | Remaining requirement |
|---|---|
| E1 | Two independent human effect-reference annotations covering all 569 unique definitions; reconciliation, raw agreement and adjudication where needed |
| E2 | Freeze sample size/design/seed and scoring rules; obtain two independent human semantic-type annotations; probe-output condition requires E3 traces |
| E3 | Identify credential-free runnable servers; collect isolated before/after and network/process traces; independently classify observed effects |
| E12 | Complete the registered calibration design: 10 task classes, log-spaced sizes 10–30,000, Latin/Arabic/CJK coverage and three pinned models |
| E8 | Prepare the full pinned benchmark sources and per-task outputs; E8 is downstream of the prerequisite gate |
| E9 | Obtain accepted E1/E2/E3/E12 release artifacts; freeze 282 GoalSpecs, 525 hash-bound contracts, E12 profile, policy/config/encoder and comparator input bundles; then run the 94-task five-budget campaign |

A Hugging Face compute submission was attempted for E8, but the job service returned **402 Payment Required**. No benchmark job started and no compute was billed. The E8 Colab route remains in the repository.

## Immediate human hand-off

1. Send the E1 Annotator A and Annotator B packages to two distinct annotators. Do not share the E1 restricted mapping before both sheets are frozen.
2. Retain the E1 owner-only mapping. Reconcile both sheets and adjudicate disagreements using the E1 runbook.
3. Review and either accept or amend the E2 120-tool sample proposal and scoring rules. Only then release the separate E2 Annotator A and B packages; keep its owner mapping private.
4. Build and accept the E3 observation traces and E12 calibration corpus before releasing downstream confirmatory experiments.

No synthetic test rows are presented as empirical observations, and no missing reference values are imputed as zero.
