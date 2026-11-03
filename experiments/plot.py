"""Publication figures from results/*.json only — this script runs no experiment.

Colour follows the validated reference palette of the dataviz method:
* categorical slots in fixed order (blue, orange, aqua, yellow, magenta, green), validated with
  ``validate_palette.js --mode light``: all adjacent-pair checks PASS; the scatter figure uses only
  the first slots plus a neutral, validated ``--pairs all``;
* ordered series (w_rel values, R@k) use one-hue blue ordinal ramps, validated ``--ordinal``;
* aqua, yellow and magenta sit below 3:1 contrast on the surface, so every figure carries marker
  shapes or direct labels, and every number is tabulated in docs/RESULTS.md (relief rule).
Each figure is written as PNG (300 dpi) and PDF (vector, embedded TrueType) to results/figures/,
and docs/FIGURES.md is regenerated with captions whose numbers are read from the same JSON.
"""
from __future__ import annotations

import json
from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import PathPatch  # noqa: E402
from matplotlib.path import Path  # noqa: E402
from matplotlib.ticker import FuncFormatter, PercentFormatter  # noqa: E402

from common import RESULTS, ROOT  # noqa: E402

FIG = RESULTS / "figures"
SURFACE, INK, INK2, MUTED, GRID, BAND = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#f0efec"
SLOTS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
ORDINAL4 = ["#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]
ORDINAL3 = ["#86b6ef", "#2a78d6", "#104281"]
MARKERS = ["o", "s", "^", "D", "v", "P"]

plt.rcParams.update({
    "figure.dpi": 150, "savefig.dpi": 300, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE, "font.family": "DejaVu Sans", "font.size": 8,
    "axes.edgecolor": MUTED, "axes.linewidth": 0.6, "axes.labelcolor": INK2, "axes.labelsize": 7.5,
    "axes.titlecolor": INK, "axes.titlesize": 8, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "axes.titlepad": 6, "axes.spines.top": False, "axes.spines.right": False,
    "xtick.color": MUTED, "ytick.color": MUTED, "xtick.labelcolor": INK2, "ytick.labelcolor": INK2,
    "xtick.labelsize": 7, "ytick.labelsize": 7, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
    "xtick.major.size": 2.5, "ytick.major.size": 2.5, "grid.color": GRID, "grid.linewidth": 0.6,
    "grid.linestyle": "-", "legend.frameon": False, "legend.fontsize": 7, "legend.labelcolor": INK2,
    "legend.handlelength": 1.6, "lines.linewidth": 1.5, "lines.markersize": 4.5, "pdf.fonttype": 42,
})
WRITTEN: list[tuple[str, str, str]] = []   # (file stem, title, caption)
PCT = PercentFormatter(1.0, decimals=0)


def load(name):
    p = RESULTS / f"{name}.json"
    return json.load(open(p)) if p.exists() else None


def grid(ax, axis="y"):
    ax.grid(True, axis=axis)
    ax.set_axisbelow(True)


def save(fig, stem, title, caption):
    for ext in ("png", "pdf"):
        fig.savefig(FIG / f"{stem}.{ext}", bbox_inches="tight", pad_inches=0.04)
    plt.close(fig)
    WRITTEN.append((stem, title, caption))


def _radius(ax, pts=2.2):
    """Corner radius of ``pts`` points in data units along x and y (call after limits are set)."""
    fig = ax.figure
    pos = ax.get_position()
    w_pt, h_pt = pos.width * fig.get_figwidth() * 72, pos.height * fig.get_figheight() * 72
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    return pts * abs(x1 - x0) / w_pt, pts * abs(y1 - y0) / h_pt


def hbar(ax, y, value, h, color, x0=0.0):
    """Horizontal bar anchored square on the baseline with a rounded data end (linear x axis)."""
    if value <= x0:
        return
    rx, ry = _radius(ax)
    rx, ry = min(rx, (value - x0) / 2), min(ry, h / 2)
    b, t, x1 = y - h / 2, y + h / 2, value
    verts = [(x0, b), (x1 - rx, b), (x1, b), (x1, b + ry), (x1, t - ry), (x1, t), (x1 - rx, t), (x0, t), (x0, b)]
    codes = [Path.MOVETO, Path.LINETO, Path.CURVE3, Path.CURVE3, Path.LINETO, Path.CURVE3, Path.CURVE3,
             Path.LINETO, Path.CLOSEPOLY]
    ax.add_patch(PathPatch(Path(verts, codes), facecolor=color, edgecolor="none", zorder=2))


def vbar(ax, x, value, w, color):
    """Vertical bar anchored on y = 0 with a rounded data end (linear y axis)."""
    if value <= 0:
        return
    rx, ry = _radius(ax)
    rx, ry = min(rx, w / 2), min(ry, value / 2)
    l, r = x - w / 2, x + w / 2
    verts = [(l, 0), (l, value - ry), (l, value), (l + rx, value), (r - rx, value), (r, value), (r, value - ry),
             (r, 0), (l, 0)]
    codes = [Path.MOVETO, Path.LINETO, Path.CURVE3, Path.CURVE3, Path.LINETO, Path.CURVE3, Path.CURVE3,
             Path.LINETO, Path.CLOSEPOLY]
    ax.add_patch(PathPatch(Path(verts, codes), facecolor=color, edgecolor="none", zorder=2))


def end_label(ax, x, y, text, dx=3, **kw):
    ax.annotate(text, (x, y), xytext=(dx, 0), textcoords="offset points", va="center", fontsize=6.5,
                color=INK2, **kw)


# --------------------------------------------------------------------------- H2
ENC = [("obs+", "verified in sandbox (obs+)"), ("att+", "signed attestation (att+)"),
       ("ann+", "MCP default: declared read-only (ann+)"), ("ann-cw", "missing hint read as safe (ann-cw)"),
       ("lex+", "name looks read-only (lex+)"), ("lex-cw", "no write words in name (lex-cw)")]


def fig_h2():
    d = load("e2_eligibility")
    if not d:
        return
    s = d["summary"]
    fars = sorted({r["far"] for r in d["rows"]})
    alphas = (0.0, 0.25, 0.5)
    fig, axes = plt.subplots(1, 3, figsize=(7.1, 2.35), sharey=True)
    for i, (ax, a) in enumerate(zip(axes, alphas)):
        for j, (enc, label) in enumerate(ENC):
            ys = [s[f"a={a}|far={f}|{enc}"]["exposure"]["mean"] for f in fars]
            ax.plot(fars, ys, color=SLOTS[j], marker=MARKERS[j], mec=SURFACE, mew=0.7, label=label,
                    lw=2.0 if enc == "obs+" else 1.2, zorder=4 if enc == "obs+" else 3)
        ax.set_title(f"{'abc'[i]}   " + ("honest servers" if a == 0 else f"{a:.0%} of servers forge"))
        ax.set_xticks([0, 0.05, 0.1, 0.15, 0.2])
        ax.xaxis.set_major_formatter(PCT)
        ax.set_xlabel("verifier false-accept rate")
        ax.set_ylim(0, 1)
        ax.yaxis.set_major_formatter(PCT)
        grid(ax)
    axes[0].set_ylabel("unsafe tools admitted")
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc="upper center", ncol=3, bbox_to_anchor=(0.5, 0.0))
    fig.tight_layout()
    obs = lambda a, f: s[f"a={a}|far={f}|obs+"]["exposure"]["mean"]  # noqa: E731
    ann = lambda a: s[f"a={a}|far=0.0|ann+"]["exposure"]["mean"]  # noqa: E731
    save(fig, "h2_exposure", "H2 — eligibility under forged and missing metadata",
         f"Share of truly unsafe tools (silver labels) admitted by a read-only policy, 569-tool registry, "
         f"5 seeds. MCP's default reading (ann+) admits {ann(0.0):.1%} with honest servers and "
         f"{ann(0.5):.0%} when half the servers forge `readOnlyHint`; reading a missing hint as safe (ann-cw) "
         f"admits {s['a=0.0|far=0.0|ann-cw']['exposure']['mean']:.0%}. Verified evidence (obs+) admits "
         f"{obs(0.0, 0.0):.0%} at a perfect verifier for every forgery rate, rising with the false-accept "
         f"rate ({obs(0.5, 0.05):.1%} at 5%, {obs(0.5, 0.2):.0%} at 20%). Source: results/e2_eligibility.json.")


