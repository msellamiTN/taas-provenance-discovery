# TaaS Integrated Studio — Colab Runtime Product Specification

**Status:** implementation contract / proposed target architecture  
**Target deployment:** Google Colab (T4 when allocated), with a local-development path  
**Product principle:** one integrated browser Studio; Colab is the managed execution host, not the product UI.  
**Compatibility principle:** preserve the existing TaaS discovery engine and its scientific semantics. Add model serving, agent orchestration and controlled tool execution as separate subsystems around it.

## 1. Product definition

TaaS Studio is a vendor-independent environment for building, testing and operating tool-using AI agents. It combines:

1. Local model discovery, compatibility assessment, download, load, inference and unload.
2. Chat and bounded agent construction.
3. MCP server connection, tool inspection and controlled invocation.
4. TaaS GoalSpec authoring, capability discovery, provenance and policy assurance.
5. Governed execution with approval gates, budgets, cancellation and output capture.
6. Run history, traces, evaluation and reproducibility.
7. Colab lifecycle management and a browser-first operator experience.

The interaction model should be as approachable as Unsloth Studio, without depending on Unsloth's runtime, UI implementation or backend. TaaS owns the governance and execution lifecycle.

## 2. User journey and acceptance definition

A first-time user should be able to:

1. Open the pinned Colab notebook and select a GPU runtime when available.
2. Run one bootstrap cell; the notebook installs the pinned project revision, checks Python/dependencies, detects hardware, starts the service and opens the Colab browser proxy.
3. Open Studio without uploading a ModelProfile or manually editing configuration files.
4. Search Hugging Face models, inspect model metadata and artifact files, choose a backend/quantization/context size, and see a compatibility decision before download.
5. Download and load a model; see actual process state, allocated memory, load logs and a real inference smoke-test result.
6. Start a chat session and receive streamed model output.
7. Create an agent from a name, instructions, model, allowed tools, budget and approval policy.
8. Connect an MCP server, inspect tools and schemas, test connectivity, and manage server credentials without exposing secrets to the browser or logs.
9. Submit a task. TaaS converts/reviews the intent as a GoalSpec, discovers candidate capabilities, applies policy and provenance constraints, and returns a pre-execution decision.
10. Review the exact plan and approve any required effects.
11. Execute only through the controlled runtime. See tool calls, inputs/outputs (redacted as configured), errors, timing, token usage and cost estimates.
12. Inspect the final answer/artifacts and distinguish model claims from tool-produced evidence.
13. Reopen the run while the Colab runtime is alive; export a trace/artifact bundle for persistence beyond Colab's ephemeral disk.

**Acceptance rule:** a button is not implemented merely because it renders. Every enabled action must call a real API, expose a truthful state transition, handle failure, and have an automated test. Unimplemented features must be marked unavailable/experimental, not simulated.

## 3. Studio information architecture

Persistent left navigation:

- **Overview** — runtime health, active model, active workspace, recent runs, resource usage.
- **Chat** — model selection, streaming conversation, system prompt, generation controls, session management.
- **Models** — Hugging Face search, model details, artifact inspection, compatibility, download/cache, load/unload, inference test.
- **Agents** — agent builder, instructions, model, tools, memory policy, workflow limits, approval policy, test/run.
- **Tools & MCP** — server connections, transport/configuration, credentials, tool discovery, schema inspection, connectivity and invocation tests.
- **TaaS** — GoalSpec editor, registry, discovery, candidate comparison, policy, provenance, certificates, counterexamples and abstention explanation.
- **Runs & Traces** — run timeline, agent steps, tool events, model events, artifacts, metrics, errors, replay metadata and export.
- **Settings** — runtime, providers, secrets, storage, security, workspace defaults and diagnostics.

Do not present benchmark browsing as live MCP connectivity. Do not present metadata discovery as model loading. Do not present a certificate as evidence of execution or task success.

## 4. Runtime architecture

Keep the browser UI, control plane, model runtime, MCP execution and TaaS assurance logically separated.

    Browser Studio
       |
       | same-origin authenticated API / SSE
       v
    Studio Control Plane (FastAPI)
       |-- Workspace & Session Service
       |-- Model Manager
       |     |-- HF metadata/artifact adapter
       |     |-- compatibility estimator
       |     |-- download/cache manager
       |     |-- inference backend adapter
       |-- Chat & Agent Orchestrator
       |-- MCP Connection/Registry Manager
       |-- TaaS Discovery & Assurance (existing core)
       |-- Policy / Approval / Budget Service
       |-- Run & Trace Store
       |
       +--> Model Worker (GPU where available)
       +--> MCP Worker (isolated process/container boundary where available)
       +--> Artifact / Trace Storage

