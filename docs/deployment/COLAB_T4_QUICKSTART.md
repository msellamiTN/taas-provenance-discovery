# TaaS Model & Agentic Studio on Google Colab — Quickstart

## 1. Launch

1. Open the maintained [Colab notebook](../../notebooks/colab/taas_core_studio_colab.ipynb).
2. Select **Runtime → Change runtime type → T4 GPU** when available. CPU mode remains possible for smaller models.
3. Run the notebook cells from top to bottom.
4. The notebook checks out an immutable revision, installs `.[studio,hf]` into the active interpreter, verifies imports, detects hardware, creates a temporary API token and starts the FastAPI service on loopback.
5. Open the generated Studio link and enter the token in the Studio token field.

The Colab notebook currently pins the integrated Studio implementation at commit `26900dece9b035ff52dee3dd465a3e01ebff3c3c`. The pin is intentional: the notebook does not install an unreviewed moving branch.

## 2. What is available in this revision

### Model Studio

- Search Hugging Face repositories using the authenticated model catalog adapter.
- Inspect repository metadata and reported architecture fields.
- Inspect repository file metadata and backend candidates without downloading those files.
- Estimate weight memory and optional decoder KV cache when the required dimensions are present.
- Explicitly load a Hugging Face causal language model into the process hosting the Studio API.
- Run real model-backed chat inference against the process-local loaded model.

Relevant API routes:

| Method | Route | Behavior |
|---|---|---|
| GET | `/api/v1/models/search` | Search repository metadata |
| GET | `/api/v1/models/detail` | Inspect reported model/config metadata |
| GET | `/api/v1/models/artifacts` | Inspect file metadata; no download |
| POST | `/api/v1/models/estimate-memory` | Advisory memory estimate |
| GET | `/api/v1/models/runtime` | Actual process-local model state |
| POST | `/api/v1/models/load` | Explicit download and load into this API process |
| POST | `/api/v1/models/chat` | Real inference using the loaded model |

The runtime accepts a Hugging Face `owner/repository` model ID and `auto`, `cpu` or `cuda` device selection. Loading uses `trust_remote_code=False` and Safetensors. A model selected in the catalog is not loaded automatically. A successful load does not prove the model produces correct answers; a successful chat request is evidence that an inference request completed.

The memory estimator is not a compatibility or load guarantee. It estimates weights, configured overhead, runtime reserve and optional decoder KV cache. It excludes activations, backend workspaces and allocator fragmentation. Artifact-extension/backend matches are candidates only; actual load and inference are the runtime checks.

### Agent Studio

- Chat with the loaded model.
- Ask the loaded model to propose a canonical TaaS GoalSpec from a natural-language objective.
- Parse and structurally validate the proposal.
- Review the proposed goals before applying them to the visual GoalSpec editor.

The proposal is not proof that the GoalSpec faithfully represents the user's intent. Structural validation is not semantic validation. This revision does not implement a bounded autonomous agent loop or MCP tool-calling execution.

Relevant API routes:

| Method | Route | Behavior |
|---|---|---|
| POST | `/api/v1/agents/decompose` | Model-assisted GoalSpec proposal |
| POST | `/api/v1/goals/validate` | Structural validation only |

### TaaS Discovery Studio

- Browse retained benchmark datasets, task prompts and tool metadata.
- Author and validate GoalSpecs.
- Inspect configured MCP stdio servers and their advertised tool schemas.
- Submit a GoalSpec, tool contracts and policy to the actual TaaS discovery engine.
- Inspect selected tools or explicit abstention, model coverage, composition statistics, certificate checks, witnesses and counterexamples.

Relevant API routes:

| Method | Route | Behavior |
|---|---|---|
| GET | `/api/v1/bench/datasets` | Retained dataset catalogue |
| GET | `/api/v1/bench/tasks` | Task prompts; evaluator gold mappings are not returned |
| GET | `/api/v1/bench/tools` | Retained tool metadata |
| GET | `/api/v1/mcp/servers` | Operator-configured MCP stdio servers |
| POST | `/api/v1/mcp/servers/{server_id}/inspect` | Connect and inspect tool schemas only |
| POST | `/api/v1/discover` | Run TaaS discovery and pre-execution assurance |

MCP inspection does not call `tools/call`. Discovery does not execute selected tools. A selected toolkit and a valid pre-execution certificate do not establish runtime success or task completion.

## 3. Model capability calibration

