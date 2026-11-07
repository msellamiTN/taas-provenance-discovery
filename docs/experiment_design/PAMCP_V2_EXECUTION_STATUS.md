# PaMCP v2 — Execution status and evidence ledger

**Frozen protocol:** `docs/experiment_design/PAMCP_CORE_PROTOCOL_V2.md` at commit `6ec17405f24874d0f2931a3b8ff39e7ebe32ee18`.

**Frozen orchestrator reference:** `notebooks/PaMCP_Core_Protocol_v2.ipynb` at commit `bc961a77160250ab10f1777fd1197bbfdf2af502`.

**Current implementation branch:** `research/pamcp-multibenchmark-v1`.

**Governance:** This ledger records implementation and execution evidence only. It does not amend the protocol, experiment catalog, metrics, baseline definitions, or acceptance criteria. The catalog's `planned_not_run` values are immutable preregistration metadata; runtime status belongs in run manifests and this ledger.

## Evidence semantics

- **EXECUTED (descriptive):** the specified descriptive computation ran and its artifacts exist. It is not a claim of inferential validity or scientific completion outside that scope.
- **PARTIAL:** some registered components ran, but the full dataset/baseline matrix has not passed its completion gate.
- **BLOCKED_DATA / BLOCKED_ORACLE / BLOCKED_EXECUTION:** a required dataset, independent reference, or runtime/evaluator is absent. These are not zero scores and not implementation failures.
- **CI PASS:** software tests and static checks passed. CI does not imply an experiment was run.
- **FIXTURE SMOKE PASS:** the end-to-end software path was exercised with synthetic test fixtures. It is not benchmark evidence and must never be reported as a measured dataset result.

## E1–E22 status

