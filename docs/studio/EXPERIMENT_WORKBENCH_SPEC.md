# TaaS Studio — Experimental Workbench Specification (PaMCP v1)

**Status:** implementation plan / capability contract. This document does not claim that the planned endpoints or experiment execution are implemented.

## 1. Product responsibility

TaaS Studio will orchestrate the new PaMCP experimental programme E1–E22. It must provide experiment definitions, immutable run manifests, sequential orchestration, evaluator isolation, result provenance, and publication artifacts.

Studio must preserve four distinct stages:

1. **Intent and experiment configuration** — the selected E-series definition, system variant, dataset/split, parameters, seeds, baseline adapters and resource limits.
2. **Discovery and pre-execution assurance** — GoalSpec interpretation, capability-gap analysis, eligibility, composition and certificate.
3. **Controlled evaluation / execution** — an evaluator with access to reference labels and, separately, an isolated MCP execution sandbox.
4. **Analysis and publication** — task-level metrics, statistical tests, figures and immutable report artifacts.

A selected toolkit is not task success. A valid certificate is not evidence of runtime behavior. Exposure, attempted actions and executed out-of-policy actions must remain separate.

## 2. Current capability boundary

The existing Studio API supports GoalSpec authoring/structural validation, retained benchmark/task/tool browsing, discovery, certificate inspection, model metadata lookup and host hardware diagnostics.

The present `POST /api/v1/discover` endpoint does not execute MCP tools. The Studio does not yet have a durable experiment store, E1–E22 orchestration, evaluator service, isolated MCP execution runtime, or live experiment trace streaming. These must be implemented explicitly; do not expose nonfunctional UI controls.

## 3. Experiment lifecycle

Each run follows a state machine:

`DRAFT → VALIDATED → QUEUED → RUNNING → EVALUATING → ANALYZING → COMPLETED`

Terminal alternatives: `FAILED`, `CANCELLED`, `INVALIDATED`.

Every transition is timestamped and audited. Runs are sequential by default (one active experiment worker) to preserve resource isolation and deterministic ordering. Parallelism may be enabled only for independent repetitions after resource and dataset isolation have been demonstrated.

A run is immutable after it enters RUNNING. Configuration changes create a new run. Resume is allowed only from a recorded checkpoint and must preserve the original seed and input hashes.

## 4. Required services / modules

- `ExperimentCatalog`: load and validate E1–E22 definitions from versioned JSON.
- `VariantFactory`: create Full PaMCP, NoGap, Declared and NoCert; validate factor configuration and diff.
- `DatasetRegistry`: dataset snapshots, upstream/source license, content hashes, split manifests and sample counts.
- `EvidencePipeline`: declared metadata, independently produced probe observations, attestations, signer trust and evidence freshness.
- `ContractPipeline`: infer/extract typed contracts without reading evaluator-only labels.
- `BaselineAdapters`: MCP-Zero, COLT, ToolScope, CMTF and AutoTool (E21 only); each records adaptation fidelity and parameters.
- `RunOrchestrator`: sequential execution, resource limits, cancellation and deterministic seeds.
- `EvaluatorBoundary`: reads reference labels only after discovery output is sealed; not importable by discovery or analyst modules.
- `MCPExecutionSandbox`: separately isolated server process/container, explicit network allowlist, credentials isolation, tool/time/budget quotas, redacted arguments/results, kill switch.
- `StatisticsEngine`: paired task comparisons, bootstrap, sign-flip tests, Holm and secondary BH correction.
- `ArtifactStore`: immutable manifests, raw task-level outputs, logs, figures, checksums and reports.
- `StudioWorkbenchAPI`: authenticated endpoints used by the browser UI.

## 5. Definitive PaMCP configurations

Factors: G = model-conditioned capability gap; P = provenance-sound eligibility; S = set-level reasoning/certification.

- Full PaMCP: G=1, P=1, S=1.
- PaMCP–NoGap: G=0, P=1, S=1. Delete model capability hyperedges and set `Γ(q)=G(q)`; all other mechanisms unchanged.
- PaMCP–Declared: G=1, P=0, S=1. Use published annotations and lexical cues only, with no observed/attested evidence and no trust policy; retain closure, cover, checks and certificate. This is a deliberate trust-disabled ablation; MCP-defaults remains a separate standards-oriented control.
- PaMCP–NoCert: G=1, P=1, S=0. Retrieve independently per subgoal and union. Disable backward closure, global set optimization, compatibility/effect/flow checks and certificate generation. The independent evaluator still measures counterfactual joint feasibility; a missing emitted certificate is not a certificate failure.

