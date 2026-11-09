# Reproducing every experiment, figure and table — guide for reviewers

This guide covers the whole experimental pipeline behind Section 8 of the manuscript: the protocol series
(E1–E22), the analyses added for the TSC revision (Revision 2), the runtime probe of MCP reference servers, and
the generation of the figures, tables and section text. Everything runs on a CPU; no GPU and no API key are
needed, because every LLM output used by the experiments was recorded once and is replayed.

Branch: `research/pamcp-final-evaluation` · Colab notebook (no installation):
[`notebooks/colab/pamcp_evaluation_reviewers.ipynb`](../notebooks/colab/pamcp_evaluation_reviewers.ipynb)
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/msellamiTN/taas-provenance-discovery/blob/research/pamcp-final-evaluation/notebooks/colab/pamcp_evaluation_reviewers.ipynb)

## 1. Environment

The reported results were produced on Linux x86_64 with two virtual CPUs and 7 GB of RAM.

| Component | Version used | Needed for |
|---|---|---|
| Python | 3.13.18 | everything |
| numpy, scipy, scikit-learn, matplotlib | 2.5.3, 1.18.1, 1.9.1, 3.11.2 | everything (`requirements-lock.txt`) |
| pytest, hypothesis | 9.1.1, 6.170.15 | unit tests (117 tests) |
| pillow, python-docx, python-pptx, openpyxl, reportlab | see `requirements-lock.txt` | runtime probe only (seed files) |
| Node.js (npx), uv (uvx), strace, git | 22.23.4, 0.11.32, 6.8 | runtime probe only |
| LaTeX (pdflatex, latexmk, booktabs) | TeX Live 2023 | section preview only |

```bash
git clone -b research/pamcp-final-evaluation https://github.com/msellamiTN/taas-provenance-discovery.git
cd taas-provenance-discovery
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-lock.txt      # exact versions; requirements.txt gives minimum versions
pip install -e .                          # the taas library (src/taas)
python -m pytest -q                       # 117 tests, a few minutes
```

Older versions of the libraries run the code but may change the last digits of some floating-point results; the
comparison scripts report such differences as "close". Set `PYTHONHASHSEED=0` (the runners do) — results do not
depend on it, but it keeps logs identical.

## 2. Inputs (frozen, hash-checked)

| Input | Location | Origin |
|---|---|---|
| Merged registry (569 tools, 76 servers), tasks, type vocabulary | `data/processed/` | LiveMCPBench @ `36a51a1`, MCPToolBench++ @ `2bd35e5` (`scripts/fetch_data.sh`) |
| LiveMCPBench server launch configuration | `data/raw/livemcpbench/all_config.json` | LiveMCPBench @ `36a51a1` (Apache-2.0) |
| LLM labels J_A (Sonnet) and J_B (Opus, blind) | `data/llm_records/silver_labels.json`, `reference_labels_opus_part*.jsonl` | recorded once |
| Analyst goal contracts, MCP-Zero requests, COLT queries, ToolScope judgements | `data/llm_records/` | recorded once |
| Calibration suite (432 items) and answers of Haiku, Sonnet, Opus | `data/llm_inputs/r2_calibration/`, `data/llm_records/r2_calibration/` | generated / answered by reading only |
| Runtime probe records of the six MCP reference servers | `data/x2_probe/` | executed 2026-11-08 |

Every result file in `results/` carries a manifest: run id, commit, SHA-256 of the code, of every input file and of
the label and LLM-record files, and the package versions. The notebook's Step 1 re-checks the input hashes.

## 3. Protocol series E1–E22 (`experiments/final/`)

```bash
python experiments/final/run_all.py --list                       # steps with measured minutes
python experiments/final/run_all.py --all --e15-max-n 10000 --out results/reproduced
python experiments/final/compare_results.py results/reproduced   # -> results/reproduced/comparison.md
```

