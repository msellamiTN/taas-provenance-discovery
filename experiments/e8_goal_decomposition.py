"""E8: evaluate LLM prompt-to-GoalSpec decomposition against an offline semantic rubric.

The rubric is evaluator-only. It is never sent to the analyst. This is a small,
expert-authored acceptance set, not a substitute for a larger independently
annotated benchmark.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

CASES: list[dict[str, Any]] = [
    {
        "id": "e8-bitcoin-report",
        "prompt": "Find current Bitcoin market information, write a deep report, and save it as Markdown at /root/markdown/bitcoin.md.",
        "goals": [
            {"classes": ["search", "fetch_web", "retrieve"], "out_kinds": ["record", "document"], "effects": [["egress", "web"]], "terms": ["bitcoin", "market", "current"], "deps": []},
            {"classes": ["summarise", "synthesise", "write"], "out_kinds": ["text", "document"], "effects": [], "terms": ["report", "bitcoin"], "deps": [0]},
            {"classes": ["create_document", "store", "write"], "out_kinds": ["path"], "effects": [["write", "fs"]], "terms": ["save", "markdown", "report"], "deps": [1]},
        ],
        "required_prompt_literals": ["/root/markdown/bitcoin.md", "Markdown"],
        "forbidden_effects": [["delete", "*"], ["money", "*"]],
    },
    {
        "id": "e8-issues-digest-slack",
        "prompt": "Fetch open bug issues from repository acme/api, summarize them, then post the digest to Slack channel #engineering.",
        "goals": [
            {"classes": ["retrieve", "search"], "out_kinds": ["record"], "effects": [["read", "db"], ["egress", "web"]], "terms": ["issues", "bug", "repository"], "deps": []},
            {"classes": ["summarise", "synthesise", "write"], "out_kinds": ["text"], "effects": [], "terms": ["summarise", "digest", "issues"], "deps": [0]},
            {"classes": ["send"], "out_kinds": ["none"], "effects": [["egress", "chat"]], "terms": ["post", "slack", "digest"], "deps": [1]},
        ],
        "required_prompt_literals": ["acme/api", "#engineering"],
        "forbidden_effects": [["delete", "*"], ["money", "*"]],
    },
    {
        "id": "e8-exact-revenue-csv",
        "prompt": "Read sales.csv, calculate the exact total revenue grouped by region, and save the result to revenue_by_region.csv.",
        "goals": [
            {"classes": ["retrieve"], "out_kinds": ["record", "table"], "effects": [["read", "fs"]], "terms": ["read", "sales", "csv"], "deps": []},
            {"classes": ["aggregate", "compute_exact", "count"], "out_kinds": ["table"], "effects": [], "terms": ["revenue", "region", "exact"], "deps": [0]},
            {"classes": ["store", "create_document", "convert_format"], "out_kinds": ["path"], "effects": [["write", "fs"]], "terms": ["save", "revenue", "csv"], "deps": [1]},
        ],
        "required_prompt_literals": ["sales.csv", "revenue_by_region.csv", "exact"],
        "forbidden_effects": [["delete", "*"], ["money", "*"], ["egress", "*"]],
    },
    {
        "id": "e8-weather-answer",
        "prompt": "What is the current weather in Tunis? Give me a concise answer.",
        "goals": [
            {"classes": ["retrieve", "search", "fetch_web"], "out_kinds": ["record"], "effects": [["egress", "web"], ["egress", "api"]], "terms": ["weather", "tunis", "current"], "deps": []},
            {"classes": ["answer", "summarise", "write"], "out_kinds": ["text"], "effects": [], "terms": ["answer", "weather", "tunis"], "deps": [0]},
        ],
        "required_prompt_literals": ["Tunis", "current"],
        "forbidden_effects": [["write", "*"], ["delete", "*"], ["money", "*"]],
    },
    {
        "id": "e8-pure-reasoning",
        "prompt": "Explain the difference between precision and recall in information retrieval, using one short example.",
        "goals": [
            {"classes": ["answer", "explain", "write"], "out_kinds": ["text"], "effects": [], "terms": ["precision", "recall", "example"], "deps": []},
        ],
        "required_prompt_literals": ["precision", "recall", "example"],
        "forbidden_effects": [["egress", "*"], ["write", "*"], ["delete", "*"], ["money", "*"]],
    },
]


def _effect_pairs(goal: dict[str, Any]) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for raw in goal.get("eff", []) or []:
        if not isinstance(raw, str) or "(" not in raw or not raw.endswith(")"):
            continue
        cls, scope = raw[:-1].split("(", 1)
        pairs.add((cls.strip(), scope.strip()))
    return pairs


def _matches(expected: dict[str, Any], actual: dict[str, Any]) -> bool:
    cls = str(actual.get("class", ""))
    out = str(actual.get("out", ""))
    kind = out.split(":", 1)[0].removesuffix("[]")
    if cls not in expected["classes"] or kind not in expected["out_kinds"]:
        return False
    effects = _effect_pairs(actual)
    required_effects = expected["effects"]
    if required_effects and not any(
        any(e_cls == required[0] and (e_scope == required[1] or required[1] == "*")
            for e_cls, e_scope in effects)
        for required in required_effects
    ):
        return False
    desc = str(actual.get("desc", "")).casefold()
    return any(term.casefold() in desc for term in expected["terms"])


def score_case(case: dict[str, Any], output: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(output, dict) or not isinstance(output.get("goals"), list):
        return {"id": case["id"], "valid_json_shape": False, "goal_precision": 0.0,
                "goal_recall": 0.0, "goal_f1": 0.0, "matched": 0,
                "expected_goals": len(case["goals"]), "predicted_goals": 0,
                "dag_valid": False, "missing_prompt_literals": case["required_prompt_literals"],
                "forbidden_effects": [], "errors": ["missing or invalid goals array"]}
    predicted = output["goals"]
    matched_actual: set[int] = set()
    matched_expected: set[int] = set()
    expected_to_actual: dict[int, int] = {}
    # Deterministic one-to-one matching; each predicted goal can satisfy at most one rubric item.
    for ei, expected in enumerate(case["goals"]):
        for ai, actual in enumerate(predicted):
            if ai not in matched_actual and isinstance(actual, dict) and _matches(expected, actual):
                matched_expected.add(ei)
                matched_actual.add(ai)
                expected_to_actual[ei] = ai
                break
    precision = len(matched_actual) / len(predicted) if predicted else 0.0
    recall = len(matched_expected) / len(case["goals"]) if case["goals"] else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    dependency_checks = []
    for expected_index, actual_index in expected_to_actual.items():
        expected_deps = case["goals"][expected_index].get("deps", [])
        actual_deps = set(predicted[actual_index].get("deps", []) or [])
        expected_actual_ids = {
            predicted[expected_to_actual[dep_index]]["id"]
            for dep_index in expected_deps if dep_index in expected_to_actual
        }
        dependency_checks.append(expected_actual_ids.issubset(actual_deps))
    dependency_valid = all(dependency_checks) if dependency_checks else False
    ids = [g.get("id") for g in predicted if isinstance(g, dict)]
    errors = []
    if len(ids) != len(predicted) or any(not isinstance(x, str) or not x for x in ids):
        errors.append("missing goal identifiers")
    if len(set(ids)) != len(ids):
        errors.append("duplicate goal identifiers")
    known = set(ids)
    for goal in predicted:
        if not isinstance(goal, dict):
            errors.append("non-object goal")
            continue
        for dep in goal.get("deps", []) or []:
            if dep not in known:
                errors.append(f"unknown dependency: {dep}")
    dag_valid = not errors
    # Reject cycles independently of the core parser, so this evaluator can diagnose raw LLM output.
    if dag_valid:
        deps = {g["id"]: set(g.get("deps", []) or []) for g in predicted}
        visited: set[str] = set()
        active: set[str] = set()
        def visit(node: str) -> bool:
            if node in active:
                return False
            if node in visited:
                return True
            active.add(node)
            if not all(visit(dep) for dep in deps[node]):
                return False
            active.remove(node)
            visited.add(node)
            return True
        dag_valid = all(visit(node) for node in deps)
        if not dag_valid:
            errors.append("dependency cycle")
    serialized_output = json.dumps(output, ensure_ascii=False).casefold()
    missing_literals = [literal for literal in case["required_prompt_literals"] if literal.casefold() not in serialized_output]
    forbidden = []
    for i, goal in enumerate(predicted):
        if not isinstance(goal, dict):
            continue
        for forbidden_cls, forbidden_scope in case["forbidden_effects"]:
            if any(cls == forbidden_cls and (scope == forbidden_scope or forbidden_scope == "*")
                   for cls, scope in _effect_pairs(goal)):
                forbidden.append({"goal": goal.get("id", i), "effect": f"{forbidden_cls}({forbidden_scope})"})
    return {
        "id": case["id"], "valid_json_shape": True,
        "goal_precision": round(precision, 4), "goal_recall": round(recall, 4), "goal_f1": round(f1, 4),
        "matched": len(matched_expected), "expected_goals": len(case["goals"]), "predicted_goals": len(predicted),
        "dag_valid": dag_valid, "dependency_valid": dependency_valid,
        "missing_prompt_literals": missing_literals,
        "forbidden_effects": forbidden, "errors": errors,
    }


def run(model: str, limit: int | None = None, record_to: str | None = None) -> dict[str, Any]:
    from taas.llm.backends import AnthropicAnalyst
    analyst = AnthropicAnalyst(model=model, record_to=record_to)
    cases = CASES[:limit] if limit else CASES
    rows = []
    for case in cases:
        try:
            result = analyst.decompose(case["id"], case["prompt"])
            row = score_case(case, result)
        except Exception as exc:  # preserve per-case failures in the report
            row = {"id": case["id"], "error": f"{type(exc).__name__}: {exc}",
                   "valid_json_shape": False, "goal_precision": 0.0, "goal_recall": 0.0, "goal_f1": 0.0}
        rows.append(row)
    scored = [r for r in rows if "goal_f1" in r]
    summary = {
        "model": analyst.name, "cases": len(rows),
        "mean_goal_precision": round(sum(r["goal_precision"] for r in scored) / len(scored), 4) if scored else 0.0,
        "mean_goal_recall": round(sum(r["goal_recall"] for r in scored) / len(scored), 4) if scored else 0.0,
        "mean_goal_f1": round(sum(r["goal_f1"] for r in scored) / len(scored), 4) if scored else 0.0,
        "dag_valid_rate": round(sum(bool(r.get("dag_valid")) for r in scored) / len(scored), 4) if scored else 0.0,
        "dependency_valid_rate": round(sum(bool(r.get("dependency_valid")) for r in scored) / len(scored), 4) if scored else 0.0,
        "forbidden_effect_cases": sum(bool(r.get("forbidden_effects")) for r in rows),
        "rows": rows,
        "rubric_notice": "Expert-authored acceptance rubric; not an independent full benchmark gold standard.",
        "gold_labels_exposed_to_analyst": False,
    }
    out = ROOT / "results" / "e8_goal_decomposition.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="claude-sonnet-4-5")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--record-to", help="Optional JSONL path for raw LLM outputs")
    args = parser.parse_args()
    run(args.model, args.limit, args.record_to)