# --------------------------------------------------------------------------- H3
NAMES3 = {"ours": "TaaS", "ours-nogap": "no gap analysis", "ours-strict": "strict profile",
          "per-subtask": "per-subtask", "per-subtask-gap": "per-subtask, gap goals", "rag-top3": "RAG top-3",
          "rag-top5": "RAG top-5", "mcp-zero": "MCP-Zero"}
GROUP3 = {"ours": ("TaaS (this paper)", SLOTS[0], "o"), "ours-nogap": ("TaaS ablations", SLOTS[1], "s"),
          "ours-strict": ("TaaS ablations", SLOTS[1], "s")}
# Label placement per panel: ("off", dx, dy, ha) in points from the mark, or ("data", x, y, ha) with a
# leader line; None = no label (the two ablations share one label because their marks coincide).
ABL = "no gap analysis,\nstrict profile"
LAB3 = {
    "LiveMCPBench": {"ours": ("off", -7, 0, "right"), "ours-nogap": ("data", 98, 0.105, "right", ABL),
                     "ours-strict": None, "per-subtask-gap": ("data", 250, 0.125, "center"),
                     "per-subtask": ("off", 0, 9, "center"), "mcp-zero": ("off", 6, -3, "left"),
                     "rag-top3": ("off", 6, -3, "left"), "rag-top5": ("off", 6, 0, "left")},
    "MCPToolBench++": {"ours": ("data", 60, 0.47, "right"), "ours-nogap": ("data", 60, 0.27, "right", ABL),
                       "ours-strict": None, "per-subtask": ("off", 0, 9, "center"),
                       "per-subtask-gap": ("data", 330, 0.36, "left"), "mcp-zero": ("off", 6, -2, "left"),
                       "rag-top3": ("off", 6, 0, "left"), "rag-top5": ("off", -6, 0, "right")},
}


