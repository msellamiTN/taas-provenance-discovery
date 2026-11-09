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


# ------------------------------------------------------------------------------------------------ 8.2 RQ1
MODELS = (("haiku", "Haiku"), ("sonnet", "Sonnet"), ("opus", "Opus"))
MCOL = {"haiku": C["green"], "sonnet": C["blue"], "opus": C["purple"]}
CLASSES = (("extract", "extract"), ("classify", "classify"), ("count", "count"), ("aggregate_sum", "sum (approx.)"),
           ("compute_exactly", "exact compute"), ("join", "join"))


def rq1():
    cal = X("R2_X2_calibration")
    # ---- Figure: accuracy by operation and input size, three models
    fig, axs = plt.subplots(1, 3, figsize=(COL2, 1.75), sharey=True)
    ns = ["10", "40", "160", "640"]
    for ax, (m, ml) in zip(axs, MODELS):
        r = cal[m]["by_class_n"]
        M = np.array([[r.get(f"{c}|{n}", np.nan) for n in ns] for c, _ in CLASSES])
        im = ax.imshow(M, cmap="cividis", vmin=0.3, vmax=1.0, aspect="auto")
        for i in range(M.shape[0]):
            for j in range(M.shape[1]):
                v = M[i, j]
                if v == v:
                    ax.text(j, i, f"{100 * v:.0f}", ha="center", va="center", fontsize=5.8,
                            color="black" if v > 0.7 else "white")
                else:
                    ax.add_patch(plt.Rectangle((j - 0.5, i - 0.5), 1, 1, facecolor="white", edgecolor="#BBBBBB",
                                               hatch="////", lw=0))
                    ax.text(j, i, "not run", ha="center", va="center", fontsize=5, color=C["grey"])
        ax.set_xticks(range(4), ns)
        ax.set_yticks(range(len(CLASSES)), [l for _, l in CLASSES])
        ax.set_xlabel("input size $n$")
        a = cal[m]
        panel(ax, "abc"[MODELS.index((m, ml))], f"{ml}: {100 * a['accuracy']:.1f}% of {a['items']} items")
        for s_ in ax.spines.values():
            s_.set_visible(False)
        ax.tick_params(length=0)
    cb = fig.colorbar(im, ax=axs, fraction=0.025, pad=0.01)
    cb.set_label("accuracy", fontsize=6)
    cb.ax.yaxis.set_major_formatter(PCT)
    cb.ax.tick_params(labelsize=5.5)
    cb.outline.set_linewidth(0.4)
    save(fig, "fig_rq1_calibration")

    # ---- Figure: self-assessment, selective risk, model-conditioned gap
    fig, axs = plt.subplots(1, 3, figsize=(COL2, 1.95), gridspec_kw={"width_ratios": [1, 1.15, 1.1]})
    ax = axs[0]
    for m, ml in MODELS:
        rel = cal[m]["self_assessment"]["reliability"]
        xs = [b["mean_conf"] for b in rel if b["n"]]
        ys = [b["accuracy"] for b in rel if b["n"]]
        ss = [8 + 0.5 * b["n"] for b in rel if b["n"]]
        ax.plot(xs, ys, color=MCOL[m], lw=0.8, alpha=0.8)
        ax.scatter(xs, ys, s=ss, color=MCOL[m], edgecolor="white", lw=0.4, zorder=3,
                   label=f"{ml} (ECE {cal[m]['self_assessment']['ece']:.2f})")
    ax.plot([0, 1], [0, 1], color=C["grey"], lw=0.6, ls="--")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.04)
    ax.set_xlabel("self-assessed P(correct)")
    ax.set_ylabel("observed accuracy")
    ax.xaxis.set_major_formatter(PCT)
    ax.yaxis.set_major_formatter(PCT)
    ax.legend(loc="lower right", handletextpad=0.1)
    grid(ax, "both")
    panel(ax, "a", "self-assessment (before items)")
    ax = axs[1]
    kinds = (("measured|exact_rule=True", "target=0.05", "o", "measured profile, risk 5%"),
             ("self_assessed|exact_rule=True", "target=0.05", "s", "self-assessed, risk 5%"),
             ("manuscript_64|exact_rule=True", "manuscript_tau=0.9", "^", "64-item profile, $\\tau$=0.9"))
    for m, ml in MODELS:
        for key, t, mk, lab in kinds:
            s_ = cal[m]["selection"].get(key)
            if not s_:
                continue
            te = s_[t]["test"]
            ax.scatter(te["coverage"], te["selective_risk"], marker=mk, s=26, color=MCOL[m], edgecolor="white",
                       lw=0.4, zorder=3)
    ax.axhline(0.05, color=C["pamcp"], lw=0.7, ls=":")
    ax.text(0.02, 0.053, "risk target 5%", fontsize=5.5, color=C["pamcp"], va="bottom")
    ax.set_xlim(0, 1.05)
    ax.set_ylim(-0.004, 0.1)
    ax.xaxis.set_major_formatter(PCT)
    ax.yaxis.set_major_formatter(PCT)
    ax.set_xlabel("coverage (operations kept native)")
    ax.set_ylabel("false-native rate (held-out)")
    hs = [Line2D([], [], marker=mk, ls="", color=C["grey"], label=lab) for _, _, mk, lab in kinds]
    hs += [Line2D([], [], marker="o", ls="", color=MCOL[m], label=ml) for m, ml in MODELS]
    ax.legend(handles=hs, loc="upper left", fontsize=5.3, ncol=2, columnspacing=0.6, handletextpad=0.1)
    grid(ax, "both")
    panel(ax, "b", "selective risk on 168 test items")
    ax = axs[2]
    R = F("E11_gap")
    nn = [30, 300, 3000, 30000]
    styles = (("0.9", "tolerant", "-", "o", C["blue"]), ("0.9", "exact", "-", "s", C["pamcp"]),
              ("0.6", "tolerant", ":", "o", C["sky"]), ("0.6", "exact", ":", "s", C["pamcp2"]))
    for i, (tau, agg, ls, mk, col) in enumerate(styles):
        ys, ab = [], []
        for n in nn:
            v = R.get(f"sonnet|{tau}|{n}|{agg}|gap")
            if v is None or v["abstain"]:
                ys.append(np.nan)
                ab.append(n)
            else:
                ys.append(v["size"])
        ax.plot(nn, ys, ls=ls, marker=mk, color=col, label=f"$\\tau$={tau}, {agg}")
        ax.scatter(ab, [0.6 + 0.18 * i] * len(ab), marker="x", s=14, color=col, lw=0.8, zorder=3)
    ax.text(30000, 1.35, "abstains", ha="right", fontsize=5.5, color=C["grey"])
    ax.set_xscale("log")
    ax.set_ylim(0.3, 8.5)
    ax.set_xlabel("reviews $n$ (scenario of Fig. 1)")
    ax.set_ylabel("toolkit size $|K|$")
    ax.legend(loc="upper left", fontsize=5.3, handlelength=1.6)
    grid(ax, "both")
    panel(ax, "c", "model-conditioned gap")
    fig.tight_layout(w_pad=0.9)
    save(fig, "fig_rq1_profile")

    # ---- Figure: typing agreement per output kind
    e2 = F("E2_typing")
    pk_t, pk_s = e2["tau"]["per_kind"], e2["struct"]["per_kind"]
    kinds_ = sorted([k for k in pk_t if pk_t[k]["support"] >= 4], key=lambda k: -pk_t[k]["support"])
    fig, ax = plt.subplots(figsize=(COL1, 1.9))
    y = np.arange(len(kinds_))
    ax.barh(y - 0.2, [pk_t[k]["f1"] for k in kinds_], 0.4, color=C["blue"], label="LLM-assisted typing $\\tau$")
    ax.barh(y + 0.2, [pk_s.get(k, {}).get("f1", 0) for k in kinds_], 0.4, color=C["light"],
            label="structural typer (schema + name)")
    for i, k in enumerate(kinds_):
        ax.text(1.02, i, f"{pk_t[k]['support']}", va="center", fontsize=5.5, color=C["grey"])
    ax.text(1.02, -0.9, "$n$", fontsize=5.5, color=C["grey"])
    ax.set_yticks(y, kinds_)
    ax.invert_yaxis()
    ax.set_xlim(0, 1.0)
    ax.set_xlabel("F1 against $J_B$ output kinds")
    ax.legend(loc="upper center", bbox_to_anchor=(0.45, -0.22), ncol=2, fontsize=5.5)
    grid(ax, "x")
    save(fig, "fig_rq1_typing")

    # ---- Table: calibration summary
    rows = []
    for m, ml in MODELS:
        r = cal[m]
        sa = r["self_assessment"]
        me = r["selection"]["measured|exact_rule=True"]["target=0.05"]
        old = r["selection"].get("manuscript_64|exact_rule=True", {}).get("manuscript_tau=0.9")
        lo, hi = r["accuracy_ci"]
        rows.append(f"{ml} & {r['items']} & {100 * r['accuracy']:.1f} [{100 * lo:.1f}, {100 * hi:.1f}] & "
                    f"{pct(r['by_n']['640']['accuracy'], 0)} & {sa['ece']:.2f} & {sa['brier']:.2f} & "
                    f"{me['tau']:.2f} & {pct(me['test']['coverage'], 0)} & {pct(me['test']['selective_risk'])} & "
                    + (f"{pct(old['test']['coverage'], 0)} & {pct(old['test']['selective_risk'])}" if old else "-- & --")
                    + r" \\")
    write_table("tab_rq1_calibration", r"""\begin{table}[t]
\centering
\caption{Model-profile calibration: accuracy (Wilson 95\% CI), self-assessment calibration, and the held-out
behaviour of the threshold $\tau$ chosen for a 5\% risk target (measured profile) versus the 64-item profile at
$\tau=0.9$. Cov.: share of operations kept native; FNR: false-native rate (errors among them).}
\label{tab:ev-calibration}
\scriptsize
\setlength{\tabcolsep}{2.2pt}
\begin{tabular}{@{}lrcrrrrrrrr@{}}
\toprule
 & & & & \multicolumn{2}{c}{Self-assess.} & \multicolumn{3}{c}{Measured, risk 5\%} & \multicolumn{2}{c}{64-item} \\
\cmidrule(lr){5-6}\cmidrule(lr){7-9}\cmidrule(l){10-11}
Model & $n$ & Accuracy (\%) & $n{=}640$ & ECE & Brier & $\tau$ & Cov. & FNR & Cov. & FNR \\
\midrule
""" + "\n".join(rows) + r"""
\bottomrule
\end{tabular}
\end{table}
""")