| Step | Script | Output (`results/final/`) |
|---|---|---|
| E1–E3 registry, typing, declared effects | `e01_e03_registry_typing_effects.py` | `E1_registry`, `E2_typing`, `E3_effects` |
| E4–E7 eligibility, forgery, verifier, trust | `e04_e07_exposure.py`, `e04_admitted.py` | `E4_*`, `E5_forgery`, `E6_verifier`, `E7_trust` |
| E8 single-tool retrieval and diagnosis | `e08_single_tool.py`, `e08_diagnostic.py` | `E8_single_tool`, `E8_diagnostic` |
| E9–E10 toolkits and joint feasibility | `e09_e10_sets.py`, `set_evaluator.py` | `E9_sets`, `E10_validity` |
| E11–E12 gap and model profile | `e11_e12_profile.py` | `E11_gap`, `E12_profile` |
| E14, E18 injection reachability, 2^3 factorial | `e14_e18_factorial.py` | `E14_injection`, `E18_factorial` |
| E15–E16 scalability, optimality, evolution | `e15_e16_scale_evolution.py` | `E15_*`, `E16_evolution` |
| E17, E20 refinement, sensitivity | `e17_e20_refine_sensitivity.py` (`--split test`) | `E17_*`, `E20_*` |
| E22 resampling, split stability, F1–F7 | `e22_statistics.py` | `E22_statistics` |

The full E15 run at 100,000 tools spends about 37 minutes building the engine in eager mode; `--e15-max-n 10000`
stops at 10,000 tools. `run_all.py --list` prints the measured minutes of every step.

## 4. Revision 2 analyses (`experiments/revision_2/`)

```bash
python experiments/revision_2/run_r2.py --list
python experiments/revision_2/run_r2.py --out results/reproduced_r2             # default steps, about 1 hour
python experiments/revision_2/run_r2.py --only label_swap,family,x6_x13,figures  # a few minutes
python experiments/final/compare_results.py results/reproduced_r2 --reference results/revision_2
```

| Step | Script | Output (`results/revision_2/`) | Paper |
|---|---|---|---|
| `label_swap` | `r2_label_swap.py` | `R2_label_swap` | 8.3, label independence |
| `evaluator_audit` | `r2_evaluator_audit.py` | `R2_evaluator_audit` (10 hand-built cases, strict re-scoring) | 8.4 |
| `x3_dev`, `x3_test` | `r2_x3_retrieval.py dev / test` | `R2_X3_dev`, `R2_X3_test` (tuned baselines, 13 variants, oracles) | 8.4 |
| `v2_select`, `v2_eval` | `r2_v2_select.py`, `r2_v2_eval.py` | `R2_v2_selection`, `R2_v2_eval` (PaMCP-L, scope-aware attacks) | 8.4, 8.5 |
| `family` | `r2_family.py` | `R2_family` (H1–H5, Holm) | 8.6 |
| `x6_x13` | `r2_x6_x13_composition.py` | `R2_X6_X13_composition` (ILP optima, QoS Pareto) | 8.6 |
| `reuse` | `r2_e21_reuse.py` | `R2_E21_reuse` (reuse with revalidation probes) | 8.6 |
| `calibration` | `r2_x2_calibration_score.py` | `R2_X2_calibration` (+ `data/processed/profile_*_r2.json`) | 8.2 |
| `x7` (optional, ~90 min; `--quick-x7`) | `r2_x7_scale.py` | `R2_X7_scale` (pair modes, heterogeneous registries) | 8.6 |
| `probe`, `probe_run`, `probe_analyse` (optional) | `r2_x2_probe.py`, `r2_x2_analyse.py` | `R2_X2_observed` | 8.3 |
| `figures` | `paper/make_eval_r2.py` | `<out>/paper/figures_r2`, `<out>/paper/tables_r2` | all of 8 |

The development/test separation is enforced by the scripts: every configuration (PaMCP variant, baseline grid) is
chosen on the 60 development requests (`R2_X3_dev`) before the test run reads `R2_X3_test`; the confirmatory family
H1–H5 is fixed in `docs/PREREGISTRATION_AMENDMENT_R2.md` (committed before the test runs). The calibration items
and their gold answers are regenerated deterministically by `r2_x2_calibration_items.py`; re-running it is not
needed and would overwrite the committed inputs.

A step whose inputs come from another step that was not run in the same output directory receives them from the
reference and the run log (`<out>/run_log.json`) lists them as `copied_from_reference`; the comparison skips those
files. Expected outcome: identical results for every deterministic step (verified on 2026-11-09 for `label_swap`,
`evaluator_audit`, `family`, `x6_x13` and `calibration`: all leaves identical).

## 5. Runtime probe of the MCP reference servers

