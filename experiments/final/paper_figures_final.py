"""Composite figures for the paper's Experimental Evaluation section (results/final/figures/paper_*.pdf)."""
from __future__ import annotations

import json
import sys

import numpy as np

import fe

sys.path.insert(0, str(fe.ROOT / "experiments"))
import plot as P  # noqa: E402  (style, palette)
import matplotlib.pyplot as plt  # noqa: E402

FIG = fe.RES / "figures"
FIG.mkdir(exist_ok=True)
S = P.SLOTS


def load(n):
    p = fe.RES / f"{n}.json"
    return json.load(open(p)) if p.exists() else None


def save(fig, stem):
    for ext in ("pdf", "png"):
        fig.savefig(FIG / f"{stem}.{ext}", bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)


def eligibility():
    e4, e5, e6 = load("E4_exposure"), load("E5_forgery"), load("E6_verifier")
    fig, axs = plt.subplots(1, 3, figsize=(7.16, 2.15), gridspec_kw={"width_ratios": [1.25, 1, 1]})
    # (a) exposure vs utility per encoding, two retrievers
    R = e4["results"]["1.0"]
    encs = [("no_filter", "no filter / MCP default", "o"), ("closed_world_annotations", "closed-world annotations", "s"),
            ("lexical_positive", "lexical", "^"), ("verified_evidence", "verified evidence", "D"),
            ("attested_only", "attested only", "v")]
    ax = axs[0]
    for j, (ret, rl) in enumerate((("pamcp_rrf", "PaMCP retrieval"), ("mcp_zero", "MCP-Zero"))):
        for i, (e, l, mk) in enumerate(encs):
            v = R[f"{ret}|{e}"]
            ax.scatter(v["Util@5"], v["Exp@5"], marker=mk, s=26, color=S[i], edgecolor=P.SURFACE, linewidth=0.6,
                       label=l if j == 0 else None, alpha=1.0 if j == 0 else 0.55, zorder=3)
        xs = [R[f"{ret}|{e}"]["Util@5"] for e, _, _ in encs]
        ys = [R[f"{ret}|{e}"]["Exp@5"] for e, _, _ in encs]
        ax.annotate(rl, (xs[0], ys[0]), xytext=(4, 4), textcoords="offset points", fontsize=6, color=P.INK2)
    ax.set_xlabel("Util@5 (gold in top-5)")
    ax.set_ylabel("Exp@5 (unsafe tool in top-5)")
    ax.xaxis.set_major_formatter(P.PCT)
    ax.yaxis.set_major_formatter(P.PCT)
    P.grid(ax, "both")
    ax.legend(fontsize=5.5, loc="upper left", handletextpad=0.2, borderaxespad=0.2)
    ax.set_title("(a) Encodings, coverage 1 (faded: MCP-Zero)", fontsize=7)
    # (b) forgery
    ax = axs[1]
    ds = [0.0, 0.05, 0.1, 0.2, 0.3]
    for i, (e, l, mk) in enumerate(encs[:4]):
        ax.plot(ds, [e5["results"][f"both|{d}"][f"pamcp_rrf|{e}"]["Exp@5"] for d in ds], marker=mk, color=S[i], ms=3.5)
    ax.set_xlabel("malicious servers δ")
    ax.xaxis.set_major_formatter(P.PCT)
    ax.yaxis.set_major_formatter(P.PCT)
    P.grid(ax)
    ax.set_title("(b) Forged + laundered metadata", fontsize=7)
    # (c) verifier false accepts
    ax = axs[2]
    phis = [0.0, 0.01, 0.02, 0.05, 0.1, 0.2]
    R6 = e6["results"]
    for i, (pl, l) in enumerate((("random", "random errors"), ("lookalike", "look-alike errors"))):
        ax.plot(phis, [R6[f"0.2|{pl}|0.0|1.0|{p}"]["pamcp_rrf|verified_evidence"]["Exp@5"] for p in phis],
                marker="D" if i == 0 else "d", color=S[3], ls="-" if i == 0 else ":", ms=3.5, label=l)
    ax.axhline(R6["0.2|random|0.0|1.0|0.0"]["pamcp_rrf|lexical_positive"]["Exp@5"], color=S[2], lw=1, ls="--",
               label="lexical")
    ax.set_xlabel("verifier false-accept rate φ")
    ax.xaxis.set_major_formatter(P.PCT)
    ax.yaxis.set_major_formatter(P.PCT)
    P.grid(ax)
    ax.legend(fontsize=5.5, loc="upper left")
    ax.set_title("(c) Imperfect verifier, δ = 20%", fontsize=7)
    fig.tight_layout(w_pad=1.0)
    save(fig, "paper_eligibility")


