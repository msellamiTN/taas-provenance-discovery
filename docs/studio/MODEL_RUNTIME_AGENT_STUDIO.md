# Studio model runtime and Agent Studio

## Product slice

This increment turns Hugging Face model discovery into an explicit, process-local model lifecycle and adds a first Agent Studio workflow:

1. Search/inspect Hugging Face model metadata (existing catalog).
2. Explicitly download and load a selected model into the process running the Studio API.
3. Select `auto`, `cpu`, or `cuda` execution.
4. Run a real chat inference request.
5. Ask the same loaded model to decompose a natural-language objective into a TaaS GoalSpec.
6. Structurally validate the proposal using the existing GoalSpec validator.
7. Apply the proposal to the visual GoalSpec editor for human review before discovery.

The model is not automatically loaded on page view. No inference is simulated.

## Runtime boundary

The model is loaded by the process hosting the Studio API. When that process is started inside a Colab runtime, the model uses that Colab runtime's CPU or GPU. This implementation does **not** connect a separate browser-hosted Studio to a remote Colab session and does not provide Colab lifecycle management.

The current runtime is process-local and single-user oriented. Do not expose it as a multi-tenant model-serving service. Production deployment requires isolated workers, quotas, lifecycle management, persistent model configuration, and authorization at workspace/project scope.

## Initial model

Default selection: `Qwen/Qwen2.5-0.5B-Instruct`.

This is a starting model choice, not a claim of validated performance on every Colab CPU/GPU shape. Validate actual download, loading, memory use, generation latency, and GoalSpec quality on the target runtime before describing it as supported.

## Install

Install the Studio API dependencies and optional Hugging Face runtime:

```bash
pip install -e '.[studio,hf,test]'
```

For Colab, install the project and the same optional extra in the notebook/runtime environment. The runtime needs internet access to download model files from Hugging Face on first load.

Start the API with a token:

```bash
export TAAS_STUDIO_API_TOKEN='replace-with-a-long-random-token'
uvicorn taas.studio.api:app --host 127.0.0.1 --port 8000
```

Open the Studio page served by this API. Keep the token in the page's memory only; do not put it in URLs, notebooks committed to Git, or browser local storage.

## API

All endpoints below require the bearer token.

| Method | Endpoint | Behavior |
|---|---|---|
| GET | `/api/v1/models/runtime` | Actual process-local model state |
| POST | `/api/v1/models/load` | Explicit model download and load |
| POST | `/api/v1/models/chat` | Real text generation |
| POST | `/api/v1/agents/decompose` | GoalSpec proposal from the loaded model |

Example load request:

```json
{"model_id":"Qwen/Qwen2.5-0.5B-Instruct","device":"auto"}
```

Device behavior:

- `auto`: CUDA if PyTorch reports it available, otherwise CPU.
- `cpu`: FP32 model weights.
- `cuda`: requires CUDA; BF16 if supported, otherwise FP16.
- No automatic CUDA-to-CPU retry is attempted after a CUDA load failure. This avoids hiding an OOM or backend problem behind an unexpected large CPU allocation.

Security behavior:

- `trust_remote_code=False` for tokenizer and model loading.
- `use_safetensors=True`; repositories without Safetensors weights are rejected by the loader.
- Model ID must be a Hugging Face `owner/name` identifier.
- No credentials are sent to Hugging Face by this API unless the environment's Hugging Face client is independently configured.
- Chat and decomposition are authenticated API operations.

## Correctness boundaries

- A loaded model is not proof that inference works; only a successful generation request establishes that inference was executed.
- A structurally valid GoalSpec is not proof that it preserves the user's intent.
- The model's decomposition is a proposal. It does not select tools, authorize side effects, or invoke MCP.
- TaaS discovery remains a separate operation.
- Discovery certificates remain pre-execution evidence, not proof of runtime success.
- Any future agent tool invocation must pass through the TaaS policy and execution gateway. This increment deliberately does not add MCP execution.

## Known limitations / next product increments

- Process-local singleton; no persistent model registry or multi-user isolation.
- No unload/switch queue, cancellation, progress stream, or GPU memory admission controller yet.
- No conversational history persistence.
- No structured generation guarantee for every model; invalid JSON is surfaced and cannot be applied.
- No tool execution from Agent Chat.
- No real Colab CPU/GPU compatibility matrix has yet been measured.
