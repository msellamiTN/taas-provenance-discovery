"""E8 — Offline evaluation of the MCP-Bench integration path (TaaSMCPBenchAdapter.select).

MCP-Bench discovers tools by launching its servers, so this experiment reproduces the adapter's
input exactly but offline: the 525-tool LiveMCPTool catalogue is converted to MCP-Bench's
``all_tools`` map (key ``server:tool``; fields name, original_name, server, description,
input_schema; MCP-Bench does not forward annotations or outputSchema), the 95 LiveMCPBench tasks
provide gold tool chains, and goal specs are replayed from recorded analyst runs.

Settings follow docs/MCP_BENCH_INTEGRATION.md: ``Policy.make("benchmark-default")``, default
EngineConfig, and the runner rule that an abstention *or an empty selection* skips the agent.

Factors
  code     codex (feature/taas-mcpbench-integration) | fixed (this branch)   [--src selects code]
  analyst  prompt-1.0 (Codex MCPBenchGoalAnalyst) | prompt-1.1 (vocabulary-aligned) |
           prompt-1.1+theta (1.1 plus the typed catalogue's domains Θ, Algorithm 1 line 2) |
           guide (docs/ANALYST_GUIDE.md, the analyst used in E3)
  typing   lexical (adapter default) | llm (silver τ of Section 6.1, hash-bound; fixed code only)
  policy   benchmark-default (documented: read(*), egress(*), session) | open (all effect classes,
           no forbidden-pair templates — the E3 policy, isolating engine from policy)

The adapter rebuilds a DiscoveryEngine for every task (~3 s on 525 tools). For speed this script
memoises engine construction per configuration (same contracts, profile and config), resetting
the composer config before each request; ``--check-cache`` verifies the outputs are identical.

Usage: python experiments/e8_mcpbench_adapter.py --label fixed [--src /path/to/other/src]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser()
ap.add_argument("--src", default=str(ROOT / "src"), help="taas source tree to evaluate")
ap.add_argument("--label", required=True)
ap.add_argument("--check-cache", type=int, default=0, help="verify cache equivalence on N tasks, then exit")
args = ap.parse_args()
sys.path.insert(0, args.src)

import copy  # noqa: E402
import inspect  # noqa: E402

import taas.mcpbench as mcpbench_mod  # noqa: E402

from taas.data.registries import load_processed, tasks_from_processed  # noqa: E402
from taas.mcpbench import TaaSMCPBenchAdapter, raw_tools_from_mcpbench  # noqa: E402
from taas.model_profile import ModelProfile  # noqa: E402
from taas.policy import Policy  # noqa: E402

REC = ROOT / "data" / "llm_records"
ANALYSTS = {"prompt-1.0": [REC / "analyst_mcpbench_prompt_v1_0_sonnet.jsonl"],
            "prompt-1.1": [REC / "analyst_mcpbench_prompt_v1_1_sonnet.jsonl"],
            "prompt-1.1+theta": [REC / "analyst_mcpbench_prompt_v1_1_theta_sonnet.jsonl"],
            "guide": [REC / "analyst_sonnet_A.jsonl", REC / "analyst_sonnet_B.jsonl"]}


def catalogue(d: dict) -> dict:
    """LiveMCPTool tools in MCP-Bench's discovered-tool map shape."""
    out = {}
    for r in d["registry"]:
        if r["source"] != "LiveMCPTool":
            continue
        out[f"{r['server']}:{r['name']}"] = {"name": r["name"], "original_name": r["name"], "server": r["server"],
                                            "description": r["description"], "input_schema": r["input_schema"]}
    return out


def load_specs(paths) -> dict[str, dict]:
    specs = {}
    for p in paths:
        if not p.exists():
            continue
        for line in open(p, encoding="utf-8"):
            if line.strip():
                x = json.loads(line)
                specs[str(x["id"])] = x
    return specs


class Replay:
    """goal_spec_factory replaying recorded analyst output for a task text."""

    def __init__(self, specs: dict[str, dict], id_by_text: dict[str, str], version: str) -> None:
        self.specs, self.id_by_text, self.prompt_version = specs, id_by_text, version
        self.last_usage, self.last_response = {}, None

    def __call__(self, task: str) -> dict:
        spec = {k: v for k, v in self.specs[self.id_by_text[task]].items() if k != "id"}
        self.last_response = json.dumps(spec)
        return spec


_ENGINE_CACHE: dict = {}
_RealEngine = mcpbench_mod.DiscoveryEngine


