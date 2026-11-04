"""Objective-aware decomposition constraints shared by TaaS Studio and Core.

This is a conservative intent frame, not an NLP proof system. It deliberately
keeps business concepts that are absent from Theta unresolved instead of
inventing ontology domains or mapping them to nearby concepts.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]


def _theta() -> dict[str, Any]:
    path = ROOT / "data" / "processed" / "theta.json"
    return json.loads(path.read_text(encoding="utf-8"))


def derive_objective_contract(objective: str) -> dict[str, Any]:
    """Derive explicit, reviewable constraints from common objective operators."""
    text = (objective or "").strip()
    lower = text.casefold()
    total = bool(re.search(r"\b(sum|summation|total|aggregate|calculate\s+(?:the\s+)?total)\b", lower))
    count = bool(re.search(r"\b(count|how many|number of)\b", lower))
    summary = bool(re.search(r"\b(summarize|summarise|summary)\b", lower))
    compare = bool(re.search(r"\b(compare|comparison|versus|\bvs\b)\b", lower))
    required = []
    if total:
        required.append("aggregate")
    elif count:
        required.append("count")
    elif summary:
        required.append("summarise")
    elif compare:
        required.append("compare")
    all_scope = bool(re.search(r"\b(all|every|each)\b", lower))
    date_scope = bool(re.search(r"\b(today|yesterday|this week|last week|this month|last month|between|from .* to)\b", lower))
    financial = bool(re.search(r"\b(transaction|transactions|payment|payments|invoice|invoices|financial|amount|value)\b", lower))
    currency_explicit = bool(re.search(r"\b(usd|eur|gbp|tnd|currency|currencies|convert|exchange rate)\b", lower))
    theta = _theta()
    domains = set(theta.get("domains", []))
    # Match only literal declared domain names. No synonym inference is performed.
    matched_domains = sorted(d for d in domains if re.search(rf"\b{re.escape(d)}s?\b", lower))
    business_terms = re.findall(
        r"\b[a-z][a-z0-9_-]{2,}(?:s)?\b",
        lower,
    )
    stop = {"calculate", "total", "value", "all", "every", "each", "please", "show",
            "find", "get", "give", "what", "how", "many", "number", "sum", "the",
            "for", "from", "with", "and", "that", "this", "last", "week", "month", "of", "is", "are", "was", "were", "to", "in", "on", "by", "per",
            "today", "yesterday", "transactions", "transaction", "payments", "payment",
            "invoices", "invoice", "amount", "financial"}
    unresolved = sorted({w.rstrip("s") for w in business_terms
                         if w.rstrip("s") not in domains and w.rstrip("s") not in stop})
    # "transactions" is intentionally unresolved in the current Theta ontology.
    if re.search(r"\btransactions?\b", lower) and "transaction" not in unresolved:
        unresolved.append("transaction")
    return {
        "objective": text,
        "operation": "aggregate" if total else "count" if count else "summarise" if summary else "compare" if compare else "general",
        "required_goal_classes": required,
        "numeric_result_required": bool(total or count),
        "exactness_required": "exact" if total or count else None,
        "scope": {"all_matching_items": all_scope, "date_or_range_constraint": date_scope},
        "source_data_required": bool(total or count or summary or compare or all_scope or financial),
        "theta_domain_candidates": matched_domains,
        "unresolved_business_concepts": sorted(set(unresolved)),
        "ambiguities": (["currency_policy"] if financial and not currency_explicit else []),
        "limitations": [
            "Lexical objective analysis is a constraint hint, not proof of semantic equivalence.",
            "A declared Theta domain is never inferred from an undeclared synonym.",
        ],
    }


def build_objective_context(objective: str) -> str:
    contract = derive_objective_contract(objective)
    return (
        "TaaS Core objective frame (deterministically derived; preserve these constraints):\n"
        + json.dumps(contract, ensure_ascii=False, indent=2)
        + "\nUse only declared Theta types. If a business concept is unresolved, use a generic "
          "record type only where appropriate and leave schema mapping explicit for Core discovery. "
          "Do not claim the source exists or that all records can be retrieved."
    )


def diagnose_objective_alignment(objective: str, spec: dict[str, Any]) -> list[dict[str, str]]:
    """Check the proposed plan against objective operators and data-flow constraints."""
    contract = derive_objective_contract(objective)
    goals = [g for g in spec.get("goals", []) if isinstance(g, dict)]
    classes = {str(g.get("class", "")).casefold() for g in goals}
    diagnostics: list[dict[str, str]] = []
    required = contract["required_goal_classes"]
    for cls in required:
        present = cls in classes or (cls == "aggregate" and "compute_exact" in classes)
        if not present:
            diagnostics.append({
                "code": "objective_operation_missing", "severity": "error",
                "message": f"The objective requires a {cls} operation, but no {cls} goal exists.",
                "suggestion": f"Add a {cls} goal; do not replace the requested operation with a different class.",
            })
    if contract["source_data_required"]:
        data_inputs = [str(x).casefold() for x in spec.get("prompt_inputs", [])
                       if str(x).split(":", 1)[0] in {"record", "table", "document"}]
        acquisitions = [g for g in goals if str(g.get("class", "")).casefold()
                        in {"retrieve", "search", "fetch_web"}]
        if not data_inputs and not acquisitions:
            diagnostics.append({
                "code": "objective_data_source_missing", "severity": "error",
                "message": "The objective requires source data, but neither typed data input nor a data-acquisition goal is present.",
                "suggestion": "Add a retrieval/search goal or explicitly supply the source data as a typed input. Do not invent a source.",
            })
    if contract["numeric_result_required"]:
        numeric_ops = [g for g in goals if str(g.get("class", "")).casefold()
                       in {"aggregate", "compute_exact", "count"}]
        if numeric_ops and not any(str(g.get("out", "")).casefold() == "number" for g in numeric_ops):
            diagnostics.append({
                "code": "objective_numeric_output_missing", "severity": "error",
                "message": "The requested calculation/count does not produce a number.",
                "suggestion": "Declare a numeric output for the required calculation.",
            })
    if contract["operation"] == "aggregate":
        aggregates = [g for g in goals if str(g.get("class", "")).casefold()
                      in {"aggregate", "compute_exact"}]
        if any(str(g.get("exactness", "tolerant")).casefold() != "exact" for g in aggregates):
            diagnostics.append({
                "code": "objective_exactness_not_preserved", "severity": "error",
                "message": "The objective requests a total, but the aggregation is not marked exact.",
                "suggestion": "Set exactness to exact; do not approximate a requested total.",
            })
        acquisitions = [g for g in goals if str(g.get("class", "")).casefold()
                        in {"retrieve", "search", "fetch_web"}]
        if acquisitions:
            acquisition_ids = {str(g.get("id")) for g in acquisitions}
            downstream = [g for g in aggregates if acquisition_ids.intersection(
                str(d) for d in g.get("deps", []))]
            if not downstream:
                diagnostics.append({
                    "code": "objective_dataflow_disconnected", "severity": "error",
                    "message": "The aggregation is not explicitly dependent on the data-acquisition goal.",
                    "suggestion": "Connect the aggregate goal to the retrieval goal and consume its declared output type.",
                })
    if contract["scope"]["all_matching_items"]:
        acquisitions = [g for g in goals if str(g.get("class", "")).casefold()
                        in {"retrieve", "search", "fetch_web"}]
        if acquisitions and not any(re.search(r"\b(all|every|each|complete|entire)\b",
                                               str(g.get("desc", "")).casefold())
                                    for g in acquisitions):
            diagnostics.append({
                "code": "objective_scope_not_preserved", "severity": "error",
                "message": "The objective requests all matching items, but the acquisition description does not preserve that scope.",
                "suggestion": "State all matching records in the acquisition goal; do not replace it with a top-N sample.",
            })
    if contract["unresolved_business_concepts"]:
        diagnostics.append({
            "code": "objective_concept_not_mapped_to_theta", "severity": "warning",
            "message": "Some business concepts are not declared Theta domains: "
                       + ", ".join(contract["unresolved_business_concepts"][:8]) + ".",
            "suggestion": "Keep the concept explicit in the goal description and resolve its source schema during discovery; do not invent a domain.",
        })
    if "currency_policy" in contract["ambiguities"]:
        diagnostics.append({
            "code": "objective_currency_policy_ambiguous", "severity": "warning",
            "message": "The financial objective does not specify how mixed currencies are handled.",
            "suggestion": "Clarify whether to reject mixed currencies, group totals by currency, or apply an explicitly supplied conversion policy.",
        })
    return diagnostics
