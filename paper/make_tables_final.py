"""LaTeX tables of the final Experimental Evaluation section, generated from results/final/*.json."""
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# PAMCP_RESULTS_DIR: read a reproduction run instead of the reference results and write its tables next to it
RES = Path(os.environ.get("PAMCP_RESULTS_DIR", str(ROOT / "results" / "final")))
RES = RES if RES.is_absolute() else ROOT / RES
OUT = ROOT / "paper" / "tables_final" if RES == ROOT / "results" / "final" else RES / "paper_tables"
OUT.mkdir(parents=True, exist_ok=True)


def L(n):
    return json.load(open(RES / f"{n}.json"))


def p(x, d=1):
    return "--" if x is None or x != x else f"{100 * x:.{d}f}"


def f(x, d=3):
    if x is None or x != x:
        return "--"
    s = f"{x:.{d}f}"
    return "$-$" + s[1:] if s.startswith("-") else s


def ledger():
    rows = [
        ("E1", "Registry characterisation", "RQ1", "run", "M, L"),
        ("E2", "Semantic typing", "RQ1", "proxy$^a$", "L"),
        ("E3", "Declared vs.\\ observed effects", "RQ2", "partial$^b$", "L"),
        ("E4", "Exposure under policy encodings", "RQ2", "run", "S"),
        ("E5", "Forged and laundered metadata", "RQ2", "run", "S"),
        ("E6", "Imperfect verifier", "RQ2", "run", "S"),
        ("E7", "Trust policy and evidence strength", "RQ2", "run", "S"),
        ("E8", "Single-tool retrieval", "RQ3", "run", "M"),
        ("E9", "Multi-tool set retrieval", "RQ3", "run", "M"),
        ("E10", "Set validity", "RQ3", "run", "L"),
        ("E11", "Capability gap", "RQ1, RQ3", "partial$^c$", "M"),
        ("E12", "Model-profile calibration", "RQ1", "partial$^d$", "M"),
        ("E13", "End-to-end execution", "--", "blocked$^e$", "--"),
        ("E14", "Prompt injection", "RQ2, RQ3", "offline$^e$", "L"),
        ("E15", "Cost and scalability", "RQ3, RQ4", "run", "Y"),
        ("E16", "Registry and model evolution", "RQ4", "run", "M"),
        ("E17", "Counterexample-guided refinement", "RQ4", "partial$^f$", "M"),
        ("E18", "Mechanism ablation ($2^3$)", "all", "run", "M, L"),
        ("E19", "LLM role configurations", "RQ1", "not run", "--"),
        ("E20", "Cost weights, utility floor", "RQ3", "run", "M"),
        ("E21", "Experience reuse", "RQ4", "blocked$^e$", "--"),
        ("E22", "Statistical validity", "all", "run", "--"),
    ]
    body = "\n".join(f"{a} & {b} & {c} & {d} & {e}\\\\" for a, b, c, d, e in rows)
    tex = r"""\begin{table}[t]
\caption{Experiment series of the protocol, research question, status and evidence class. M: measured on
benchmark data; L: scored against the independent labels $J_B$; S: simulated evidence or attacker scored against
$J_B$; Y: synthetic registries. $^a$Agreement with $J_B$; human study not run. $^b$Observed effects need executed
servers. $^c$Task success needs E13. $^d$64-item set, three models. $^e$Needs executed MCP servers.
$^f$Deterministic repairs only.}
\label{tab:ev-ledger}
\centering\footnotesize\setlength{\tabcolsep}{2.6pt}
\begin{tabular}{@{}lllll@{}}
\toprule
ID & Series & RQ & Status & Evid.\\
\midrule
""" + body + r"""
\bottomrule
\end{tabular}
\end{table}
"""
    (OUT / "tab_ledger.tex").write_text(tex)