def _cached_engine(contracts, profile, trust=None, cfg=None, **kw):
    key = (tuple((c.tool, c.h, str(c.head), tuple(map(str, c.tail)), c.tool_class, tuple(sorted(map(str, c.eff))))
                 for c in contracts), id(profile), id(cfg))
    eng = _ENGINE_CACHE.get(key)
    if eng is None:
        eng = _RealEngine(contracts, profile, trust=trust, cfg=cfg, **kw) if trust is not None else \
            _RealEngine(contracts, profile, cfg=cfg, **kw)
        eng._pristine = copy.deepcopy(eng.cfg)
        _ENGINE_CACHE[key] = eng
    eng.cfg = copy.deepcopy(eng._pristine)
    eng.composer.cfg = eng.cfg.composer
    return eng


def policies() -> dict:
    return {"default": Policy.make("benchmark-default"),
            "open": Policy.make("open", allowed=("read(*)", "write(*)", "delete(*)", "exec", "egress(*)", "money",
                                                 "session"), forbidden_pairs=())}


def main() -> None:
    d = load_processed()
    tools = catalogue(d)
    raw, _ = raw_tools_from_mcpbench(tools)
    cat_ids = {t.id for t in raw}
    silver = json.load(open(REC / "silver_labels.json"))
    llm_typing = {t.id: {"in": silver[t.id]["in"], "out": silver[t.id]["out"], "class": silver[t.id]["class"],
                         "hash": t.definition_hash()} for t in raw if t.id in silver}
    tasks = tasks_from_processed(d, "livemcpbench")
    id_by_text = {t.query: t.id for t in tasks}
    gold = {t.id: [set(g.split("|")) & cat_ids for g in t.gold_tools] for t in tasks}
    gold = {k: [a for a in v if a] for k, v in gold.items()}
    profile = ModelProfile.load(ROOT / "data/processed/profile_sonnet.json")
    profile.strict = False
    supports_typing = "typing" in inspect.signature(TaaSMCPBenchAdapter.__init__).parameters
    silver_ro = {t: not (silver[t].get("modifies_state") or any(e.split("(")[0] in ("write", "delete", "exec", "money")
                                                                 for e in silver[t].get("effects", [])))
                 for t in silver}
    read_only_task = {t.id: bool(gold[t.id]) and all(any(silver_ro.get(x, False) for x in alts) for alts in gold[t.id])
                      for t in tasks}
    if args.check_cache:
        specs = load_specs(ANALYSTS["guide"])
        sub = [t for t in tasks if t.id in specs][:args.check_cache]
        outs = []
        for cached in (False, True):
            mcpbench_mod.DiscoveryEngine = _cached_engine if cached else _RealEngine
            ad = TaaSMCPBenchAdapter(profile, Replay(specs, id_by_text, "guide"), policies()["open"],
                                     **({"typing": llm_typing} if supports_typing else {}))
            outs.append([(sorted(ad.select(t.query, tools).tools), ) for t in sub])
        print("cache equivalence on", len(sub), "tasks:", outs[0] == outs[1])
        return
    mcpbench_mod.DiscoveryEngine = _cached_engine
    rows = []
    for an_name, paths in ANALYSTS.items():
        specs = load_specs(paths)
        if not specs:
            print(f"skip {an_name}: no recorded analyst output")
            continue
        for typing_mode, (pol_name, pol) in [(tm, pp) for tm in (("lexical", "llm") if supports_typing else ("lexical",))
                                             for pp in policies().items()]:
            kw = {"typing": llm_typing} if typing_mode == "llm" else {}
            adapter = TaaSMCPBenchAdapter(profile, Replay(specs, id_by_text, an_name), pol, **kw)
            for t in tasks:
                if t.id not in specs:
                    continue
                t0 = time.perf_counter()
                try:
                    sel = adapter.select(t.query, tools)
                    err = None
                except Exception as e:  # recorded, never hidden
                    sel, err = None, f"{type(e).__name__}: {e}"
                dt = time.perf_counter() - t0
                if sel is None:
                    rows.append({"analyst": an_name, "typing": typing_mode, "policy": pol_name, "task": t.id,
                                 "error": err, "runner_abstained": True, "recall": 0.0, "size": 0,
                                 "read_only_task": read_only_task[t.id]})
                    continue
                tr = sel.trace
                K = {f"{v['server']}::{v['original_name']}" for v in sel.tools.values()}
                G = gold[t.id]
                rec = sum(1 for alts in G if alts & K) / len(G) if G else float("nan")
                cx = tr.get("counterexample") or {}
                cert = tr.get("certificate") or {}
                voc = tr.get("goal_spec_vocabulary") or {}
                rows.append({
                    "analyst": an_name, "typing": typing_mode, "policy": pol_name, "task": t.id, "error": None,
                    "read_only_task": read_only_task[t.id],
                    "engine_abstained": tr["abstained"], "runner_abstained": tr["abstained"] or not sel.tools,
                    "empty_valid": (not tr["abstained"]) and not sel.tools,
                    "size": len(K), "recall": rec,
                    "valid": bool(cert) and all(cert.get("checks", {}).get(k) is True for k in "SCPELV"),
                    "chi": cx.get("kind", ""), "chi_check": cx.get("check", ""),
                    "binding_violation": bool(cx.get("witness", {}).get("failed_checks")) and
                                         cx.get("check") == "CERTIFICATE",
                    "unknown_kinds": len(voc.get("unknown_type_kinds", [])),
                    "dropped_effects": len(voc.get("unknown_effects", [])),
                    "aliased_effects": len(voc.get("aliased_effects", [])),
                    "time_s": dt, "toolkit": sorted(K)})
    summary = {}
    for key in sorted({(r["analyst"], r["typing"], r["policy"]) for r in rows}):
        sel = [r for r in rows if (r["analyst"], r["typing"], r["policy"]) == key]
        ro = [r for r in sel if r["read_only_task"]]
        n = len(sel)
        rec = [r["recall"] for r in sel if r["recall"] == r["recall"]]
        ran = [r for r in sel if not r["runner_abstained"]]
        summary["|".join(key)] = {
            "n": n, "runner_abstain": sum(r["runner_abstained"] for r in sel) / n,
            "engine_abstain": sum(r.get("engine_abstained", True) for r in sel) / n,
            "empty_valid": sum(r.get("empty_valid", False) for r in sel) / n,
            "certificate_rejections": sum(r.get("binding_violation", False) for r in sel) / n,
            "recall": sum(rec) / max(1, len(rec)),
            "recall_when_run": (sum(r["recall"] for r in ran if r["recall"] == r["recall"]) / max(1, len(ran))),
            "size_when_run": sum(r["size"] for r in ran) / max(1, len(ran)),
            "goal_specs_with_unknown_kinds": sum(1 for r in sel if r.get("unknown_kinds", 0)) / n,
            "goal_specs_with_dropped_effects": sum(1 for r in sel if r.get("dropped_effects", 0)) / n,
            "goal_specs_with_aliased_effects": sum(1 for r in sel if r.get("aliased_effects", 0)) / n,
            "read_only_tasks": len(ro),
            "read_only_runner_abstain": sum(r["runner_abstained"] for r in ro) / max(1, len(ro)),
            "read_only_recall": sum(r["recall"] for r in ro if r["recall"] == r["recall"]) / max(1, len(ro)),
            "chi": dict(Counter(f"{r.get('chi', '')}/{r.get('chi_check', '')}" for r in sel if r["runner_abstained"])),
            "errors": sum(1 for r in sel if r.get("error")),
            "mean_time_ms": 1000 * sum(r.get("time_s", 0) for r in sel) / n}
    print(f"\nE8 [{args.label}] adapter on {len(tools)} tools × {len(tasks)} LiveMCPBench tasks "
          f"(typing param supported: {supports_typing})")
    print(f"{'analyst|typing|policy':30s} {'runner-abst':>11} {'cert-rej':>8} {'recall':>7} {'rec|run':>7} "
          f"{'|K|run':>6} {'RO-abst':>7} {'RO-rec':>6} {'unk-kind':>8}")
    for k, m in summary.items():
        print(f"{k:30s} {m['runner_abstain']:11.2f} {m['certificate_rejections']:8.2f} {m['recall']:7.3f} "
              f"{m['recall_when_run']:7.3f} {m['size_when_run']:6.2f} {m['read_only_runner_abstain']:7.2f} "
              f"{m['read_only_recall']:6.3f} {m['goal_specs_with_unknown_kinds']:8.2f}")
    out = ROOT / "results" / f"e8_mcpbench_adapter_{args.label}.json"
    json.dump({"label": args.label, "src": args.src, "summary": summary, "rows": rows}, open(out, "w"), indent=1)
    print("wrote", out)


if __name__ == "__main__":
    main()
