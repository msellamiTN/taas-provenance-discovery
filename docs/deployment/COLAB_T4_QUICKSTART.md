# TaaS Core Studio on Google Colab T4 — step-by-step guide

This is the operator runbook for launching the **TaaS discovery workspace inside the Colab VM**. Repeat it for each fresh runtime.

> **Scope:** this milestone accepts a GoalSpec and tool metadata and runs the TaaS discovery engine. It does not connect to an LLM provider, invoke MCP tools, execute an agent loop, stream live execution events, or persist run history.

## 1. Open the notebook

Open [the Colab notebook](../../notebooks/colab/taas_core_studio_colab.ipynb) in Google Colab. Use **File → Save a copy in Drive** for a personal working copy. A saved Colab copy is not automatically synchronized with later repository changes.

## 2. Allocate a T4 runtime

1. Select **Runtime → Change runtime type**.
2. Choose **T4 GPU** under Hardware accelerator, if available.
3. Save and reconnect/restart.
4. Run the notebook checkout and GPU-check cells.
5. Confirm that `nvidia-smi` reports an NVIDIA Tesla T4.

The Studio API and TaaS discovery core run on CPU. A visible T4 does not accelerate this discovery code; a CUDA model backend is not included in this milestone. Colab GPU availability and session limits depend on account/service conditions.

## 3. Configure Colab Secrets

Open the Colab **Secrets** panel and add:

| Secret | Required? | Purpose |
|---|---:|---|
| `TAAS_STUDIO_API_TOKEN` | Yes | Bearer token for discovery API calls |
| `CF_TUNNEL_TOKEN` | No | Only for a preconfigured named Cloudflare Tunnel |

Grant the notebook access to the required secret. Do not hardcode credentials in cells, JSON, Git, notebook metadata, logs, or screenshots. No LLM provider key is consumed by the current API.

## 4. Prepare the TaaS ModelProfile

The API's `TAAS_MODEL_PROFILE` setting is **not an LLM connection configuration**. It loads TaaS capability-calibration data used by the discovery engine: model identifier, threshold, strictness and per-class calibration measurements.

A deliberately conservative example is provided at [strict-empty.json](../../examples/model_profiles/strict-empty.json). It is syntactically valid but contains no measured classes. In strict mode, unknown capabilities receive `rho = 0`; this is useful for validating startup and fail-closed behavior, **not** for demonstrating successful model-native task coverage.

For a meaningful experiment:
1. Create a profile from actual, documented calibration observations for the intended model/version.
2. Populate per-class buckets with measured accuracy, sample counts, language coverage and provenance.
3. Do not invent measurements or copy the example's empty profile and label it calibrated.
4. Validate it with `ModelProfile.load(path)` before upload.
5. Upload the reviewed JSON when the notebook requests it.

See `src/taas/model_profile.py` for the exact schema and interpolation/strictness semantics. Provider URLs, inference credentials, temperature and generation settings belong to a future, separate model-provider configuration layer.

## 5. Install the Studio

Run the notebook installation cell. It installs the repository's `studio` optional dependencies in editable mode and imports `taas.studio.api`.

Expected message: `Studio imports OK`.

If installation fails, inspect the first package/build error, confirm the Python version meets `pyproject.toml`, restart the runtime and retry from checkout. Avoid arbitrary NumPy/SciPy upgrades.

## 6. Start the web application

Run the launch cell. Uvicorn binds to `127.0.0.1:8000`. The notebook checks `GET /health` and the browser page at `GET /`. The `/ready` endpoint checks that the API token and ModelProfile path are configured; it does not verify an LLM provider.

Keep the server process running while using the UI.

## 7. Open the browser UI

Run the proxy cell and click **Open TaaS Core Studio**. The URL belongs to the active Colab runtime/session and is not permanent.

1. Enter the `TAAS_STUDIO_API_TOKEN` in the password field.
2. Review the sample JSON.
3. Submit a synthetic GoalSpec and trusted tool metadata.
4. Click **Run TaaS discovery**.
5. Inspect selected tools, abstention, coverage gap, discovery time, certificate and response.
6. Confirm `execution_performed: false`: no MCP tool was invoked.

The bundled UI example is illustrative. Use request shapes accepted by the current TaaS GoalSpec parser and engine.

## 8. Optional team sharing

Only enable the optional tunnel cell after configuring a **named Cloudflare Tunnel** and a **Cloudflare Access application/policy**:
1. Create the named tunnel in Cloudflare Zero Trust.
2. Route a public hostname to `http://127.0.0.1:8000`.
3. Protect the entire hostname with an Access application and restrictive allow policy.
4. Store its tunnel token in Colab Secrets as `CF_TUNNEL_TOKEN`.
5. Enable the optional cell and verify authentication from a separate browser/session.

**Do not use an unauthenticated quick tunnel.** Tunnel connectivity is not user authentication. Keep the Studio bearer token enabled as a second layer.

## 9. Stop and reset

Run the notebook shutdown cell. Colab runtimes are ephemeral; files under `/content`, processes and RAM/VRAM state can disappear when the runtime ends. Do not treat this notebook as durable experiment storage. Rotate credentials if a notebook/runtime was unintentionally shared.

## Troubleshooting

| Symptom | Checks / remedy |
|---|---|
| No GPU / `nvidia-smi` unavailable | Re-select T4 if available, reconnect and rerun hardware check; CPU discovery remains possible |
| Git checkout fails | Check network/repository access and pinned revision |
| Editable install fails | Inspect first pip error, check Python version, restart and retry |
| API exits | Inspect `/content/taas-studio.log`; check dependencies and port 8000 |
| `/ready` returns 503 | Check API token Secret and uploaded ModelProfile path in this runtime |
| UI discovery returns 401 | Enter the exact API token in the UI |
| Profile returns 503 | Validate JSON using `ModelProfile.load`; check required `model_id`, `tau` and `classes` fields |
| Discovery returns 422 | Check GoalSpec, policy and engine fields against current core interfaces |
| Colab proxy fails | Confirm runtime is connected; rerun proxy cell and check `/health` |
| Public hostname bypasses Access | Disable tunnel immediately and fix Access policy before sharing |

## 10. What remains before this is a full agent Studio

The next increments are a distinct model-provider/agent configuration layer, explicit MCP server registration and sandboxed invocation, observable execution events, durable experiment storage, and benchmark-native execution adapters. Each requires implementation, automated tests, operator instructions and a live Colab smoke test before being described as operational.