# ------------------------------------------------------------------------------------------------ 8.3 RQ2
ENC = (("no_filter", "no filter / MCP default", "o", C["grey"]),
       ("closed_world_annotations", "closed-world annotations", "s", C["purple"]),
       ("lexical_positive", "lexical cues", "^", C["green"]),
       ("verified_evidence", "verified evidence (P)", "D", C["pamcp"]),
       ("attested_only", "attested only", "v", C["blue"]))


def rq2():
    e4, e5, e6, e7 = F("E4_exposure"), F("E5_forgery"), F("E6_verifier"), F("E7_trust")
    adm = F("E4_admitted")
    # ---- Figure: exposure under encodings, forgery and verifier error
    fig, axs = plt.subplots(1, 3, figsize=(COL2, 2.0), gridspec_kw={"width_ratios": [1.2, 1, 1]})
    ax = axs[0]
    R = e4["1.0"]
    for e, lab, mk, col in ENC:
        a, b = R[f"pamcp_rrf|{e}"], R[f"mcp_zero|{e}"]
        ax.plot([a["Util@5"], b["Util@5"]], [a["Exp@5"], b["Exp@5"]], color=col, lw=0.6, alpha=0.5)
        ax.scatter(a["Util@5"], a["Exp@5"], marker=mk, s=30, color=col, edgecolor="white", lw=0.4, zorder=3, label=lab)
        ax.scatter(b["Util@5"], b["Exp@5"], marker=mk, s=30, facecolor="white", edgecolor=col, lw=0.8, zorder=3)
    for cov, al in (("0.75", 0.75), ("0.5", 0.5), ("0.25", 0.3)):
        v = e4[cov]["pamcp_rrf|verified_evidence"]
        ax.scatter(v["Util@5"], v["Exp@5"], marker="D", s=14, color=C["pamcp"], alpha=al, lw=0, zorder=3)
        ax.annotate(f"$\\kappa$={cov}", (v["Util@5"], v["Exp@5"]), xytext=(0, 5), textcoords="offset points",
                    fontsize=5, ha="center", color=C["pamcp"])
    ax.set_xlabel("Util@5 (gold tool in top 5)")
    ax.set_ylabel("Exp@5 (unsafe tool in top 5)")
    ax.xaxis.set_major_formatter(PCT)
    ax.yaxis.set_major_formatter(PCT)
    ax.set_xlim(-0.02, 0.85)
    ax.set_ylim(-0.02, 0.48)
    ax.text(0.84, 0.47, "filled: PaMCP retrieval\nopen: MCP-Zero", fontsize=5, ha="right", va="top",
            color=C["grey"])
    grid(ax, "both")
    panel(ax, "a", "policy encodings, full coverage")
    ax = axs[1]
    rows = raw(FIN / "raw" / "E5_forgery.jsonl.gz")
    ds = [0.0, 0.05, 0.1, 0.2, 0.3]
    for e, lab, mk, col in ENC[:4]:
        ys = [e5[f"both|{d}"][f"pamcp_rrf|{e}"]["Exp@5"] for d in ds]
        ax.plot(ds, ys, marker=mk, color=col, label=lab)
        per = [[sum(a == "1" and b == "1" for a, b in zip(r["exp5"], r["ro"])) / r["ro"].count("1")
                for r in rows if r.get("attack") == "both" and r.get("delta") == d and
                r.get("retriever") == "pamcp_rrf" and r.get("encoding") == e and "exp5" in r] for d in ds]
        if all(per) and e == "verified_evidence":
            ax.fill_between(ds, [min(p_) for p_ in per], [max(p_) for p_ in per], color=col, alpha=0.15, lw=0)
    ax.set_xlabel("share of forging servers $\\delta$")
    ax.set_ylabel("Exp@5")
    ax.xaxis.set_major_formatter(PCT)
    ax.yaxis.set_major_formatter(PCT)
    ax.text(0.3, 0.17, "band: verified, 5 seeds (min-max)", fontsize=5, ha="right", color=C["pamcp"])
    grid(ax, "both")
    panel(ax, "b", "forged + laundered metadata")
    ax = axs[2]
    phis = [0.0, 0.01, 0.02, 0.05, 0.1, 0.2]
    for pl, lab, ls, mk in (("random", "random errors", "-", "D"), ("lookalike", "look-alike errors", ":", "d")):
        ax.plot(phis, [e6[f"0.2|{pl}|0.0|1.0|{p_}"]["pamcp_rrf|verified_evidence"]["Exp@5"] for p_ in phis],
                ls=ls, marker=mk, color=C["pamcp"], label=f"verified, {lab}")
    lex = e6["0.2|random|0.0|1.0|0.0"]["pamcp_rrf|lexical_positive"]["Exp@5"]
    ax.axhline(lex, color=C["green"], lw=0.9, ls="--", label="lexical cues")
    ax.axvspan(0, 0.05, color=C["pamcp"], alpha=0.06, lw=0)
    ax.text(0.025, 0.17, "verified\nbelow\nlexical", fontsize=5, ha="center", color=C["pamcp"])
    ax.set_xlabel("verifier false-accept rate $\\varphi$")
    ax.set_ylabel("Exp@5")
    ax.xaxis.set_major_formatter(PCT)
    ax.yaxis.set_major_formatter(PCT)
    ax.legend(loc="lower right", fontsize=5.3)
    ax.set_ylim(-0.005, 0.2)
    grid(ax, "both")
    panel(ax, "c", "imperfect verifier, $\\delta$ = 20%")
    fig.tight_layout(w_pad=0.8, rect=(0, 0.07, 1, 1))
    fig.legend(handles=[Line2D([], [], marker=mk, color=col, ls="-", label=lab) for _, lab, mk, col in ENC],
               loc="lower center", ncol=5, bbox_to_anchor=(0.42, -0.01), fontsize=6)
    save(fig, "fig_rq2_exposure")

    # ---- Figure: trust threshold and label independence
    fig, axs = plt.subplots(1, 2, figsize=(COL1, 1.75), gridspec_kw={"width_ratios": [1.25, 1]})
    ax = axs[0]
    ls_ = sorted({float(k.split("|")[2]) for k in e7})
    for kap, ls in (("0.0", "-"), ("0.8", ":")):
        ax.plot(ls_, [e7[f"default|{kap}|{l}"]["Exp@5"] for l in ls_], ls=ls, color=C["pamcp"],
                label=f"Exp@5, $\\kappa\\geq${kap}")
        ax.plot(ls_, [e7[f"default|{kap}|{l}"]["Util@5"] for l in ls_], ls=ls, color=C["blue"],
                label=f"Util@5, $\\kappa\\geq${kap}")
    ax.plot(ls_, [e7[f"default|0.0|{l}"]["eligible_share"] for l in ls_], color=C["grey"], lw=0.7,
            label="eligible share")
    ax.axvline(0.65, color=C["black"], lw=0.5, ls="--")
    ax.set_xlabel("trust threshold $\\ell_{\\min}$")
    ax.yaxis.set_major_formatter(PCT)
    ax.set_ylim(0, 1.0)
    ax.legend(loc="upper right", fontsize=4.8, handlelength=1.4)
    grid(ax, "both")
    panel(ax, "a", "trust threshold")
    ax = axs[1]
    sw = X("R2_label_swap")
    dirs = (("paper: verifier A, scored B", "$J_A\\to J_B$", C["light"]),
            ("swapped: verifier B, scored A", "$J_B\\to J_A$", C["pamcp"]))
    rets = (("pamcp_rrf", "PaMCP"), ("rag_mcp", "RAG"), ("mcp_zero", "MCP-0"), ("toolscope", "TScope"))
    x = np.arange(len(rets))
    for j, (k, lab, col) in enumerate(dirs):
        v = [sw[k]["Exp@5"][r] for r, _ in rets]
        ci = [sw[k]["Exp@5_ci_target_clusters"][r] for r, _ in rets]
        ax.bar(x + (j - 0.5) * 0.36, v, 0.36, color=col, label=lab,
               yerr=[[a - c[0] for a, c in zip(v, ci)], [c[1] - a for a, c in zip(v, ci)]],
               error_kw={"lw": 0.6, "capsize": 1.2})
    ax.set_xticks(x, [l for _, l in rets], fontsize=5.5)
    ax.yaxis.set_major_formatter(PCT)
    ax.set_ylabel("Exp@5, verified evidence")
    ax.legend(loc="upper left", fontsize=5.2, title="verifier $\\to$ scorer", title_fontsize=5.2)
    grid(ax)
    panel(ax, "b", "label swap")
    fig.tight_layout(w_pad=0.6)
    save(fig, "fig_rq2_trust")

    # ---- Figure: observed effects of executed reference servers
    obs = X("R2_X2_observed")
    rws = [r for r in raw(R2 / "raw" / "R2_X2_observed.jsonl.gz") if "id" in r]
    srv_order = ["filesystem", "git", "memory", "time", "sequential-thinking", "fetch"]
    rws.sort(key=lambda r: (srv_order.index(r["server"]), r["id"]))
    srcs = (("observed", "observed"), ("ja_state", "$J_A$"), ("jb_state", "$J_B$"), ("ann_state", "live annot."))
    fig, axs = plt.subplots(1, 2, figsize=(COL2, 2.35), gridspec_kw={"width_ratios": [4.2, 1]})
    ax = axs[0]
    for j, r in enumerate(rws):
        for i, (k, _) in enumerate(srcs):
            if k == "observed":
                if not r["exercised"]:
                    ax.add_patch(plt.Rectangle((j - 0.45, i - 0.4), 0.9, 0.8, facecolor="white",
                                               edgecolor=C["light"], hatch="////", lw=0.4))
                    continue
                v = r["obs_state"]
            else:
                v = r[k]
            ax.add_patch(plt.Rectangle((j - 0.45, i - 0.4), 0.9, 0.8, lw=0,
                                       facecolor=C["pamcp"] if v else "#D9D9D9"))
            if k != "observed" and r["exercised"] and bool(v) != bool(r["obs_state"]):
                ax.scatter(j, i, marker="x", s=10, color="black", lw=0.6, zorder=4)
    ax.set_xlim(-0.6, len(rws) - 0.4)
    ax.set_ylim(len(srcs) - 0.5, -0.5)
    ax.set_yticks(range(len(srcs)), [l for _, l in srcs])
    names = [r["id"].split("::")[1].replace("git_", "").replace("_", " ") for r in rws]
    ax.set_xticks(range(len(rws)), names, rotation=90, fontsize=4.6)
    pos = 0
    for sv in srv_order:
        n = sum(1 for r in rws if r["server"] == sv)
        if n:
            short = {"sequential-thinking": "seq.", "time": "time", "fetch": "fetch"}.get(sv, sv)
            ax.text(pos + (n - 1) / 2, -0.62, short, ha="center", va="bottom", fontsize=5.5)
            if pos:
                ax.axvline(pos - 0.5, color="black", lw=0.5)
            pos += n
    for s_ in ax.spines.values():
        s_.set_visible(False)
    ax.tick_params(length=0)
    ax.legend(handles=[Patch(color=C["pamcp"], label="modifies state"), Patch(color="#D9D9D9", label="read-only"),
                       Patch(facecolor="white", edgecolor=C["light"], hatch="////", label="call failed (not exercised)"),
                       Line2D([], [], marker="x", ls="", color="black", label="differs from observation")],
              loc="lower right", bbox_to_anchor=(1.0, 1.1), ncol=4, fontsize=5.3, columnspacing=0.8)
    ax = axs[1]
    d = obs["drift"]
    items = (("hash_invalidated", "$h(t)$ invalidated"), ("annotations_changed", "annotations"),
             ("schema_changed", "input schema"), ("schema_unpublished", "schema without\nproperties"),
             ("description_changed", "description"), ("removed", "tool removed"))
    vals = [d[k] / d["registry_tools"] for k, _ in items]
    ax.barh(range(len(items)), vals, 0.65, color=[C["pamcp"]] + [C["blue"]] * (len(items) - 1))
    for i, v in enumerate(vals):
        ax.text(v + 0.02, i, f"{round(v * d['registry_tools'])}", va="center", fontsize=5.5)
    ax.set_yticks(range(len(items)), [l for _, l in items], fontsize=5.5)
    ax.invert_yaxis()
    ax.set_xlim(0, 1.25)
    ax.xaxis.set_major_formatter(PCT)
    ax.set_xlabel(f"of {d['registry_tools']} snapshot tools", fontsize=6)
    grid(ax, "x")
    panel(ax, "b", "definition drift")
    axs[0].set_title("(a) state change: executed vs. labelled, per tool", loc="left", fontsize=7, pad=9)
    fig.tight_layout(w_pad=0.5)
    save(fig, "fig_rq2_observed")

    # ---- Table: policy encodings
    R1 = e4["1.0"]
    lab = {e: l for e, l, _, _ in ENC}
    lab.update({"mcp_default_annotations": "MCP default (display only)", "no_filter": "no filter",
                "observed_lexical_fallback": "observed + lexical fallback"})
    order = ["no_filter", "mcp_default_annotations", "closed_world_annotations", "lexical_positive",
             "verified_evidence", "observed_lexical_fallback", "attested_only"]
    rows = []
    for e in order:
        a, z = R1[f"pamcp_rrf|{e}"], R1[f"mcp_zero|{e}"]
        f2 = e5["both|0.2"].get(f"pamcp_rrf|{e}")
        rows.append(f"{lab[e]} & {pct(adm[e]['eligible'] / 569, 1)} & {adm[e]['unsafe_admitted']} & "
                    f"{pct(a['Exp@5'])} & {pct(a['Util@5'])} & {pct(z['Exp@5'])} & {pct(z['Util@5'])} & "
                    f"{pct(f2['Exp@5']) if f2 else '--'} \\\\")
    write_table("tab_rq2_encodings", r"""\begin{table}[t]
\centering
\caption{Encodings of a read-only policy over 273 requests with read-only gold tools: eligible share of the
registry, unsafe tools admitted (of 120, $J_B$), exposure and utility of the top five for \pamcp{}'s retrieval
stage and MCP-Zero, and exposure when 20\% of the servers forge and launder their metadata (verifier
false-accept rate 5\%, mean of five seeds).}
\label{tab:ev-encodings}
\scriptsize
\setlength{\tabcolsep}{2.2pt}
\begin{tabular}{@{}lrrrrrrr@{}}
\toprule
 & & & \multicolumn{2}{c}{\pamcp{} retr.} & \multicolumn{2}{c}{MCP-Zero} & $\delta{=}0.2$ \\
\cmidrule(lr){4-5}\cmidrule(lr){6-7}\cmidrule(l){8-8}
Encoding & Elig. & Unsafe & Exp@5 & Util@5 & Exp@5 & Util@5 & Exp@5 \\
\midrule
""" + "\n".join(rows) + r"""
\bottomrule
\end{tabular}
\end{table}
""")
    # ---- Table: observed vs labelled
    L = obs["labels_vs_observed_state"]
    rows = []
    for k, lab_ in (("J_A", "$J_A$ (Sonnet)"), ("J_B", "$J_B$ (Opus)"), ("live_annotations", "live annotations")):
        v = L[k]
        lo, hi = v["false_safe_ci"]
        rows.append(f"{lab_} & {v['tp']} & {v['fn']} & {v['fp_unconfirmed']} & {v['tn']} & "
                    f"{pct(v['false_safe_rate'], 0)} [{pct(lo, 0)}, {pct(hi, 1)}] & {pct(v['agreement'], 0)} \\\\")
    write_table("tab_rq2_observed", r"""\begin{table}[t]
\centering
\caption{State changes observed when executing the """ + str(obs["exercised"]) + r""" exercised tools of six MCP
reference servers, against the two labellings and the servers' current annotations. FS: labelled read-only but
observed to modify state (false safe; Wilson 95\% CI); Unconf.: labelled state-changing, not triggered by the
probe.}
\label{tab:ev-observed}
\scriptsize
\setlength{\tabcolsep}{3pt}
\begin{tabular}{@{}lrrrrrr@{}}
\toprule
Reference & TP & FS & Unconf. & TN & False-safe rate (\%) & Agree. \\
\midrule
""" + "\n".join(rows) + r"""
\bottomrule
\end{tabular}
\end{table}
""")