The existing discovery engine remains authoritative for its current selection and assurance semantics. The orchestrator must call it through a typed adapter; it must not reimplement or weaken the core algorithms.

Colab is a single-user, ephemeral execution environment. The initial release must state that limitation and must not imply production multi-tenancy. A future persistent deployment can replace local SQLite/filesystem storage and process isolation with managed services without changing the browser/API contracts.

## 5. Colab runtime contract

### 5.1 Bootstrap

The notebook must:

- Pin a release tag or immutable commit SHA; never install an unpinned moving branch in a reproducibility path.
- Install into the active notebook interpreter and verify imports.
- Detect Python version, OS, CPU, RAM, disk, GPU model, total/free VRAM, CUDA visibility, driver and PyTorch CUDA support.
- Distinguish host GPU visibility from actual inference readiness.
- Start the API on loopback only and expose it through the Colab proxyPort mechanism.
- Generate a per-runtime random bearer token; display it once and keep it out of logs, URLs, notebook source and persisted traces.
- Provide idempotent start, stop and restart controls; retain process handles and logs.
- Run /health, /ready and a lightweight runtime self-test before presenting the Studio URL.
- Print actionable diagnostics and stop on bootstrap failure rather than continuing in a partially configured state.

No public unauthenticated tunnel. No mandatory ModelProfile upload. No assumption that a T4 is always allocated.

### 5.2 Runtime lifecycle API

Proposed endpoints (final names may follow existing API conventions):

| Method | Endpoint | Contract |
|---|---|---|
| GET | /api/v1/runtime/status | Host, GPU, CUDA, process and readiness status |
| POST | /api/v1/runtime/start | Start selected runtime components |
| POST | /api/v1/runtime/stop | Graceful stop; return actual final state |
| POST | /api/v1/runtime/restart | Controlled restart |
| GET | /api/v1/runtime/logs | Bounded, redacted diagnostic logs |

### 5.3 Colab resource constraints

- Never hard-code a T4 memory assumption as available memory. Query the live device.
- Reserve VRAM for CUDA context, model activations, KV cache, allocator fragmentation and backend overhead.
- Estimate before download/load, then validate using actual backend load and a real smoke test.
- Offer conservative defaults: batch size 1, bounded context, bounded generation, explicit quantization.
- Do not load multiple models concurrently by default.
- Provide unload and cleanup actions and verify that allocated memory/process state changes.
- Explain that Colab sessions can disconnect, reset or reclaim resources; persist user-requested artifacts to mounted Drive or explicit export, with clear consent.

## 6. Model Manager

### User-visible lifecycle

Search → Inspect → Compatibility check → Select backend/quantization → Download → Verify → Load → Smoke test → Use → Unload

Required behavior:

- Search Hugging Face metadata using bounded, authenticated server-side requests.
- Inspect repository metadata and exact candidate artifact files; show license, gated/private status, file sizes, formats and revision.
- Pin an immutable model revision for every download and run.
- Treat model cards, repository metadata and custom code as untrusted.
- Do not execute trust_remote_code by default. Any exceptional opt-in must be explicit, isolated and warned.
- Validate backend support for architecture, tensor format, quantization and hardware before download/load.
- Support an initial documented backend set (for example Transformers + bitsandbytes where compatible); do not claim support for a backend until its integration tests pass.
- Provide download progress, cache path, checksum/size verification where available, cancellation and cleanup.
- Load/unload in a worker boundary; capture actual errors and memory deltas.
- Run a deterministic short inference smoke test after load.

### Proposed endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | /api/v1/models/search | Bounded catalog search |
| GET | /api/v1/models/detail | Repository/revision metadata |
| POST | /api/v1/models/compatibility | Artifact/backend/hardware compatibility assessment |
| POST | /api/v1/models/download | Start cancellable download job |
| GET | /api/v1/models/jobs/{job_id} | Download/load job status |
| POST | /api/v1/models/load | Load verified artifact |
| POST | /api/v1/models/unload | Unload active model |
| GET | /api/v1/models/active | Actual loaded model and backend state |
| POST | /api/v1/models/smoke-test | Real bounded inference test |

