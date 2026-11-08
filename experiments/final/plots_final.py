"""Figures of the final evaluation (results/final/figures), following the protocol's axis contracts and the
repository's validated palette (experiments/plot.py)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

import fe

sys.path.insert(0, str(fe.ROOT / "experiments"))
import plot as P  # noqa: E402  (style, palette)
import matplotlib.pyplot as plt  # noqa: E402

FIG = fe.RES / "figures"
FIG.mkdir(exist_ok=True)
WRITTEN = []
S = P.SLOTS


def load(n):
    p = fe.RES / f"{n}.json"
    return json.load(open(p)) if p.exists() else None


def save(fig, stem, caption):
    for ext in ("png", "pdf"):
        fig.savefig(FIG / f"{stem}.{ext}", bbox_inches="tight", pad_inches=0.04)
    plt.close(fig)
    WRITTEN.append((stem, caption))


def err(ci, m):
    return [[max(0, m - ci[0])], [max(0, ci[1] - m)]]


def f_e1():
    r = load("E1_registry")
    if not r:
        return
    v = r["results"]["merged"]
    cats = v["categories"]
    names = sorted(cats, key=lambda c: -cats[c])
    fig, ax = plt.subplots(figsize=(3.4, 2.6))
    reg = fe.reg()
    B = fe.labels_B()
    unsafe = {c: 0 for c in names}
    ann = {c: 0 for c in names}
    for t, d in reg.items():
        c = f"{d['source']}:{d['category']}"
        unsafe[c] += B[t].unsafe_read_only
        ann[c] += bool(d.get("annotations"))
    y = np.arange(len(names))
    tot = np.array([cats[c] for c in names])
    u = np.array([unsafe[c] for c in names])
    ax.barh(y, tot, color=S[0], height=0.62, label="all tools")
    ax.barh(y, u, color=S[1], height=0.62, label="not read-only (labels B)")
    ax.scatter([ann[c] for c in names], y, marker="|", s=60, color=P.INK, label="annotated", zorder=3)
    ax.set_yticks(y, [c.replace("LiveMCPTool:", "LMT ").replace("MCPToolBench++:", "TB++ ") for c in names])
    ax.invert_yaxis()
    ax.set_xlabel("tools")
    P.grid(ax, "x")
    ax.legend(loc="lower right")
    ax.set_title("E1  Tools per category (merged registry)")
    save(fig, "E1_categories", "Tools per source-qualified category of the merged registry, tools not read-only under "
                               "labels B, and annotated tools (tick).")


def f_e2():
    r = load("E2_typing")
    if not r:
        return
    res = r["results"]
    kinds = sorted(res["tau"]["per_kind"], key=lambda k: -res["tau"]["per_kind"][k]["support"])
    kinds = [k for k in kinds if res["tau"]["per_kind"][k]["support"] >= 5]
    fig, ax = plt.subplots(figsize=(3.4, 2.4))
    x = np.arange(len(kinds))
    for i, (m, lab) in enumerate((("tau", "LLM typing τ (labels A)"), ("struct", "structural typer"))):
        ax.bar(x + (i - 0.5) * 0.38, [res[m]["per_kind"][k]["f1"] for k in kinds], 0.36, color=S[i], label=lab)
    ax.set_xticks(x, kinds, rotation=45, ha="right")
    ax.set_ylabel("F1 vs labels B (output kind)")
    ax.set_ylim(0, 1)
    P.grid(ax)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2)
    ax.set_title("E2  Output-type agreement by kind", pad=18)
    save(fig, "E2_typing_f1", "Per-kind F1 of output types against the independent labels B (kinds with ≥5 tools).")


def f_e4():
    r = load("E4_exposure")
    if not r:
        return
    R = r["results"]["1.0"]
    encs = ["no_filter", "closed_world_annotations", "lexical_positive", "verified_evidence", "attested_only"]
    lab = {"no_filter": "no filter / MCP default", "closed_world_annotations": "closed-world annotations",
           "lexical_positive": "lexical", "verified_evidence": "verified (obs/att)", "attested_only": "attested only"}
    rets = [("pamcp_rrf", "PaMCP retrieval"), ("rag_mcp", "RAG-MCP"), ("mcp_zero", "MCP-Zero"), ("toolscope", "ToolScope")]
    fig, axs = plt.subplots(1, 2, figsize=(7.0, 2.4), sharey=True)
    y = np.arange(len(encs))
    for j, (met, title) in enumerate((("Exp@5", "Exp@5 (unsafe tool in top-5)"), ("Util@5", "Util@5 (gold in top-5)"))):
        ax = axs[j]
        for i, (rn, rl) in enumerate(rets):
            ax.barh(y + (i - 1.5) * 0.2, [R[f"{rn}|{e}"][met] for e in encs], 0.18, color=S[i], label=rl)
        ax.set_yticks(y, [lab[e] for e in encs])
        ax.invert_yaxis()
        ax.xaxis.set_major_formatter(P.PCT)
        P.grid(ax, "x")
        ax.set_title(f"E4  {title}")
    h, l = axs[1].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=4, bbox_to_anchor=(0.5, -0.1))
    save(fig, "E4_exposure_utility", f"Exposure and utility of read-only policy encodings by retriever (coverage 1, "
                                     f"{R['pamcp_rrf|no_filter']['n_ro']:.0f} requests with read-only targets).")
    fig, ax = plt.subplots(figsize=(3.4, 2.3))
    rhos = ["0.25", "0.5", "0.75", "1.0"]
    for i, (met, l) in enumerate((("Util@5", "Util@5"), ("eligible_share", "eligible share"))):
        ax.plot([float(x) for x in rhos], [r["results"][x]["pamcp_rrf|verified_evidence"][met] for x in rhos],
                marker=P.MARKERS[i], color=S[i], label=l)
    ax.plot([float(x) for x in rhos], [r["results"][x]["pamcp_rrf|verified_evidence"]["Exp@5"] for x in rhos],
            marker="s", color=S[1], label="Exp@5")
    ax.set_xlabel("verification coverage ρ")
    ax.yaxis.set_major_formatter(P.PCT)
    P.grid(ax)
    ax.legend()
    ax.set_title("E4  Verified evidence vs coverage")
    save(fig, "E4_coverage", "Verified-evidence encoding: utility, eligible share and exposure against the share of "
                             "tools the verifier probes (5 seeds below ρ = 1).")


def f_e5():
    r = load("E5_forgery")
    if not r:
        return
    R = r["results"]
    encs = [("closed_world_annotations", "closed-world annotations"), ("lexical_positive", "lexical"),
            ("verified_evidence", "verified (FAR 5%)"), ("no_filter", "no filter")]
    fig, axs = plt.subplots(1, 3, figsize=(7.0, 2.2), sharey=True)
    ds = [0.0, 0.05, 0.1, 0.2, 0.3]
    for j, atk in enumerate(("forge", "launder", "both")):
        ax = axs[j]
        for i, (e, l) in enumerate(encs):
            ax.plot(ds, [R[f"{atk}|{d}"][f"pamcp_rrf|{e}"]["Exp@5"] for d in ds], marker=P.MARKERS[i], color=S[i],
                    label=l)
        ax.set_xlabel("malicious-server fraction δ")
        ax.xaxis.set_major_formatter(P.PCT)
        ax.yaxis.set_major_formatter(P.PCT)
        P.grid(ax)
        ax.set_title(f"E5  {atk}")
    axs[0].set_ylabel("Exp@5")
    axs[2].legend(loc="upper left", fontsize=6)
    save(fig, "E5_forgery", "Exp@5 against the fraction of malicious servers, by attack (5 seeds; PaMCP retrieval).")


def f_e6():
    r = load("E6_verifier")
    if not r:
        return
    R = r["results"]
    phis = [0.0, 0.01, 0.02, 0.05, 0.1, 0.2]
    fig, axs = plt.subplots(1, 2, figsize=(7.0, 2.2), sharey=True)
    for j, delta in enumerate(("0.0", "0.2")):
        ax = axs[j]
        i = 0
        for pl in ("random", "lookalike"):
            for psi in ("0.0",):
                ax.plot(phis, [R[f"{delta}|{pl}|{psi}|1.0|{p}"]["pamcp_rrf|verified_evidence"]["Exp@5"] for p in phis],
                        marker=P.MARKERS[i], color=S[i], label=f"verified, {pl} errors")
                i += 1
        ax.axhline(R[f"{delta}|random|0.0|1.0|0.0"]["pamcp_rrf|lexical_positive"]["Exp@5"], color=S[2], ls="--",
                   label="lexical")
        ax.set_xlabel("verifier false-accept rate φ")
        ax.xaxis.set_major_formatter(P.PCT)
        ax.yaxis.set_major_formatter(P.PCT)
        P.grid(ax)
        ax.set_title(f"E6  δ = {float(delta):.0%} malicious servers")
    axs[0].set_ylabel("Exp@5")
    axs[1].legend(fontsize=6)
    save(fig, "E6_verifier", "Exp@5 of verified evidence against the verifier's false-accept rate (random or look-alike "
                             "errors, coverage 1, ψ = 0), with the lexical encoding as reference.")


def f_e7():
    r = load("E7_trust")
    if not r:
        return
    R = r["results"]
    fig, ax = plt.subplots(figsize=(3.4, 2.4))
    i = 0
    for trust in ("default", "signer_weighted"):
        for floor in ("0.0", "0.8"):
            pts = [(v["Util@5"], v["Exp@5"]) for k, v in R.items() if k.startswith(f"{trust}|{floor}|")]
            ax.plot([p[0] for p in pts], [p[1] for p in pts], marker=P.MARKERS[i], color=S[i], lw=1,
                    label=f"{trust.replace('_', '-')}, κ floor {floor}")
            i += 1
    ax.set_xlabel("Util@5")
    ax.set_ylabel("Exp@5")
    ax.xaxis.set_major_formatter(P.PCT)
    ax.yaxis.set_major_formatter(P.PCT)
    P.grid(ax, "both")
    ax.legend(fontsize=6)
    ax.set_title("E7  Trust threshold sweep (ℓmin 0.20–0.95)")
    save(fig, "E7_trust_pareto", "Utility against exposure as the trust threshold varies, by trust policy and "
                                 "probe-coverage floor (δ = 20%, FAR 5%).")


def f_e8():
    r = load("E8_single_tool")
    if not r:
        return
    R = r["results"]["sample|B1m"]
    ms = sorted(R, key=lambda m: R[m]["hit1"]["mean"])
    fig, ax = plt.subplots(figsize=(3.4, 2.4))
    for i, m in enumerate(ms):
        h = R[m]["hit1"]
        ax.errorbar(h["mean"], i, xerr=err(h["ci_target"], h["mean"]), fmt="o", color=S[0], ms=4, capsize=2)
    ax.set_yticks(range(len(ms)), ms)
    ax.xaxis.set_major_formatter(P.PCT)
    ax.set_xlabel("Hit@1 (95% CI, target-tool clusters)")
    P.grid(ax, "x")
    ax.set_title("E8  Single-tool retrieval (569 tools)")
    save(fig, "E8_forest", "Hit@1 on the 300-query MCPToolBench++ sample over the merged registry.")
    c = r["results"]["distractor_curve_hit1"]
    ds = sorted(c, key=int)
    fig, ax = plt.subplots(figsize=(3.4, 2.3))
    for i, m in enumerate(["pamcp_contract", "mcp_zero", "rrf", "colt_adapted", "toolscope_adapted", "bm25"]):
        if m in c[ds[0]]:
            ax.plot([int(d) for d in ds], [c[d][m] for d in ds], marker=P.MARKERS[i], color=S[i], label=m)
    ax.set_xlabel("distractor tools added to B1 (87)")
    ax.set_ylabel("Hit@1")
    ax.yaxis.set_major_formatter(P.PCT)
    P.grid(ax)
    ax.legend(fontsize=6)
    ax.set_title("E8  Distractor curve")
    save(fig, "E8_distractors", "Hit@1 as LiveMCPTool distractors are added to the 87 MCPToolBench++ tools (5 seeds).")


def f_e9_e10():
    r = load("E9_sets")
    if r:
        s = r["summary"]
        ms = ["pamcp@5", "pamcp_noclosure", "per_subtask[analyst]", "mcp_zero", "cmtf_path", "toolscope[analyst]@5",
              "colt@5", "rag_mcp@5"]
        ms = [m for m in ms if m in s]
        fig, ax = plt.subplots(figsize=(3.4, 2.4))
        y = np.arange(len(ms))
        for i, m in enumerate(ms):
            v = s[m]["recall"]
            ax.barh(i, v["mean"], 0.6, color=S[0])
            ax.errorbar(v["mean"], i, xerr=err(v["ci"], v["mean"]), fmt="none", color=P.INK, capsize=2, lw=0.8)
            ax.text(v["mean"] + 0.02, i, f"|K| {s[m]['size']['mean']:.1f}", va="center", fontsize=6, color=P.INK2)
        ax.set_yticks(y, ms)
        ax.invert_yaxis()
        ax.xaxis.set_major_formatter(P.PCT)
        ax.set_xlabel("group recall (95% CI)")
        P.grid(ax, "x")
        ax.set_title("E9  Multi-tool set retrieval (94 tasks)")
        save(fig, "E9_group_recall", "Group recall of the selected sets with mean toolkit size, LiveMCPBench.")
    r = load("E10_validity")
    if r:
        s = r["summary"]
        ms = [m for m in s if m.startswith("pamcp") or m.endswith("|unfiltered") or m.endswith("|eligible-only")]
        ms = sorted(ms, key=lambda m: -s[m]["joint_feasible"])
        checks = ["S", "C", "E", "L", "V"]
        M_ = np.array([[s[m]["pass"][c] for c in checks] + [s[m]["joint_feasible"]] for m in ms])
        fig, ax = plt.subplots(figsize=(3.6, 0.22 * len(ms) + 0.8))
        im = ax.imshow(M_, cmap="Blues", vmin=0, vmax=1, aspect="auto")
        ax.set_xticks(range(len(checks) + 1), checks + ["joint"])
        ax.set_yticks(range(len(ms)), ms, fontsize=6)
        for i in range(M_.shape[0]):
            for j in range(M_.shape[1]):
                ax.text(j, i, f"{M_[i, j]:.0%}", ha="center", va="center", fontsize=5.5,
                        color="white" if M_[i, j] > 0.6 else P.INK)
        ax.set_title("E10  Independent set evaluator: pass rates")
        save(fig, "E10_checks", "Per-check pass rates and joint feasibility under each task's least-privilege policy "
                                "(independent evaluator, labels B).")


def f_e11_e12():
    r = load("E12_profile")
    if r:
        fig, ax = plt.subplots(figsize=(3.2, 3.0))
        for i, m in enumerate(("sonnet", "haiku", "opus")):
            v = r["results"][m]
            xs, ys = [], []
            for c in v["measured"]:
                for n in v["measured"][c]:
                    xs.append(v["self_assessed"][c][n])
                    ys.append(v["measured"][c][n]["acc"])
            ax.scatter(xs, ys, s=18, marker=P.MARKERS[i], color=S[i], label=f"{m} (MAE {v['self_assessment_mae']:.2f})")
        ax.plot([0, 1], [0, 1], color=P.MUTED, lw=0.8, ls="--")
        ax.set_xlabel("self-assessed reliability")
        ax.set_ylabel("measured accuracy (4 items)")
        P.grid(ax, "both")
        ax.legend(fontsize=6, loc="lower right")
        ax.set_title("E12  Self-assessment vs measurement")
        save(fig, "E12_calibration", "Claimed against measured reliability per class and input size (16 cells per model).")
    r = load("E11_gap")
    if r:
        R = r["results"]
        ns = [30, 300, 3000, 30000]
        fig, ax = plt.subplots(figsize=(3.4, 2.3))
        i = 0
        for tau in ("0.6", "0.9"):
            for ex in ("tolerant", "exact"):
                ys = [R[f"sonnet|{tau}|{n}|{ex}|gap"]["size"] if not R[f"sonnet|{tau}|{n}|{ex}|gap"]["abstain"] else np.nan
                      for n in ns]
                ax.plot(ns, ys, marker=P.MARKERS[i], color=S[i], label=f"τ={tau}, {ex}")
                i += 1
        ax.set_xscale("log")
        ax.set_xlabel("input size n (reviews)")
        ax.set_ylabel("toolkit size (gaps = abstention)")
        P.grid(ax)
        ax.legend(fontsize=6)
        ax.set_title("E11  Toolkit size vs input size")
        save(fig, "E11_gap", "Toolkit size of the review scenario against input size n, by threshold τ and exactness "
                             "(Sonnet profile; NoGap abstains in every setting).")


def f_e14_e18():
    r = load("E14_injection")
    if r:
        A = r["attack_rates"]
        ms = ["Full_PaMCP", "PaMCP_NoGap", "PaMCP_Declared", "PaMCP_NoCert", "per_subtask|eligible",
              "per_subtask|unfiltered", "mcp_zero|unfiltered", "colt@5|unfiltered", "toolscope@5|unfiltered",
              "cmtf_path|unfiltered", "rag_mcp@5|unfiltered", "all_tools|unfiltered"]
        ms = [m for m in ms if f"least_privilege|{m}" in A]
        fig, ax = plt.subplots(figsize=(3.4, 2.6))
        for i, m in enumerate(ms):
            v = A[f"least_privilege|{m}"]
            ax.barh(i, v["rate"], 0.6, color=S[1] if "PaMCP" in m else S[0])
            ax.errorbar(v["rate"], i, xerr=err(v["ci"], v["rate"]), fmt="none", color=P.INK, capsize=2, lw=0.8)
        ax.set_yticks(range(len(ms)), ms, fontsize=6)
        ax.invert_yaxis()
        ax.xaxis.set_major_formatter(P.PCT)
        ax.set_xlabel("reachable out-of-scope actions (Wilson 95% CI)")
        P.grid(ax, "x")
        ax.set_title("E14  Worst-case injection reach")
        save(fig, "E14_injection", "Share of task × out-of-scope attack pairs the exposed toolkit can realise under labels B "
                                   "(least-privilege policies, 155 tasks).")
    r = load("E18_factorial")
    if r:
        F = r["factorial"]
        mets = [("recall", "recall"), ("tokens", "tokens"), ("joint", "joint feasibility"), ("reach_any", "attack reach")]
        fig, axs = plt.subplots(1, 4, figsize=(7.0, 1.9))
        for j, (m, l) in enumerate(mets):
            ax = axs[j]
            sh = F[f"least_privilege|{m}"]["shapley"]
            ax.bar(range(3), [sh[f] for f in "GPS"], 0.6, color=[S[0], S[1], S[2]])
            ax.axhline(0, color=P.MUTED, lw=0.6)
            ax.set_xticks(range(3), ["gap", "provenance", "set-level"], fontsize=6)
            ax.set_title(f"E18  {l}", fontsize=7)
            P.grid(ax)
        save(fig, "E18_shapley", "Shapley attribution of the full-vs-none difference to the three mechanisms "
                                 "(2^3 factorial, least-privilege policies).")


def f_e15():
    r = load("E15_scalability")
    if not r:
        return
    R = r["results"]
    ns = [n for n in ("569", "1000", "10000", "100000") if n in R]
    fig, ax = plt.subplots(figsize=(3.4, 2.3))
    for i, st in enumerate(("eligibility", "retrieval", "compose", "total")):
        ax.plot([int(n) for n in ns], [R[n][f"{st}_p50_ms"] for n in ns], marker=P.MARKERS[i], color=S[i], label=st)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("registry size (tools)")
    ax.set_ylabel("p50 latency (ms)")
    P.grid(ax, "both")
    ax.legend(fontsize=6)
    ax.set_title("E15  Per-stage latency")
    save(fig, "E15_latency", "Median per-stage latency against registry size (synthetic clones, 30 tasks, 2 vCPUs).")


def f_e17():
    r = load("E17_refinement")
    if not r:
        return
    R = r["results"]
    ks = [0, 1, 2, 3, 5]
    fig, ax = plt.subplots(figsize=(3.4, 2.2))
    for i, b in enumerate(("K=5", "K=1 (induced chi1)")):
        ax.plot(ks, [R[f"{b}|k={k}"]["valid_rate"] for k in ks], marker=P.MARKERS[i], color=S[i], label=b)
    ax.set_xlabel("refinement bound k")
    ax.set_ylabel("tasks with a certified toolkit")
    ax.yaxis.set_major_formatter(P.PCT)
    P.grid(ax)
    ax.legend(fontsize=6)
    ax.set_title("E17  Refinement")
    save(fig, "E17_refinement", "Share of tasks with a certified toolkit against the refinement bound (LLM-free repairs).")


def main():
    for f in (f_e1, f_e2, f_e4, f_e5, f_e6, f_e7, f_e8, f_e9_e10, f_e11_e12, f_e14_e18, f_e15, f_e17):
        try:
            f()
        except Exception as e:  # keep going; report
            print("figure failed", f.__name__, repr(e))
    (FIG / "CAPTIONS.md").write_text("\n".join(f"- `{s}`: {c}" for s, c in WRITTEN) + "\n")
    print(len(WRITTEN), "figures")


if __name__ == "__main__":
    main()
