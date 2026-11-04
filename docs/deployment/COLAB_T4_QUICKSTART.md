# TaaS Studio on Google Colab — CPU, CUDA and Ollama quickstart

## One-click launch

1. Open [the Colab notebook](../../notebooks/colab/taas_core_studio_colab.ipynb).
2. Select **Runtime → Change runtime type → T4 GPU** when available; CPU-only runtimes are also supported.
3. Run the notebook cells from top to bottom.
4. Wait for the package import and /health + /ready checks.
5. Open the generated **TaaS Studio** browser link.
6. Copy the temporary API token printed by the launch cell into the persistent **Studio authentication** control in the application header, then select **Connect**. The header verifies the token against the current runtime and keeps it in page memory only; Discovery, GoalSpec validation, Model Studio and Agent Studio reuse the authenticated session.

No ModelProfile upload, Hugging Face token, model endpoint or manual provider configuration is required to launch the current Studio.

## GPU diagnostics milestone

The Studio includes an authenticated **Runtime · GPU diagnostics** panel. Enter the current runtime token and select **Check GPU and CUDA**.

- `gpu_detected` and `nvidia_smi_available` report host-level NVIDIA visibility.
- `cuda_available` reports whether the installed PyTorch build can access CUDA.
- `inference_ready` is true only when PyTorch reports CUDA and a device can be queried.
- GPU memory is reported in MiB when available.
- A visible T4 with `inference_ready=false` is not yet a working inference runtime.

This endpoint is diagnostic only. It does not install CUDA, PyTorch, model weights or an inference engine, and it does not allocate GPU memory or run a model.

## Model runtime backends

The integrated Model/Agent Studio supports:

- **Hugging Face Transformers on CPU** — supported without a GPU. Automatic mode selects CPU when CUDA is unavailable.
- **Hugging Face Transformers on CUDA** — optional acceleration when Colab allocates a compatible GPU.
- **Ollama** — optional separate daemon in the same Colab VM or at an operator-configured endpoint. Set `TAAS_OLLAMA_BASE_URL` before launching Uvicorn when the daemon is not at `http://127.0.0.1:11434`.

The notebook installs the Hugging Face extras, including `sentencepiece` and `tiktoken`, and includes an opt-in Ollama setup cell. Ollama is not installed or started by default. See [Model Runtime Backends](MODEL_RUNTIME_BACKENDS.md) for setup, memory guidance, tokenizer fallback behavior, and troubleshooting.

A Hugging Face model load is an actual weight-load operation inside the TaaS process. Ollama model selection validates an installed tag; Ollama loads weights lazily on the first inference. Device placement and quantization for Ollama remain managed by Ollama.

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
- A successful discovery response returns the canonical parsed GoalSpec, including `in`, `out`, `eff`, `desc`, and `deps`. Before discovery, review the objective-to-GoalSpec mapping and selected tool metadata, then confirm the Studio human-review checkbox. The API rejects discovery with HTTP 409 when this confirmation is absent; editing the prompt, GoalSpec or tool selection invalidates the confirmation.

An `abstained` result remains a valid safety outcome. Inspect `counterexample`, `gap`, `composition.stats.per_goal`, and the eligible/candidate counts; do not weaken policy or type checks merely to obtain a selected toolkit.

## Default calibration mode

Studio starts without TAAS_MODEL_PROFILE. The API creates an explicit uncalibrated-default profile with strict=True. Unknown model-native capabilities therefore receive rho=0; the system does not invent calibration measurements or claim calibrated model competence.

A measured model profile can be configured later through a dedicated Studio configuration interface. It must be produced from actual calibration observations and validated using ModelProfile.load(path). Model-provider configuration (Hugging Face repository, quantization, inference runtime and generation parameters) is separate from this calibration profile.

## Runtime and security

- Uvicorn binds to 0.0.0.0:8000 inside the ephemeral Colab runtime so Colab's proxy can reach it. Readiness checks use 127.0.0.1:8000. API routes remain bearer-token protected; no unauthenticated public tunnel is created.
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
| Discovery returns 409 | Review the objective, GoalSpec, effects, dependencies and selected tool metadata, then confirm the human-review checkbox. Any subsequent edits require reconfirmation. |\n| Discovery returns 422 | Check GoalSpec, policy and engine fields against the current TaaS core contract. |
| Colab proxy returns `RpcError(NOT_FOUND)` | Confirm `/health` and `/ready` passed, then verify Uvicorn binds to `0.0.0.0:8000`, not loopback-only. Rerun the proxy-link cell after the server is ready. |
| Colab proxy fails for another reason | Confirm the runtime remains connected and rerun the proxy-link cell. |

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


## 9. Clean-runtime validation procedure

For a reproducible operator check:

1. In Colab, select **Runtime → Disconnect and delete runtime** to remove stale server processes and proxy state.
2. Reopen the maintained notebook from the PR link and run every cell from the top.
3. Confirm the printed commit equals `7859cd76670f00ec54f0b245ca6b257f8cb9c83e`.
4. Confirm installation/import checks complete, then verify both health and readiness return HTTP 200.
5. Open the generated proxy URL and connect with the ephemeral token from that runtime only.
6. Record runtime type, Python version, GPU allocation, model repository/revision, device, precision, load outcome, inference outcome, latency and peak memory when an actual model test is performed.
7. Keep the Colab output and logs private if they contain the temporary bearer token.

A CPU-only launch validates the Studio API and discovery workflow; it does not validate GPU model loading. A T4 allocation alone is not model inference evidence. Report each validation level independently and do not label a notebook as passed until its cells have actually run.