def fig_h3():
    d = load("e3_gap_sonnet")
    if not d:
        return
    fig, axes = plt.subplots(1, 2, figsize=(7.1, 2.75), sharey=True)
    panels = [("LiveMCPBench", "a   LiveMCPBench — 95 tasks (test)"),
              ("MCPToolBench++", "b   MCPToolBench++ — 60 queries (dev)")]
    for ax, (src, title) in zip(axes, panels):
        ax.set_xscale("log")
        ax.set_xlim(30, 3000)
        ax.set_ylim(0, 0.7)
        for s, name in NAMES3.items():
            m = d["summary"][f"{src}|{s}"]
            x, y, e = m["tokens"]["mean"], m["recall"]["mean"], m["recall"]["ci95"]
            lab, col, mk = GROUP3.get(s, ("retrieval baselines", MUTED, "D"))
            ax.errorbar(x, y, yerr=e, fmt="none", ecolor=col, elinewidth=0.7, alpha=0.55, zorder=2)
            ax.scatter(x, y, s=34, marker=mk, color=col, edgecolor=SURFACE, linewidth=1.1,
                       zorder=4 if s == "ours" else 3, label=lab)
            spec = LAB3[src][s]
            if spec is None:
                continue
            text = spec[4] if len(spec) > 4 else name
            if spec[0] == "off":
                ax.annotate(text, (x, y), xytext=(spec[1], spec[2]), textcoords="offset points", fontsize=6.5,
                            color=INK2, ha=spec[3], va="center")
            else:
                ax.annotate(text, (x, y), xytext=(spec[1], spec[2]), textcoords="data", fontsize=6.5, color=INK2,
                            ha=spec[3], va="center",
                            arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.5, shrinkA=2, shrinkB=4))
        allm = d["summary"][f"{src}|all-tools"]
        ax.text(0.98, 0.96, f"all 569 tools: {allm['tokens']['mean'] / 1000:.0f}k tokens,\nrecall "
                f"{allm['recall']['mean']:.2f} (off scale)", transform=ax.transAxes, ha="right", va="top",
                fontsize=6.5, color=INK2)
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.1f}"))
        ax.set_xlabel("context tokens of the exposed tool definitions (log scale)")
        ax.set_title(title)
        grid(ax, "both")
    axes[0].set_ylabel("gold tool recall (95% CI)")
    h, l = axes[0].get_legend_handles_labels()
    uniq = dict(zip(l, h))
    fig.legend(uniq.values(), uniq.keys(), loc="upper center", ncol=3, bbox_to_anchor=(0.5, 0.0))
    fig.tight_layout()
    S = d["summary"]
    lv = lambda s, k: S[f"LiveMCPBench|{s}"][k]["mean"]  # noqa: E731
    save(fig, "h3_tokens_vs_recall", "H3 — toolkit size against gold-tool recall",
         f"Mean context tokens of the exposed tool definitions against gold-tool recall; recorded Claude "
         f"Sonnet analyst, 569-tool registry. On LiveMCPBench TaaS exposes {lv('ours', 'tokens'):.0f} tokens "
         f"for recall {lv('ours', 'recall'):.3f}; per-subtask retrieval {lv('per-subtask', 'tokens'):.0f} tokens "
         f"for {lv('per-subtask', 'recall'):.3f}; RAG top-5 {lv('rag-top5', 'tokens'):.0f} tokens for "
         f"{lv('rag-top5', 'recall'):.3f}. Without gap analysis TaaS uses {lv('ours-nogap', 'size'):.2f} tools "
         f"instead of {lv('ours', 'size'):.2f}. Source: results/e3_gap_sonnet.json.")


# --------------------------------------------------------------------------- H4
def _label4(n):
    if n.startswith("certified"):
        mode = "conservative (L)" if "cons" in n else "derivation (L)"
        far = n.split("FAR=")[1].rstrip(")")
        return f"certified, {mode}, FAR {float(far):.0%}"
    return {"per-subtask": "per-subtask retrieval", "rag-top5": "RAG-MCP top-5", "mcp-zero": "MCP-Zero routing",
            "all-tools": "all 569 tools"}.get(n, n)


