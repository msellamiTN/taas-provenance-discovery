# Colab T4 deployment profile for TaaS Core Studio

**Status:** deployment design / implementation gate  
**Target:** Google Colab runtime with NVIDIA T4 when available  
**Repository:** `msellamiTN/taas-provenance-discovery`  
**Purpose:** reproducible research/demo runtime, not a persistent production host

## 1. Deployment decision

Colab T4 is a supported *ephemeral compute profile*. It is not the system of record and it is not the production hosting tier.

Separate the platform into:

- **Studio control plane:** browser UI, API, authentication, experiment metadata, configuration and trace query APIs.
- **TaaS core:** contract extraction, capability hypergraph, provenance/policy checks, toolkit composition, certificates and discovery.
- **Optional GPU workers:** embedding generation, reranking, local model inference or other explicitly GPU-backed extensions.
- **Persistent services:** PostgreSQL/object storage or an equivalent durable backend, hosted outside the Colab runtime.

The current TaaS core dependencies are NumPy, SciPy, scikit-learn and Matplotlib. The inspected discovery engine does not currently require CUDA. A T4 therefore does **not** automatically accelerate the existing core. Use it only when an enabled extension actually uses CUDA; otherwise the Colab CPU runtime is sufficient.

## 2. Supported profiles

| Profile | Compute | Persistence | Intended use |
|---|---|---|---|
| Local development | Docker / CPU | Local volumes | Engineering |
| Colab CPU | Colab CPU | External durable store | Functional demos and smoke tests |
| Colab T4 | T4 GPU + CPU | External durable store | GPU-backed semantic enrichment and demos |
| Hosted Studio | VM/container service | Managed database and object storage | Team/reviewer access and continuous use |

The notebook must detect the actual accelerator. It must not assume that a T4 was allocated merely because the user selected a GPU runtime.

## 3. Colab notebook workflow

The eventual notebook `notebooks/colab/taas_core_studio_t4.ipynb` should contain these ordered sections:

1. **Runtime inspection**
   - Python version, RAM, disk and GPU availability.
   - Run `nvidia-smi` when available.
   - Record runtime metadata in the experiment environment manifest.
2. **Pinned checkout**
   - Clone the TaaS repository.
   - Checkout an explicit commit SHA supplied by the release configuration.
   - Never install from an unpinned moving branch for a reported experiment.
3. **Environment setup**
   - Install the project and its declared extras.
   - Install the Studio server/UI dependencies from a lock file once those services exist.
   - Run dependency and import checks.
4. **Persistent storage**
   - Mount Google Drive only for user-owned demo artifacts if desired.
   - Prefer external PostgreSQL and S3-compatible storage for shared/persistent experiments.
   - Do not keep the authoritative database only in Colab's local filesystem.
5. **Secrets**
   - Read API keys and tunnel credentials from Colab Secrets or a user-supplied secret manager.
   - Never write credentials to notebooks, output cells, manifests or Git.
   - Do not print environment variables.
6. **TaaS core validation**
   - Load a pinned model profile and tool registry.
   - Run deterministic unit/smoke tests.
   - Persist the exact commit, profile hash, policy and registry snapshot.
7. **Optional GPU extension**
   - Verify CUDA and GPU memory.
   - Load only a configured embedding/reranking model.
   - Fall back to CPU or disable the extension if CUDA is unavailable.
   - Record device, model revision, precision and batch size.
8. **Studio launch**
   - Start the FastAPI backend and built frontend when the Studio application is implemented.
   - Bind to loopback, not an unrestricted public interface.
   - Expose it through an authenticated, short-lived tunnel.
   - Display the session URL only after the tunnel has actually started.
9. **Run and persist**
   - Execute a small interactive task.
   - Persist manifest, discovery decision, event trace and redacted outputs outside the runtime.
10. **Shutdown**
   - Stop child processes.
   - Flush pending events and artifacts.
   - Revoke/expire the tunnel and release runtime resources.

## 4. Security requirements

- Never expose an unauthenticated FastAPI, Gradio or notebook server to the public internet.
- Prefer an authenticated tunnel with a short lifetime; do not use a public share URL as an authentication mechanism.
- Require application authentication even when a tunnel has access controls.
- Restrict MCP server egress with an explicit allowlist. Validate DNS resolution and resolved IP ranges to mitigate SSRF and DNS rebinding.
- Do not allow arbitrary user-provided URLs to be fetched by a privileged worker.
- Run MCP tools in isolated workers; do not execute untrusted server code inside the notebook kernel.
- Redact credentials, authorization headers, private arguments and sensitive outputs before trace persistence.
- Keep benchmark gold labels and evaluator-only metadata out of the interactive TaaS worker.
- Store secrets in Colab Secrets or an external secret manager, not in Drive files or notebook source.