The three leave-one-out comparisons are conditional marginal effects and are not assumed additive. E18 includes all eight cells of the complete 2^3 factorial and estimates interactions. Shapley allocation may be reported over all six factor orderings.

## 6. Gold-label and trust boundary

- Discovery, GoalSpec analysis, retrieval and baseline adapters receive no gold task labels.
- Evaluator-only reference labels are stored in a separate module/process or access-controlled store.
- Contract-generation evidence and evaluation labels must be independent. Contract builders must not import silver/human evaluator labels.
- Probe evidence is generated by actual controlled executions for E3, not by a simulator that reads evaluation labels.
- Every tool definition and evidence record is bound to a snapshot/hash. Stale or changed definitions invalidate evidence according to the evidence policy.
- Report human, probe, declaration and attestation sources separately.

## 7. E1–E22 catalogue

The authoritative definitions, variables, metrics, comparators and chart types are stored in `docs/experiment_design/pamcp_experiments_v1.json`. All begin as `planned_not_run`. The catalog includes:
E1 registry characterization; E2 semantic typing; E3 declared-vs-observed effects; E4 policy exposure; E5 forged/laundered metadata; E6 imperfect verifier; E7 evidence strength and trust policy; E8 single-tool retrieval; E9 multi-tool set retrieval; E10 joint feasibility; E11 capability gap/bridge ratio; E12 model-profile calibration; E13 end-to-end execution; E14 prompt injection; E15 cost/scalability; E16 evolution; E17 counterexample-guided refinement; E18 primary factorial and component ablations; E19 LLM role configurations; E20 cost/utility sensitivity; E21 experience reuse; E22 statistical validity.

## 8. API contract (planned)

All routes require bearer authentication except health/readiness. Planned endpoints:

- `GET /api/v1/experiments/catalog` — list definitions, status and dependencies.
- `GET /api/v1/experiments/catalog/{experiment_id}` — full definition.
- `POST /api/v1/experiments/validate` — validate configuration without execution.
- `POST /api/v1/experiments/runs` — create immutable run in DRAFT/VALIDATED.
- `GET /api/v1/experiments/runs` — list runs with filters.
- `GET /api/v1/experiments/runs/{run_id}` — status, configuration and summary.
- `POST /api/v1/experiments/runs/{run_id}/execute` — start one run; reject if another is running unless explicitly isolated.
- `POST /api/v1/experiments/runs/{run_id}/cancel` — request cooperative cancellation.
- `GET /api/v1/experiments/runs/{run_id}/events` — event stream when SSE is implemented.
- `GET /api/v1/experiments/runs/{run_id}/artifacts` — immutable artifact references.
- `GET /api/v1/experiments/compare` — matched run comparisons and statistical analysis.

Do not implement an endpoint that claims runtime execution until the sandbox exists and records actual tool calls.

## 9. Run-manifest requirements

A run manifest must record: spec version; experiment and run IDs; configuration; dataset snapshot/hash and split; evaluator-label snapshot hash (kept evaluator-side); source repository and commit; worktree status; environment/container digest; model/provider/version/quantization; prompt and profile hashes; policy and engine parameters; candidate budget; random seeds; tokenization version; baseline adapter version; resource limits; exact metric denominators; statistical plan; artifact paths and SHA-256 hashes.

A completed result is not paper-eligible unless the manifest validates, dataset/label hashes are frozen, the evaluator boundary is tested, and raw task-level outputs are archived.

## 10. Studio UX

Add an Experiments workspace with:
- Overview and pipeline dependency map.
- E1–E22 catalog with objective, inputs, factors, metrics, baselines, status and prerequisites.
- Run configuration wizard: dataset snapshot, split, PaMCP variant, baseline, parameters, seed, compute budget and validation.
- Explicit review screen before execution.
- Sequential queue with state, progress, cancellation and logs.
- Run detail: configuration digest, model/dataset metadata, per-stage timings, task-level output and failures.
- Comparison view: Full vs NoGap / Declared / NoCert, factorial interaction view, baseline ranking and confidence intervals.
- Artifact browser for manifests, raw JSONL/Parquet, plots and manuscript tables.
- Evidence/source provenance badges (declared, human-reviewed, probed, attested), never presenting metadata declarations as verified evidence.
- Separate discovery/certificate and runtime execution outcomes.

