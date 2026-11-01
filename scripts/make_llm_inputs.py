"""Prepare the inputs handed to the LLM roles (recorded once, replayed by experiments).

1. data/llm_inputs/label_part{k}.txt   – compact tool definitions for silver effect/type labelling
2. data/llm_inputs/analyst_prompts.json – prompts for the analyst role (no tool information)
3. data/calibration/items/*.txt         – ρ_LLM calibration items, stratified by n
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from taas.data.registries import load_processed  # noqa: E402

OUT = ROOT / "data" / "llm_inputs"
CAL = ROOT / "data" / "calibration"

SCENARIOS = [
    {"id": "scenario-reviews", "category": "Scenario",
     "query": "Analyze customer reviews, identify the most frequent complaints, and generate a report with recommendations.",
     "context": "The review database holds about 300 English reviews; approximate accuracy is acceptable. Reports go under /reports."},
    {"id": "scenario-github-slack", "category": "Scenario",
     "query": "Summarise the open bug issues of acme/api and post a digest to Slack #eng",
     "context": "acme/api has a few dozen open bug issues."},
    {"id": "scenario-revenue", "category": "Scenario",
     "query": "Compute last week's revenue per region from the sales database, write the table to /reports/weekly.csv and notify #finance",
     "context": "Last week's sales table has about 40,000 rows; revenue figures must be exact."},
]


def compact_tool(t: dict) -> str:
    props = (t["input_schema"] or {}).get("properties", {}) or {}
    req = set((t["input_schema"] or {}).get("required", []) or [])
    args = []
    for a, s in list(props.items())[:12]:
        ty = (s or {}).get("type", "any") if isinstance(s, dict) else "any"
        d = ((s or {}).get("description") or "")[:60].replace("\n", " ") if isinstance(s, dict) else ""
        args.append(f"{a}{'*' if a in req else ''}:{ty}" + (f" ({d})" if d else ""))
    desc = " ".join((t["description"] or "").split())[:320]
    return f"[{t['id']}] {desc}\n    args: {'; '.join(args) if args else '-'}"


def main(n_parts: int = 3, seed: int = 0) -> None:
    d = load_processed()
    OUT.mkdir(parents=True, exist_ok=True)
    reg = d["registry"]
    # 1. labelling chunks (servers kept together so a part sees whole servers)
    servers = sorted({t["server"] for t in reg})
    parts: list[list[dict]] = [[] for _ in range(n_parts)]
    sizes = [0] * n_parts
    for s in sorted(servers, key=lambda s: -sum(1 for t in reg if t["server"] == s)):
        k = sizes.index(min(sizes))
        tools = [t for t in reg if t["server"] == s]
        parts[k].extend(tools)
        sizes[k] += len(tools)
    for k, ts in enumerate(parts):
        lines = [compact_tool(t) for t in sorted(ts, key=lambda t: t["id"])]
        (OUT / f"label_part{k}.txt").write_text("\n".join(lines) + "\n")
        print(f"label_part{k}: {len(ts)} tools")
    # 2. analyst prompts
    rng = random.Random(seed)
    pp = d["tasks_mcptoolbenchpp"]
    sample = []
    for cat in sorted({t["category"] for t in pp}):
        uniq = {}
        for t in pp:
            if t["category"] == cat:
                uniq.setdefault(t["query"], t)
        qs = sorted(uniq.values(), key=lambda t: t["id"])
        sample += rng.sample(qs, 10)
    prompts = (
        [{"id": s["id"], "source": "Scenario", "category": s["category"], "query": s["query"],
          "context": s["context"]} for s in SCENARIOS]
        + [{"id": t["id"], "source": "LiveMCPBench", "category": t["category"], "query": t["query"], "context": ""}
           for t in d["tasks_livemcpbench"]]
        + [{"id": t["id"], "source": "MCPToolBench++", "category": t["category"], "query": t["query"], "context": ""}
           for t in sample]
    )
    json.dump(prompts, open(OUT / "analyst_prompts.json", "w"), indent=1, ensure_ascii=False)
    print("analyst prompts:", len(prompts))
    # 3. calibration items
    make_calibration(seed)


POS = ["great battery life", "fast delivery and well packed", "excellent build quality", "works perfectly",
       "very comfortable to use", "the support team was helpful", "great value for money", "screen is bright and sharp"]
NEG = ["battery died after two days", "arrived broken", "terrible customer support", "stopped working after a week",
       "the strap is uncomfortable", "overpriced for what it is", "app keeps crashing", "screen scratches too easily"]
FIRST = ["Ana", "Bilel", "Chen", "Dora", "Emeka", "Farah", "Goran", "Hana", "Ivo", "Jana", "Karim", "Lea", "Malik",
         "Nora", "Omar", "Pia", "Rami", "Sara", "Taha", "Una", "Victor", "Wafa", "Yara", "Zied"]
LAST = ["Silva", "Ben Ali", "Wang", "Novak", "Okafor", "Haddad", "Petrov", "Sato", "Horvat", "Kral", "Mansour",
        "Dupont", "Rossi", "Jensen", "Trabelsi", "Moreau", "Nakamura", "Costa", "Bauer", "Kaya"]
CITY = ["Porto", "Tunis", "Lyon", "Osaka", "Lagos", "Sfax", "Graz", "Bergen", "Quito", "Pune", "Cork", "Turin",
        "Leeds", "Izmir", "Sousse", "Dakar", "Krakow", "Malaga", "Utrecht", "Bilbao"]
WORDS = ["delay", "refund", "battery", "screen", "price", "support", "strap", "app", "shipping", "noise"]


def make_calibration(seed: int, buckets=(10, 40, 160, 640), reps: int = 4) -> None:
    rng = random.Random(seed + 1)
    items_dir = CAL / "items"
    items_dir.mkdir(parents=True, exist_ok=True)
    index, gold = [], {}
    for cls in ("aggregate_sum", "count", "classify", "extract"):
        for n in buckets:
            for r in range(reps):
                iid = f"{cls}-n{n}-r{r}"
                if cls == "aggregate_sum":
                    xs = [rng.randint(10, 99) for _ in range(n)]
                    body = "\n".join(str(x) for x in xs)
                    q = "What is the exact sum of all the numbers listed below (one per line)? Answer with a single integer."
                    gold[iid] = {"answer": sum(xs), "exact": True}
                elif cls == "count":
                    target = rng.choice(WORDS)
                    xs = [rng.choice(WORDS) for _ in range(n)]
                    body = "\n".join(xs)
                    q = f"How many lines below are exactly the word '{target}'? Answer with a single integer."
                    gold[iid] = {"answer": xs.count(target), "exact": True}
                elif cls == "classify":
                    p = rng.choice([0.62, 0.68, 0.32, 0.38])
                    xs = [("+", rng.choice(POS)) if rng.random() < p else ("-", rng.choice(NEG)) for _ in range(n)]
                    body = "\n".join(f"review {i + 1}: {txt}" for i, (_, txt) in enumerate(xs))
                    npos = sum(1 for s, _ in xs if s == "+")
                    maj = "positive" if npos * 2 > n else "negative" if npos * 2 < n else "tie"
                    q = "Classify each review below as positive or negative. Is the majority positive or negative? Answer 'positive' or 'negative'."
                    gold[iid] = {"answer": maj, "exact": False}
                else:
                    recs = []
                    for i in range(n):
                        recs.append((f"K{rng.randint(1000, 9999)}{i:03d}", f"{rng.choice(FIRST)} {rng.choice(LAST)}",
                                     rng.choice(CITY)))
                    tid, _, tcity = rng.choice(recs)
                    body = "\n".join(f"id={a} | name={b} | city={c}" for a, b, c in recs)
                    q = f"In the records below, which city belongs to the record with id {tid}? Answer with the city name."
                    gold[iid] = {"answer": tcity, "exact": False}
                (items_dir / f"{iid}.txt").write_text(f"ITEM {iid}\nQUESTION: {q}\n---BEGIN DATA---\n{body}\n---END DATA---\n")
                index.append({"id": iid, "class": cls, "n": n, "file": f"data/calibration/items/{iid}.txt"})
    rng.shuffle(index)
    json.dump(index, open(CAL / "index.json", "w"), indent=1)
    json.dump(gold, open(CAL / "gold.json", "w"), indent=1)
    print("calibration items:", len(index))


if __name__ == "__main__":
    main()