| ID | Frozen experiment | Current status | Evidence / blocker |
|---|---|---|---|
| E1 | Registry characterization | **EXECUTED — descriptive metadata scope** | CI run `42301622172`, commit `0ae6429a3211b654e31f52107e0962822fa957ef`; 569 registry rows, 569 unique tool IDs, 2 sources, 0 published definition-hash mismatches. Inferential semantic/effect claims still require independent references. |
| E2 | Semantic typing quality | **BLOCKED_ORACLE** | Requires frozen human-annotated sample, two independent annotations and adjudication. E2 intake preparation is not an E2 result. |
| E3 | Declared versus observed effects | **BLOCKED_ORACLE / BLOCKED_EXECUTION** | Requires isolated runtime traces and adjudicated observed-effect references. Declarations and lexical inference are not observations. |
| E4 | Exposure under policy encodings | **BLOCKED_ORACLE** | Requires independent unsafe/effect references and frozen policy conditions. |
| E5 | Forged and laundered metadata | **BLOCKED_ORACLE** | Requires independently labelled attack/forgery cases and outcomes. |
| E6 | Imperfect verifier | **BLOCKED_ORACLE** | Requires independent verifier error/reference cases. |
| E7 | Trust policy and evidence strength | **BLOCKED_ORACLE** | Requires independently sourced trust/evidence references. |
| E8 | Single-tool retrieval quality | **PARTIAL — software pipeline fixture only; full campaign NOT RUN** | End-to-end artifact-pipeline fixture test is being validated in CI. Full ToolRet + MCPToolBench++ run requires the Colab campaign and pinned model/data artifacts. Registered MCP-Zero/COLT/ToolScope/CMTF adaptations remain blocked by their E8-specific inputs/oracles; B1/B1m are absent; MCP-Atlas remains diagnostic only. |
| E9 | Multi-tool set retrieval | **BLOCKED_DATA / BLOCKED_ORACLE** | Requires exhaustive acceptable multi-tool sets and source-specific candidate visibility; MCP-Atlas trajectories are not exhaustive gold. |
| E10 | Set validity and compatibility | **BLOCKED_ORACLE / BLOCKED_EXECUTION** | Requires independent composition/interface/effect/policy oracle and compatible runnable tasks. |
| E11 | Capability gap and bridge ratio | **BLOCKED_ORACLE** | Requires independent required-capability/GoalSpec reference. |
| E12 | Model profile calibration | **BLOCKED_DATA / BLOCKED_ORACLE** | Requires frozen calibration corpus and independent calibration outcomes. |
| E13 | End-to-end agent execution | **BLOCKED_EXECUTION** | Requires common sandbox, pinned tasks, and independent final-state evaluator. |
| E14 | Robustness under prompt injection | **PARTIAL_OFFLINE_ONLY** | Offline attack data can support only the permitted offline scope; executed-action claims require sandbox and evaluator. |
| E15 | Cost per request and scalability | **BLOCKED_DATA / IMPLEMENTATION GAP** | Frozen catalog requires ToolRet, MCPVerse registry/tool pool and controlled synthetic clones; metrics are per-stage p50/p95 latency, memory and exact/greedy gap. No E15-specific runner currently exists; `experiments/e7_scalability.py` is E7 and must not be relabelled as E15. Synthetic expansion parameters and exact/greedy comparison contract must be sourced/preregistered, not guessed. |
| E16 | Registry and model evolution | **BLOCKED_DATA** | Requires versioned snapshots and a controlled update/invalidation sequence. |
| E17 | Counterexample-guided refinement | **BLOCKED_ORACLE** | Requires independently verified valid/invalid compositions and counterexamples. |
| E18 | Component and primary mechanism ablation | **PREVIEW EXECUTED (software only); confirmatory BLOCKED_ORACLE** | New shared-input eight-cell runner executed in CI on a tiny fixture; confirmatory execution still requires the same frozen independent task/contract oracle and matched conditions for all eight. |
| E19 | LLM role configurations | **BLOCKED_DATA** | Requires fixed task set, role definitions and equal model/token/time budgets. |
| E20 | Sensitivity to cost and utility weights | **BLOCKED_DATA** | Requires frozen development set and preregistered weight grid. |
| E21 | Experience reuse | **BLOCKED_DATA** | Requires confirmed train-only trajectories and held-out test tasks; AutoTool applies here, not as an E8 retrieval baseline. |
| E22 | Statistical validity and reproducibility | **PENDING** | Must aggregate only after confirmatory experiments have valid matched observations, denominators, independent units, CIs, paired tests and multiplicity correction. |

## E1 execution evidence