def retrieval():
    e8 = load("E8_single_tool")
    R = e8["results"]
    fig, axs = plt.subplots(1, 2, figsize=(7.16, 2.45), gridspec_kw={"width_ratios": [1, 1.1]})
    ax = axs[0]
    lab = {"pamcp_contract": "PaMCP (goal contract)", "mcp_zero": "MCP-Zero", "bm25": "BM25", "rrf": "RRF (raw text)",
           "dense_lsa": "dense / RAG-MCP", "colt_adapted": "COLT", "toolscope_adapted": "ToolScope",
           "cmtf_adapted": "CMTF"}
    ms = sorted(R["sample|B1m"], key=lambda m: R["sample|B1m"][m]["hit1"]["mean"])
    for i, m in enumerate(ms):
        for j, (key, col, off) in enumerate((("sample|B1", S[0], 0.17), ("sample|B1m", S[1], -0.17))):
            h = R[key][m]["hit1"]
            ax.errorbar(h["mean"], i + off, xerr=[[h["mean"] - h["ci_target"][0]], [h["ci_target"][1] - h["mean"]]],
                        fmt="o", ms=3, color=col, capsize=1.5, lw=0.8,
                        label=("81-tool B1" if j == 0 else "569-tool registry") if i == 0 else None)
    ax.set_yticks(range(len(ms)), [lab[m] for m in ms], fontsize=6)
    ax.xaxis.set_major_formatter(P.PCT)
    ax.set_xlabel("Hit@1 (95% CI, target-tool clusters)")
    P.grid(ax, "x")
    ax.legend(fontsize=5.5, loc="upper center", bbox_to_anchor=(0.5, -0.36), ncol=2, frameon=False)
    ax.set_title("(a) Single-tool retrieval, 300 requests", fontsize=7)
    ax = axs[1]
    c = R["distractor_curve_hit1"]
    ds = sorted(c, key=int)
    for i, m in enumerate(["pamcp_contract", "mcp_zero", "rrf", "toolscope_adapted", "colt_adapted"]):
        ax.plot([int(d) for d in ds], [c[d][m] for d in ds], marker=P.MARKERS[i], color=S[i], ms=3, label=lab[m])
    ax.set_xlabel("LiveMCPTool distractors added to B1")
    ax.set_ylabel("Hit@1")
    ax.yaxis.set_major_formatter(P.PCT)
    P.grid(ax)
    ax.legend(fontsize=5.5, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.4), frameon=False)
    ax.set_title("(b) Distractor curve (5 seeds)", fontsize=7)
    fig.tight_layout(w_pad=1.0)
    save(fig, "paper_retrieval")


