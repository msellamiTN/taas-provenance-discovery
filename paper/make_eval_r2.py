"""Figures and tables of the revised Experimental Evaluation section (paper/sections/eval_r2/*.tex).

Reads only frozen outputs: results/final/*.json (protocol series), results/revision_2/*.json (revision analyses),
data/processed and data/llm_records (registry and labels). Writes vector PDFs to paper/figures_r2/ and booktabs
tables to paper/tables_r2/. Usage: python paper/make_eval_r2.py [setup rq1 rq2 rq3 sec eff]
"""
from __future__ import annotations

import gzip
import json
import sys
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from matplotlib.ticker import FuncFormatter, LogLocator  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FIN, R2 = ROOT / "results" / "final", ROOT / "results" / "revision_2"
FIG, TAB = ROOT / "paper" / "figures_r2", ROOT / "paper" / "tables_r2"
FIG.mkdir(exist_ok=True)
TAB.mkdir(exist_ok=True)

# ------------------------------------------------------------------------------------------------ style
# Okabe-Ito palette (colour-blind safe); PaMCP is always vermillion, baselines blues/greens/greys.
C = {"pamcp": "#D55E00", "pamcp2": "#E69F00", "blue": "#0072B2", "sky": "#56B4E9", "green": "#009E73",
     "purple": "#CC79A7", "yellow": "#F0E442", "black": "#000000", "grey": "#7F7F7F", "light": "#BDBDBD"}
plt.rcParams.update({
    "font.family": "serif", "font.serif": ["TeX Gyre Termes", "STIXGeneral", "DejaVu Serif"],
    "mathtext.fontset": "stix", "font.size": 7, "axes.titlesize": 7, "axes.labelsize": 7, "xtick.labelsize": 6.5,
    "ytick.labelsize": 6.5, "legend.fontsize": 6, "legend.frameon": False, "axes.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
    "xtick.major.size": 2.5, "ytick.major.size": 2.5, "xtick.direction": "out", "ytick.direction": "out",
    "lines.linewidth": 1.0, "lines.markersize": 3.5, "errorbar.capsize": 1.5, "axes.titlepad": 3,
    "axes.labelpad": 2, "pdf.fonttype": 42, "savefig.dpi": 300, "figure.dpi": 150, "hatch.linewidth": 0.4})
PCT = FuncFormatter(lambda v, _: f"{100 * v:.0f}%")
COL1, COL2 = 3.5, 7.16      # IEEE column and page widths (inches)


def grid(ax, axis="y"):
    ax.grid(True, axis=axis, color="#E3E3E3", lw=0.5, zorder=0)
    ax.set_axisbelow(True)


def panel(ax, letter, title=""):
    ax.set_title(f"({letter}) {title}", loc="left", fontsize=7, fontweight="bold" if not title else "normal")


def save(fig, stem):
    fig.savefig(FIG / f"{stem}.pdf", bbox_inches="tight", pad_inches=0.02)
    fig.savefig(FIG / f"{stem}.png", bbox_inches="tight", pad_inches=0.02, dpi=200)
    plt.close(fig)
    print("figure", stem)


def load(path: Path):
    d = json.loads(path.read_text())
    return d.get("results", d)


def F(n):
    return load(FIN / f"{n}.json")


def X(n):
    return load(R2 / f"{n}.json")


def raw(path: Path):
    with gzip.open(path, "rt") as f:
        return [json.loads(x) for x in f if x.strip()]


def write_table(stem, body: str):
    (TAB / f"{stem}.tex").write_text(body)
    print("table", stem)


def pct(v, d=1):
    return "--" if v is None else f"{100 * v:.{d}f}"


def labels():
    ja = json.loads((ROOT / "data/llm_records/silver_labels.json").read_text())
    jb = {}
    for k in range(3):
        for x in (ROOT / f"data/llm_records/reference_labels_opus_part{k}.jsonl").read_text().splitlines():
            if x.strip():
                r = json.loads(x)
                jb[r["id"]] = r
    return ja, jb


def registry():
    return json.loads((ROOT / "data/processed/registry_merged.json").read_text())["registry"]


