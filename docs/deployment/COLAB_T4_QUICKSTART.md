# TaaS Core Studio on Google Colab T4 — step-by-step guide

This guide is the operator runbook for launching the **TaaS Studio application inside the Colab VM**. Follow it each time you create a fresh Colab runtime.

> **Current milestone boundary:** this is the discovery workspace (GoalSpec + tool metadata → TaaS discovery decision). It is not yet a full agent runtime: it does not invoke MCP tools, execute an agent loop, stream live execution events, or persist run history in a database.

## 1. Open the notebook

Open [`taas_core_studio_colab.ipynb`](../../notebooks/colab/taas_core_studio_colab.ipynb) in Google Colab. Use **File → Save a copy in Drive** if you want your own working copy. The source notebook is versioned in the TaaS GitHub repository; your Colab copy is not automatically synchronized with later repository updates.

## 2. Allocate a T4 runtime

1. In Colab, select **Runtime → Change runtime type**.
2. Choose **T4 GPU** under Hardware accelerator, if available to your account.
3. Save and reconnect/restart the runtime.
4. Run notebook Step 1 (checkout) and Step 2 (GPU check).
5. Confirm that `nvidia-smi` reports an NVIDIA Tesla T4. If no GPU is allocated, the Studio API/UI can still run on CPU, but GPU-backed model inference is unavailable.

Colab GPU availability, quotas, idle timeout and maximum session duration depend on the Colab account and service conditions.

## 3. Configure Colab Secrets

Open the Colab **Secrets** panel (key icon) and add:

| Secret | Required? | Purpose |
|---|---:|---|
| `TAAS_STUDIO_API_TOKEN` | Yes | Bearer token for discovery API calls; use a long random value |
| `CF_TUNNEL_TOKEN` | No | Only for a preconfigured named Cloudflare Tunnel |
| Model provider key(s) | Depends on ModelProfile | Credentials for a remote model provider, if selected |

Grant the notebook access to each secret it needs. Do not hardcode secrets into cells, notebook metadata, Git, uploaded JSON, or screenshots.

## 4. Prepare a ModelProfile

The current discovery API requires a valid TaaS ModelProfile file through `TAAS_MODEL_PROFILE`.

1. Use a ModelProfile example/schema from this repository as the starting point.
2. Configure the model/provider fields required by the existing `ModelProfile.load` implementation.
3. Keep provider credentials in Colab Secrets or the environment; do not place secret values in the JSON.
4. Validate the profile locally against the repository implementation before uploading.
5. When prompted by notebook Step 4, upload exactly one reviewed JSON profile.

If you do not yet have a valid profile, stop here. Do not guess its schema: inspect `src/taas/model_profile.py` and existing profile fixtures/examples first.

## 5. Install the Studio

Run notebook Step 3. It installs the repository's `studio` optional dependencies in editable mode and imports `taas.studio.api`.

Expected success message: `Studio imports OK`.

If installation fails:
- Read the first package/build error rather than only the final pip summary.
- Restart the runtime and rerun from Step 1.
- Confirm the Colab Python version satisfies `pyproject.toml` (`>=3.10`).
- Do not randomly upgrade NumPy/SciPy independently of the repository constraints.

## 6. Start the Studio web application

Run notebook Step 6. It starts Uvicorn inside the Colab VM, bound to `127.0.0.1:8000`, and checks:
- `GET /health`
- `GET /` (browser UI)

The app must remain running while you use the browser. The API's `/ready` endpoint also checks that the API token and ModelProfile environment variables are configured.

## 7. Open the browser UI

Run notebook Step 7 and click **Open TaaS Core Studio**. This uses Colab's notebook port proxy. The URL is associated with the active notebook/runtime session; it is not a permanent deployment URL.

In the UI:
1. Paste the `TAAS_STUDIO_API_TOKEN` into the password field.
2. Review the sample JSON request.
3. Replace the example GoalSpec and tool metadata with your own test fixture.
4. Click **Run TaaS discovery**.
5. Inspect selected tools, abstention status, coverage gap, discovery latency, certificate and full API response.
6. Remember that `execution_performed: false` means no MCP tool was invoked.

Use only trusted metadata and synthetic/non-sensitive examples during this milestone.

## 8. Optional team sharing

For a team-accessible URL, configure a **named Cloudflare Tunnel** and a **Cloudflare Access application/policy** before enabling the optional notebook cell:

1. Create a named tunnel in Cloudflare Zero Trust.
2. Configure a public hostname and route it to `http://127.0.0.1:8000`.
3. Create an Access application for that hostname.
4. Add a restrictive allow policy for the intended users/groups.
5. Store the tunnel token in Colab Secrets as `CF_TUNNEL_TOKEN`.
6. Set `enable_cf = True` in the optional cell.
7. Verify the hostname prompts for Access authentication from a separate browser/session before sharing it.

**Do not use an unauthenticated quick tunnel.** Tunnel connectivity is not identity authorization. The entire hostname (including `/`, `/health`, and API routes) must be protected by the Access policy. Keep the API bearer token enabled as a second layer.

## 9. T4 model inference (optional, not yet wired as a turnkey backend)

The current TaaS discovery core is CPU-oriented. A T4 only accelerates a model component if an actual CUDA-capable model server is installed, started, and used by a configured TaaS provider adapter.

This notebook does not automatically download or launch an LLM. Before adding one:
- Select a quantized model that fits the T4's available VRAM.
- Pin the model revision and serving stack.
- Verify CUDA is used by the model process (not merely that `nvidia-smi` works).
- Configure the provider adapter and ModelProfile to target the local model endpoint.
- Benchmark latency, memory use and output quality against a remote model.
- Record model revision, quantization, GPU type and serving parameters in the experiment manifest.

Do not report TaaS as GPU-accelerated until this is implemented and measured.

## 10. Stop and reset

Run the final notebook cell to stop the Studio and optional tunnel processes. When finished:
- Do not assume files in `/content` survive runtime termination.
- Do not store durable experiment records only in Colab local storage.
- Remove uploaded sensitive files from the runtime if any were used.
- Revoke/rotate credentials if a notebook or runtime was shared unintentionally.

## Troubleshooting

| Symptom | Checks / remedy |
|---|---|
| `nvidia-smi` not found or no GPU | Change runtime type to T4 GPU if available; reconnect and rerun hardware check |
| Git checkout fails | Check repository access/network and pinned commit; retry from a clean runtime |
| `pip install -e .[studio]` fails | Inspect first pip error; verify Python >=3.10; restart and retry |
| API exits immediately | Inspect `/content/taas-studio.log`; verify dependencies and port 8000 availability |
| `/ready` returns 503 | Confirm API token Secret and uploaded ModelProfile path are set in the same runtime |
| UI loads but discovery returns 401 | Paste the exact API token in the UI; confirm the secret was loaded |
| Discovery returns 503 for profile | Validate ModelProfile schema with `src/taas/model_profile.py` and fixture files |
| Discovery returns 422 | Validate GoalSpec, policy and engine keys against the TaaS core interfaces |
| Colab proxy link fails | Confirm runtime is connected, rerun Step 7, and check `/health` |
| Public hostname is reachable without Access login | Disable the tunnel immediately; correct Cloudflare Access application/policy before sharing |

## 11. What is required before calling this a full TaaS Studio

The next product increments are: (1) validated model/agent configuration and local inference integration, (2) explicit MCP server registration and sandboxed invocation, (3) observable event stream, (4) durable experiment/run store, and (5) benchmark-native execution adapters. Each increment needs automated tests and a fresh Colab T4 smoke test before it is described as working.
