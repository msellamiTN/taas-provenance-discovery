"""E3-tune — Stage 2 (baseline tuning) on the DEV split only (MCPToolBench++ sample, 60 queries).

Sweeps the retrieval budget K and the relevance weight w_rel added to Eq. (6) (w_rel = 0 is the
paper's objective). The chosen setting is then used unchanged on the TEST split (LiveMCPBench).
"""
from __future__ import annotations

import copy
import itertools

from common import analyst, banner, gold_recall, gold_sets, load_processed, mean_ci, profile, prompts, save, \
    tasks_from_processed

from e3_gap import make_engine, open_policy
from taas.goals import parse_goal_spec


def main(Ks=(3, 5, 10), rels=(0.0, 1.0, 3.0, 10.0)) -> dict:
    banner("E3-tune (dev = MCPToolBench++ sample): retrieval budget K × relevance weight in the cost")
    d = load_processed()
    gold = {t.id: t for t in tasks_from_processed(d, "mcptoolbenchpp")}
    an = analyst("sonnet")
    ps = [p for p in prompts() if p["source"] == "MCPToolBench++"]
    prof = profile("sonnet", strict=False)
    pol = open_policy()
    out = {}
    for K, rel in itertools.product(Ks, rels):
        eng = make_engine(prof, K=K, relevance=rel)
        rec, size, abst = [], [], 0
        for p in ps:
            spec = parse_goal_spec(copy.deepcopy(an.decompose(p["id"], p["query"])), p["query"])
            r = eng.discover(spec, pol)
            rec.append(gold_recall(r.toolkit or [], gold_sets(gold[p["id"]].gold_tools)))
            size.append(len(r.toolkit or []))
            abst += r.toolkit is None
        out[f"K={K}|rel={rel}"] = {"recall": mean_ci(rec), "size": mean_ci(size), "abstain": abst / len(ps)}
        print(f"K={K:2d} w_rel={rel:5.1f}  recall={out[f'K={K}|rel={rel}']['recall']['mean']:.3f} "
              f"|K|={out[f'K={K}|rel={rel}']['size']['mean']:.2f} abstain={abst / len(ps):.2f}", flush=True)
    best = max(out, key=lambda k: (out[k]["recall"]["mean"], -out[k]["size"]["mean"]))
    print("selected on dev:", best)
    save("e3_tune", {"grid": out, "selected": best})
    return out


if __name__ == "__main__":
    main()
