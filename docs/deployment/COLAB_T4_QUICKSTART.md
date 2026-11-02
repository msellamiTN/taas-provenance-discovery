# TaaS Studio on Google Colab T4 — quickstart

## One-click launch

1. Open [the Colab notebook](../../notebooks/colab/taas_core_studio_colab.ipynb).
2. Select **Runtime → Change runtime type → T4 GPU** when available.
3. Run the notebook cells from top to bottom.
4. Wait for the package import and /health + /ready checks.
5. Open the generated **TaaS Studio** browser link.
6. Copy the temporary API token printed by the launch cell into the Studio token field when submitting discovery requests.

No ModelProfile upload, Hugging Face token, model endpoint or manual provider configuration is required to launch the current Studio.

## GPU diagnostics milestone

The Studio includes an authenticated **Runtime · GPU diagnostics** panel. Enter the current runtime token and select **Check GPU and CUDA**.

- `gpu_detected` and `nvidia_smi_available` report host-level NVIDIA visibility.
- `cuda_available` reports whether the installed PyTorch build can access CUDA.
- `inference_ready` is true only when PyTorch reports CUDA and a device can be queried.
- GPU memory is reported in MiB when available.
- A visible T4 with `inference_ready=false` is not yet a working inference runtime.

This endpoint is diagnostic only. It does not install CUDA, PyTorch, model weights or an inference engine, and it does not allocate GPU memory or run a model.

## Current capability boundary

This PR milestone launches the existing **TaaS discovery workspace**. It does not yet provide Hugging Face model search/download/load, model-backed chat, agent orchestration, MCP server invocation, live execution streaming or persistent run history. These must be implemented and tested before being advertised as available.

The Colab notebook installs the package into the active interpreter and verifies the taas import before starting Uvicorn. If installation fails, it prints the pip output and stops instead of continuing into a misleading profile-import error.

## Valid discovery example

The browser workspace ships with a runnable, read-only metadata example. Its GoalSpec follows the parser contract:

```json
{
  "prompt": "List the available orders",
  "goals": [{
    "id": "g1",
    "class": "retrieve",
    "in": [],
    "out": "record[]",
    "eff": ["read(*)"],
    "sigma": "data",
    "desc": "Retrieve the available orders",
    "deps": []
  }]
}
```

The accompanying demo tool is named `demo-orders::list_orders`, declares an array output schema, and has the MCP `readOnlyHint` annotation. This is synthetic metadata supplied to the discovery engine; it is not a live MCP connection and does not execute the tool.

Important contract rules:

- Use `out`, `desc`, and `deps`; the API rejects the legacy aliases `output`, `reason`, and `dependencies`.
- Goal `class` must be a supported model or external class. `read` is an effect, not a goal class.
- `eff` is an array of effect expressions, e.g. `["read(*)"]`, not a scalar string.
- `sigma` is one of `native`, `data`, `effect`, or `unreliable`.
- Semantic output types must agree with the tool contract. The demo uses `record[]` on both sides.
- The demo policy uses `lmin: ann` because its synthetic read-only evidence comes from an MCP annotation; an `obs` threshold would correctly exclude annotation-only evidence.
- A successful discovery response returns the canonical parsed GoalSpec, including `in`, `out`, `eff`, `desc`, and `deps`.

An `abstained` result remains a valid safety outcome. Inspect `counterexample`, `gap`, `composition.stats.per_goal`, and the eligible/candidate counts; do not weaken policy or type checks merely to obtain a selected toolkit.

## Default calibration mode

Studio starts without TAAS_MODEL_PROFILE. The API creates an explicit uncalibrated-default profile with strict=True. Unknown model-native capabilities therefore receive rho=0; the system does not invent calibration measurements or claim calibrated model competence.

A measured model profile can be configured later through a dedicated Studio configuration interface. It must be produced from actual calibration observations and validated using ModelProfile.load(path). Model-provider configuration (Hugging Face repository, quantization, inference runtime and generation parameters) is separate from this calibration profile.

## Runtime and security

- The API binds to 127.0.0.1:8000 and is opened through Colab's proxyPort helper.
- The notebook creates a temporary bearer token per runtime. Treat the notebook output as sensitive; do not share it.
- Colab is ephemeral. Model weights, process state and files under /content may disappear when the runtime ends.
- A visible T4 does not accelerate the current CPU-oriented discovery engine. It is intended for a future local inference backend.
- Do not expose the service through an unauthenticated public tunnel. Team sharing requires a named tunnel and an identity-aware access policy protecting the complete hostname.

## Troubleshooting

| Symptom | Action |
|---|---|
| Repository checkout fails | Check network access and pinned commit availability. |
| taas import fails | Confirm the install cell completed; inspect its pip stdout/stderr and verify src/taas exists in the checked-out repository. |
| GPU not visible | Select T4 if available; check `nvidia-smi` in Colab. |
| GPU visible, CUDA unavailable | A CUDA-compatible PyTorch build and inference backend are not yet configured; host visibility alone is insufficient. |
| Hardware diagnostics return 401 | Enter the current runtime token in Studio. |
| API exits | Inspect /content/taas-studio.log. |
| /ready returns 503 | Confirm the generated API token is present in the notebook runtime and rerun launch. |
| Discovery returns 401 | Paste the current runtime's token into the Studio token field. |
| Discovery returns 422 | Check GoalSpec, policy and engine fields against the current TaaS core contract. |
| Colab proxy fails | Confirm the runtime remains connected and rerun the proxy-link cell. |