# ------------------------------------------------------------------------------------------------ 8.1 setup
def setup():
    reg = registry()
    ja, jb = labels()
    # ---- Figure: registry characterisation
    fig, axs = plt.subplots(1, 3, figsize=(COL2, 1.85), gridspec_kw={"width_ratios": [1.45, 1.0, 1.0]})
    ax = axs[0]
    by = {}
    for t in reg:
        by.setdefault(t["server"], set()).add(t["source"])
    cnt = Counter(t["server"] for t in reg)
    order = sorted(cnt, key=lambda s: (-cnt[s], s))
    cols = [C["blue"] if by[s] == {"LiveMCPTool"} else C["green"] if by[s] == {"MCPToolBench++"} else C["purple"]
            for s in order]
    ax.bar(range(len(order)), [cnt[s] for s in order], width=0.85, color=cols, lw=0)
    ax.set_yscale("log")
    ax.set_xlim(-1, len(order))
    ax.set_xticks([0, 19, 39, 59, 75], ["1", "20", "40", "60", "76"])
    ax.set_xlabel("server rank (by tools)")
    ax.set_ylabel("tools per server")
    hs = [Patch(color=C["blue"], label="LiveMCPTool"), Patch(color=C["green"], label="MCPToolBench++")]
    if C["purple"] in cols:
        hs.append(Patch(color=C["purple"], label="both sources"))
    ax.legend(handles=hs, loc="upper right", handlelength=1, ncol=1)
    grid(ax)
    med = int(np.median(list(cnt.values())))
    ax.axhline(med, color=C["grey"], lw=0.6, ls="--")
    ax.text(len(order) - 1, med * 1.08, f"median {med}", ha="right", va="bottom", fontsize=5.5, color=C["grey"])
    panel(ax, "a", f"{len(reg)} tools on {len(cnt)} servers")
    ax = axs[1]
    classes = ["read", "write", "delete", "exec", "egress", "session", "money"]
    ca = Counter(c for t in reg for c in {e.split("(")[0] for e in ja.get(t["id"], {}).get("effects", [])})
    cb = Counter(c.replace("egress_any", "egress") for t in reg for c in set(jb.get(t["id"], {}).get("classes", [])))
    y = np.arange(len(classes))
    ax.barh(y + 0.19, [ca[c] for c in classes], 0.38, color=C["sky"], label=r"$J_A$ (Sonnet)")
    ax.barh(y - 0.19, [cb[c] for c in classes], 0.38, color=C["blue"], label=r"$J_B$ (Opus, blind)")
    ax.set_yticks(y, classes)
    ax.invert_yaxis()
    ax.set_xscale("log")
    ax.set_xlim(1, 4000)
    ax.set_xlabel("tools with effect class")
    ax.legend(loc="lower right", handlelength=1)
    grid(ax, "x")
    panel(ax, "b", "effect classes")
    ax = axs[2]
    ro_b = {t["id"]: not ({"write", "delete", "exec", "money"} & set(jb.get(t["id"], {}).get("classes", []))
                         or jb.get(t["id"], {}).get("state")) for t in reg}
    groups = {"readOnlyHint\n= true": [], "other\nannotation": [], "no\nannotation": []}
    for t in reg:
        a = t.get("annotations") or {}
        k = "no\nannotation" if not a else "readOnlyHint\n= true" if a.get("readOnlyHint") is True else "other\nannotation"
        groups[k].append(ro_b[t["id"]])
    groups = {k: v for k, v in groups.items() if v}
    xs = np.arange(len(groups))
    safe = [sum(v) for v in groups.values()]
    unsafe = [len(v) - sum(v) for v in groups.values()]
    ax.bar(xs, safe, 0.6, color=C["light"], label=r"read-only ($J_B$)")
    ax.bar(xs, unsafe, 0.6, bottom=safe, color=C["pamcp"], label=r"not read-only ($J_B$)")
    for x, s, u in zip(xs, safe, unsafe):
        ax.text(x, s + u + 8, f"{u}/{s + u}", ha="center", va="bottom", fontsize=5.5)
    ax.set_xticks(xs, list(groups), fontsize=6)
    ax.set_ylabel("tools")
    ax.set_ylim(0, 640)
    ax.legend(loc="upper left", handlelength=1)
    grid(ax)
    panel(ax, "c", "declared annotations")
    fig.tight_layout(w_pad=0.9)
    save(fig, "fig_setup_registry")

    # ---- Figure: evidence map (claims x evidence class)
    cls = ["Formal", "Simulated", "Labelled", "Measured", "Observed", "Human-\nvalidated"]
    rows = [  # (claim, {class: 2 primary, 1 supporting}, not_measured)
        ("Annotation sparsity of the registries", {"Measured": 2}),
        ("Typing $\\tau$ and effect labels", {"Labelled": 2, "Observed": 1}),
        ("Model profile $\\rho_{\\mathrm{LLM}}$ (3 models, 432 items)", {"Measured": 2}),
        ("Model-conditioned gap and toolkit size", {"Formal": 1, "Measured": 2}),
        ("Soundness of eligibility (Prop. 1)", {"Formal": 2}),
        ("Exposure under forged / imperfect evidence", {"Simulated": 2, "Labelled": 1}),
        ("Labels vs. executed reference servers", {"Observed": 2, "Labelled": 1}),
        ("Single-tool retrieval quality", {"Measured": 2}),
        ("Toolkit recall and size", {"Measured": 2}),
        ("Joint feasibility and certification", {"Formal": 1, "Labelled": 2, "Measured": 1}),
        ("Injection reachability; manifest leakage", {"Labelled": 2, "Measured": 1}),
        ("Mechanism contributions ($2^3$ design)", {"Labelled": 1, "Measured": 2}),
        ("Scalability and pair-relation modes", {"Simulated": 1, "Measured": 2}),
        ("Optimality (ILP) and QoS trade-offs", {"Simulated": 1, "Measured": 2}),
        ("Evolution, rug pulls, definition drift", {"Measured": 2, "Observed": 1}),
        ("Repair and experience reuse", {"Measured": 2}),
        ("End-to-end task success", {}),
        ("Human-validated contracts and effects", {}),
    ]
    fig, ax = plt.subplots(figsize=(COL1, 2.75))
    for i, (claim, m) in enumerate(rows):
        if not m:
            ax.axhspan(i - 0.5, i + 0.5, color="#F4F4F4", lw=0, zorder=0)
            ax.text((len(cls) - 1) / 2, i, "not measured in this study", ha="center", va="center", fontsize=6,
                    color=C["pamcp"], style="italic")
            continue
        for j, c in enumerate(cls):
            v = m.get(c.replace("-\n", "-"), 0)
            if v == 2:
                ax.scatter(j, i, s=30, color=C["blue"], zorder=3)
            elif v == 1:
                ax.scatter(j, i, s=30, facecolor="white", edgecolor=C["blue"], lw=0.8, zorder=3)
            else:
                ax.scatter(j, i, s=3, color="#CFCFCF", zorder=2)
    ax.set_yticks(range(len(rows)), [r[0] for r in rows], fontsize=6)
    ax.set_xticks(range(len(cls)), cls, fontsize=6)
    ax.xaxis.tick_top()
    ax.set_xlim(-0.5, len(cls) - 0.5)
    ax.set_ylim(len(rows) - 0.5, -0.5)
    for s in ("left", "bottom"):
        ax.spines[s].set_visible(False)
    ax.tick_params(length=0)
    ax.legend(handles=[Line2D([], [], marker="o", ls="", color=C["blue"], label="primary evidence"),
                       Line2D([], [], marker="o", ls="", mfc="white", mec=C["blue"], label="supporting evidence")],
              loc="upper center", bbox_to_anchor=(0.3, -0.01), ncol=2, handletextpad=0.2)
    save(fig, "fig_setup_evidence")


if __name__ == "__main__":
    which = sys.argv[1:] or ["setup", "rq1", "rq2", "rq3", "sec", "eff"]
    for w in which:
        globals()[w]()