Colab is a shared, ephemeral research environment. It must not host sensitive production credentials or high-trust workloads.

## 5. Persistence contract

Every run should produce a durable bundle containing:

- `experiment_manifest.json`
- `environment.json` (Python, OS, accelerator, package versions, commit SHA)
- `taas_profile.json`
- `registry_snapshot.json` or a content-addressed registry reference
- `goal_spec.json`
- `discovery_decision.json`
- `decision_certificate.json`, when produced
- `events.jsonl`
- `evaluation.json`, when an evaluator is configured
- redacted output artifacts and checksums

Use stable experiment IDs and content hashes. A Colab runtime restart must not destroy already completed experiment records.

## 6. GPU usage policy

GPU acceleration is optional and component-specific.

| Component | Default device | T4 usage |
|---|---|---|
| Contract extraction | CPU | Not required |
| Hypergraph construction | CPU | Not required |
| Policy/provenance evaluation | CPU | Not required |
| Toolkit composition | CPU | Not required by current implementation |
| Embedding model | CPU by default | Optional CUDA acceleration |
| Cross-encoder reranker | CPU by default | Optional CUDA acceleration |
| Local LLM inference | External API by default | Optional, subject to model memory/quantization |
| GUI/API | CPU | No GPU benefit |

A GPU-enabled run must record whether the GPU was actually used. Merely running in a T4 runtime is not evidence of GPU acceleration.

## 7. Studio service topology in Colab

For the first Studio prototype, use a single-origin deployment:

```text
Browser
  |
Authenticated short-lived tunnel
  |
Colab loopback listener
  |
FastAPI (API + built frontend)
  |             |                 |
TaaS Core    Worker adapter    Trace service
  |             |                 |
CPU discovery  Optional GPU     External PostgreSQL
               extensions      + object storage
```

Do not start a separate public frontend and API with independent unauthenticated tunnel URLs. A single origin simplifies CORS, session handling and access control.

## 8. Readiness gate: current code vs Studio

The inspected repository currently contains the Python TaaS discovery package and a draft MCP-Bench adapter. It does **not** yet contain the complete FastAPI Studio, frontend, persistent experiment service or Colab notebook launcher.

Therefore, the Colab deployment profile is an approved target architecture, not a claim that the full Studio is already deployable today.

Before publishing the one-click notebook, implement and test:

- [ ] FastAPI application and health/readiness endpoints.
- [ ] Studio frontend build and same-origin serving.
- [ ] Experiment create/run/status APIs.
- [ ] Trace/event persistence and redaction.
- [ ] Secret references (no secret values in experiment payloads).
- [ ] Authenticated short-lived tunnel workflow.
- [ ] Runtime cleanup and persistence flush.
- [ ] CPU-only smoke test.
- [ ] T4 smoke test with an explicitly GPU-backed extension.
- [ ] Colab runtime disconnect/restart recovery test.

## 9. Acceptance criteria

A Colab release is acceptable when:

1. The notebook checks out a pinned TaaS commit.
2. The environment can be rebuilt from a clean runtime.
3. The TaaS core smoke test passes on CPU.
4. The notebook correctly reports whether a T4 is present.
5. No component claims GPU acceleration unless CUDA execution is observed.
6. A user can launch the Studio through an authenticated, temporary endpoint.
7. The user can execute a task and inspect discovery and execution traces.
8. Experiment records survive runtime termination.
9. No secrets appear in notebook outputs, logs or persisted artifacts.
10. The notebook documents Colab disconnection and session-duration limitations.

## 10. Engineering sequence

- **C0:** Core import, registry/profile loading and deterministic smoke test in Colab.
- **C1:** FastAPI service with health/readiness and discovery endpoint.
- **C2:** Minimal Studio GUI and live trace viewer.
- **C3:** Durable experiment/event persistence and redaction.
- **C4:** Authenticated tunnel and notebook launcher.
- **C5:** Optional GPU-backed embedding/reranking extension and T4 validation.
- **C6:** Full interactive demo, followed by benchmark adapter integration.

Do not couple the benchmark's native evaluator or runner to the Colab UI. The benchmark adapter should call the same versioned TaaS service/core interface, while benchmark execution remains reproducible and independently runnable.