The TaaS core uses a measured `ModelProfile` to estimate native model capability. This is different from Hugging Face model metadata and different from successful model loading.

By default, the notebook removes `TAAS_MODEL_PROFILE`, so the API starts with an explicit strict, uncalibrated profile. Unmeasured model-native capabilities are not assumed. Do not infer `rho` values from model names, parameter counts, model cards or artifact metadata.

At this revision, the loaded Model Runtime identity is not yet automatically bound to a measured TaaS ModelProfile. Treat that as a known integration limitation. A configured profile must be produced from actual calibration observations and must correspond to the model being evaluated.

## 4. MCP server configuration and boundaries

MCP servers are operator-configured through `TAAS_MCP_SERVERS_JSON` or `TAAS_MCP_SERVERS_FILE`. The current adapter supports configured stdio servers for inspection. The server process is started only for the bounded inspection session; the feature returns the advertised tool descriptions, schemas and annotations.

- Tool descriptions, schemas and MCP annotations are declarations, not independently verified evidence.
- The current Studio does not provide a general MCP server connection manager, credential vault, remote HTTP/SSE transport support or invocation API.
- The execution-gateway module contains authorization primitives, but it does not start MCP servers or invoke tools.
- Do not expose a button or workflow as executable unless a server-side invocation implementation and its security controls have been separately delivered and tested.

## 5. Runtime and Colab behavior

- The API binds to `127.0.0.1:8000` and is exposed using Colab's `proxyPort` helper.
- The model runs inside the same Colab Python process that hosts the API; this is not a remote Colab connector.
- The notebook creates a temporary bearer token for the runtime. Treat notebook output as sensitive and do not share the token.
- Colab storage and process state are ephemeral. Model downloads may consume substantial disk and memory.
- A visible T4 is a host-level observation. Actual model load and inference must be verified from Model Studio.
- The discovery core is CPU-oriented; a GPU is intended for local model inference, not for accelerating the current discovery algorithms.

The API is experimental, process-local and single-user oriented. It is not a production multi-tenant deployment.

## 6. Trust and result interpretation

Keep these states distinct:

1. **GoalSpec structural validity** — the contract passes syntax, type vocabulary and dependency checks.
2. **Discovery selection** — the engine found a candidate toolkit under the submitted contracts and policy.
3. **Pre-execution certificate** — the mandatory checks and recorded witnesses validate under the model, provenance and policy assumptions.
4. **Runtime outcome** — whether an actual model or MCP invocation ran and what it returned.

The current MCP workflow reaches inspection and discovery, not runtime tool invocation. Never describe a certificate as an execution trace, a selected toolkit as proof of semantic task completion, or metadata as runtime observation.

## 7. Troubleshooting

| Symptom | Action |
|---|---|
| Repository checkout fails | Check Colab network access and the immutable pinned commit. |
| Installation fails | Inspect the pip output in the notebook. The integrated Model Studio requires the `hf` extra. |
| Import check fails | Confirm `torch`, `transformers`, `safetensors`, FastAPI and Uvicorn imports succeed in the active interpreter. |
| GPU not visible | Select a GPU runtime when available; inspect `nvidia-smi`. |
| Model load fails | Inspect the API/Colab log. Confirm model access, available disk/VRAM, supported Safetensors artifacts and backend requirements. |
| Chat reports no model loaded | Use the explicit Model Runtime load action first. |
| API returns 401 | Enter the temporary token printed by the current notebook runtime. |
| Discovery returns 422 | Validate the GoalSpec, semantic types, effects and engine settings. |
| Discovery abstains | Inspect the counterexample, gap, evidence threshold, policy and composition diagnostics; do not weaken safety constraints just to force selection. |
| Colab proxy fails | Keep the runtime connected and rerun the proxy-link cell. |

## 8. Deliberately not included yet

The following remain separate implementation milestones:

- model unload and managed download/load jobs;
- immutable model revision pinning and revision-bound calibration;
- streaming chat and conversation persistence;
- model identity and measured TaaS ModelProfile binding;
- durable workspaces, discovery run history and exportable traces;
- persistent MCP server sessions, credential isolation and broader transport support;
- sandboxed MCP invocation, runtime authorization enforcement, cancellation and output redaction;
- bounded autonomous agent orchestration;
- production identity, tenancy, quotas, audit and operational hardening.

The current Studio should be evaluated against the features actually delivered above, not against this future roadmap.