```bash
sudo apt-get install -y strace nodejs npm && pip install uv   # or use your distribution's packages
python experiments/revision_2/run_r2.py --out results/reproduced_r2 --only probe,probe_run,probe_analyse
```

The probe starts the six servers maintained by the modelcontextprotocol organisation (filesystem, git, memory,
time, sequential-thinking, fetch) with their published launch commands, in a temporary sandbox
(`PAMCP_PROBE_DIR`, default the system temp directory; `HOME`, working directory and `TMPDIR` are redirected into
it, the filesystem server is rooted in it). Each registry tool is called once with schema-derived arguments under
`strace -f`, and the sandbox is snapshotted before and after the call. Records go to `<out>/x2_probe/`
(`PAMCP_PROBE_RECORDS`), never to `data/x2_probe/`. Servers are fetched at their current versions, so tool
definitions and some calls will differ from the reference run; the classification code and the comparison with
the labels are the same. Third-party servers (for example those that execute shell commands) are deliberately not
probed by this script; probing them should be done in a disposable virtual machine.

## 6. Figures, tables and the section text

```bash
python paper/make_eval_r2.py                    # 16 figures (PDF+PNG) -> paper/figures_r2, 9 tables -> paper/tables_r2
cd paper && latexmk -pdf evaluation_r2_preview.tex   # preview of Section 8, pp. 13-24
```

`make_eval_r2.py` reads only frozen result files (`PAMCP_FINAL_RESULTS`, `PAMCP_R2_RESULTS`) and writes to
`PAMCP_PAPER_OUT` (default `paper/`); `run_r2.py --only figures` renders them from a reviewer's re-run instead.
The section is `paper/sections/evaluation_r2.tex` with one file per subsection in `paper/sections/eval_r2/`;
the three descriptive tables (data, methods, parameters) are written in `s1_setup.tex`, the nine result tables are
generated. Figures of the protocol-era section: `experiments/final/paper_figures_final.py`, tables:
`paper/make_tables_final.py`, number check: `paper/check_numbers_final.py`.

| Figure | Function in `make_eval_r2.py` | Data |
|---|---|---|
| `fig_setup_evidence`, `fig_setup_registry` | `setup()` | registry, J_A, J_B |
| `fig_rq1_calibration`, `fig_rq1_profile`, `fig_rq1_typing` | `rq1()` | `R2_X2_calibration`, `E11_gap`, `E2_typing` |
| `fig_rq2_exposure`, `fig_rq2_trust`, `fig_rq2_observed` | `rq2()` | `E4`–`E7`, `R2_label_swap`, `R2_X2_observed` |
| `fig_rq3_retrieval`, `fig_rq3_sets` | `rq3()` | `R2_X3_*`, `E8`, `E9`, `E10`, `R2_evaluator_audit`, `R2_v2_eval` |
| `fig_sec_injection`, `fig_sec_factorial` | `sec()` | `E14`, `E18`, `R2_v2_eval` |
| `fig_eff_scale`, `fig_eff_opt`, `fig_eff_evolution` | `eff()` | `E15`, `R2_X7_scale`, `R2_X6_X13_composition`, `E16`, `E17`, `R2_E21_reuse` |

## 7. What cannot be re-run identically, and why

* **LLM outputs.** Labels, analyst goals, baseline inputs and calibration answers were produced once by Claude
  models through sub-agents of the build session and are replayed; the provider did not expose exact model
  version strings. `src/taas/llm/backends.py` regenerates analyst outputs live when `ANTHROPIC_API_KEY` is set, but
  new outputs will differ. One Opus calibration batch (45 items) was not answered (usage limit) and is excluded.
* **Live MCP servers** change between versions (all 37 reference-server definitions changed since the snapshot).
* **Timings** depend on the machine; the comparison scripts ignore timing fields.
* **Not run in this study:** executed end-to-end compositions, adversarial third-party servers, LLM-proposed
  repairs, human annotation, faithful baselines with their original encoders (see Section 8.7).

## 8. Where results are

`results/final/` (protocol series), `results/revision_2/` (revision analyses), per-item records in
`results/*/raw/*.jsonl.gz`, findings in `docs/FINAL_EVALUATION.md` and `docs/REVISION_2_PROGRESS.md`, the revision
plan in `docs/REVISION_PLAN_TSC.md`.