def fig_h4():
    d = load("e4_injection")
    if not d:
        return
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.1, 2.45), gridspec_kw={"width_ratios": [1.4, 1]})
    names = list(d["summary"])
    a1.set_xlim(0, 1.13)
    a1.set_ylim(len(names) - 0.45, -0.55)
    for i, n in enumerate(names):
        v = d["summary"][n]["ASR_worst_out"]["mean"]
        hbar(a1, i, v, 0.62, SLOTS[0] if n.startswith("certified") else MUTED)
        end_label(a1, v, i, f"{v:.3f}")
    a1.set_yticks(range(len(names)), [_label4(n) for n in names])
    a1.tick_params(axis="y", length=0)
    a1.xaxis.set_major_formatter(PCT)
    a1.set_xlabel("out-of-scope injected actions that can succeed (worst case)")
    a1.set_title("a   Attack success through the exposed toolkit")
    grid(a1, "x")
    p1 = d["property1"]
    keys = sorted(p1, key=lambda k: ("deriv" in k, k))
    a2.set_xlim(0, 0.215)
    a2.set_ylim(len(keys) - 0.45, -0.55)
    for i, k in enumerate(keys):
        v = p1[k]["flow_violations"] / p1[k]["sequences"]
        hbar(a2, i, v, 0.62, SLOTS[0] if "cons" in k else SLOTS[1])
        end_label(a2, v, i, f"{v:.1%}")
    a2.set_yticks(range(len(keys)), [_label4(k).replace("certified, ", "") for k in keys])
    a2.tick_params(axis="y", length=0)
    a2.xaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    a2.set_xlabel("random call sequences realising a forbidden flow")
    total = sum(v["sequences"] for v in p1.values())
    eff = sum(v["effect_violations"] for v in p1.values())
    a2.set_title("b   Property 1 at run time")
    a2.text(0.98, 0.97, f"effect-bound violations:\n{eff} of {total:,} sequences", transform=a2.transAxes,
            ha="right", va="top", fontsize=6.5, color=INK2)
    grid(a2, "x")
    fig.tight_layout(w_pad=2.0)
    S = d["summary"]
    der = [p1[k]["flow_violations"] / p1[k]["sequences"] for k in keys if "deriv" in k]
    save(fig, "h4_injection", "H4 — injected actions and Property 1",
         f"(a) Share of injected actions outside the task's needed effect classes (exfiltrate, destroy, "
         f"execute, pay, tamper) that some exposed tool can truly realise; least-privilege policy per task, "
         f"evidence at least obs, 3 verifier seeds. Certified toolkits: {S[names[0]]['ASR_worst_out']['mean']:.3f}; "
         f"RAG-MCP top-5 {S['rag-top5']['ASR_worst_out']['mean']:.3f}; all tools 1.000. (b) Random call sequences "
         f"over certified toolkits with true effects: no effect-bound violation in {total:,} sequences; certifying "
         f"(L) along derivations only lets {min(der):.1%}–{max(der):.1%} of sequences realise a forbidden flow, "
         f"the conservative reading none. Source: results/e4_injection.json.")


# --------------------------------------------------------------------------- calibration
def fig_calibration():
    d = load("calibration_table")
    if not d:
        return
    panels = [("aggregate_sum", "a   exact sum", True), ("count", "b   exact count", True),
              ("classify", "c   majority sentiment", False), ("extract", "d   record look-up", False)]
    # Haiku drawn first with the larger marker so Sonnet stays visible where the two coincide.
    models = [("haiku", "Claude Haiku", SLOTS[1], "s", 5.2, 1.5), ("sonnet", "Claude Sonnet", SLOTS[0], "o", 3.2, 1.2)]
    fig, axes = plt.subplots(1, 4, figsize=(7.1, 2.05), sharey=True)
    for ax, (c, title, exact) in zip(axes, panels):
        if exact:
            ax.axvspan(20, 1000, color=BAND, lw=0, zorder=0)
        ax.axhline(0.9, color=MUTED, lw=0.7, zorder=1)
        for key, lab, col, mk, ms, lw in models:
            t = d.get(key, {}).get(c)
            if not t:
                continue
            ns = sorted(int(n) for n in t)
            ax.plot(ns, [t[str(n)] for n in ns], color=col, marker=mk, ms=ms, lw=lw, mec=SURFACE, mew=0.6,
                    label=lab, zorder=3)
        ax.set_xscale("log")
        ax.set_xlim(7, 900)
        ax.set_xticks([10, 40, 160, 640], ["10", "40", "160", "640"])
        ax.minorticks_off()
        ax.set_ylim(-0.03, 1.08)
        ax.set_xlabel("items in context (n)")
        ax.set_title(title)
        grid(ax)
    axes[2].text(8, 0.875, "τ = 0.9", fontsize=6.5, color=INK2, va="top")
    axes[0].set_ylabel("accuracy (4 items per point)")
    axes[0].yaxis.set_major_formatter(PCT)
    from matplotlib.patches import Patch
    h, l = axes[0].get_legend_handles_labels()
    h, l = h[::-1], l[::-1]
    h.append(Patch(facecolor=BAND, edgecolor="none"))
    l.append("rule 1: exact classes never native beyond n = 20")
    fig.legend(h, l, loc="upper center", ncol=3, bbox_to_anchor=(0.5, 0.0))
    fig.tight_layout()
    hs = d["haiku"]["aggregate_sum"]
    save(fig, "rho_calibration", "Measured reliability profiles ρ_LLM",
         f"Accuracy answering by reading alone, per class and input size; 4 items per point, answered by "
         f"session sub-agents with the Read tool only. Claude Sonnet is exact at every size; Claude Haiku's exact "
         f"sum falls from {hs['40']:.0%} at n = 40 to {hs['160']:.0%} at n = 160 and {hs['640']:.0%} at n = 640. "
         f"The shaded band is where rule 1 forbids native exact classes whatever was measured. "
         f"Source: results/calibration_table.json.")


