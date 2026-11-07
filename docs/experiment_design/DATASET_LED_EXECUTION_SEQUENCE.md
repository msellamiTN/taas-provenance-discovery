# PaMCP E1-E22 — dataset-led execution sequence

**Purpose:** run the registered PaMCP evaluations on their declared datasets and independent evaluation references. This is the execution map for the frozen protocol, not a protocol amendment.

## Non-negotiable execution rules

1. Use the dataset(s) named by each experiment entry in \`pamcp_experiments_v1.json\`. Preserve each dataset as a separate evaluation track.
2. Pin the exact source revision, split, license, adapter version, and source-file hashes before execution.
3. Generate discovery predictions without evaluator access. Open evaluator labels only after rankings and run manifests have been frozen.
4. Use only registered baselines for each experiment. Report native reproductions, adaptations, surrogates and partial adapters with their registered fidelity labels.
5. Use the metric numerator, denominator, evaluation unit and statistical procedure specified in the protocol. Missing labels are \`null/blocked\`, never zero.
6. Keep synthetic fixtures out of empirical result directories. Unit-test fixtures validate software only.
7. Do not advance past the prerequisite gate below simply because a later experiment's code or adapter exists.

## Prerequisite gate and order

The protocol execution gate explicitly requires E1, E2, E3 and E12 prerequisites to be accepted before the downstream experiment series is released.

| Gate | Dataset / input | Required execution and acceptance evidence | Current state |
|---|---|---|---|
| E1 | LiveMCPTool + MCPToolBench++ pinned snapshots | Three registry views; definition-hash reconciliation; independent human reference non-read-only labels covering all 569 unique definitions; raw agreement and adjudication records; accepted manifest | Descriptive census executed; reference-label coverage 0/569, therefore E1 not complete |
| E2 | Frozen human-annotated subset of the merged registry | Preregister sample size/design/seed and registry hash; two blinded annotators; raw Cohen's kappa; frozen type-match/scoring rules; probe-output condition only after E3 traces exist | Annotation preparation exists; no completed human labels |
| E3 | Credential-free runnable servers from the pinned tool sources | Isolated least-privilege sandbox; synthetic non-sensitive data; before/after state, network and process traces; independent effect annotations/adjudication; trace and probe-coverage manifest | Blocked: no confirmed runnable server inventory or accepted observed traces |
| E12 | Purpose-built calibration corpus | 10 task classes; log-spaced sizes 10–30,000; Latin/Arabic/CJK script coverage; three pinned models; gold answers; measured accuracy/reliability and confidence intervals | Existing checked-in corpus is incomplete against the registered design |

### E1 annotation hand-off

The E1 workflow artifact contains two blank, independently shuffled 569-row annotation sheets and the owner-restricted mapping. Separate packages have been prepared:

- Annotator A receives only the A sheet and instructions.
- Annotator B receives only the B sheet and instructions.
- The restricted mapping stays with the study owner until both sheets are frozen.

The E1 binary reference judgment is a human classification of the documented intended capability, not a runtime observation. E3 is the experiment that measures observed behavior. Neither annotator may use LLM silver labels, PaMCP predictions or the other annotator's sheet. The reconciliation utility reports raw Cohen's kappa and never auto-resolves disagreements.

## Dataset-to-experiment map

| Experiment | Registered datasets | Primary evaluation use | Separation / restriction |
|---|---|---|---|
| E1 | LiveMCPTool; MCPToolBench++; merged registry | Registry census and independent non-read-only reference share | Three views reported separately; reference labels keyed by tool ID + full definition hash |
| E2 | Human-annotated subset of merged registry | Semantic input/output typing quality | Two independent human annotators; no LLM silver labels as gold |
| E3 | Credential-free runnable servers | Declared vs observed operational effects | Observed sandbox traces only; MCP hints and lexical labels are not observations |
| E4-E7 | Merged registry + MCPToolBench++ | Policy exposure/utility, forged metadata, verifier error, trust thresholds | Require accepted E1 reference labels; preserve each policy and threat condition |
| E8 | MCPToolBench++; B1/B1m; ToolRet; MCP-Atlas public | Single-tool retrieval: Hit@1, Hit@5, MRR@10, macro Hit@1 | MCPToolBench++, ToolRet, and MCP-Atlas remain separate tracks; ToolRet is not MCP execution or safety ground truth |
| E9 | LiveMCPBench strict 64-task subset; MCP-Atlas public; MCPVerse v1.1 | Multi-tool group recall, set precision, documented-reference complete-set share | Validator-scrutinized LiveMCPBench chains are one benchmark-native successful reference set when IDs/counts reconcile; not exhaustive alternatives. MCP-Atlas trajectories remain diagnostics; MCPVerse labels are single-target, not multi-tool gold |
| E10 | LiveMCPBench; Toolathlon-Verified; τ³-bench | Joint set feasibility, interface/effect/policy/flow violations | Use each benchmark's native/independent oracle; do not infer execution validity from a retrieved set |
| E11 | Review-type tasks | Goal gaps, bridge ratio, toolkit size and task outcome | GoalSpecs and required-capability references frozen independently |
| E12 | Purpose-built calibration sets | Model reliability and confidence calibration | Three pinned models; class/size/script coverage required by preregistration |
| E13 | MCP-Atlas; Toolathlon-Verified; MCP-Universe; MCPVerse v1.1; MCP-Bench subset | End-to-end task success, wrong-tool calls, steps, tokens | Native evaluators and executable environments only; report unavailable runtimes separately |
| E14 | MCPTox; InjecAgent; R-Judge secondary; controlled injection sandbox | Prompt-injection robustness and out-of-policy action outcomes | Offline labels are not executed-action evidence; live claims require a sandbox |
| E15 | ToolRet corpus; MCPVerse registry/tool pool; synthetic registry clones | Per-stage latency, memory and optimality gap | Synthetic clones are a separately labelled scalability stress test, not a public-benchmark result |
| E16 | MCPVerse v1.1; pinned live registry snapshots; controlled mutation traces | Update, invalidation, recomputation and stale-evidence correctness | Versioned snapshots and controlled event traces required |
| E17 | LiveMCPBench | Counterexample-guided refinement | Independently validated valid/invalid composition pairs; trace semantics preserved |
| E18 | LiveMCPBench common task set; MCP-Atlas common subset | G×P×S factorial and component ablations | All eight factorial cells; same task, visibility, budget and independent oracle |
| E19 | LiveMCPBench | GoalSpec validity, repair, task outcome, tokens and latency | Same task/model budget across role configurations |
| E20 | LiveMCPBench + MCPToolBench++ | Sensitivity to cost/utility weights | Dataset-specific result panels; no cross-dataset pooled leaderboard |
| E21 | Toolathlon-Verified training trajectories; confirmed PaMCP execution traces | Experience reuse and stale-error detection | Training-only trajectories; held-out test tasks; exact registry/policy/tool-hash revalidation |
| E22 | MCPToolBench++ tool-disjoint sample + E8-E10 result sets | CI width, adjusted significance and rank stability | Only valid, paired, protocol-conformant runs enter confirmatory inference |

## Dataset-specific source handling

### ToolRet (E8/E15/E22)
Use the complete candidate corpus and query configurations with graded relevance judgments. Pin independent immutable revisions for \`mangopy/ToolRet-Queries\` and \`mangopy/ToolRet-Tools\`. Do not build a candidate corpus from positive qrels. Preserve relevance grades; do not silently binarize them. ToolRet is a heterogeneous retrieval track and must not be merged into MCP execution or safety claims.

### MCP-Atlas public (E8/E9/E10/E13/E18)
The public Hugging Face release contains 500 tasks. \`ENABLED_TOOLS\` defines per-task visibility; \`GTFA_CLAIMS\` supports claims-based answer analysis; \`TRAJECTORY\` is a positive reference trace, not exhaustive acceptable-tool-set gold. The full benchmark includes private tasks unavailable in the public release. Keep the public subset and its limitations explicit.

### LiveMCPBench (E1/E9/E10/E17/E18/E19/E20)
Use the pinned tool catalogue and task annotations. The source paper describes proposer-completed tasks whose toolchains are scrutinized by validators. The strict E9 preprocessor accepts only unique tool identities with declared tool count matching the parsed sequence: 64/95 tasks on the pinned snapshot; 3 count mismatches and 28 ambiguous/unresolved tasks are excluded with an audit. Each accepted chain is one benchmark-native successful reference, not an exhaustive collection of all acceptable alternatives. Native execution claims still require the benchmark runtime and LiveMCPEval.

### MCPVerse v1.1 (E1/E9/E13/E15/E16)
Pin the exact time-invariant CSV revision. The CSV provides question and annotated MCP/tool references, not complete executable schemas. Use it for its declared retrieval/registry/evolution roles; do not turn a single annotated tool into multi-tool complete-set gold.

### MCPToolBench++ (E1/E4-E8/E9/E20/E22)
The current E1 source snapshot is an 87-tool/10-server subset across six categories. Report that scope exactly; do not equate it with the dataset-card claim of a larger server population. Preserve its six raw category files and source commit.

## Statistical and reporting contract

For every experiment and dataset track, retain:
- exact source revisions, split, license and file SHA-256;
- task/tool/server IDs and the evaluation unit;
- registered method ID, implementation-fidelity label, parameters and seed;
- raw per-task predictions and evaluator-only references in separate paths;
- metric numerator/denominator, exclusions, abstentions and coverage;
- point estimates, 95% confidence intervals, paired effects and corrected p-values where preregistered;
- run manifest, environment, code commit and artifact checksums.

Use paired task-level comparisons on the common task intersection. Cluster-bootstrap only when the protocol's sampling unit and actual cluster IDs justify it. Preserve Holm correction for the confirmatory family and BH only for the declared exploratory family. Do not treat seeds as independent observations.

## Release decision

Until E1, E2, E3 and E12 are accepted, downstream E4-E22 remain blocked from confirmatory execution under the current protocol gate. Code, adapters, plotting, test fixtures, downloaded data previews and historical aggregate results are not substitutes for accepted experiment runs.

The next scientific action is to complete the two independent E1 annotation sheets and adjudicate them. Then execute E2/E3/E12 according to their frozen requirements; only after those manifests are accepted should the downstream dataset campaigns be released.
