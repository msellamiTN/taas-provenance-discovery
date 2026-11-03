# Colab validation protocol for every pull request

**Rule:** a GitHub Actions pass is necessary but not sufficient. Every PR receives an explicit Colab validation record against its exact head SHA before it can be accepted. A PR is not marked Done while its applicable Colab gates are pending.

## 1. Validation levels

Each PR must be classified before execution:

| Level | Applies to | Required Colab evidence |
|---|---|---|
| C0 — Source/runtime integrity | Every PR | Fresh runtime, exact checkout SHA, Python/runtime inventory, dependency installation, import checks, no uncommitted source mutation |
| C1 — Regression | Every PR changing Python, tests, packaging, notebooks, or runtime configuration; also documentation-only PRs when they alter operator instructions | Targeted tests plus full `python -m pytest -q`; record pass/fail/skip counts |
| C2 — Product smoke | Any PR changing Studio/API/UI, discovery, model, agent, MCP, execution, or deployment behavior | Start the service, health/readiness, auth negative/positive checks, relevant API/UI acceptance checks |
| C3 — Hardware/model | PRs claiming GPU/model runtime behavior | Actual GPU inventory; explicit model load and inference; capture model/revision, device, precision, latency, peak memory, and errors |
| C4 — Notebook/operator | PRs changing Colab notebooks or launch instructions | Open the notebook from the PR head, run every cell top-to-bottom in a clean runtime, verify the app link, stop process, and retain notebook execution evidence |

A level may be marked N/A only with a short technical reason. Do not substitute CI, static notebook parsing, CPU fallback, or a GPU probe for a required live model load/inference test.

## 2. Reproducible per-PR procedure

1. Open the Colab notebook from the PR branch (not from `main`): `https://colab.research.google.com/github/msellamiTN/taas-provenance-discovery/blob/<PR_BRANCH>/notebooks/colab/taas_core_studio_colab.ipynb`.
2. Select a fresh runtime. Use T4 for C3 where available; record if Colab allocated another device or CPU.
3. Record PR number, branch, expected head SHA and timestamp.
4. In a setup cell, clone/fetch the repository and checkout the exact expected SHA. Assert `git rev-parse HEAD` equals it. Never validate a moving branch name alone.
5. Install the PR's declared extras using the repository's documented command. Record Python, pip, OS, torch, CUDA, Transformers and Safetensors versions as applicable.
6. Run the PR's targeted checks, then the full regression suite. Preserve full output and exit codes.
7. For product PRs, launch the app and run the relevant API/UI smoke checks. For model-runtime PRs, perform an actual load and inference; do not infer success from metadata or `nvidia-smi`.
8. Stop all processes. Save the executed notebook (`.ipynb`) and a concise machine-readable validation report containing PR number, exact SHA, runtime type, timestamps, commands, exit codes, test counts, hardware/model measurements, artifacts and limitations.
9. Add the evidence link and result to this tracker and the PR. If the SHA changes after validation, the result is invalidated and the new head must be rerun.

## 3. Current PR validation matrix

| PR | Scope | Required levels | Current Colab state |
|---|---|---|---|
| #20 Model Engineering Workbench | Studio/model UI and runtime implementation | C0, C1, C2, C3 | **Not run** — live model load/inference and Studio smoke remain unverified |
| #21 Colab launcher alignment | Notebook and launch configuration for PR #20 implementation | C0, C1, C2, C4; C3 for the integrated model runtime claim | **Not run** — notebook is structurally checked in CI only; actual clean Colab execution pending |
| #22 Engineering tracker | Documentation-only | C0, C1; C2/C3/C4 N/A with rationale | **Not run** |
| #23 Studio regression assertions | Test-only | C0, C1; C2/C3/C4 N/A because application code is unchanged | **Not run** |

Important distinction: the maintained notebook currently checks out the immutable PR #20 application commit `26900dece9b035ff52dee3dd465a3e01ebff3c3c`. When validating PR #21, open the notebook file from PR #21's branch so the launcher changes are exercised, while separately recording that the launched application code is the pinned PR #20 SHA.

## 4. Result vocabulary

- **PASS** — every applicable level passed on the exact PR head SHA with retained evidence.
- **PASS WITH LIMITATIONS** — all required checks passed, but an explicitly non-required optional check was unavailable; state the limitation.
- **FAIL** — a required check failed. Include the first failing cell/command and traceback.
- **BLOCKED** — the required Colab runtime, access, hardware, or model artifact was unavailable. This is not a pass.
- **NOT RUN** — no execution evidence exists.

Never report a PR as Colab-validated based only on a notebook link, static source inspection, GitHub Actions, or user intent.

## 5. Evidence template

For each PR, record:

- PR URL, branch, head SHA, base SHA
- Colab notebook URL and executed notebook artifact
- Runtime: Colab CPU/T4/other; Python, OS, GPU, VRAM, CUDA
- Start/end timestamps and runtime reconnects
- Install command and result
- Targeted and full test commands; passed/failed/skipped counts
- Service health/readiness, auth tests, relevant API/UI results
- Model ID/revision, actual device, precision, load duration, inference result, latency and peak memory (when C3 applies)
- Logs/artifact links, redaction confirmation, cleanup result
- Final PASS/FAIL/BLOCKED/NOT RUN decision and reviewer

Do not place API tokens, Hugging Face tokens, private tool arguments, or other secrets in the notebook output or evidence report.