# --------------------------------------------------------------------------- tuning
def fig_tune():
    d = load("e3_tune")
    if not d:
        return
    g = d["grid"]
    rels = sorted({float(k.split("rel=")[1]) for k in g})
    Ks = sorted({int(k.split("|")[0][2:]) for k in g})
    fig, ax = plt.subplots(figsize=(3.45, 2.35))
    ends = defaultdict(list)
    for i, r in enumerate(rels):
        ys = [g[f"K={K}|rel={r}"]["recall"]["mean"] for K in Ks]
        lab = f"w_rel = {r:g}" + ("  (Eq. 6)" if r == 0 else "")
        ax.plot(Ks, ys, color=ORDINAL4[i], marker=MARKERS[i], mec=SURFACE, mew=0.7, label=lab, zorder=3)
        ends[round(ys[-1], 4)].append(f"{r:g}")
    for y, rs in ends.items():
        end_label(ax, Ks[-1], y, "w_rel = " + ", ".join(rs), dx=5)
    sel = d["selected"]
    sK, sr = int(sel.split("|")[0][2:]), float(sel.split("rel=")[1])
    sy = g[sel]["recall"]["mean"]
    ax.scatter([sK], [sy], s=120, facecolor="none", edgecolor=INK, linewidth=0.8, zorder=4)
    ax.annotate("selected on dev", (sK, sy), xytext=(0, 10), textcoords="offset points", ha="center",
                fontsize=6.5, color=INK)
    ax.set_xticks(Ks)
    ax.set_xlim(2.4, 12.6)
    ax.set_ylim(0, 0.5)
    ax.set_xlabel("retrieval budget K per goal")
    ax.set_ylabel("gold recall, dev split")
    ax.legend(loc="lower left", fontsize=6.5)
    grid(ax)
    fig.tight_layout()
    e6 = load("e6_ablations")
    tail = ""
    if e6:
        p = e6["path"]
        tail = (f" On the test split pure Eq. 6 gives recall {p['pure Eq.6 (w_rel=0)']['recall']['mean']:.3f} against "
                f"{p['full (dev-tuned)']['recall']['mean']:.3f} with the selected setting.")
    save(fig, "tune_relevance", "Relevance term in the cost (dev-split tuning)",
         f"Gold recall on the MCPToolBench++ dev sample (60 queries) for retrieval budget K and relevance weight "
         f"w_rel added to Eq. 6. Under pure Eq. 6 recall falls as K grows "
         f"({g['K=3|rel=0.0']['recall']['mean']:.2f} → {g['K=10|rel=0.0']['recall']['mean']:.2f}), because the "
         f"cheapest type-compatible tool wins. Selected: K = {sK}, w_rel = {sr:g}.{tail} Source: results/e3_tune.json.")


# --------------------------------------------------------------------------- latency
def fig_latency():
    d = load("e7_scalability")
    if not d:
        return
    lat = d["latency"]
    ns = sorted(int(n) for n in lat)
    fig, ax = plt.subplots(figsize=(3.45, 2.35))
    series = [("bitmap_us", "bitmap intersection (Eq. 3)", SLOTS[0], "o"), ("naive_us", "scan of every tool",
                                                                           SLOTS[1], "s")]
    for key, lab, col, mk in series:
        ys = [lat[str(n)][key] for n in ns]
        ax.plot(ns, ys, color=col, marker=mk, mec=SURFACE, mew=0.7, label=lab, zorder=3)
        end_label(ax, ns[-1], ys[-1], f"{ys[-1]:,.0f} µs" if ys[-1] >= 10 else f"{ys[-1]:.1f} µs", dx=5)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(700, 4e5)
    ax.set_xlabel("registry size (tools)")
    ax.set_ylabel("eligibility latency (µs, log)")
    ax.legend(loc="upper left", fontsize=6.5)
    grid(ax, "both")
    fig.tight_layout()
    big = lat[str(ns[-1])]
    p3 = d["prop3"]["confusion"]
    save(fig, "eligibility_latency", "Eligibility cost and exactness (RQ4)",
         f"Time to compute the eligible set for three properties. At {ns[-1]:,} tools the bitmap answers in "
         f"{big['bitmap_us']:.1f} µs against {big['naive_us'] / 1000:.0f} ms for a scan (×{big['speedup']:,.0f}); "
         f"the two return identical sets. Proposition 3 over {sum(p3.values()):,} (event, cache entry) checks: "
         f"{p3['changed&kept']} stale entries kept, {p3['same&invalidated']} needless invalidations. Wall-clock, "
         f"one run on 2 CPUs. Source: results/e7_scalability.json.")


# --------------------------------------------------------------------------- E5
NAMES5 = {"ours-exact": "exact (branch-and-bound)", "ours-greedy": "greedy cover", "ours-no-closure":
          "no backward closure", "per-subtask": "per-subtask retrieval"}


