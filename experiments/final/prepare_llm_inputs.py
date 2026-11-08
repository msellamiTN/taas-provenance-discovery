"""Prepare the inputs of the LLM roles used by the final evaluation (deterministic, seed 7).

* E8 sample: 50 distinct MCPToolBench++ queries per category, excluding the 60-query development split;
* MCP-Zero active requests: LiveMCPBench test (95) + development (60) + E8 sample (300);
* analyst goal contracts for the E8 sample (the other prompts already have recorded contracts);
* COLT training scenes: random 2-3 tool groups over the merged registry (no benchmark query is used);
* server tool lists, for MCP-Zero's server summaries.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "llm_inputs" / "final"
OUT.mkdir(parents=True, exist_ok=True)


def main(seed: int = 7) -> None:
    d = json.load(open(ROOT / "data/processed/registry_merged.json"))
    reg = {t["id"]: t for t in d["registry"]}
    prompts = json.load(open(ROOT / "data/llm_inputs/analyst_prompts.json"))
    dev = [p for p in prompts if p["source"] == "MCPToolBench++"]
    dev_q = {p["query"] for p in dev}
    live = [p for p in prompts if p["source"] == "LiveMCPBench"]
    rng = random.Random(seed)
    pp = d["tasks_mcptoolbenchpp"]
    sample = []
    for cat in sorted({t["category"] for t in pp}):
        uniq = {}
        for t in sorted(pp, key=lambda t: t["id"]):
            if t["category"] == cat and t["query"] not in dev_q:
                uniq.setdefault(t["query"], t)
        for t in rng.sample(list(uniq.values()), 50):
            sample.append({"id": t["id"], "source": "MCPToolBench++", "category": cat, "query": t["query"],
                           "gold_tools": t["gold_tools"]})
    json.dump(sample, open(OUT / "e8_sample.json", "w"), indent=1, ensure_ascii=False)
    # MCP-Zero request prompts
    mz = [{"id": p["id"], "query": p["query"]} for p in live + dev] + [{"id": s["id"], "query": s["query"]} for s in sample]
    for k in range(4):
        json.dump(mz[k::4], open(OUT / f"mcpzero_prompts_part{k}.json", "w"), indent=1, ensure_ascii=False)
    # analyst prompts for the E8 sample
    an = [{"id": s["id"], "source": s["source"], "category": s["category"], "query": s["query"], "context": ""}
          for s in sample]
    for k in range(3):
        json.dump(an[k::3], open(OUT / f"analyst_e8_part{k}.json", "w"), indent=1, ensure_ascii=False)
    # COLT training scenes
    by_server: dict[str, list[str]] = {}
    for t in reg.values():
        by_server.setdefault(t["server"], []).append(t["id"])
    by_cat: dict[str, list[str]] = {}
    for t in reg.values():
        by_cat.setdefault(t["category"], []).append(t["id"])
    scenes, seen = [], set()
    while len(scenes) < 450:
        n = rng.choice([2, 2, 3])
        if rng.random() < 0.6:
            s = rng.choice([s for s, v in by_server.items() if len(v) >= n])
            tools = sorted(rng.sample(by_server[s], n))
        else:
            c = rng.choice([c for c, v in by_cat.items() if len({reg[x]["server"] for x in v}) >= 2])
            tools = sorted(rng.sample(by_cat[c], n))
            if len({reg[x]["server"] for x in tools}) < 2:
                continue
        key = tuple(tools)
        if key in seen:
            continue
        seen.add(key)
        scenes.append({"scene": f"S{len(scenes):03d}", "tools": [
            {"id": x, "description": (reg[x]["description"] or "")[:300],
             "args": list(((reg[x]["input_schema"] or {}).get("properties") or {}).keys())[:8]} for x in tools]})
    for k in range(3):
        json.dump(scenes[k::3], open(OUT / f"colt_scenes_part{k}.json", "w"), indent=1, ensure_ascii=False)
    # server tool lists
    lines = []
    for s in sorted(by_server):
        lines.append(f"## {s}")
        for x in sorted(by_server[s]):
            lines.append(f"- {reg[x]['name']}: {(reg[x]['description'] or '').strip()[:160]}")
    (OUT / "server_tools.md").write_text("\n".join(lines) + "\n")
    print(len(sample), len(mz), len(an), len(scenes), len(by_server))


if __name__ == "__main__":
    main()


def toolscope_pairs(th: float = 0.7, topn: int = 5) -> None:
    """ToolScope merger candidates: top-n cosine neighbours with similarity >= th (dense stand-in encoder)."""
    import numpy as np
    from taas.retrieval import LSAEncoder
    d = json.load(open(ROOT / "data/processed/registry_merged.json"))
    R = {t["id"]: t for t in d["registry"]}
    ids = sorted(R)
    docs = [f"{R[i]['name']} {R[i]['description'] or ''} "
            f"{' '.join(((R[i]['input_schema'] or {}).get('properties') or {}).keys())}" for i in ids]
    enc = LSAEncoder().fit(docs)
    V = enc.encode(docs)
    V = V / np.maximum(np.linalg.norm(V, axis=1, keepdims=True), 1e-9)
    S = V @ V.T
    np.fill_diagonal(S, -1)
    pairs = set()
    for i in range(len(ids)):
        for j in np.argsort(-S[i])[:topn]:
            if S[i, j] >= th:
                pairs.add(tuple(sorted((int(i), int(j)))))

    def card(i):
        t = R[ids[i]]
        args = ", ".join(((t["input_schema"] or {}).get("properties") or {}).keys())
        return {"id": t["id"], "description": (t["description"] or "")[:400], "args": args}
    items = [{"pair": f"P{n:04d}", "a": card(a), "b": card(b), "cos": round(float(S[a, b]), 3)}
             for n, (a, b) in enumerate(sorted(pairs))]
    for k in range(2):
        json.dump(items[k::2], open(OUT / f"toolscope_pairs_part{k}.json", "w"), indent=1, ensure_ascii=False)
    print("toolscope pairs", len(items))
