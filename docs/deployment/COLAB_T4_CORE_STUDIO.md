# Colab-hosted TaaS Core Studio (T4 profile)

**Status:** experimental deployment guide  
**Target:** Google Colab runtime with T4 GPU when available  
**Deployment model:** the TaaS Studio web application itself runs inside the Colab VM and is opened through Colab's notebook port proxy. Optional remote sharing uses a named Cloudflare Tunnel protected by Cloudflare Access.

## 1. Intended user experience

The target is similar to a notebook-launched web studio:

1. Open the TaaS Colab notebook.
2. Select **Runtime → Change runtime type → T4 GPU** (subject to Colab availability).
3. Run notebook cells from top to bottom.
4. The notebook checks out a pinned TaaS revision, installs Studio into the active interpreter, verifies package imports and GPU visibility, generates a temporary API token, and starts the web application on the Colab VM. No profile upload or provider configuration is needed to launch.
5. Open the Studio UI through Colab's port proxy.
6. Optionally configure a named Cloudflare Tunnel plus Cloudflare Access to share a protected hostname.

This is not a remote API client calling an unrelated Studio host. The FastAPI server and browser UI execute on the Colab runtime.

## 2. Current TaaS capabilities vs target

The current PR implementation has:
- FastAPI health/readiness endpoints (readiness does not require calibration).
- Bearer-authenticated discovery endpoint.
- Same-origin browser UI for GoalSpec and tool-catalogue submission.
- Selection/abstention, coverage gap, discovery latency, certificate and composition output.

Not implemented yet:
- MCP tool invocation and isolated MCP worker execution.
- Agent loop/model chat orchestration inside Studio.
- Live execution-event streaming.
- Persistent multi-run database and trace browser.
- Multi-user/workspace access control.

The notebook must not imply those capabilities are available. It currently launches the discovery workspace, not a complete agent execution product.

## 3. Colab runtime model

The application runs on the Colab VM:
- Uvicorn listens on `127.0.0.1:8000`.
- Browser traffic is forwarded through the Colab notebook's port proxy.
- TaaS CPU discovery runs in the same Python runtime.
- A future or separately configured local model backend can use the T4 for inference, embeddings or reranking.

T4 presence is checked with `nvidia-smi`. The existing discovery engine (contract extraction, hypergraph construction, provenance/policy checks and toolkit composition) is CPU-oriented; the notebook does not claim it is GPU-accelerated.

A T4 is a constrained GPU. Choose quantized models and batch sizes compatible with available VRAM. A Hugging Face model manager and local inference backend are not yet implemented in this milestone.

## 4. Access paths

### Owner-only notebook access

The notebook uses Colab's `google.colab.kernel.proxyPort(8000)` helper to open the application through the notebook origin. Access is governed by the Colab notebook/runtime session and Google account permissions. Do not publish the notebook with secrets embedded.

### Optional protected public hostname

For team access, use a named Cloudflare Tunnel and a Cloudflare Access application/policy:
- Configure the tunnel's origin as `http://127.0.0.1:8000`.
- Apply an Access policy that restricts permitted identities.
- Add the tunnel token as a Colab Secret named `CF_TUNNEL_TOKEN`.
- Enable the optional tunnel cell only after the hostname and Access policy are provisioned.

A tunnel token provides tunnel connectivity, not end-user authorization by itself. A random quick-tunnel URL is not an authentication mechanism. Do not expose the service without Access protection and application authentication. The current root UI and health endpoints are public at the origin, so the external Access layer must protect the whole hostname.

The notebook downloads the Cloudflare binary from its latest release in the optional branch. For reproducible or production use, pin the cloudflared version and verify its checksum before deployment.

## 5. Credentials

- Store `TAAS_STUDIO_API_TOKEN` and any model provider keys in Colab Secrets.
- The notebook generates a temporary API bearer token for the active runtime; treat its printed value as sensitive.
- ModelProfile calibration is optional at startup. Without one, the API uses a strict uncalibrated profile and does not assume unmeasured model capabilities.
- Provider credentials and model settings must be managed separately from calibration data when the model-provider interface is implemented.
- Do not print secrets or place them in source cells, Git, Drive, logs or experiment manifests.
- Do not submit private user arguments or secrets in discovery request JSON.
- The API token protects discovery POSTs; it does not replace tunnel-level access control.

## 6. Persistence and lifecycle

Colab runtimes are ephemeral and can be recycled. Files under `/content`, the process and model weights in RAM/VRAM are temporary.

For this milestone:
- Treat the runtime as disposable.
- Store reviewed model artifacts in a user-controlled durable model cache or re-download them.
- Persist experiment outputs externally only after the durable run-store milestone is implemented.
- Stop Studio and tunnel processes when finished.

Do not treat Google Drive mounting as a substitute for a transactional experiment database.

## 7. Reproducibility

The notebook checks out an explicit Git commit. For published experiments, also record:
- TaaS commit SHA.
- Python and dependency versions.
- Actual GPU model/VRAM reported by `nvidia-smi`.
- Model name/revision, quantization, precision and inference server version (if enabled).
- ModelProfile and policy hashes.
- Tool registry snapshot/hash and GoalSpec.
- Seed, sampling parameters and prompt version for model calls.
- Colab runtime timestamps and any restart/reconnect event.

Do not publish a result as GPU-accelerated without verifying the model process actually used CUDA.

## 8. Security constraints

- Never bind an unauthenticated service to `0.0.0.0`.
- Do not use public quick-tunnel URLs for sensitive work.
- Use a named tunnel with a restrictive Access policy for team sharing.
- Retain application bearer-token authentication for discovery requests.
- Restrict outbound MCP access to an explicit server allowlist when execution is added.
- Do not execute arbitrary server code inside the notebook process.
- Treat MCP metadata as declarations rather than proof of tool behavior.
- Redact credentials, authorization headers, sensitive tool arguments and outputs from logs.
- Do not load unreviewed notebooks or packages into a runtime containing credentials.

## 9. Deployment acceptance gates

A Colab deployment can be called ready for interactive discovery when:
- [ ] A clean T4 runtime checks out the pinned commit.
- [ ] Dependencies install successfully.
- [ ] `nvidia-smi` reports the allocated GPU (or notebook clearly falls back to CPU).
- [ ] Studio imports and starts without errors.
- [ ] `/health`, `/ready` and browser `/` respond.
- [ ] Discovery API rejects requests with missing/invalid bearer tokens.
- [ ] A valid GoalSpec/tool fixture returns a discovery decision.
- [ ] Browser UI displays that decision and does not claim tool execution.
- [ ] Colab port proxy opens for the notebook owner.
- [ ] Optional public endpoint is gated by a configured Cloudflare Access policy.
- [ ] Secrets are absent from notebook output and logs.
- [ ] Runtime shutdown behavior is tested.

A **full agent Studio** additionally requires Hugging Face model management, model-backed chat, agent orchestration, MCP execution, live trace stream, durable run persistence, user/workspace isolation and execution safety. Those are separate milestones.

## 10. Related materials

- Notebook: `notebooks/colab/taas_core_studio_colab.ipynb`
- API and browser UI: `src/taas/studio/`
- Quickstart: `docs/studio/API_QUICKSTART.md`