def profile_gap():
    e12, e11 = load("E12_profile"), load("E11_gap")
    fig, axs = plt.subplots(1, 2, figsize=(3.5, 1.8))
    ax = axs[0]
    for i, m in enumerate(("sonnet", "haiku", "opus")):
        v = e12["results"][m]
        xs = [v["self_assessed"][c][n] for c in v["measured"] for n in v["measured"][c]]
        ys = [v["measured"][c][n]["acc"] for c in v["measured"] for n in v["measured"][c]]
        ax.scatter(xs, ys, s=10, marker=P.MARKERS[i], color=S[i], label=m.capitalize(), zorder=3)
    ax.plot([0, 1], [0, 1], color=P.MUTED, lw=0.7, ls="--")
    ax.set_xlabel("self-assessed", fontsize=6.5)
    ax.set_ylabel("measured", fontsize=6.5)
    ax.tick_params(labelsize=6)
    P.grid(ax, "both")
    ax.legend(fontsize=5, loc="lower right", handletextpad=0.1)
    ax.set_title("(a) E12 reliability", fontsize=6.5)
    ax = axs[1]
    R = e11["results"]
    ns = [30, 300, 3000, 30000]
    for i, ex in enumerate(("tolerant", "exact")):
        ys = [np.nan if R[f"sonnet|0.9|{n}|{ex}|gap"]["abstain"] else R[f"sonnet|0.9|{n}|{ex}|gap"]["size"] for n in ns]
        ax.plot(ns, ys, marker=P.MARKERS[i], color=S[i], ms=3, label=ex)
        ab = [n for n, y in zip(ns, ys) if y != y]
        ax.scatter(ab, [1.4 + 0.25 * i] * len(ab), marker="x", s=14, color=S[i], zorder=3)
    ax.annotate("abstains", (30000, 1.5), xytext=(-4, 0), textcoords="offset points", ha="right", va="center",
                fontsize=5.5, color=P.INK2)
    ax.set_ylim(1.0, 6.6)
    ax.set_xscale("log")
    ax.set_xlabel("reviews n", fontsize=6.5)
    ax.set_ylabel("|K|", fontsize=6.5)
    ax.tick_params(labelsize=6)
    P.grid(ax)
    ax.legend(fontsize=5)
    ax.set_title("(b) E11 toolkit size", fontsize=6.5)
    fig.tight_layout(w_pad=0.6)
    save(fig, "paper_profile_gap")


def factorial():
    e18 = load("E18_factorial")
    if not e18:
        return
    F = e18["factorial"]
    mets = [("recall", "group recall"), ("tokens", "tokens"), ("joint", "joint feasibility"),
            ("reach_any", "attack reachable")]
    fig, axs = plt.subplots(1, 4, figsize=(7.16, 1.6))
    for j, (m, l) in enumerate(mets):
        ax = axs[j]
        sh = F[f"least_privilege|{m}"]["shapley"]
        vals = [sh[f] for f in "GPS"]
        ax.bar(range(3), vals, 0.55, color=[S[0], S[1], S[2]])
        ax.axhline(0, color=P.MUTED, lw=0.6)
        ax.set_xticks(range(3), ["G", "P", "S"], fontsize=6.5)
        ax.tick_params(labelsize=6)
        ax.set_title(f"{l}", fontsize=6.5)
        P.grid(ax)
    fig.tight_layout(w_pad=0.8)
    save(fig, "paper_factorial")


def scalability():
    e15 = load("E15_scalability")
    if not e15:
        return
    R = e15["results"]
    ns = [n for n in ("569", "1000", "10000", "100000") if n in R]
    fig, ax = plt.subplots(figsize=(3.5, 1.8))
    for i, (st, l) in enumerate((("eligibility", "eligibility"), ("retrieval", "retrieval"), ("compose", "composition"),
                                 ("total", "total"))):
        ax.plot([int(n) for n in ns], [R[n][f"{st}_p50_ms"] for n in ns], marker=P.MARKERS[i], color=S[i], ms=3,
                label=l)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("registry size (tools)")
    ax.set_ylabel("median latency (ms)")
    P.grid(ax, "both")
    ax.legend(fontsize=5.5, ncol=2)
    save(fig, "paper_scalability")


if __name__ == "__main__":
    for f in (eligibility, retrieval, profile_gap, factorial, scalability):
        try:
            f()
        except Exception as e:
            print("failed", f.__name__, repr(e))
    print("done")
