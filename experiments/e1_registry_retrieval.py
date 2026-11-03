"""E1 — leakage-separated retrieval evaluation on the pinned MCP benchmark snapshot.

The ranking path receives only task query text and tool-definition contracts.
Gold tool mappings are consulted only after ranking, inside the metric functions.
This is a retrieval-only experiment: it does not construct GoalSpecs, apply policy
eligibility, run the composer, invoke MCP tools, or measure task completion.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean

from taas.contracts import extract_contract
from taas.data.registries import load_processed, raw_tools_from_processed, tasks_from_processed
from taas.retrieval import HybridRetriever, LSAEncoder


DEFAULT_K = (1, 5, 10, 20)
COMPONENTS = {
    "bm25": ("lex",),
    "lsa": ("den",),
    "hybrid_lex_lsa": ("lex", "den"),
}


def resolved_gold_groups(task, known_ids: set[str]) -> tuple[list[set[str]], int]:
    """Return any-of alternative groups, preserving ambiguity and excluding unresolved IDs."""
    groups: list[set[str]] = []
    unresolved = 0
    for raw in task.gold_tools or []:
        alternatives = {part.strip() for part in str(raw).split("|") if part.strip()}
        resolved = alternatives & known_ids
        unresolved += len(alternatives - known_ids)
        if resolved:
            groups.append(resolved)
    return groups, unresolved + len(task.gold_unresolved or [])


def group_ranks(ranking: list[str], groups: list[set[str]]) -> list[int]:
    """Rank each required group by the first-ranked member of any-of alternatives."""
    positions = {tool: i + 1 for i, tool in enumerate(ranking)}
    return sorted(min((positions[t] for t in group if t in positions), default=len(ranking) + 1)
                  for group in groups)


def metrics_at_k(ranks: list[int], n_groups: int, k: int) -> dict[str, float]:
    hits = sum(rank <= k for rank in ranks)
    return {
        "group_precision": hits / k,
        "group_recall": hits / n_groups if n_groups else 0.0,
    }


def task_metrics(ranking: list[str], groups: list[set[str]], ks=DEFAULT_K) -> dict:
    if not groups:
        return {"n_gold_groups": 0, "mrr": 0.0, "map": 0.0, "ndcg": 0.0,
                "at_k": {str(k): {"group_precision": 0.0, "group_recall": 0.0} for k in ks}}
    ranks = group_ranks(ranking, groups)
    reciprocal_rank = 1.0 / ranks[0] if ranks and ranks[0] <= len(ranking) else 0.0
    precisions = [(i + 1) / rank for i, rank in enumerate(ranks) if rank <= len(ranking)]
    ap = sum(precisions) / len(groups)
    dcg = sum(1.0 / math.log2(rank + 1) for rank in ranks if rank <= len(ranking))
    ideal = sum(1.0 / math.log2(i + 2) for i in range(min(len(groups), len(ranking))))
    return {
        "n_gold_groups": len(groups),
        "mrr": reciprocal_rank,
        "map": ap,
        "ndcg": dcg / ideal if ideal else 0.0,
        "at_k": {str(k): metrics_at_k(ranks, len(groups), k) for k in ks},
    }


def _macro(rows: list[dict], ks=DEFAULT_K) -> dict:
    if not rows:
        return {"n_evaluable_tasks": 0, "mrr": 0.0, "map": 0.0, "ndcg": 0.0,
                "at_k": {str(k): {"group_precision": 0.0, "group_recall": 0.0} for k in ks}}
    return {
        "n_evaluable_tasks": len(rows),
        "mrr": mean(r["mrr"] for r in rows),
        "map": mean(r["map"] for r in rows),
        "ndcg": mean(r["ndcg"] for r in rows),
        "at_k": {
            str(k): {
                "group_precision": mean(r["at_k"][str(k)]["group_precision"] for r in rows),
                "group_recall": mean(r["at_k"][str(k)]["group_recall"] for r in rows),
            } for k in ks
        },
    }


def evaluate_snapshot(data: dict, ks=DEFAULT_K) -> dict:
    raw_tools = raw_tools_from_processed(data)
    contracts = [extract_contract(tool, typing=None, store=None) for tool in raw_tools]
    known_ids = {c.tool for c in contracts}
    # The retriever is fitted exclusively on registry-derived contract renderings.
    retriever = HybridRetriever(encoder=LSAEncoder()).fit(contracts)
    eligible = list(known_ids)
    reach = set()

    dataset_names = ("livemcpbench", "mcptoolbenchpp")
    results = {}
    for dataset_name in dataset_names:
        tasks = tasks_from_processed(data, dataset_name)
        rows_by_component = defaultdict(list)
        n_with_gold = n_evaluable = n_unresolved = 0
        for task in tasks:
            groups, unresolved = resolved_gold_groups(task, known_ids)
            n_with_gold += bool(task.gold_tools or task.gold_unresolved)
            n_unresolved += unresolved > 0
            n_evaluable += bool(groups)
            # Gold mappings are not passed to score/rank; only the natural-language query is.
            for label, components in COMPONENTS.items():
                scores = retriever.scores(task.query, None, eligible, reach, components=components)
                ranking = sorted(scores, key=lambda tool: (-scores[tool], tool))
                rows_by_component[label].append(task_metrics(ranking, groups, ks) if groups else None)

        component_results = {}
        for label, rows in rows_by_component.items():
            evaluable = [row for row in rows if row is not None]
            component_results[label] = _macro(evaluable, ks)
        results[dataset_name] = {
            "n_tasks": len(tasks),
            "n_tasks_with_any_gold_mapping": n_with_gold,
            "n_tasks_with_resolved_gold_groups": n_evaluable,
            "n_tasks_with_unresolved_gold_entries": n_unresolved,
            "coverage_resolved_gold_tasks": n_evaluable / len(tasks) if tasks else 0.0,
            "metrics": component_results,
        }

    return {
        "schema_version": "taas-retrieval-evaluation/1.0",
        "experiment": "E1",
        "evaluation_mode": "offline_retrieval_only",
        "registry_tools": len(contracts),
        "retrieval_inputs": ["task.query", "tool definition name/server/category/description via contract rendering"],
        "gold_usage": "evaluation_only_after_ranking",
        "not_evaluated": [
            "GoalSpec semantic validity", "policy eligibility", "hypergraph composition",
            "certificate validity", "runtime tool execution", "end-to-end task completion",
        ],
        "metrics": {
            "unit": "required gold mapping group; alternatives within a pipe-delimited group are any-of",
            "group_precision": "distinct gold groups first hit within top-k divided by k",
            "group_recall": "distinct gold groups first hit within top-k divided by number of resolved groups",
            "map": "mean average precision over first-hit ranks of resolved gold groups",
            "ndcg": "binary group relevance using each group's first alternative hit",
        },
        "datasets": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    result = evaluate_snapshot(load_processed())
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