def fig_e5():
    d = load("e5_synthetic")
    if not d:
        return
    S = d["summary"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.1, 2.2), gridspec_kw={"width_ratios": [1.25, 1]})
    names = [n for n in NAMES5 if n in S]
    a1.set_xlim(0, 1.15)
    a1.set_ylim(len(names) - 0.45, -0.55)
    for i, n in enumerate(names):
        v = S[n]["valid_rate"]
        hbar(a1, i, v, 0.6, SLOTS[0])
        end_label(a1, v, i, f"{v:.0%}")
    a1.set_yticks(range(len(names)), [NAMES5[n] for n in names])
    a1.tick_params(axis="y", length=0)
    a1.xaxis.set_major_formatter(PCT)
    a1.set_xlabel("valid toolkits (independent checker)")
    a1.set_title("a   All 48 synthetic tasks")
    grid(a1, "x")
    by = defaultdict(lambda: defaultdict(list))
    for r in d["rows"]:
        by[r["system"]][r["L"]].append(bool(r["valid"]))
    Ls = sorted({r["L"] for r in d["rows"]})
    # drawn back to front: per-subtask (large marker) under exact (small marker) where both are 100%
    lines = {}
    for j, n, ms in ((2, "per-subtask", 5.4), (1, "ours-no-closure", 4.5), (0, "ours-exact", 3.2)):
        ys = [sum(by[n][L]) / len(by[n][L]) for L in Ls]
        lines[n], = a2.plot(Ls, ys, color=SLOTS[j], marker=MARKERS[j], ms=ms, mec=SURFACE, mew=0.6,
                            label=NAMES5[n], zorder=3)
    a2.set_xticks(Ls)
    a2.set_xlim(Ls[0] - 0.3, Ls[-1] + 0.3)
    a2.set_ylim(-0.04, 1.08)
    a2.yaxis.set_major_formatter(PCT)
    a2.set_xlabel("hidden chain length L")
    a2.set_ylabel("valid toolkits")
    a2.set_title("b   By chain length")
    order = ["ours-exact", "ours-no-closure", "per-subtask"]
    a2.legend([lines[n] for n in order], [NAMES5[n] for n in order], loc="center left", fontsize=6.5,
              bbox_to_anchor=(0.0, 0.55), title="greedy cover identical to exact", title_fontsize=6.5)
    grid(a2)
    fig.tight_layout(w_pad=2.0)
    save(fig, "e5_composition", "Composition on synthetic typed registries (RQ3)",
         f"Hidden typed chains with five kinds of distractor; validity graded by an independent checker, optimum "
         f"by brute force. Exact and greedy regimes: {S['ours-exact']['valid_rate']:.0%} valid and "
         f"{S['ours-exact']['optimal_rate']:.0%} optimal; without backward closure "
         f"{S['ours-no-closure']['valid_rate']:.1%}; per-subtask retrieval {S['per-subtask']['valid_rate']:.1%}. "
         f"Source: results/e5_synthetic.json.")


# --------------------------------------------------------------------------- E6
NAMES6 = {"pure Eq.6 (w_rel=0)": "pure Eq. 6 (no relevance term)", "Alg.1 literal ctx": "Algorithm 1 read literally",
          "strict profile (rule 2)": "strict rule 2 (unmeasured = not native)", "Haiku analyst": "Claude Haiku analyst",
          "Haiku profile": "Claude Haiku ρ profile", "closure depth 0": "no backward closure",
          "derivation-mode flow": "derivation-mode (L)", "rule 1 off (exact_n_max=1e9)": "rule 1 off"}


