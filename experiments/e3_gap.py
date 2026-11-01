"""E3 — H3: gap analysis with the conditional profile shrinks toolkits without loss of task coverage.

Tasks: LiveMCPBench (95 multi-tool tasks, annotated tool chains) and a 60-query sample of
MCPToolBench++ (10 per category). Goal contracts come from the analyst role (Claude Sonnet, recorded).
All systems search the same 569-tool registry with the same retriever.

Systems
  ours              gap analysis (measured profile + declared priors) → Alg. 2 → Alg. 3A
  ours-nogap        same, every goal in the gap (no model coverage)            [ablation]
  ours-strict       unmeasured classes treated as not native (paper's rule 2)  [ablation]
  per-subtask       one tool per subgoal by hybrid retrieval (no checks)
  per-subtask-gap   one tool per *gap* goal (isolates set-level composition)
  rag-top3/top5     RAG-MCP style dense retrieval of the whole prompt
  mcp-zero          route to best server, then best tool, per goal
  all-tools         the whole registry in context

Metrics: |K|, context tokens of the exposed definitions, gold recall (any server::name the gold
name resolves to), boundary recall (gold tools that cross the model boundary according to J),
precision, abstention, certificate validity, bridge ratio β, time.
"""
from __future__ import annotations

import copy
import sys

from common import (SEEDS, Timer, analyst, banner, bootstrap_ci, gold_precision, gold_recall, gold_sets, load_processed,
                    mean_ci, profile, prompts, save, tasks_from_processed)

from taas import baselines
from taas.composer import ComposerConfig
from taas.engine import DiscoveryEngine, EngineConfig
from taas.goals import parse_goal_spec
from taas.manifest import manifest_tokens, raw_tokens
from taas.policy import Policy
from taas.realreg import build_contracts, truth

OPEN_POLICY = dict(required=(), allowed=("read(*)", "write(*)", "delete(*)", "exec", "egress(*)", "money", "session"),
                   lmin=0.0, forbidden_pairs=())


def open_policy() -> Policy:
    return Policy.make("open", **OPEN_POLICY)


def boundary(t: str, J) -> bool:
    tr = J.get(t)
    return tr is not None and any(e.cls != "read" or e.scope not in ("local",) for e in tr.effects)


def make_engine(prof, use_gap=True, ctx_mode="all_predecessors", **ccfg):
    cs = build_contracts()
    cfg = EngineConfig(ComposerConfig(**ccfg), use_gap=use_gap, ctx_mode=ctx_mode)
    return DiscoveryEngine(cs, prof, cfg=cfg, pair_policy=open_policy())