Unavailable capabilities must be visibly marked as planned. No fake progress, fabricated values or static demo results.

## 11. Safety and reproducibility

- Run only credential-free servers in E3 unless an explicit per-tool sandbox credential profile exists.
- Use network-deny-by-default with destination allowlists.
- Redact secrets and sensitive arguments/results.
- Never execute arbitrary MCP server code in the Studio API process.
- Use isolated workers/containers and resource quotas.
- Do not log bearer tokens or provider secrets.
- Preserve request, registry, model profile, policy, adapter and evaluator snapshot hashes.
- Use deterministic seeds; avoid Python process-randomized `hash()`.
- Distinguish simulated, synthetic, replayed, probed and real runtime evidence in every record.
- No result value may be imported from the superseded experiment outputs.

## 12. Acceptance criteria

1. Catalog API returns exactly E1–E22 from the versioned JSON.
2. Four primary configurations pass variant-factory tests; all eight factorial cells are representable.
3. NoGap changes only G; Declared changes only P; NoCert changes only S.
4. Discovery has no import path or API access to evaluator labels.
5. A completed run has a valid immutable manifest and checksummed artifacts.
6. Runs execute sequentially and have reproducible seeds.
7. Evaluator scores only sealed discovery outputs.
8. Actual execution claims are possible only for sandbox-backed runs with invocation traces.
9. UI clearly separates selected toolkit, certificate, task success and runtime policy outcomes.
10. Unit/integration/security tests and a local dry-run pass before any E1 execution.


## 13. Baseline architecture and per-experiment assignment

Baselines are first-class experiment inputs, not hard-coded labels in a plotting script. Their authoritative registry is `docs/experiment_design/pamcp_baselines_v1.json`; each E1–E22 experiment has an explicit `baseline_ids` allowlist in the experiment catalogue. The API rejects a selected baseline that is not assigned to the experiment.

Baseline families are separated to avoid invalid comparisons:

- **Retrieval controls:** BM25, Dense-LSA, RAG-MCP-style multi-query dense RRF, and per-subtask retrieval.
- **External retrieval/planning adaptations:** MCP-Zero, COLT-style scene completeness, ToolScope-style merger/context ranking, CMTF-style typed state-frontier planning.
- **Trajectory baseline:** AutoTool (AAAI 2026), E21 only.
- **Eligibility/effect controls:** MCP annotation semantics, closed-world annotation reading, positive/closed-world lexical filters, observed/attested evidence, schema/lexical typing, and declared/lexical effect inference.
- **Runtime security comparators:** Progent-style call policy, Fides-style IFC and CaMeL-style taint tracking. These are not retrieval baselines.
- **Systems controls:** linear eligibility scan and full registry rebuild.
- **Internal controls:** no-refinement, uncalibrated profile, self-assessment and no-experience reuse.

The common adapter output records selected tool IDs, rankings, stepwise frontiers, merge clusters, diagnostics and adapter status. The current runner executes retrieval/planning adapters, and the E2/E3 registry-side rules. A baseline requiring actual probe traces, security runtime hooks, learned COLT training or trajectory data is not silently substituted: it returns an explicit blocked/not-implemented status or requires the corresponding training/runtime input.

### Baseline fidelity policy

- **Ready component/control:** implemented in this repository and reproducible from its recorded parameters.
- **Surrogate:** substitutes a different encoder or component and must be identified as such.
- **Partial adapter:** reproduces one algorithmic stage, not the complete original method.
- **Clean-room adaptation:** implements a method-inspired mechanism, but is not the original model/prompt/training pipeline.
- **Pipeline to build / planned:** not executable yet.

BM25 is the lexical control. Dense-LSA is explicitly a surrogate for a downloaded dense embedding model. MCP-Zero currently performs single-pass hierarchical routing, not its full active LLM request loop. COLT uses a scene co-use graph built from training-only query/tool bundles, not the paper's full learned graph architecture. ToolScope uses embedding clusters and contextual representatives; it does not reproduce the paper's LLM equivalence verification and cross-encoder pipeline. CMTF uses typed TaaS contracts as planner preconditions/effects, not an independently implemented native benchmark world-state model. AutoTool-style experience reuse is enabled only when confirmed trajectories and all registry/policy/tool hashes are revalidated.

For every result, report the baseline adapter ID, implementation maturity, source commit, exact parameter JSON, data split, training artifact hash and any deviation from the original paper.