Memory estimates are advisory, not compatibility guarantees. Report assumptions and unknowns. Compatibility must be based on the exact artifact revision and selected backend, not only model name, parameter count or catalog tags.

## 7. Chat and agent runtime

### Chat

- Select an actually loaded model.
- Stream tokens through Server-Sent Events (SSE), with explicit completion/error/cancel events.
- Support system prompt, temperature, top-p, max-new-tokens, stop sequences and context limits only when supported by the backend.
- Store session metadata and messages locally with explicit retention/export controls.
- Show model identity/revision, backend and generation parameters for reproducibility.

### Agents

An agent definition contains:

- name and description;
- system instructions;
- model reference and immutable revision;
- allowed tool references;
- optional memory policy;
- maximum steps, wall-clock duration and token budget;
- per-tool timeout/retry limits;
- approval requirements by effect/risk;
- output/artifact contract.

The agent loop must be bounded and observable. Each model turn, tool proposal, policy decision, approval, tool invocation and finalization is a separate event. The agent must never invoke MCP directly around TaaS policy. All tool calls pass through the TaaS-governed execution gateway.

No hidden autonomous infinite loop. Cancellation must propagate to model generation and tool processes.

## 8. MCP manager and controlled tool invocation

Initial connection support should explicitly document supported transports and authentication mechanisms. Do not imply universal MCP compatibility.

Required lifecycle:

1. Add server endpoint/configuration.
2. Resolve credentials through server-side secret storage.
3. Connect with bounded timeouts.
4. Discover tools and capture server identity/version and schema snapshot.
5. Validate schemas and display untrusted declarations as declarations.
6. Test a read-only tool only when the operator explicitly requests it.
7. Register tool contracts/provenance with TaaS.
8. Invoke only through the execution gateway after policy checks and required approval.

Security requirements:

- Secrets never enter browser local storage, URLs, trace payloads or ordinary logs.
- Tool arguments and outputs are size-limited and redacted.
- Apply per-server allowlists, network egress controls and timeouts.
- Enforce read/write/destructive effect distinctions; annotations alone are not proof of behavior.
- Isolate MCP server processes where the deployment permits. Colab limitations must be documented honestly.
- Treat tool descriptions, schemas, annotations and outputs as untrusted data, never as instructions to the control plane.
- Record server/tool identity, schema hash, policy decision and invocation outcome.

## 9. TaaS governance in the agent lifecycle

The mandatory execution sequence is:

User intent → GoalSpec review/validation → Capability discovery → Policy/provenance assurance → Plan review → Approval (if required) → Runtime invocation → Output validation → Trace finalization

Invariants:

- Discovery does not execute tools.
- A selected toolkit is not proof of task completion.
- A valid pre-execution certificate is not runtime evidence.
- Metadata/schema/annotations are not proof of tool behavior.
- Runtime must enforce the policy decision; UI-only approval is insufficient.
- If discovery abstains, required evidence is missing, policy denies, or the runtime cannot enforce the decision, execution must not proceed.
- Re-discover/re-authorize when the GoalSpec, tool definition/schema hash, policy, model identity or relevant context changes.
- Preserve the strict uncalibrated model profile behavior; do not fabricate calibration values.
- Keep benchmark gold labels behind the evaluator boundary. They must never be exposed to the discovery UI, analyst prompt, agent or runtime planner.

## 10. Runs, traces and evaluation

A run record should include:

- run/workspace/agent IDs and timestamps;
- prompt and GoalSpec version/hash;
- model repository, immutable revision, backend and generation parameters;
- discovery request/response and certificate references;
- policy version and approval records;
- MCP server/tool identity and schema hash;
- redacted arguments and outputs (subject to retention policy);
- model/tool timing, token counts, retries, errors and cancellation;
- resource observations and clearly labelled estimated costs;
- final response, output artifacts and validation status.

Use an append-only event sequence for the run timeline. Persist initially to SQLite plus a local artifact directory; support explicit export to ZIP/JSONL with a manifest and checksums. Colab local persistence is ephemeral. Google Drive persistence must be opt-in and clearly disclosed.

Evaluation must distinguish retrieval metrics, policy/assurance checks, runtime reliability and end-task quality. Never collapse them into one unqualified success score.

## 11. API and event design principles

