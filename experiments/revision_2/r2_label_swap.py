"""Revision 2, review Critical 1: how much of the zero-exposure result of E4 comes from the label construction.

The paper simulates the verifier from labels A and scores against labels B, with U_B ⊆ U_A, so an error-free
verifier cannot admit a B-unsafe tool. Here the roles are swapped (verifier from B, scored against A), which
exposes the tools that only one labelling considers unsafe. Both directions are reported with the same code
(experiments/final/e04_e07_exposure.py), coverage 1, no verifier errors, read-only policy.
Evidence class: SIMULATED verifier, LABELLED scoring (both labellings are LLM-generated; neither is ground truth).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "final"))

import fe  # noqa: E402
import methods as M  # noqa: E402
import e04_e07_exposure as X  # noqa: E402
from taas.realreg import build_contracts  # noqa: E402


def main() -> None:
    A, B = fe.labels_A(), fe.labels_B()
    raw = fe.raw()
    reqs = X.requests()
    w = M.World()
    mz, ts = M.MCPZero(w), M.ToolScope(w)
    cs0 = build_contracts(raw, None)
    rk = X.Rankers(cs0, w, mz, ts)
    names = ["rag_mcp", "pamcp_rrf", "mcp_zero", "toolscope"]
    uA = {t for t in A if A[t].unsafe_read_only}
    uB = {t for t in B if B[t].unsafe_read_only}
    out = {"unsafe_A": len(uA), "unsafe_B": len(uB), "unsafe_A_only": sorted(uA - uB),
           "unsafe_B_only": sorted(uB - uA)}
    for direction, (V, S) in {"paper: verifier A, scored B": (A, B), "swapped: verifier B, scored A": (B, A)}.items():
        el = X.eligibility(raw, cs0, X.verifier_decisions(raw, V, rho=1.0, seed=0))
        res = X.score(rk, reqs, el, S, names, ks=(5,))
        ver = el["verified_evidence"]
        uS = {t for t in S if S[t].unsafe_read_only}
        out[direction] = {"eligible": len(ver), "scoring_unsafe_admitted": sorted(ver & uS),
                          "Exp@5": {n: res[f"{n}|verified_evidence"]["Exp@5"] for n in names},
                          "Util@5": {n: res[f"{n}|verified_evidence"]["Util@5"] for n in names},
                          "lexical_Exp@5": {n: res[f"{n}|lexical_positive"]["Exp@5"] for n in names},
                          "n_scored_requests": res["pamcp_rrf|verified_evidence"]["n_ro"],
                          "Exp@5_ci_target_clusters": {n: res[f"{n}|verified_evidence"]["Exp@5_ci"] for n in names}}
        print(direction, "admitted unsafe:", len(ver & uS), {n: round(v, 4) for n, v in out[direction]["Exp@5"].items()})
    fe.save("R2_label_swap", {"results": out},
            "SIMULATED verifier (error-free, coverage 1), LABELLED scoring; swap of the two LLM labellings",
            inputs=["data/llm_inputs/final/e8_sample.json"], config={"rho": 1.0, "far": 0.0, "k": 5})


if __name__ == "__main__":
    main()
