# TaaS Studio — Reviewer Guide

This package lets a reviewer run TaaS Studio on a Google Colab runtime and
walk the live UI in about ten minutes. Everything is real: the notebook
checks out a pinned commit, installs the project, launches one Studio
process, and exposes it through a fresh Colab proxy URL.

## Watch the walkthrough (~1:45)

[![TaaS Studio walkthrough](https://github.com/msellamiTN/taas-provenance-discovery/raw/main/docs/studio/reviewer/recording/taas-studio-full-walkthrough.mp4)](https://github.com/msellamiTN/taas-provenance-discovery/raw/main/docs/studio/reviewer/recording/taas-studio-full-walkthrough.mp4)

## What you need

- A Google account (Colab free tier is enough; a CPU runtime is fine)
- About 10 minutes

## Files

| File | Purpose |
|---|---|
| `notebooks/colab/taas_studio_reviewer_colab.ipynb` | Clean top-to-bottom reviewer notebook (19 cells) |
| `recording/taas-studio-full-walkthrough.mp4` | **End-to-end walkthrough (~1:45)** — Part 1: real Colab runtime (open notebook → connect → run all → proxy URL → token). Part 2: real Studio UI, 8 narrated lifecycle steps. All steps subtitled |
| `recording/colab.srt`, `recording/walkthrough-full.srt` | Subtitle tracks (Colab part; combined full video) |
| `recording/colab-frames/` | Source screenshots of the real Colab run used in Part 1 |
| `recording/taas-studio-step-by-step.mp4` | Studio-only recording (Part 2 of the full walkthrough) |
| `recording/walkthrough.srt` | Subtitle track for the Studio-only recording |
| `taas-studio-reviewer-tour.mp4` | 46-second captioned tour of the key surfaces |
| `notebooks/colab/taas_studio_acceptance_colab.ipynb` | Optional: automated A1–A6 acceptance matrix (29 checks) |
| `notebooks/colab/taas_core_studio_colab.ipynb` | Developer notebook with pytest batches and optional tunnel/Ollama cells |

The full walkthrough's Studio part was produced by
`scripts/record_studio_walkthrough.py`, which drives the live UI in headless
Chromium and emits the SRT aligned to the recording. Re-run it against any
reachable Studio to regenerate that segment; the Colab segment was captured
from a real Colab run of this notebook (screenshots in `recording/colab-frames/`).

## Steps

1. Open `taas_studio_reviewer_colab.ipynb` in Colab (**File → Upload notebook**
   if it is not already in your Drive).
2. **Runtime → Run all** (or run cells top to bottom). The notebook:
   - checks out the pinned commit,
   - installs `.[test,studio,hf]`,
   - writes a demo MCP server (`echo_message`, `add_numbers`) and its config,
   - generates an ephemeral API token (never committed, never shared),
   - launches `uvicorn taas.studio.api:app` on port 8000,
   - prints a fresh `https://8000-….colab.dev` proxy URL.
3. Copy the **API token** printed by the launch cell.
4. Open the proxy URL, paste the token into **Studio authentication → Connect**.
5. Walk the lifecycle navigation. The video shows the key surfaces.

## What to look at

- **MCP connections** — *Refresh configured servers*, then *Inspect server
  tools*. Inspection performs `tools/list` only; the UI states
  "Inspection completed. No tools/call request was made."
- **Discovery history** — persisted runs are analysis observations; the UI
  says they do not imply execution.
- **Audit timeline** — *Load audit records* then *Verify hash chain*.
  A valid chain is tamper evidence over recorded events — not proof of
  event truth, authorization, or execution.
- **Agent lifecycle** — draft → validated → published → signed are
  configuration states, not runtime states.
- **Environment overview** — runtime diagnostics report observed state
  only; a visible GPU is not proof a model is loaded.

## Boundaries (by design)

- `proposal ≠ evidence ≠ authorization ≠ execution`
- MCP inspection never invokes tools; governed `tools/call` is disabled.
- The Agent workspace does not run an autonomous tool-calling loop.
- Unsupported live data renders `UNAVAILABLE`, never fabricated demo data.
- No production auth, tenant isolation, streaming traces, or multi-user
  support in this build. Colab tokens are ephemeral.

## If something fails

- Studio log: `/content/taas-studio.log`
- Data dir: `/content/taas-data` (all SQLite stores live here)
- Re-running the launch cell is safe — it stops any previous Studio process.
- Colab proxy URLs expire when the runtime stops; re-run the proxy cell for
  a fresh URL.