# ------------------------------------------------------------------------------------------------ 8.4 RQ3
BASE = (("bm25|k1=1.5,b=0.9", "BM25", C["sky"]), ("dense|-", "RAG-MCP (dense)", C["blue"]),
        ("rrf|k0=30", "RRF fusion", C["green"]), ("mcp_zero|servers_k=2", "MCP-Zero", C["black"]),
        ("colt|lam=0.0,mu=0.0", "COLT", C["purple"]), ("toolscope|lex", "ToolScope", C["grey"]),
        ("cmtf|N=20,depth=4", "CMTF", C["light"]), ("pamcp|E", "PaMCP (Eq. 5)", C["pamcp"]),
        ("pamcp|A", "PaMCP-L", C["pamcp2"]))
VAR = (("A", "lexical"), ("B", "dense"), ("C", "lex+dense"), ("D", "structural only"), ("E", "Eq. (5): lex+den+str"),
       ("F", "relevance first"), ("F2", "type filter first"), ("G85", "conf.-gated str."), ("W50", "str. weight 0.5"),
       ("W25", "str. weight 0.25"), ("I", "oracle goal types"), ("J", "oracle tool types"), ("IJ", "both oracles"))


def rq3():
    t3, d3 = X("R2_X3_test")["summary"], X("R2_X3_dev")["summary"]
    e8 = F("E8_single_tool")
    fig, axs = plt.subplots(1, 3, figsize=(COL2, 2.25), gridspec_kw={"width_ratios": [1.05, 1.25, 0.95]})
    ax = axs[0]
    ms = sorted(BASE, key=lambda b: t3["B1m"][b[0]]["hit1"])
    for i, (k, lab, col) in enumerate(ms):
        a, b = t3["B1m"][k], t3["B1"][k]
        lo, hi = a["hit1_ci_target"]
        ax.plot([lo, hi], [i, i], color=C["pamcp"] if "pamcp" in k else C["grey"], lw=1.0)
        ax.scatter(a["hit1"], i, s=18, color=C["pamcp"] if "pamcp" in k else C["black"], zorder=3,
                   label="569 tools (95% CI)" if i == 0 else None)
        ax.scatter(b["hit1"], i, s=18, marker="o", facecolor="white",
                   edgecolor=C["pamcp"] if "pamcp" in k else C["black"], lw=0.8, zorder=3,
                   label="81 tools" if i == 0 else None)
    ax.set_yticks(range(len(ms)), [l for _, l, _ in ms])
    ax.set_xlim(0, 0.9)
    ax.xaxis.set_major_formatter(PCT)
    ax.set_xlabel("Hit@1 (300 test requests)")
    ax.legend(loc="upper center", bbox_to_anchor=(0.4, -0.2), ncol=2, fontsize=5.3, handletextpad=0.1)
    grid(ax, "x")
    panel(ax, "a", "tuned methods")
    ax = axs[1]
    y = np.arange(len(VAR))
    h1 = [t3["B1m"][f"pamcp|{v}"]["hit1"] for v, _ in VAR]
    mr = [t3["B1m"][f"pamcp|{v}"]["mrr10"] for v, _ in VAR]
    dv = [d3["B1m"][f"pamcp|{v}"]["hit1"] for v, _ in VAR]
    cols = [C["light"] if v in ("I", "J", "IJ") else C["pamcp"] if v == "E" else C["pamcp2"] if v == "A"
            else C["sky"] for v, _ in VAR]
    ax.barh(y, h1, 0.62, color=cols, label="Hit@1 (test)")
    ax.scatter(mr, y, marker="|", s=40, color=C["black"], lw=1.0, zorder=3, label="MRR@10 (test)")
    ax.scatter(dv, y, marker="o", s=10, facecolor="white", edgecolor=C["black"], lw=0.6, zorder=3,
               label="Hit@1 (dev, selection)")
    ax.axvline(t3["B1m"]["bm25|k1=1.5,b=0.9"]["hit1"], color=C["sky"], lw=0.6, ls="--")
    ax.text(t3["B1m"]["bm25|k1=1.5,b=0.9"]["hit1"] + 0.01, len(VAR) - 0.6, "tuned BM25", fontsize=5,
            color=C["blue"], va="top")
    ax.axhline(9.5, color=C["grey"], lw=0.5)
    ax.text(0.86, 9.75, "diagnostic (oracles)", fontsize=5, ha="right", va="center", color=C["grey"],
            style="italic")
    ax.set_yticks(y, [f"{v}  {l}" for v, l in VAR], fontsize=5.6)
    ax.invert_yaxis()
    ax.set_xlim(0, 0.88)
    ax.xaxis.set_major_formatter(PCT)
    ax.set_xlabel("569-tool registry")
    ax.legend(loc="upper center", bbox_to_anchor=(0.45, -0.2), ncol=3, fontsize=5, handletextpad=0.2,
              columnspacing=0.6)
    grid(ax, "x")
    panel(ax, "b", "PaMCP ranking variants")
    ax = axs[2]
    c = e8["distractor_curve_hit1"]
    ds = sorted(c, key=int)
    curves = (("pamcp_contract", "PaMCP (Eq. 5)", C["pamcp"], "o"), ("mcp_zero", "MCP-Zero", C["black"], "s"),
              ("bm25", "BM25", C["sky"], "^"), ("rrf", "RRF fusion", C["green"], "v"),
              ("toolscope_adapted", "ToolScope", C["grey"], "D"))
    for k, lab, col, mk in curves:
        ax.plot([81 + int(d) for d in ds], [c[d][k] for d in ds], marker=mk, color=col, label=lab, ms=3)
    ax.set_xlabel("registry size (B1 + LiveMCPTool tools)")
    ax.set_ylabel("Hit@1")
    ax.yaxis.set_major_formatter(PCT)
    ax.legend(loc="lower left", fontsize=5.3)
    grid(ax, "both")
    panel(ax, "c", "added distractors (5 seeds)")
    fig.tight_layout(w_pad=0.7)
    save(fig, "fig_rq3_retrieval")

    # ---- Figure: set-level quality
    e9, e10 = F("E9_sets")["summary"], F("E10_validity")["summary"]
    st = X("R2_evaluator_audit")["e10_strict"]
    v2 = X("R2_v2_eval")["summary"]
    fig, axs = plt.subplots(1, 3, figsize=(COL2, 2.05), gridspec_kw={"width_ratios": [1.15, 1.1, 1.0]})
    ax = axs[0]
    series = (("pamcp", "PaMCP", C["pamcp"], "o"), ("per_subtask[analyst]", "per-subtask", C["green"], "s"),
              ("rag_mcp", "RAG-MCP", C["blue"], "^"), ("colt", "COLT", C["purple"], "v"),
              ("toolscope[analyst]", "ToolScope", C["grey"], "D"), ("mcp_zero_ranked", "MCP-Zero", C["black"], "P"))
    for k, lab, col, mk in series:
        pts = []
        for b in ("size-matched", "5", "10", "20"):
            v = e9.get(f"{k}@{b}") or (e9.get(k) if b == "5" and k == "per_subtask[analyst]" else None)
            if v:
                pts.append((v["size"]["mean"], v["recall"]["mean"], v["recall"]["ci"]))
        pts.sort()
        ax.plot([p_[0] for p_ in pts], [p_[1] for p_ in pts], color=col, marker=mk, ms=3, label=lab)
        if pts:
            x0, y0, ci = pts[0]
            ax.errorbar(x0, y0, yerr=[[y0 - ci[0]], [ci[1] - y0]], color=col, lw=0.6, capsize=1)
    ax.scatter(v2["pamcp_v2"]["size9"], v2["pamcp_v2"]["recall"], marker="*", s=40, color=C["pamcp2"], zorder=4,
               label="PaMCP-L")
    cm = e9["cmtf_path"]
    ax.scatter(cm["size"]["mean"], cm["recall"]["mean"], marker="x", s=18, color=C["light"], lw=1, label="CMTF")
    ax.set_xscale("log")
    ax.set_xlabel("toolkit size $|K|$ (budgets: matched, 5, 10, 20)")
    ax.set_ylabel("group recall (94 tasks)")
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
    ax.legend(loc="upper left", fontsize=5, ncol=2, columnspacing=0.5, handletextpad=0.2)
    ax.set_ylim(0, 0.55)
    grid(ax, "both")
    panel(ax, "a", "recall against toolkit size")
    ax = axs[1]
    rows = (("pamcp(K=10)", "PaMCP"), ("pamcp_nocert", "PaMCP NoCert"),
            ("per_subtask[analyst]|eligible-only", "per-subtask (elig.)"),
            ("toolscope[analyst]@5|eligible-only", "ToolScope (elig.)"), ("rag_mcp@5|eligible-only", "RAG-MCP (elig.)"),
            ("colt@5|eligible-only", "COLT (elig.)"), ("mcp_zero|eligible-only", "MCP-Zero (elig.)"),
            ("cmtf_path|eligible-only", "CMTF (elig.)"), ("rag_mcp@5|unfiltered", "RAG-MCP (publ.)"))
    for i, (k, lab) in enumerate(rows):
        a, b = st[k]["joint_paper"], st[k]["joint_strict"]
        col = C["pamcp"] if k.startswith("pamcp") else C["blue"]
        ax.plot([b, a], [i, i], color=col, lw=1.2, alpha=0.5)
        ax.scatter(a, i, s=18, color=col, zorder=3, label="coarse evaluator" if i == 0 else None)
        ax.scatter(b, i, s=18, facecolor="white", edgecolor=col, lw=0.9, zorder=3,
                   label="strict evaluator" if i == 0 else None)
    ax.scatter(v2["pamcp_v2"]["joint_paper"], -0.9, s=18, color=C["pamcp2"], zorder=3)
    ax.scatter(v2["pamcp_v2"]["joint_strict"], -0.9, s=18, facecolor="white", edgecolor=C["pamcp2"], lw=0.9)
    ax.plot([v2["pamcp_v2"]["joint_strict"], v2["pamcp_v2"]["joint_paper"]], [-0.9, -0.9], color=C["pamcp2"],
            lw=1.2, alpha=0.5)
    ax.set_yticks([-0.9] + list(range(len(rows))), ["PaMCP-L"] + [l for _, l in rows], fontsize=5.6)
    ax.invert_yaxis()
    ax.set_xlim(0, 0.85)
    ax.xaxis.set_major_formatter(PCT)
    ax.set_xlabel("jointly feasible toolkits (94 tasks)")
    ax.legend(loc="lower right", fontsize=5.2, handletextpad=0.1)
    grid(ax, "x")
    panel(ax, "b", "joint feasibility")
    ax = axs[2]
    checks = ["S", "C", "E", "L", "V", "M"]
    hr = (("pamcp(K=10)", "PaMCP"), ("pamcp_nocert", "NoCert"), ("per_subtask[analyst]|eligible-only", "per-subtask"),
          ("toolscope[analyst]@5|eligible-only", "ToolScope"), ("rag_mcp@5|eligible-only", "RAG-MCP"),
          ("rag_mcp@5|unfiltered", "RAG (publ.)"))
    M = np.array([[e10[k]["pass"][c] for c in checks] for k, _ in hr])
    ax.imshow(M, cmap="cividis", vmin=0.2, vmax=1.0, aspect="auto")
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            ax.text(j, i, f"{100 * M[i, j]:.0f}", ha="center", va="center", fontsize=5.6,
                    color="black" if M[i, j] > 0.65 else "white")
    ax.set_xticks(range(len(checks)), checks)
    ax.set_yticks(range(len(hr)), [l for _, l in hr], fontsize=5.8)
    for s_ in ax.spines.values():
        s_.set_visible(False)
    ax.tick_params(length=0)
    panel(ax, "c", "checks passed (%), coarse")
    fig.tight_layout(w_pad=0.7)
    save(fig, "fig_rq3_sets")

    # ---- Table: retrieval
    rows = []
    for k, lab, _ in BASE + (("pamcp|IJ", "PaMCP, oracle types (diag.)", None),):
        a, b = t3["B1m"][k], t3["B1"][k]
        lo, hi = a["hit1_ci_target"]
        rows.append(f"{lab} & {pct(b['hit1'])} & {pct(a['hit1'])} [{pct(lo, 0)}, {pct(hi, 0)}] & {pct(a['hit3'])} & "
                    f"{pct(a['hit5'])} & {a['mrr10']:.3f} & {a['ndcg10']:.3f} \\\\")
    write_table("tab_rq3_retrieval", r"""\begin{table}[t]
\centering
\caption{Single-tool retrieval on the 300 test requests with configurations selected on the development split:
Hit@1 over the 81 MCPToolBench++ tools and, with target-tool clustered 95\% CI, over the 569-tool registry, and
the other metrics over 569 tools.}
\label{tab:ev-retrieval}
\scriptsize
\setlength{\tabcolsep}{2.4pt}
\begin{tabular}{@{}lrrrrrr@{}}
\toprule
 & 81 tools & \multicolumn{5}{c}{569 tools} \\
\cmidrule(lr){2-2}\cmidrule(l){3-7}
Method & Hit@1 & Hit@1 [CI] & Hit@3 & Hit@5 & MRR & nDCG \\
\midrule
""" + "\n".join(rows) + r"""
\bottomrule
\end{tabular}
\end{table}
""")
    # ---- Table: sets
    def row(lab, s9, k10, ks):
        r9 = s9["recall"]
        return (f"{lab} & {s9['size']['mean']:.2f} & {s9['tokens']['mean']:.0f} & {r9['mean']:.3f} "
                f"[{r9['ci'][0]:.2f}, {r9['ci'][1]:.2f}] & "
                + (f"{pct(e10[k10]['joint_feasible'])} & {pct(st[k10]['joint_strict'])}" if k10 else "-- & --")
                + (f" & {pct(e10[k10].get('abstain', 0))}" if k10 and k10.startswith("pamcp") else " & --")
                + " \\\\")
    rows = [row("\\pamcp{} ($K{=}10$)", e9["pamcp@10"], "pamcp(K=10)", None),
            f"\\pamcp{{}}-L & {v2['pamcp_v2']['size9']:.2f} & {v2['pamcp_v2']['tokens9']:.0f} & "
            f"{v2['pamcp_v2']['recall']:.3f} & {pct(v2['pamcp_v2']['joint_paper'])} & {pct(v2['pamcp_v2']['joint_strict'])}"
            f" & {pct(v2['pamcp_v2']['abstain9'])} \\\\",
            row("\\pamcp{} NoCert", e9["pamcp@5"], "pamcp_nocert", None).replace(
                f"{e9['pamcp@5']['size']['mean']:.2f} & {e9['pamcp@5']['tokens']['mean']:.0f} & "
                f"{e9['pamcp@5']['recall']['mean']:.3f} [{e9['pamcp@5']['recall']['ci'][0]:.2f}, "
                f"{e9['pamcp@5']['recall']['ci'][1]:.2f}]", "-- & -- & --"),
            row("Per-subtask (elig.)", e9["per_subtask[analyst]"], "per_subtask[analyst]|eligible-only", None),
            row("RAG-MCP@5 (elig.)", e9["rag_mcp@5"], "rag_mcp@5|eligible-only", None),
            row("COLT@5 (elig.)", e9["colt@5"], "colt@5|eligible-only", None),
            row("ToolScope@5 (elig.)", e9["toolscope[analyst]@5"], "toolscope[analyst]@5|eligible-only", None),
            row("MCP-Zero (elig.)", e9["mcp_zero"], "mcp_zero|eligible-only", None),
            row("CMTF (elig.)", e9["cmtf_path"], "cmtf_path|eligible-only", None),
            row("RAG-MCP@5 (published)", e9["rag_mcp@5"], "rag_mcp@5|unfiltered", None)]
    write_table("tab_rq3_sets", r"""\begin{table}[t]
\centering
\caption{Toolkits on the 94 LiveMCPBench test tasks: size, manifest tokens, group recall (task bootstrap 95\%
CI), share of toolkits jointly feasible for the coarse and the strict independent evaluator (least-privilege
policies), and abstentions. Baselines restricted to eligible tools unless marked published.}
\label{tab:ev-sets}
\scriptsize
\setlength{\tabcolsep}{2.1pt}
\begin{tabular}{@{}lrrlrrr@{}}
\toprule
 & & & & \multicolumn{2}{c}{Joint feas. (\%)} & \\
\cmidrule(lr){5-6}
Method & $|K|$ & Tok. & Group recall [CI] & coarse & strict & Abst. \\
\midrule
""" + "\n".join(rows) + r"""
\bottomrule
\end{tabular}
\end{table}
""")


if __name__ == "__main__":
    which = sys.argv[1:] or ["setup", "rq1", "rq2", "rq3", "sec", "eff"]
    for w in which:
        globals()[w]()
