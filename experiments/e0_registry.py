"""E0 — Registry characterisation (Table 1) and H1 on published metadata.

Replicates Table 1 (servers, tools, annotated tools) and the Section 2.2 statistics: annotated tools
all claim readOnlyHint=true; how many of them are not read-only; the share of tools that modify
persistent, shared or external state; and the share kept by "require declared read-only hints".
Effect labellings compared: the engine's lexical labeller (lex), published annotations (ann) and
the silver LLM labels J. H1 (declared vs observed) is reported here for the registry-level evidence
and in E1 for real sandbox traces.
"""
from __future__ import annotations

from collections import Counter

from common import ROOT, banner, load_processed, save

from taas.contracts import extract_contract
from taas.data.registries import raw_tools_from_processed
from taas.effects import lexical_effects, modifies_state
from taas.realreg import truth


def main() -> dict:
    banner("E0: registry characterisation (Table 1) — this checks the data matches the paper before any method runs")
    d = load_processed()
    raw = raw_tools_from_processed(d)
    J = truth()
    st = d["stats"]
    n = len(raw)
    ann = [t for t in raw if t.annotations]
    ann_not_ro = [t.id for t in ann if J.get(t.id) and J[t.id].unsafe_read_only]
    j_mod = [t.id for t in raw if J[t.id].unsafe_read_only]
    lex_mod = {t.id for t in raw if modifies_state(lexical_effects(t.name, t.description, list(
        ((t.input_schema or {}).get("properties") or {}).keys())))}
    tp = len(lex_mod & set(j_mod))
    prec = tp / max(1, len(lex_mod))
    rec = tp / max(1, len(j_mod))
    by_cls = Counter(e.cls for t in raw for e in J[t.id].effects)
    res = {
        "table1": {k: {"servers": v["servers"], "tools": v["tools"], "annotated": v["annotated"]}
                   for k, v in st.items() if k != "requests"},
        "requests": st["requests"],
        "annotated_all_claim_read_only": all((t.annotations or {}).get("readOnlyHint") is True for t in ann),
        "annotated_servers": sorted({t.server for t in ann}),
        "annotated_but_not_read_only_silver": ann_not_ro,
        "modify_state_silver": {"count": len(j_mod), "share": len(j_mod) / n},
        "modify_state_lexical": {"count": len(lex_mod), "share": len(lex_mod) / n},
        "lexical_vs_silver": {"precision": prec, "recall": rec, "f1": 2 * prec * rec / max(1e-9, prec + rec),
                              "silver_unsafe_missed_by_lex": len(set(j_mod) - lex_mod)},
        "require_declared_read_only_keeps": {"count": len(ann), "share": len(ann) / n},
        "closed_world_ann_filters": sum(1 for t in raw if (t.annotations or {}).get("readOnlyHint") is False),
        "silver_effect_classes": dict(by_cls),
        "paper_reference": {"servers": 76, "tools": 569, "annotated": 44, "not_read_only_annotated": 1,
                            "modify_state": 158, "modify_state_share": 0.278, "require_hints_share": 0.077,
                            "MCPToolBench++_requests": 1429},
    }
    print(f"merged registry: {st['merged']['servers']} servers, {n} tools, {len(ann)} annotated "
          f"(paper: 76/569/44)")
    print(f"annotated tools that are not read-only (silver): {len(ann_not_ro)} {ann_not_ro} (paper: 1)")
    print(f"modify state — silver: {len(j_mod)} ({len(j_mod)/n:.1%}), lexical: {len(lex_mod)} ({len(lex_mod)/n:.1%})"
          f" (paper: 158, 27.8%)")
    print(f"lexical labeller vs silver: P={prec:.2f} R={rec:.2f}; unsafe tools missed by lex: {len(set(j_mod)-lex_mod)}")
    print(f"'require declared read-only hints' keeps {len(ann)}/{n} = {len(ann)/n:.1%} (paper 7.7%); "
          f"closed-world@ann filters {res['closed_world_ann_filters']} tools (nothing to filter)")
    print(f"MCPToolBench++ requests: {st['requests']['MCPToolBench++']} (unique queries "
          f"{st['requests']['MCPToolBench++_unique_queries']}; paper reports 1,429)")
    save("e0_registry", res)
    return res


if __name__ == "__main__":
    main()
