"""Figures for docs/RESULTS.md from results/*.json (matplotlib, colour-blind-safe palette)."""
from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from common import RESULTS  # noqa: E402

FIG = RESULTS / "figures"
PAL = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00", "#F0E442", "#000000"]
plt.rcParams.update({"figure.dpi": 150, "axes.spines.top": False, "axes.spines.right": False, "font.size": 9})


def load(name):
    p = RESULTS / f"{name}.json"
    return json.load(open(p)) if p.exists() else None


def fig_h2():
    d = load("e2_eligibility")
    if not d:
        return
    fars = sorted({r["far"] for r in d["rows"]})
    fig, axes = plt.subplots(1, 2, figsize=(8.2, 3.2), sharey=True)
    for ax, a in zip(axes, (0.0, 0.25)):
        for i, e in enumerate(["ann+", "ann-cw", "lex+", "lex-cw", "obs+", "att+"]):
            ys = [d["summary"][f"a={a}|far={f}|{e}"]["exposure"]["mean"] for f in fars]
            ax.plot(fars, ys, marker="o", ms=3, color=PAL[i], label=e, lw=2 if e == "obs+" else 1.2)
        ax.set_title(f"{int(a * 100)}% of servers forge metadata")
        ax.set_xlabel("verifier false-accept rate (FAR)")
    axes[0].set_ylabel("exposure: unsafe tools admitted")
    axes[1].legend(frameon=False, fontsize=8, ncol=2)
    fig.tight_layout()
    fig.savefig(FIG / "h2_exposure.png")
    plt.close(fig)


def fig_h3():
    d = load("e3_gap_sonnet")
    if not d:
        return
    fig, ax = plt.subplots(figsize=(5.2, 3.4))
    systems = [s for s in ["ours", "ours-nogap", "ours-strict", "per-subtask", "per-subtask-gap", "rag-top3",
                           "rag-top5", "mcp-zero"] if f"LiveMCPBench|{s}" in d["summary"]]
    for i, s in enumerate(systems):
        m = d["summary"][f"LiveMCPBench|{s}"]
        ax.errorbar(m["tokens"]["mean"], m["recall"]["mean"], yerr=m["recall"]["ci95"], fmt="o",
                    color=PAL[i % len(PAL)], ms=6 if s.startswith("ours") else 4, capsize=2)
        ax.annotate(s, (m["tokens"]["mean"], m["recall"]["mean"]), xytext=(4, 3), textcoords="offset points",
                    fontsize=7)
    ax.set_xscale("log")
    ax.set_xlabel("context tokens of exposed tool definitions (log)")
    ax.set_ylabel("gold tool recall (LiveMCPBench, test)")
    fig.tight_layout()
    fig.savefig(FIG / "h3_tokens_vs_recall.png")
    plt.close(fig)


def fig_h4():
    d = load("e4_injection")
    if not d:
        return
    names = list(d["summary"])
    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    ys = [d["summary"][n]["ASR_worst_out"]["mean"] for n in names]
    ax.barh(range(len(names)), ys, color=[PAL[0] if n.startswith("certified") else PAL[1] for n in names])
    ax.set_yticks(range(len(names)), names, fontsize=7)
    ax.invert_yaxis()
    ax.set_xlabel("worst-case success of out-of-scope injected actions")
    for i, y in enumerate(ys):
        ax.text(y + 0.01, i, f"{y:.3f}", va="center", fontsize=7)
    fig.tight_layout()
    fig.savefig(FIG / "h4_injection.png")
    plt.close(fig)


def fig_calibration():
    d = load("calibration_table")
    if not d:
        return
    fig, axes = plt.subplots(1, 4, figsize=(9, 2.4), sharey=True)
    for ax, c in zip(axes, ["aggregate_sum", "count", "classify", "extract"]):
        for i, (m, t) in enumerate(d.items()):
            ns = sorted(int(n) for n in t[c])
            ax.plot(ns, [t[c][str(n)] for n in ns], marker="o", ms=3, color=PAL[i], label=m)
        ax.axhline(0.9, color="grey", lw=.6, ls="--")
        ax.set_xscale("log")
        ax.set_title(c, fontsize=8)
        ax.set_xlabel("n items")
    axes[0].set_ylabel("measured ρ")
    axes[-1].legend(frameon=False, fontsize=7)
    fig.tight_layout()
    fig.savefig(FIG / "rho_calibration.png")
    plt.close(fig)


def fig_tune():
    d = load("e3_tune")
    if not d:
        return
    fig, ax = plt.subplots(figsize=(4.2, 2.8))
    rels = sorted({float(k.split("rel=")[1]) for k in d["grid"]})
    Ks = sorted({int(k.split("|")[0][2:]) for k in d["grid"]})
    for i, r in enumerate(rels):
        ax.plot(Ks, [d["grid"][f"K={K}|rel={r}"]["recall"]["mean"] for K in Ks], marker="o", ms=3, color=PAL[i],
                label=f"w_rel={r:g}" + (" (Eq. 6)" if r == 0 else ""))
    ax.set_xlabel("retrieval budget K per goal")
    ax.set_ylabel("gold recall (dev)")
    ax.legend(frameon=False, fontsize=7)
    fig.tight_layout()
    fig.savefig(FIG / "tune_relevance.png")
    plt.close(fig)


def fig_latency():
    d = load("e7_scalability")
    if not d:
        return
    ns = sorted(int(n) for n in d["latency"])
    fig, ax = plt.subplots(figsize=(4.2, 2.8))
    ax.plot(ns, [d["latency"][str(n)]["bitmap_us"] for n in ns], marker="o", color=PAL[0], label="bitmap (Eq. 3)")
    ax.plot(ns, [d["latency"][str(n)]["naive_us"] for n in ns], marker="s", color=PAL[1], label="naive scan")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("registry size (tools)")
    ax.set_ylabel("eligibility latency (µs)")
    ax.legend(frameon=False, fontsize=7)
    fig.tight_layout()
    fig.savefig(FIG / "eligibility_latency.png")
    plt.close(fig)


def main() -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    for f in (fig_h2, fig_h3, fig_h4, fig_calibration, fig_tune, fig_latency):
        f()
    print("figures written to", FIG)


if __name__ == "__main__":
    main()
