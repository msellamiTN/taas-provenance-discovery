# PaMCP final-evaluation artifact completeness audit

**Audited ref:** \`research/pamcp-final-evaluation\`  
**Audited commit:** \`0a9c5f2a17ae89c30a380410636a9249236bb296\`  
**Audit date:** 2026-11-08

This is a repository-artifact audit, not a rerun of the experiments. “Present” means a versioned output file exists in the audited Git tree; it does not independently validate the scientific design or the correctness of every reported number. “Missing” means the expected versioned output was not found anywhere in the audited repository tree under the expected result name.

## Versioned result artifacts

| Experiment | Expected versioned output | Audited status | Notes |
|---|---|---|---|
| E1 | \`results/final/E1_registry.json\` | Present | Three registry views recorded |
| E2 | \`results/final/E2_typing.json\` | Present | Proxy agreement only; human annotation remains blocked |
| E3 | \`results/final/E3_effects.json\` | Present, partial | Latest checked-in result applies unknown-aware confusion counts but has the older schema and a manifest with dirty code files; expanded hash-pinned tri-state output is pending |
| E4 | \`results/final/E4_admitted.json\`, \`E4_exposure.json\` | Present | Exposure results are explicitly simulated from labels A and scored against labels B |
| E5 | \`results/final/E5_forgery.json\` | Present | Synthetic forgery/metadata experiments |
| E6–E7 | Separate E6/E7 JSON outputs | Missing | Historical \`results/run_all.log\` reports E6/E7 figures, but no corresponding versioned final JSON outputs were found |
| E8 | \`results/final/E8_single_tool.json\`, \`E8_diagnostic.json\` | Present | E8 diagnostic raw records are also present |
| E9 | \`results/final/E9_sets.json\` | Missing | Runner exists; output not present |
| E10 | \`results/final/E10_validity.json\` | Missing | Runner exists; output not present |
| E11 | \`results/final/E11_gap.json\` | Present, partial | Checked-in runner and result use only the 11-tool review-scenario registry; E13 task success remains blocked |
| E12 | \`results/final/E12_profile.json\` | Present, partial | 64-item, four-class calibration only; the full 10-class/30k/three-script corpus is out of scope |
| E13 | Execution trajectories and task-oracle results | Blocked | Requires executable MCP environment and task oracles |
| E14 | \`results/final/E14_injection.json\` | Missing | Offline runner exists; output not present |
| E15–E16 | E15/E16 versioned outputs | Missing | Reported in plan but corresponding versioned output files were not found |
| E17 | \`results/final/E17_refinement.json\` | Missing | Output not present |
| E18 | \`results/final/E18_factorial.json\` | Missing | Factorial runner exists; output and its raw per-item records are not present |
| E19 | Role-configuration outputs | Not run | The plan already records this as not run |
| E20 | \`results/final/E20_sensitivity.json\` | Missing | Output not present |
| E21 | Confirmed execution trajectories | Blocked | Requires execution evidence |
| E22 | \`results/final/E22_statistics.json\` | Missing / not reproducible | The E22 script requires E8, E9, E10 and E18 outputs, plus E18 raw rows; E9/E10/E18 inputs are absent |

The audited \`results/final/\` directory contains E1, E2, E3, E4 admitted/exposure, E5, E8 diagnostic/single-tool, E11 and E12 result files. Its \`raw/\` subdirectory contains E2, E4, E5, E8 diagnostic and E12 records. This inventory is not equivalent to a complete E1–E22 result archive.

## E11 registry-scope correction

The checked-in \`experiments/final/e11_e12_profile.py\` constructs its E11 engine with \`list(reviews_registry())\`. It does not append the 569-tool public registry. The checked-in E11 result manifest is clean and identifies run \`E11_gap-2026-11-08T06:49:10Z-12b5336ee5\`, code commit \`afc62c905baaa841c35fa91530db0e9d71b78a47\`. The statement in the findings narrative that 569 public tools were added and caused a public-document-tool shortlist counterexample is not supported by this checked-in E11 implementation/result. That expanded-registry scenario must be a separately scoped and executed experiment before it can be reported.

## E22 dependency gate

The checked-in \`experiments/final/e22_statistics.py\` loads:
- \`E8_single_tool.json\`
- \`E9_sets.json\`
- \`E10_validity.json\`
- \`E18_factorial.json\`
- raw E18 rows via \`fe.load_raw("E18_factorial")\`

Because E9, E10, E18 and E18 raw records are absent, E22 cannot be reproduced from the audited repository snapshot. The “E22 run” label in the plan and findings should be read as an earlier reported status, not as evidence that its required inputs are committed here.

## Next execution order

1. Run the standalone E3 tri-state runner and verify its manifest and consistency counts.
2. Execute E9 and E10, saving both aggregate JSON and raw per-item rows.
3. Execute E14 and E18, saving raw E18 rows as required by E22.
4. Run E22 only after E8/E9/E10/E18 inputs have been hash-verified; preserve the preregistered F1–F7 family.
5. Reconcile the plan, findings and generated tables against the resulting committed output inventory.

No missing experiment result has been synthesized or inferred in this audit.
