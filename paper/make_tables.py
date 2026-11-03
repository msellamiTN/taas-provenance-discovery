"""Generate the LaTeX result tables of paper/sections/evaluation.tex from paper/evaluation_numbers.json.

Tables are generated, never typed, so every cell traces to results/*.json. Run after
paper/evaluation_numbers.py:  python paper/make_tables.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
N = json.load(open(ROOT / "paper" / "evaluation_numbers.json"))
OUT = ROOT / "paper" / "tables"
OUT.mkdir(exist_ok=True)


def sgn(x: float, nd: int) -> str:
    """Signed difference with a typographic minus: +0.007, $-$0.104."""
    s = f"{abs(x):.{nd}f}"
    return ("$-$" if x < -0.5 * 10 ** -nd else "+") + s


def r3(x: float) -> str:
    """0.186 -> .186 (IEEE style for proportions in tables)."""
    s = f"{x:.3f}"
    return s[1:] if s.startswith("0.") else s


def tab_h3() -> None:
    rows = [("ours", "TaaS"), ("ours-nogap", "\\quad no gap analysis"), ("ours-strict", "\\quad strict rule 2"),
            ("per-subtask", "Per-subtask"), ("per-subtask-gap", "\\quad gap goals only"),
            ("rag-top3", "RAG-MCP top-3"), ("rag-top5", "RAG-MCP top-5"), ("mcp-zero", "MCP-Zero"),
            ("all-tools", "Full catalogue")]
    S = N["e3_summary"]
    lines = []
    for key, name in rows:
        cells = []
        for src in ("LiveMCPBench", "MCPToolBench++"):
            m = S[f"{src}|{key}"]
            ci = "" if key == "all-tools" else f"\\,$\\pm$\\,{r3(m['recall_ci95'])}"
            cells += [f"{m['size']:.2f}", f"{m['tokens']:,.0f}".replace(",", "{,}"), f"{r3(m['recall'])}{ci}"]
        lines.append(f"{name} & " + " & ".join(cells) + " \\\\")
        if key == "ours-strict":
            lines.append("\\addlinespace[2pt]")
    body = "\n".join(lines)
    tex = r"""\begin{table}[t]
\caption{Toolkit size, context cost and gold-tool recall (H3). Means over tasks; recall with its 95\% confidence
interval. LMB: LiveMCPBench, 95 tasks (test). TB++: MCPToolBench++, 60 queries (development). Tok.: tokens of the
exposed tool definitions.}
\label{tab:eval-h3}
\centering\footnotesize\setlength{\tabcolsep}{2.2pt}
\begin{tabular}{@{}lrrlrrl@{}}
\toprule
 & \multicolumn{3}{c}{LMB (test)} & \multicolumn{3}{c}{TB++ (dev)}\\
\cmidrule(lr){2-4}\cmidrule(l){5-7}
System & $|K|$ & Tok. & Recall & $|K|$ & Tok. & Recall\\
\midrule
""" + body + r"""
\bottomrule
\end{tabular}
\end{table}
"""
    (OUT / "tab_h3.tex").write_text(tex)


ABL = [("full (dev-tuned)", "Reference (dev-tuned)"),
       ("pure Eq.6 (w_rel=0)", "No relevance term (Eq.~(6))"),
       ("no structural score", "No structural score"),
       ("closure depth 0", "No backward closure ($d=0$)"),
       ("no refinement", "No refinement (Alg.~3A)"),
       ("Alg.1 literal ctx", "Alg.~1 read literally"),
       ("strict profile (rule 2)", "Strict rule~2"),
       ("rule 1 off (exact_n_max=1e9)", "Rule~1 off"),
       ("Haiku profile", "Haiku $\\rho_{\\mathrm{LLM}}$ profile"),
       ("Haiku analyst", "Haiku analyst"),
       ("derivation-mode flow", "(L) along derivations")]


def tab_ablation() -> None:
    P = N["e6"]["path"]
    ref = P["full (dev-tuned)"]
    lines = []
    for key, name in ABL:
        m = P[key]
        if key == "full (dev-tuned)":
            lines.append(f"{name} & {r3(m['recall'])} & {m['size']:.2f} & {m['abstain']:.2f} \\\\\n\\midrule")
            continue
        d = m["recall"] - ref["recall"]
        dk = m["size"] - ref["size"]
        lines.append(f"{name} & {r3(m['recall'])} ({sgn(d, 3)}) & {m['size']:.2f} ({sgn(dk, 2)}) & {m['abstain']:.2f} \\\\")
    tex = r"""\begin{table}[t]
\caption{Request-path ablations on the LiveMCPBench test split (95 tasks). Each row changes one component of the
reference configuration; differences to the reference in parentheses. Abst.: share of tasks with an explicit
abstention.}
\label{tab:eval-ablation}
\centering\footnotesize\setlength{\tabcolsep}{3pt}
\begin{tabular}{@{}lllr@{}}
\toprule
Variant & Recall & $|K|$ & Abst.\\
\midrule
""" + "\n".join(lines) + r"""
\bottomrule
\end{tabular}
\end{table}
"""
    (OUT / "tab_ablation.tex").write_text(tex)


def tab_composition() -> None:
    names = [("ours-exact", "Exact (B\\&B)"), ("ours-greedy", "Greedy cover"),
             ("ours-no-closure", "No backward closure"), ("per-subtask", "Per-subtask")]
    lines = []
    for key, name in names:
        m = N["e5"][key]
        lo, hi = m["valid_wilson"]
        byL = "/".join(f"{100 * v:.0f}" for v in m["by_L"].values())
        t = f"{m['time_ms']:.1f}" if key.startswith("ours") else "--"
        lines.append(f"{name} & {m['valid_k']}/{m['n']} & [{100 * lo:.1f}, {100 * hi:.1f}] & {byL} & "
                     f"{100 * m['optimal']:.0f} & {t} \\\\")
    tex = r"""\begin{table}[t]
\caption{Composition on synthetic typed registries (RQ3): 48 tasks with hidden chains of length $L\in\{2,3,4\}$.
Valid: toolkits accepted by an independent checker, with the 95\% Wilson interval (\%). By $L$: valid share
(\%) for $L=2/3/4$. Opt.: share (\%) whose cost equals the brute-force optimum.}
\label{tab:eval-composition}
\centering\footnotesize\setlength{\tabcolsep}{2.0pt}
\begin{tabular}{@{}lrlcrr@{}}
\toprule
Regime & Valid & 95\% CI & By $L$ & Opt. & ms\\
\midrule
""" + "\n".join(lines) + r"""
\bottomrule
\end{tabular}
\end{table}
"""
    (OUT / "tab_composition.tex").write_text(tex)


if __name__ == "__main__":
    tab_h3()
    tab_ablation()
    tab_composition()
    print("tables written to", OUT)