- Version all public API routes.
- Use typed request/response models and stable error codes.
- Use job IDs for downloads, model loads and long-running runs.
- Use SSE for token streaming, job progress and run events; include event IDs for reconnection where feasible.
- Make start/stop/download/run operations idempotent or reject duplicate requests explicitly.
- Every operation has bounded timeouts, cancellation semantics and resource limits.
- Authenticate all non-health endpoints. Apply CSRF/origin protections appropriate to same-origin browser access.
- Redact bearer tokens, provider keys, MCP credentials and sensitive tool data.
- Do not trust client-supplied model compatibility, provenance, effect or approval state.

## 12. Delivery phases and exit gates

### Phase 0 — Colab baseline and contract audit
- Verify current main, existing endpoints, notebook, packaging and tests.
- Freeze API/event contracts and a feature-to-test matrix.
- Confirm open PRs remain independent; do not merge them without authorization.

**Exit:** reproducible pinned Colab bootstrap contract and current-state audit.

### Phase 1 — Studio shell and runtime lifecycle
- Persistent navigation and workspace shell.
- Runtime status, start/stop/restart, logs and Colab health.
- Token handling and readiness gating.

**Exit:** notebook launches the same-origin Studio reliably; failures are visible and recoverable.

### Phase 2 — Real Model Manager
- Artifact/revision inspection, compatibility, download, cache, load/unload and smoke test.
- T4 memory checks and cancellation.

**Exit:** one supported model loads and generates a response in a live Colab T4 session; logs and memory evidence captured.

### Phase 3 — Chat
- Streaming chat, session management, generation controls and cancellation.

**Exit:** repeatable model-backed conversation with correct loaded-model identity.

### Phase 4 — MCP manager
- Supported transport connections, server credentials, schema registry and connectivity tests.

**Exit:** connect to a test MCP server and enumerate tools without invoking them implicitly.

### Phase 5 — TaaS-governed agent execution
- Agent definition, bounded orchestration, GoalSpec mapping, discovery, policy, approvals and runtime gateway.

**Exit:** allowed read-only test task executes through TaaS; denied/abstained task is blocked; no bypass path exists.

### Phase 6 — Runs, traces and artifacts
- Event timeline, redaction, export, artifact capture and evaluation separation.

**Exit:** run is auditable and exportable, with pre-execution assurance clearly separated from runtime evidence.

### Phase 7 — Hardening
- Dependency pinning, vulnerability review, resource isolation, secret handling, quotas, recovery, docs and browser accessibility.

**Exit:** documented threat model, regression suite and tested Colab lifecycle.

## 13. Feature-to-test acceptance matrix

| Feature | Minimum automated test | Live Colab acceptance |
|---|---|---|
| Bootstrap | pinned install/import/start/health tests | clean runtime opens Studio |
| GPU diagnostics | mocked and no-GPU paths | actual device/CUDA state displayed |
| Model compatibility | artifact/backend/VRAM edge cases | selected artifact accepted/rejected truthfully |
| Download | revision pin, cancellation, checksum/error | progress and cache verified |
| Load/unload | backend errors, state transitions, cleanup | real load, inference, unload |
| Chat | SSE ordering, error, cancel | streamed answer from active model |
| MCP | auth, timeout, schema change, disconnect | connect to test server and enumerate |
| TaaS gateway | deny/abstain/stale certificate blocks | denied call never reaches server |
| Agent loop | max-step/budget/cancel enforcement | bounded multi-step run |
| Trace | event order, redaction, export integrity | export and inspect a real run |
| Colab lifecycle | restart/stop/log cleanup | repeat launch and stop without orphan process |

## 14. Non-goals for the initial Colab release

- Production multi-user tenancy or enterprise identity.
- Arbitrary execution of model repository code.
- Unrestricted public MCP server hosting.
- Guaranteed availability of a T4 or any fixed VRAM size.
- Persistent storage without explicit user configuration.
- Claiming end-task correctness solely from a model response, discovery certificate or successful tool call.

## 15. Required release artifacts

Every release must include:

- pinned Colab notebook and quickstart;
- supported-model/backend compatibility table with tested revisions;
- architecture and data-flow diagrams;
- API and SSE event reference;
- security/threat-model notes;
- setup/troubleshooting guide;
- feature-to-test matrix and CI results;
- known limitations and explicit unimplemented-feature list;
- live Colab validation record identifying runtime type, commit SHA, model revision, backend, tests and observed results.

A release must not claim live Colab validation unless the exact commit has actually been run in Colab and the evidence is recorded.