def sets():
    s9 = L("E9_sets")["summary"]
    a9 = L("E9_sets")["abstention_and_certification"]
    s10 = L("E10_validity")["summary"]
    rows = [
        ("\\pamcp{} ($K{=}5$)", "pamcp@5", "pamcp(K=10)", "pamcp@size-matched"),
        ("\\quad without closure", "pamcp_noclosure", None, None),
        ("Per-subtask", "per_subtask[analyst]", "per_subtask[analyst]|eligible-only",
         "per_subtask[analyst]@size-matched"),
        ("MCP-Zero", "mcp_zero", "mcp_zero|eligible-only", "mcp_zero_ranked@size-matched"),
        ("RAG-MCP top-5", "rag_mcp@5", "rag_mcp@5|eligible-only", "rag_mcp@size-matched"),
        ("COLT top-5", "colt@5", "colt@5|eligible-only", "colt@size-matched"),
        ("ToolScope top-5", "toolscope[analyst]@5", "toolscope[analyst]@5|eligible-only", None),
        ("CMTF (path)", "cmtf_path", "cmtf_path|eligible-only", None),
    ]
    body = []
    for name, k9, k10, ksm in rows:
        v = s9[k9]
        jf = s10[k10]["joint_feasible"] if k10 else None
        jfu = s10.get(k10.replace("eligible-only", "unfiltered"), {}).get("joint_feasible") if k10 and "|" in k10 \
            else None
        sm = s9[ksm]["recall"]["mean"] if ksm else None
        ab = a9.get(k9, {}).get("abstain_rate") or 0.0
        body.append(f"{name} & {v['size']['mean']:.2f} & {v['tokens']['mean']:.0f} & {f(v['recall']['mean'])} & "
                    f"{p(v['complete']['mean'])} & {f(sm)} & {p(jf, 0)}{'/' + p(jfu, 0) if jfu is not None else ''} & "
                    f"{p(ab, 0)}\\\\")
    tex = r"""\begin{table}[t]
\caption{Set retrieval (E9, open policy) and set validity (E10, each task's least-privilege policy) on the 94
LiveMCPBench tasks. Rec.: group recall; Comp.: share of tasks whose gold groups are all covered; Rec.$_{sm}$:
recall with every method truncated to \pamcp{}'s toolkit size (84 tasks with a non-empty toolkit); Joint: joint
feasibility under the independent evaluator (\pamcp{} with $K{=}10$, identical for $K{=}20, 40$; baselines
restricted to eligible tools / as published); Abst.: abstentions. Per-subtask uses the analyst's subgoals. Tokens
of the raw tool definitions.}
\label{tab:ev-sets}
\centering\footnotesize\setlength{\tabcolsep}{1.5pt}
\begin{tabular}{@{}lrrrrrrr@{}}
\toprule
Method & $|K|$ & Tok. & Rec. & Comp.\% & Rec.$_{sm}$ & Joint\% & Abst.\%\\
\midrule
""" + "\n".join(body) + r"""
\bottomrule
\end{tabular}
\end{table}
"""
    (OUT / "tab_sets.tex").write_text(tex)