def fig_e6():
    d = load("e6_ablations")
    if not d:
        return
    P = d["path"]
    full = "full (dev-tuned)"
    others = sorted([k for k in P if k != full], key=lambda k: P[k]["recall"]["mean"])
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.1, 2.9), sharey=True)
    for ax, key, xl, fmt in ((a1, "recall", "gold recall", "{:.3f}"), (a2, "size", "tools exposed |K|", "{:.2f}")):
        ref = P[full][key]["mean"]
        ax.axvline(ref, color=MUTED, lw=0.8, zorder=1)
        for i, k in enumerate(others):
            v = P[k][key]["mean"]
            ax.plot([ref, v], [i, i], color=GRID, lw=2.2, solid_capstyle="round", zorder=2)
            ax.scatter([v], [i], s=26, color=SLOTS[0], edgecolor=SURFACE, linewidth=1.0, zorder=3)
        ax.annotate(f"full model {fmt.format(ref)}", (ref, -0.5), xytext=(3, 0),
                    textcoords="offset points", fontsize=6.5, color=INK2, va="center")
        ax.set_xlabel(xl)
        grid(ax, "x")
    a1.set_yticks(range(len(others)), [NAMES6.get(k, k) for k in others])
    a1.tick_params(axis="y", length=0)
    a1.set_ylim(-0.85, len(others) - 0.45)
    a1.set_xlim(0.05, 0.21)
    a2.set_xlim(1.2, 2.05)
    a1.set_title("a   Gold recall, LiveMCPBench test split")
    a2.set_title("b   Toolkit size")
    fig.tight_layout(w_pad=1.5)
    save(fig, "e6_ablations", "Request-path ablations",
         f"Each variant changes one component of the dev-tuned system (vertical line); recorded Claude Sonnet "
         f"analyst unless stated, 95 LiveMCPBench tasks. Removing the relevance term (pure Eq. 6) cuts recall from "
         f"{P[full]['recall']['mean']:.3f} to {P['pure Eq.6 (w_rel=0)']['recall']['mean']:.3f}; reading Algorithm 1 "
         f"literally or treating unmeasured classes as non-native (strict rule 2) leaves recall close but raises "
         f"|K| to {P['Alg.1 literal ctx']['size']['mean']:.2f} and {P['strict profile (rule 2)']['size']['mean']:.2f}. "
         f"Source: results/e6_ablations.json.")
    R = d["retrieval"]
    fig, ax = plt.subplots(figsize=(3.45, 2.3))
    rets = list(R)
    ks = ["R@1", "R@3", "R@5"]
    w = 0.24
    ax.set_xlim(-0.55, len(rets) - 0.45)
    ax.set_ylim(0, 0.75)
    for j, k in enumerate(ks):
        for i, r in enumerate(rets):
            vbar(ax, i + (j - 1) * (w + 0.03), R[r][k], w, ORDINAL3[j])
        ax.bar([0], [0], color=ORDINAL3[j], label=k)  # legend proxy
    ax.set_xticks(range(len(rets)), ["BM25 (lexical)", "dense (LSA)", "RRF fusion"])
    ax.tick_params(axis="x", length=0)
    ax.yaxis.set_major_formatter(PCT)
    ax.set_ylabel("gold tool in top k")
    ax.legend(loc="upper right", ncol=3, fontsize=6.5)
    grid(ax)
    fig.tight_layout()
    save(fig, "e6_retrieval", "Retrieval components",
         f"Raw-query retrieval over the 569-tool registry for all 1,509 MCPToolBench++ requests. BM25 alone reaches "
         f"R@5 = {R['lex']['R@5']:.3f}; the LSA dense stand-in for BGE-M3 {R['den']['R@5']:.3f}; reciprocal-rank "
         f"fusion {R['rrf(lex+den)']['R@5']:.3f}, below BM25 because the dense component is weak. "
         f"Source: results/e6_ablations.json.")


# --------------------------------------------------------------------------- Codex regression
ROWS_REG = [("LiveMCPBench|ours", "TaaS, LiveMCPBench"), ("LiveMCPBench|ours-nogap", "no gap analysis, LiveMCPBench"),
            ("LiveMCPBench|ours-strict", "strict profile, LiveMCPBench"), ("MCPToolBench++|ours", "TaaS, MCPToolBench++")]


def fig_regression():
    fixed, codex = load("e3_gap_sonnet"), load("e3_gap_sonnet_codex")
    if not (fixed and codex):
        return
    series = [("this fix (= published baseline)", fixed, SLOTS[0]),
              ("feature/taas-mcpbench-integration as shipped", codex, SLOTS[1])]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.1, 2.4), sharey=True)
    h = 0.34
    for ax, metric, xl, xmax in ((a1, "abstain_rate", "requests abstained", 0.8),
                                 (a2, "recall", "gold tool recall", 0.48)):
        ax.set_xlim(0, xmax)
        ax.set_ylim(len(ROWS_REG) - 0.4, -0.6)
        for j, (lab, d, col) in enumerate(series):
            for i, (key, _) in enumerate(ROWS_REG):
                m = d["summary"][key]
                v = m[metric] if metric == "abstain_rate" else m[metric]["mean"]
                y = i + (j - 0.5) * (h + 0.04)
                hbar(ax, y, v, h, col)
                end_label(ax, v, y, f"{v:.0%}" if metric == "abstain_rate" else f"{v:.3f}")
            ax.bar([0], [0], color=col, label=lab)
        ax.set_xlabel(xl)
        if metric == "abstain_rate":
            ax.xaxis.set_major_formatter(PCT)
        grid(ax, "x")
    a1.set_yticks(range(len(ROWS_REG)), [r[1] for r in ROWS_REG])
    a1.tick_params(axis="y", length=0)
    a1.set_title("a   Abstention")
    a2.set_title("b   Gold recall")
    h_, l_ = a1.get_legend_handles_labels()
    fig.legend(h_, l_, loc="upper center", ncol=2, bbox_to_anchor=(0.5, 0.0))
    fig.tight_layout(w_pad=1.5)
    f, c = fixed["summary"]["LiveMCPBench|ours"], codex["summary"]["LiveMCPBench|ours"]
    save(fig, "codex_binding_regression", "Binding-check regression in the Codex integration branch",
         f"E3 re-run unchanged on two code versions. The witness-binding check added in commit 3a8a28e rejects "
         f"valid certificates, so TaaS abstains on {c['abstain_rate']:.0%} of LiveMCPBench tasks instead of "
         f"{f['abstain_rate']:.0%} and recall falls from {f['recall']['mean']:.3f} to {c['recall']['mean']:.3f}. "
         f"The fix reproduces all 337 compared baseline numbers. Sources: results/e3_gap_sonnet.json, "
         f"results/e3_gap_sonnet_codex.json.")