## Next product milestones

1. Hugging Face Model Manager with T4-aware memory estimation and load/unload.
2. Model-backed chat and a bounded agent runtime.
3. MCP server/tool registry and controlled invocation.
4. TaaS-governed tool selection, approval and execution enforcement.
5. Observable run timeline, decision certificates and persistent trace storage.

The benchmark-native execution adapters remain separate from interactive Studio chat so that interactive features do not alter benchmark protocols.


## Interpreting discovery results

Studio distinguishes model delegation from external-tool coverage:

- **Model-delegated goals** is the core engine's `gap`: goals not handled natively by the configured model profile and therefore passed to tool composition. It is not, by itself, a remaining coverage failure.
- **Toolkit-bound goals** counts goal bindings in a successful composition certificate.
- **Selected tools** lists metadata contracts chosen by composition.
- A selected result and certificate establish compatibility under the supplied metadata, provenance and policy assumptions. They do not establish that a live MCP server is reachable or that executing a tool will return correct data.
- `rho` is the model capability estimate. A zero value in an uncalibrated strict profile is not a tool quality score.

Studio preserves the natural-language `goal_spec.prompt` when parsing and returning the canonical GoalSpec.


## Model Manager foundation: VRAM estimation

The authenticated endpoint `POST /api/v1/models/estimate-memory` provides an early model-size filter. Example:

```json
{
  "parameters_billion": 7,
  "quantization": "int4",
  "overhead_fraction": 0.2,
  "runtime_reserve_gib": 2.0
}
```

Supported weight-storage assumptions are FP16 (2 bytes/parameter), INT8 (1 byte/parameter), and INT4 (0.5 byte/parameter). The estimate adds a configurable overhead fraction and runtime reserve, and compares the result with currently observed free GPU memory when available.

**This is not a model compatibility or load guarantee.** When architecture inputs are supplied, the estimator adds decoder KV cache using `2 × layers × KV heads × head dimension × context length × batch size × bytes per element`. Supported cache dtypes are FP16, INT8 and FP32. If any architecture dimension is supplied, all four dimensions are required. Without them, KV cache is reported as unknown and is not included in the total. The estimate still excludes activations, CUDA workspaces, allocator fragmentation and backend-specific quantization metadata. No model is downloaded or loaded by this endpoint.


## Read-only Hugging Face model catalog

The Studio **Model catalog · Hugging Face** panel calls the authenticated endpoint:

`GET /api/v1/models/search?q=...&limit=10&sort=downloads`

The adapter queries the fixed Hugging Face model metadata API and returns a bounded subset of repository metadata: model ID, model page, task tag, library, downloads, likes, last modification time, gated/private flags, license tag, tags, safetensors presence and parameter count when supplied by the catalog.

Operational properties:

- Search limit is capped at 30 records; request timeout is 12 seconds.
- An optional `HF_TOKEN` environment variable can be used for access to metadata that requires authentication. It is never returned by the API.
- The Studio bearer token is required for the endpoint.
- Repository IDs and metadata are treated as untrusted display data. No model card code, custom Python, or repository file is executed.
- Search does **not** download weights, inspect all weight shards, load a model, or certify T4 compatibility.
- Parameter counts may be absent. Safetensors metadata is not a substitute for inspecting a specific downloadable artifact and its quantization format.


The authenticated detail endpoint is:

`GET /api/v1/models/detail?model_id=namespace/repository`

It returns a whitelist of configuration fields explicitly reported by the Hugging Face model API, including model type, architecture names, layer/head counts, explicit head dimension and reported context-limit fields when present. It does not infer missing architecture values from the model name or from unrelated dimensions. The response marks whether the reported dimensions are sufficient for the current conventional decoder KV-cache estimator. It does not inspect downloadable weight artifacts, download files, execute model code or establish backend compatibility.

The next compatibility milestone must combine verified artifact metadata, architecture-specific KV-cache estimates, context length and the selected inference backend before allowing a download or load operation.


Example architecture inputs for a decoder model:

```json
{
  "parameters_billion": 7,
  "quantization": "int4",
  "num_hidden_layers": 32,
  "num_key_value_heads": 8,
  "head_dim": 128,
  "context_length": 4096,
  "batch_size": 1,
  "kv_cache_dtype": "fp16"
}
```

For those illustrative architecture values, the KV cache estimate is 0.5 GiB. These values are not inferred from the Hugging Face search result; they must be obtained from the selected model's verified configuration. The formula assumes a conventional decoder attention cache with separate key and value tensors. Architectures with sliding-window, latent, hybrid or otherwise nonstandard attention require a model-specific estimator.