def run(task_filter=None, analyst_model="sonnet", verbose=True) -> dict:
    banner("E3 / H3: does gap analysis shrink toolkits without losing the tools the task needs? "
           "(compare |K|, tokens and gold recall across systems)")
    d = load_processed()
    J = truth()
    gold = {t.id: t for t in tasks_from_processed(d, "livemcpbench") + tasks_from_processed(d, "mcptoolbenchpp")}
    an = analyst(analyst_model)
    ps = [p for p in prompts() if p["source"] != "Scenario" and (task_filter is None or task_filter(p))]
    pol = open_policy()
    prof = profile("sonnet", strict=False)
    engines = {
        "ours": make_engine(prof),
        "ours-nogap": make_engine(prof, use_gap=False),
        "ours-strict": make_engine(profile("sonnet", strict=True)),
    }
    ref = engines["ours"]
    pool = list(ref.H.contracts)
    rows = []
    missing = 0
    for p in ps:
        rec = an.decompose(p["id"], p["query"], p.get("context", ""))
        if rec is None:
            missing += 1
            continue
        G = [set(x) for x in gold_sets(gold[p["id"]].gold_tools)]
        Gb = [alts for alts in G if any(boundary(t, J) for t in alts)]
        base = {"id": p["id"], "source": p["source"], "category": p["category"], "n_gold": len(G),
                "n_goals": len(rec.get("goals", []))}
        for name, eng in engines.items():
            spec = parse_goal_spec(copy.deepcopy(rec), p["query"])
            with Timer() as tm:
                r = eng.discover(spec, pol)
            K = r.toolkit or []
            rows.append(base | {"system": name, "size": len(K), "abstain": r.toolkit is None,
                                "tokens": manifest_tokens(r.manifest["tools"]) if r.manifest else 0,
                                "raw_tokens": raw_tokens(eng.H, K), "recall": gold_recall(K, G),
                                "boundary_recall": gold_recall(K, Gb), "precision": gold_precision(K, G),
                                "gap": len(r.gap.gap), "valid": bool(r.certificate and r.certificate.valid),
                                "beta": r.certificate.bridge_ratio if r.certificate else float("nan"),
                                "chi": r.counterexample.kind if r.counterexample else "",
                                "refined": bool(r.trace and r.trace.steps), "time_s": tm.s, "toolkit": K})
        spec = parse_goal_spec(copy.deepcopy(rec), p["query"])
        gr = ref.gap(copy.deepcopy(spec))
        bl = {
            "per-subtask": baselines.per_subtask(ref.retriever, spec, pool, 1),
            "per-subtask-gap": baselines.per_subtask(ref.retriever, gr.spec, pool, 1, include_native=False),
            "rag-top3": baselines.rag_topk(ref.retriever, p["query"], pool, 3),
            "rag-top5": baselines.rag_topk(ref.retriever, p["query"], pool, 5),
            "mcp-zero": baselines.mcp_zero(ref.retriever, spec, pool),
            "all-tools": pool,
        }
        for name, K in bl.items():
            rows.append(base | {"system": name, "size": len(K), "abstain": False, "tokens": raw_tokens(ref.H, K),
                                "raw_tokens": raw_tokens(ref.H, K), "recall": gold_recall(K, G),
                                "boundary_recall": gold_recall(K, Gb), "precision": gold_precision(K, G),
                                "gap": len(gr.gap), "valid": False, "beta": float("nan"), "chi": "",
                                "refined": False, "time_s": 0.0, "toolkit": K if name != "all-tools" else []})
    systems = list(dict.fromkeys(r["system"] for r in rows))
    summary = {}
    for src in ("LiveMCPBench", "MCPToolBench++", "all"):
        for s in systems:
            sel = [r for r in rows if r["system"] == s and (src == "all" or r["source"] == src)]
            if not sel:
                continue
            summary[f"{src}|{s}"] = {k: mean_ci(r[k] for r in sel) for k in
                                     ("size", "tokens", "recall", "boundary_recall", "precision", "time_s")} | {
                "abstain_rate": sum(r["abstain"] for r in sel) / len(sel),
                "valid_rate": sum(r["valid"] for r in sel) / len(sel),
                "recall_ci_boot": bootstrap_ci(r["recall"] for r in sel),
                "beta": mean_ci(r["beta"] for r in sel)}
    if verbose:
        for src in ("LiveMCPBench", "MCPToolBench++"):
            print(f"\n[{src}] {'system':16s} {'|K|':>6} {'tokens':>8} {'recall':>7} {'bnd-rec':>7} {'prec':>6} "
                  f"{'abst':>5} {'valid':>6}")
            for s in systems:
                m = summary.get(f"{src}|{s}")
                if m:
                    print(f"[{src}] {s:16s} {m['size']['mean']:6.2f} {m['tokens']['mean']:8.0f} "
                          f"{m['recall']['mean']:7.3f} {m['boundary_recall']['mean']:7.3f} "
                          f"{m['precision']['mean']:6.3f} {m['abstain_rate']:5.2f} {m['valid_rate']:6.2f}")
        print(f"\nprompts without a recorded analyst output: {missing}")
    res = {"rows": rows, "summary": summary, "missing": missing, "analyst": an.name}
    save(f"e3_gap_{analyst_model}", res)
    return res


if __name__ == "__main__":
    run(analyst_model=sys.argv[1] if len(sys.argv) > 1 else "sonnet")
