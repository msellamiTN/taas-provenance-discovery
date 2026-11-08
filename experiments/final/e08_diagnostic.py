"""E8 diagnostic: why goal-contract retrieval loses to raw-text retrieval on the 569-tool registry.
Separates the request text (raw query vs the analyst's goal rendering) from the structural (type) component."""
from __future__ import annotations

import fe
import methods as M


def main() -> None:
    w = M.World()
    sample = fe.tasks_e8_sample()
    variants = {"raw | lex+den": ("raw", ("lex", "den")), "raw | lex+den+str": ("raw", ("lex", "den", "str")),
                "goal | lex+den": ("goal", ("lex", "den")), "goal | lex+den+str": ("goal", ("lex", "den", "str"))}
    rows = []
    for t in sample:
        spec, rec = fe.spec_for(t)
        goals = [g for g in spec.goals if not g.optional] or spec.goals
        g = goals[0]
        for name, (src, comps) in variants.items():
            q = t["query"] if src == "raw" else g.rendering()
            s = w.ret.scores(q, g.out if "str" in comps else None, w.pool, set(), components=comps)
            r = [x for x, _ in sorted(s.items(), key=lambda kv: (-kv[1], kv[0]))]
            gold = set().union(*t["gold"])
            compat = sum(1 for x in w.pool if M.subtype(w.H.contracts[x].head, g.out)) if "str" in comps else None
            rows.append({"id": t["id"], "variant": name, "hit1": fe.hit_at(r, t["gold"], 1),
                         "hit5": fe.hit_at(r, t["gold"], 5), "goal_out": str(g.out),
                         "gold_type_compatible": any(M.subtype(w.H.contracts[x].head, g.out) for x in gold
                                                     if x in w.H.contracts),
                         "n_type_compatible": compat})
    summ = fe.summarise(rows, ["variant"], ["hit1", "hit5"])
    gc = [r for r in rows if r["variant"] == "goal | lex+den+str"]
    out = {"summary": summ,
           "gold_type_compatible_share": sum(r["gold_type_compatible"] for r in gc) / len(gc),
           "median_type_compatible_tools": sorted(r["n_type_compatible"] for r in gc)[len(gc) // 2]}
    fe.save("E8_diagnostic", out, "MEASURED (MCPToolBench++ gold), 300-query sample, B1m",
            config={"variants": list(variants)}, raw=fe.save_raw("E8_diagnostic", rows))
    for k, v in summ.items():
        print(k, round(v["hit1"]["mean"], 3), round(v["hit5"]["mean"], 3))
    print({k: v for k, v in out.items() if k != "summary"})


if __name__ == "__main__":
    main()