- Workflow: [run #42301622172](https://github.com/msellamiTN/taas-provenance-discovery/actions/runs/42301622172).
- Run ID: `E1-0ae6429a3211b654e31f52107e0962822fa957ef-42301622172`.
- Registry SHA-256: `a24bb9c5c788f8856288993c8f3c21b7fcd84b6491cc1a2b778b3b5d5a787045`.
- Tool rows / unique IDs: 569 / 569.
- Source count: 2.
- Published definition-hash mismatches: 0.
- Guardrails: no silver labels, no task gold labels, no MCP server execution.
- Artifact name: `pamcp-e1-0ae6429a3211b654e31f52107e0962822fa957ef-42301622172`.
- CI on that commit: 105 PaMCP tests + 61 Studio API tests passed. This was before the E8 fixture test was added.

The v2 core protocol says E1 is runnable descriptively and independent references are required for inferential semantic/effect claims. The separate legacy `E1_PROTOCOL_RUNBOOK.md` specifies an additional independent non-read-only reference-share gate and uses `experiments/e1_protocol_runner.py`. Do not conflate that legacy/reference-label metric with the v2 catalog's E1 `metadata distribution` metric. The latter is what the v2 descriptive CI run executed. The independent-reference metric remains blocked; no effect labels were inferred.

## E8 software pipeline validation

The E8 runner deliberately writes a `partial` manifest for its selected retrieval controls and preserves the registered MCP-style baselines as blocked/not-comparable when their required GoalSpecs, training splits, equivalence oracle or independent typed contracts are absent. The end-to-end fixture test exercises both dataset-track loaders, ranking stages, metric/plot outputs, manifest generation, checksums, ZIP creation and immutable-run refusal. It uses tiny synthetic fixtures and monkeypatched model stages; it is strictly a software regression test, not a ToolRet or MCPToolBench++ measurement.

## E18 factorial preview orchestration

The new `run_pamcp_factorial_preview` executes the eight frozen G×P×S cells in catalog order with one shared model profile and shared registry, GoalSpec and policy fingerprints. It fingerprints the complete capability-contract contents, GoalSpec, effective policy and full model-profile contents; it checks the exact factor tuple per cell and asserts that evaluator labels and MCP tools are not accessed. The CI test executes all eight variants on a tiny synthetic contract fixture and verifies that every `S=0` cell remains uncertified and disables backward closure and joint checks. This is a software preview, not confirmatory E18 evidence or a PaMCP performance score. The Studio preview API now routes a request containing all eight variants through this shared-input runner and returns the `pamcp_factorial_preview` metadata; subset previews retain their existing single-variant path.

## Current CI evidence

- Latest E18 fingerprint-hardening test commit: `e370ae433b50921978794effdc5b7d27f298f65d`.
- Push run: [#42305707617](https://github.com/msellamiTN/taas-provenance-discovery/actions/runs/42305707617) — success.
- Pull-request run: [#42305714682](https://github.com/msellamiTN/taas-provenance-discovery/actions/runs/42305714682) — success.
- PaMCP tests: **107 passed, 6 warnings**.
- Studio API tests: **61 passed, 1 warning**.
- Four notebooks syntax-validated; 22 experiment IDs and 31 baseline IDs validated.
- E1 descriptive CI execution and artifact upload succeeded in both workflows.
- E8 end-to-end fixture pipeline and E18 all-eight-cell preview tests passed; neither is a real benchmark result.

## Next execution order

1. Close the E8 software regression gate after paired PR CI passes.
2. Execute the amended E8 Colab campaign on the pinned source revisions; preserve ToolRet and MCPToolBench++ as separate tracks. ToolRet uses BM25+TF-IDF RRF and skips Cross-Encoder inference; MCPToolBench++ retains Cross-Encoder. Use a new run ID after the runner amendment. Do not mark E8 complete while its registered baseline/data matrix remains partial.
3. Implement E15 only from the frozen E15 contract and explicit controlled expansion inputs; do not repurpose E7's scalability script.
4. Continue E14 offline-only where permitted, and E18 preview/test work; keep runtime/oracle claims blocked until prerequisites exist.
5. Obtain independent human annotation and isolated runtime references for E2/E3 and the downstream experiments that depend on them.

No protocol change, fabricated score, baseline substitution, or unsupported superiority claim is permitted.


## E8 ToolRet lightweight amendment

The implementation branch now contains amendment `E8-TOOLRET-LIGHTWEIGHT-RRF-v1` in `docs/experiment_design/E8_TOOLRET_LIGHTWEIGHT_AMENDMENT.md`. ToolRet's selected retrieval-control matrix replaces Cross-Encoder inference with BM25+TF-IDF reciprocal-rank fusion over top-100 lexical rankings (RRF k0=60). MCPToolBench++ retains its original Cross-Encoder baseline and all other original controls. E5 dense and BM25+E5 RRF remain enabled on both tracks. The amendment is explicitly lexical and is not claimed to be semantically equivalent to Cross-Encoder reranking.

The original partial run and its checkpoints must remain untouched. The notebook adds the amendment identifier to its run-configuration fingerprint so its active-run recovery logic creates a new run rather than selecting the previous Cross-Encoder ToolRet run. The amendment changes the selected retrieval controls only; it does not change dataset snapshots, task selection, qrels, metrics, statistical tests, seeds, or the frozen E8 completion gate. Passing software tests will not constitute a full benchmark result.