# --------------------------------------------------------------------------- E8
AN8 = [("prompt-1.0", "prompt 1.0 (Codex)"), ("prompt-1.1", "prompt 1.1, aligned types"),
       ("prompt-1.1+theta", "prompt 1.1 + registry Θ"), ("guide", "E3 analyst guide")]
POL8 = [("default", "benchmark-default policy", SLOTS[0]), ("open", "open policy", SLOTS[1])]


def fig_e8():
    d = load("e8_mcpbench_adapter_fixed")
    if not d:
        return
    S = d["summary"]
    ans = [a for a in AN8 if f"{a[0]}|lexical|default" in S]
    fig, axes = plt.subplots(2, 2, figsize=(7.1, 3.9), sharey=True)
    h = 0.34
    spec = [("runner_abstain", "tasks skipped (abstain or empty)", 1.12, True, "skipped"),
            ("recall", "gold tool recall (skipped = 0)", 0.26, False, "recall")]
    for r, (metric, xl, xmax, pct, mlab) in enumerate(spec):
        for c, (typing, tlab) in enumerate((("lexical", f"{mlab} · lexical typing (adapter default)"),
                                            ("llm", f"{mlab} · LLM-assisted typing (Section 6.1)"))):
            ax = axes[r, c]
            ax.set_xlim(0, xmax)
            ax.set_ylim(len(ans) - 0.4, -0.6)
            for j, (pol, plab, col) in enumerate(POL8):
                for i, (an, _) in enumerate(ans):
                    v = S[f"{an}|{typing}|{pol}"][metric]
                    y = i + (j - 0.5) * (h + 0.04)
                    hbar(ax, y, v, h, col)
                    end_label(ax, v, y, f"{v:.0%}" if pct else f"{v:.3f}")
                if r == 0 and c == 0:
                    ax.bar([0], [0], color=col, label=plab)
            if pct:
                ax.xaxis.set_major_formatter(PCT)
            ax.set_xlabel(xl)
            ax.set_title(f"{'abcd'[2 * r + c]}   {tlab}")
            grid(ax, "x")
    for r in range(2):
        axes[r, 0].set_yticks(range(len(ans)), [a[1] for a in ans])
        axes[r, 0].tick_params(axis="y", length=0)
    hh, ll = axes[0, 0].get_legend_handles_labels()
    fig.legend(hh, ll, loc="upper center", ncol=2, bbox_to_anchor=(0.5, 0.0))
    fig.tight_layout(h_pad=1.2, w_pad=1.5)
    g = lambda k, m: S[k][m]  # noqa: E731
    save(fig, "e8_adapter", "MCP-Bench integration path, offline",
         f"TaaSMCPBenchAdapter.select on the 525-tool LiveMCPTool catalogue in MCP-Bench's tool-map shape, 95 "
         f"LiveMCPBench tasks, recorded Claude Sonnet analyst runs, fixed code. With the Codex defaults (prompt 1.0, "
         f"lexical typing, benchmark-default policy) {g('prompt-1.0|lexical|default', 'runner_abstain'):.0%} of tasks "
         f"are skipped. Aligning the prompt's vocabulary, passing Θ, typing contracts and opening the policy brings this "
         f"to {g('prompt-1.1+theta|llm|open', 'runner_abstain'):.0%} (recall "
         f"{g('prompt-1.1+theta|llm|open', 'recall'):.3f}); the E3 analyst guide reaches "
         f"{g('guide|llm|open', 'runner_abstain'):.0%} (recall {g('guide|llm|open', 'recall'):.3f}). "
         f"Source: results/e8_mcpbench_adapter_fixed.json.")


FIGURES = [fig_h2, fig_h3, fig_h4, fig_calibration, fig_tune, fig_latency, fig_e5, fig_e6, fig_regression, fig_e8]


def write_index() -> None:
    lines = ["# Figures", "",
             "Generated by `experiments/plot.py` from `results/*.json` (no experiment is run). Each figure is in "
             "`results/figures/` as PNG (300 dpi) and PDF (vector). Captions are generated from the same JSON. "
             "Colours: validated reference palette (categorical slots in fixed order; one-hue ordinal ramps for "
             "ordered series); identity is also carried by marker shape or direct labels, and every number is "
             "tabulated in [RESULTS.md](RESULTS.md).", ""]
    for i, (stem, title, cap) in enumerate(WRITTEN, 1):
        lines += [f"## Figure {i} — {title}", "", f"![{title}](../results/figures/{stem}.png)", "",
                  cap, "", f"Files: `results/figures/{stem}.png`, `results/figures/{stem}.pdf`", ""]
    (ROOT / "docs" / "FIGURES.md").write_text("\n".join(lines))


def main() -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    WRITTEN.clear()
    for f in FIGURES:
        f()
    write_index()
    print(f"{len(WRITTEN)} figures written to {FIG} (PNG + PDF); index: docs/FIGURES.md")


if __name__ == "__main__":
    main()
