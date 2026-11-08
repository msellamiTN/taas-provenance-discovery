"""Regenerate all final-evaluation figures and add Revision 1 audit figures.

Inputs: results/revision_1 JSONs. Baseline JSONs are copied from results/final.
Outputs: results/revision_1/figures (PNG and PDF), FIGURE_INDEX.md, plot_run.json.

The E14 figure is replaced by the scope-aware offline re-analysis. No figure is
presented as an executed attack or an end-to-end runtime result.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "final"))
sys.path.insert(1, str(ROOT / "experiments"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import fe
import plots_final as base_plots
import paper_figures_final as paper_plots

OUT = Path(os.environ.get("PAMCP_RESULTS_DIR", ROOT / "results" / "revision_1"))
FIG = OUT / "figures"
FIG.mkdir(parents=True, exist_ok=True)

STANDARD_STEMS = [
    "E1_categories", "E2_typing_f1", "E4_exposure_utility", "E4_coverage",
    "E5_forgery", "E6_verifier", "E7_trust_pareto", "E8_forest",
    "E8_distractors", "E9_group_recall", "E10_checks", "E12_calibration",
    "E11_gap", "E14_injection", "E18_shapley", "E15_latency", "E17_refinement",
]
PAPER_STEMS = [
    "paper_eligibility", "paper_retrieval", "paper_profile_gap",
    "paper_factorial", "paper_scalability",
]


def load_json(name: str) -> dict:
    path = OUT / name
    if not path.exists():
        raise FileNotFoundError(f"Required Revision 1 result missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_figure(fig, stem: str) -> None:
    for ext in ("png", "pdf"):
        fig.savefig(FIG / f"{stem}.{ext}", bbox_inches="tight", pad_inches=0.04)
    plt.close(fig)


def figure_label_overlap() -> str:
    d = load_json("label_overlap_audit.json")
    labels = ["Unsafe under A", "Unsafe under B", "A intersect B", "B not in A"]
    vals = [
        int(d["unsafe_A"]), int(d["unsafe_B"]), int(d["intersection"]),
        len(d["B_unsafe_not_in_A"]),
    ]
    colors = [base_plots.S[0], base_plots.S[1], base_plots.S[2], base_plots.S[3]]
    fig, ax = plt.subplots(figsize=(4.8, 2.6))
    y = np.arange(len(labels))
    ax.barh(y, vals, color=colors, height=0.58)
    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    ax.set_xlabel("Tools (common labelled universe)")
    ax.set_title("Revision 1 — JA/JB unsafe-set audit")
    ax.text(
        0.99, 0.96,
        f"common tools: {d['n_common_tools']}\nB subset A: {d['B_unsafe_subset_A_unsafe']}\n"
        f"binary kappa: {d['cohen_kappa_binary_unsafe']:.3f}",
        transform=ax.transAxes, ha="right", va="top", fontsize=7,
        bbox={"boxstyle": "round,pad=0.3", "facecolor": "white", "edgecolor": "0.8"},
    )
    base_plots.grid(ax, "x")
    save_figure(fig, "revision1_label_overlap")
    return (
        "Machine-label audit only, not human ground truth. If B-unsafe is a subset of A-unsafe, "
        "an ideal simulated verifier based on A cannot admit a B-unsafe tool; this is construction-dependent."
    )


def figure_sanitiser() -> str:
    d = load_json("sanitiser_audit.json")
    c = d["counts"]
    labels = ["Description", "Tool name", "Argument key"]
    current = [
        c["current_description_canary_leaks"],
        c["current_tool_name_canary_leaks"],
        c["current_argument_key_canary_leaks"],
    ]
    alias = [c["alias_manifest_canary_leaks"]] * 3
    x = np.arange(3)
    width = 0.34
    fig, ax = plt.subplots(figsize=(4.8, 2.6))
    ax.bar(x - width / 2, current, width, label="Current sanitizer", color=base_plots.S[1])
    ax.bar(x + width / 2, alias, width, label="Alias-manifest prototype", color=base_plots.S[0])
    ax.set_xticks(x, labels)
    ax.set_ylabel("Canary leaks / tested tools")
    ax.set_title("Revision 1 — manifest field canary audit")
    ax.legend(fontsize=7)
    ax.set_ylim(bottom=0)
    base_plots.grid(ax, "y")
    save_figure(fig, "revision1_manifest_canaries")
    return (
        "Transformation-level canary test, not an agent or runtime attack experiment. "
        "The alias manifest is a prototype; the adapter and execution path are not validated here."
    )


def figure_e14_scope_aware() -> str:
    d = load_json("E14_scope_aware.json")
    summary = d["summary"]
    chosen = [
        ("least_privilege|Full_PaMCP", "PaMCP"),
        ("least_privilege|PaMCP_NoCert", "PaMCP NoCert"),
        ("least_privilege|per_subtask|eligible", "Per-subtask eligible"),
        ("least_privilege|per_subtask|unfiltered", "Per-subtask unfiltered"),
        ("least_privilege|rag_mcp@5|unfiltered", "RAG-MCP top-5"),
        ("least_privilege|mcp_zero|unfiltered", "MCP-Zero"),
    ]
    chosen = [(key, label) for key, label in chosen if key in summary]
    if not chosen:
        raise ValueError("No expected methods found in E14_scope_aware.json")
    labels = [label for _, label in chosen][::-1]
    data = [summary[key] for key, _ in chosen][::-1]
    y = np.arange(len(data))
    h = 0.22
    fig, ax = plt.subplots(figsize=(6.2, 3.1))
    series = (
        ("definite_oos_task_rate", "Definite out-of-scope", base_plots.S[0]),
        ("indeterminate_task_rate", "Indeterminate scope", base_plots.S[1]),
        ("conservative_possible_oos_task_rate", "Possible (definite or indeterminate)", base_plots.S[2]),
    )
    for offset, (metric, label, color) in enumerate(series):
        values = [float(row[metric]) for row in data]
        ax.barh(y + (offset - 1) * h, values, h, label=label, color=color)
    ax.set_yticks(y, labels)
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(base_plots.PCT)
    ax.set_xlabel("Share of tasks")
    ax.set_title("E14 Revision 1 — scope-aware offline reachability")
    ax.legend(fontsize=6.5, loc="lower right")
    base_plots.grid(ax, "x")
    fig.text(
        0.01, 0.01,
        "Attacks are nested within task. Labels B are LLM-generated; no action was executed. "
        "Indeterminate bars overlap definite violations.",
        fontsize=6, color=base_plots.INK2,
    )
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    save_figure(fig, "E14_injection")
    return (
        "Revision 1 offline re-analysis using task-level outcomes and all five attack classes. "
        "Definite violations and indeterminate scope cases are separate; conservative possible exposure "
        "is their union. LLM labels are not human ground truth and attacks were not executed."
    )


def main() -> None:
    os.environ.setdefault("MPLBACKEND", "Agg")
    base_plots.main()

    for fn in (
        paper_plots.eligibility,
        paper_plots.retrieval,
        paper_plots.profile_gap,
        paper_plots.factorial,
        paper_plots.scalability,
    ):
        fn()

    captions = {
        "E14_injection": figure_e14_scope_aware(),
        "revision1_label_overlap": figure_label_overlap(),
        "revision1_manifest_canaries": figure_sanitiser(),
    }
    expected = STANDARD_STEMS + PAPER_STEMS + [
        "revision1_label_overlap", "revision1_manifest_canaries"
    ]
    missing = [
        f"{stem}.{ext}" for stem in expected for ext in ("png", "pdf")
        if not (FIG / f"{stem}.{ext}").exists()
    ]
    if missing:
        raise RuntimeError(f"Figure generation incomplete; missing: {missing}")

    existing = {stem: caption for stem, caption in base_plots.WRITTEN}
    existing.update(captions)
    lines = []
    for stem in STANDARD_STEMS:
        if stem in existing:
            lines.append(f"- {stem}: {existing[stem]}")
    for stem in PAPER_STEMS:
        lines.append(
            f"- {stem}: composite regenerated from committed final-evaluation JSONs; "
            "underlying evidence retains its original measured/labelled/simulated/synthetic status."
        )
    for stem in ("revision1_label_overlap", "revision1_manifest_canaries"):
        lines.append(f"- {stem}: {captions[stem]}")
    (FIG / "CAPTIONS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    index = [
        "# Revision 1 figure report",
        "",
        f"Generated UTC: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}",
        "",
        "## Provenance and interpretation",
        "",
        "- The standard and composite figures use committed results/final JSON inputs copied into results/revision_1 for isolated plotting.",
        "- E14 is replaced by the Revision 1 scope-aware offline re-analysis; the original class-level plot is not carried forward.",
        "- The additional audit figures use the Revision 1 machine-label and manifest-canary audit JSONs.",
        "- No figure represents a human annotation study, actual MCP attack execution, end-to-end task success, or measured QoS advantage.",
        "",
        "## Files",
        "",
        "| Figure | PNG | PDF |",
        "|---|---|---|",
    ]
    stems = STANDARD_STEMS + PAPER_STEMS + [
        "revision1_label_overlap", "revision1_manifest_canaries"
    ]
    for stem in stems:
        index.append(f"| {stem} | {stem}.png | {stem}.pdf |")
    (OUT / "FIGURE_INDEX.md").write_text("\n".join(index) + "\n", encoding="utf-8")

    manifests = {}
    for stem in stems:
        for ext in ("png", "pdf"):
            p = FIG / f"{stem}.{ext}"
            manifests[str(p.relative_to(ROOT))] = {
                "bytes": p.stat().st_size,
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            }
    report = {
        "status": "success",
        "figure_stems": stems,
        "figure_count": len(stems),
        "formats_per_figure": ["png", "pdf"],
        "files": manifests,
        "input_class": "committed final-evaluation JSONs plus Revision 1 offline audit JSONs",
        "runtime_execution": False,
        "human_ground_truth": False,
        "note": "E14 plot replaced by scope-aware Revision 1 analysis; all other base charts retain their original evidence class.",
    }
    (OUT / "plot_run.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "figures": report["figure_count"],
        "files": len(manifests),
        "output": str(FIG),
    }, indent=2))


if __name__ == "__main__":
    main()
