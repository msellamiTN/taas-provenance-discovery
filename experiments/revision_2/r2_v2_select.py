"""Revision 2: choose the composition configuration of PaMCP-v2 on the 60 development prompts only.

Candidates: the paper's configuration and variants that change how typing enters candidate retrieval and goal
coverage (X3 found the structural ranking harmful unless goal and tool typings agree):
  paper      components lex+den+str, certain-type filter
  lex        components lex, certain-type filter
  lex_unc    components lex, uncertain (kind-level) matching allowed, recorded as uncertain in the certificate
  lexden_unc components lex+den, uncertain matching
  K10 variants of the two uncertain configurations with K = 10.
Selection rule (fixed here before running): highest mean group recall on dev; ties broken by lower abstention, then
smaller toolkits, then list order. The chosen configuration is written to R2_v2_selection.json and used unchanged on
the test tasks (LiveMCPBench) after the preregistration amendment.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "final"))

import fe  # noqa: E402
import methods as M  # noqa: E402
from taas.composer import ComposerConfig  # noqa: E402
from taas.engine import DiscoveryEngine, EngineConfig  # noqa: E402

CONFIGS = {
    "paper": dict(),
    "lex": dict(components=("lex",)),
    "lex_unc": dict(components=("lex",), uncertain_ok=True),
    "lexden_unc": dict(components=("lex", "den"), uncertain_ok=True),
    "lex_unc_K10": dict(components=("lex",), uncertain_ok=True, K=10),
    "lexden_unc_K10": dict(components=("lex", "den"), uncertain_ok=True, K=10),
}


def main() -> None:
    cs = fe.contracts_cached("verified")
    prof = fe.profile("sonnet", strict=False)
    dev = fe.tasks_dev()
    res, rows = {}, []
    for name, kw in CONFIGS.items():
        eng = DiscoveryEngine(cs, prof, cfg=EngineConfig(ComposerConfig(**kw)), pair_policy=M.open_policy())
        rec_, ab_, sz_ = [], [], []
        for t in dev:
            spec, rec = fe.spec_for(t)
            if spec is None:
                continue
            pol, _ = M.least_privilege(rec)
            r = eng.discover(copy.deepcopy(spec), pol)
            K = r.toolkit or []
            rec_.append(fe.group_recall(K, t["gold"]))
            ab_.append(float(r.toolkit is None))
            sz_.append(len(K))
            rows.append({"config": name, "id": t["id"], "recall": rec_[-1], "abstain": ab_[-1], "size": sz_[-1],
                         "toolkit": K})
        res[name] = {"recall": float(np.nanmean(rec_)), "abstain": float(np.mean(ab_)), "size": float(np.mean(sz_)),
                     "n": len(rec_)}
        print(name, {k: round(v, 3) for k, v in res[name].items()})
    order = list(CONFIGS)
    chosen = max(order, key=lambda c: (res[c]["recall"], -res[c]["abstain"], -res[c]["size"], -order.index(c)))
    fe.save("R2_v2_selection", {"results": res, "chosen": chosen, "chosen_config": CONFIGS[chosen],
                                "rule": "max dev recall; ties: lower abstention, smaller size, list order"},
            "MEASURED on the 60 development prompts only", config={"configs": {k: str(v) for k, v in CONFIGS.items()}},
            raw=fe.save_raw("R2_v2_selection", rows))
    print("chosen", chosen, CONFIGS[chosen])


if __name__ == "__main__":
    main()