def factorial():
    r = L("E18_factorial")
    S = r["summary"]
    att = L("E14_injection")["attack_rates"]
    cells = [("Full \\pamcp{}", "Full_PaMCP", "G P S"), ("NoCert", "PaMCP_NoCert", "G P \\textendash"),
             ("Declared", "PaMCP_Declared", "G \\textendash{} S"), ("NoGap", "PaMCP_NoGap", "\\textendash{} P S"),
             ("", "G1_P0_S0", "G \\textendash{} \\textendash"), ("", "G0_P1_S0", "\\textendash{} P \\textendash"),
             ("", "G0_P0_S1", "\\textendash{} \\textendash{} S"), ("None", "G0_P0_S0", "\\textendash{} \\textendash{} \\textendash")]
    body = []
    for name, k, fac in cells:
        v = S[f"least_privilege|{k}"]
        a = att[f"least_privilege|{k}"]
        a2 = att[f"read_only|{k}"]
        body.append(f"{name} & {fac} & {v['size']['mean']:.2f} & {v['tokens']['mean']:.0f} & {f(v['recall']['mean'])} & "
                    f"{p(v['joint']['mean'], 1)} & {p(a['rate'], 1)} & {p(a2['rate'], 1)} & {p(v['abstain']['mean'], 1)}\\\\")
    body.append("\\midrule")
    for name, k in (("RAG-MCP top-5", "rag_mcp@5|unfiltered"), ("Per-subtask", "per_subtask|unfiltered"),
                    ("MCP-Zero", "mcp_zero|unfiltered"), ("ToolScope top-5", "toolscope@5|unfiltered"),
                    ("COLT top-5", "colt@5|unfiltered"), ("CMTF (path)", "cmtf_path|unfiltered")):
        v = S[f"least_privilege|{k}"]
        a = att[f"least_privilege|{k}"]
        a2 = att[f"read_only|{k}"]
        body.append(f"{name} & & {v['size']['mean']:.2f} & {v['tokens']['mean']:.0f} & {f(v['recall']['mean'])} & "
                    f"{p(v['joint']['mean'], 1)} & {p(a['rate'], 1)} & {p(a2['rate'], 1)} & --\\\\")
    sh = r["factorial"]
    shrow = []
    for m, lab in (("recall", "Rec."), ("tokens", "Tok."), ("joint", "Joint"), ("reach_any", "Reach")):
        x = sh[f"least_privilege|{m}"]["shapley"]
        shrow.append(f"{lab}: {f(x['G'], 3 if m != 'tokens' else 1)}/{f(x['P'], 3 if m != 'tokens' else 1)}/"
                     f"{f(x['S'], 3 if m != 'tokens' else 1)}")
    tex = r"""\begin{table}[t]
\caption{Mechanism ablation (E18) and injection reach (E14) on 155 tasks under each task's least-privilege
policy. G: model-conditioned gap; P: provenance-sound eligibility; S: set-level reasoning and certificate. Joint:
joint feasibility (independent evaluator); Reach: worst-case share of task $\times$ out-of-scope attack pairs the
toolkit can realise under $J_B$ (least privilege: 712 pairs; strict read-only: 775). Shapley attribution of the
full-vs-none difference (G/P/S): """ + "; ".join(shrow).replace("$-$", "$-$") + r""".}
\label{tab:ev-factorial}
\centering\footnotesize\setlength{\tabcolsep}{1.5pt}
\begin{tabular}{@{}llrrrrrrr@{}}
\toprule
Cell & Mech. & $|K|$ & Tok. & Rec. & Joint\% & Reach\% & R-O\% & Abst.\%\\
\midrule
""" + "\n".join(body) + r"""
\bottomrule
\end{tabular}
\end{table}
"""
    (OUT / "tab_factorial.tex").write_text(tex)


def family():
    fam = L("E22_statistics")["family"]
    lab = {"F1": "E9 recall, \\pamcp{} vs.\\ per-subtask (non-inferiority, $\\Delta_0{=}0.05$)",
           "F2": "E9 recall at equal size, \\pamcp{} vs.\\ RAG-MCP",
           "F3": "E10 joint feasibility, \\pamcp{} vs.\\ per-subtask (eligible)",
           "F4": "E4 Exp@5, verified vs.\\ lexical evidence",
           "F5": "E14 reachable attacks, \\pamcp{} vs.\\ per-subtask",
           "F6": "E18 tokens, Full vs.\\ NoGap",
           "F7": "E8 Hit@1, goal contract vs.\\ raw-text RRF"}
    body = []
    for k, v in fam.items():
        dd = 1 if k == "F6" else 3
        pv = v["p"]
        ph = v["p_holm"]
        fmt = lambda x: ("$<$0.001" if x < 0.001 else f"{x:.3f}")
        body.append(f"{k} & {lab[k]} & {v['n']} & {f(v['diff'], dd)} & [{f(v['ci'][0], dd)}, {f(v['ci'][1], dd)}] & "
                    f"{fmt(pv)} & {fmt(ph)}\\\\")
    tex = r"""\begin{table}[t]
\caption{Preregistered confirmatory family (E22): paired sign-flip tests, bootstrap 95\% CIs of the mean
difference (first method minus second), Holm-adjusted $p_H$. For F1, $p$ is the one-sided non-inferiority test.}
\label{tab:ev-family}
\centering\footnotesize\setlength{\tabcolsep}{1.8pt}
\begin{tabular}{@{}lp{2.6cm}rrlrr@{}}
\toprule
ID & Comparison & $n$ & $\Delta$ & 95\% CI & $p$ & $p_H$\\
\midrule
""" + "\n".join(body) + r"""
\bottomrule
\end{tabular}
\end{table}
"""
    (OUT / "tab_family.tex").write_text(tex)


if __name__ == "__main__":
    ledger()
    sets()
    factorial()
    family()
    print("tables written", sorted(x.name for x in OUT.glob("*.tex")))
