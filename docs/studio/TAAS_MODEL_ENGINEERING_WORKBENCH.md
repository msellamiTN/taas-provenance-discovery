# TaaS Model Engineering Workbench

## Product intent

Model Studio is an engineering workflow, not merely a model-ID text field. The workbench connects public repository discovery, configuration inspection, artifact evidence, resource estimation, and the actual process-local model loader.

## Workflow

1. **Discover repositories** through the authenticated Hugging Face metadata search endpoint.
2. **Inspect a candidate** through the model detail endpoint. The selected repository's reported architecture, parameter count, license, gated status, Safetensors flag, and other available metadata are rendered as separate facts.
3. **Inspect artifacts** through the artifact metadata endpoint. File formats and backend candidates are displayed as repository evidence, not proof of runtime support.
4. **Estimate resources** using reported parameter count and the existing memory estimator. KV-cache inputs are sent only when all required architecture dimensions are reported. The estimator explicitly excludes activations and backend workspaces and does not guarantee loading.
5. **Promote selection to runtime** by copying the exact selected repository ID into the existing Model Runtime workspace.
6. **Load and infer** only through the existing authenticated model runtime endpoints. A successful metadata inspection never implies that weights are loaded.

## TaaS integration

The model workbench is one stage in the broader TaaS pipeline:

- The selected HF model can support agent chat and propose a canonical GoalSpec.
- GoalSpec structural validation checks the contract and dependency graph, but does not prove semantic correctness.
- The user reviews the proposal before it is applied to the discovery GoalSpec editor.
- TaaS discovery then evaluates registered tool contracts against the GoalSpec and policy.
- Assurance presents the pre-execution certificate, mandatory checks, bindings, gaps, and counterexamples.
- No tool execution is performed by this model workbench. A discovery certificate is not runtime proof or authorization to execute.

## Evidence and non-claims

| UI evidence | What it supports | What it does not support |
|---|---|---|
| Hugging Face search result | Repository metadata returned by the Hub API | Artifact availability at load time |
| Model detail | Reported config and parameter metadata | Successful loading or inference |
| Artifact inspection | File names, available sizes, format hints, backend candidates | GPU/kernel compatibility |
| Memory estimate | Approximate weights and optional KV cache under stated assumptions | Guaranteed fit or successful load |
| Runtime status | Actual process-local loaded model state | Remote Colab session control |
| Successful inference | A completed request on the current loaded runtime | Agent correctness or task fulfillment |

## Safety and operational boundaries

- Repository metadata and artifact inspection do not download weights.
- Model loading is an explicit user action in the API process.
- Remote repository code execution remains disabled by the model runtime.
- No HF token or Studio bearer token is inserted into browser storage by this workflow.
- Model repository IDs and metadata are displayed using DOM text nodes, not interpolated HTML.
- Memory estimation omits KV cache when the model configuration does not report all required dimensions.
- Search and inspection errors are displayed as errors; they do not create compatibility claims.

## Validation status

Static regression tests cover selectable model cards, detail/artifact/memory/load endpoint wiring, conditional KV-cache estimation, and non-claims. They must be executed in CI. Browser-level tests must additionally cover search, selection, detail failure, artifact inspection, resource estimation, navigation to Model Runtime, and mobile layout.


## Colab operator entry point

The maintained integrated Model & Agent Studio launcher is available in [Google Colab](https://colab.research.google.com/github/msellamiTN/taas-provenance-discovery/blob/feature/taas-model-engineering-workbench/notebooks/colab/taas_core_studio_colab.ipynb).

The notebook checks out the immutable application revision `4a3e4e460f2556f6556b1ef4736f991337cf32c2`, installs the `studio,hf` extras, binds Uvicorn to `0.0.0.0:8000` for Colab proxy access, and keeps health/readiness probes on loopback. It uses a runtime-generated bearer token and does not persist it in browser storage.

The notebook is an operator-run launch and API smoke test. GitHub Actions validates repository code and notebook structure; it does not establish that Colab ran, that a T4 was allocated, or that a model loaded and completed inference. Record those outcomes separately against the exact notebook-pinned revision.
