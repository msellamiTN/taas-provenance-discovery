"""Objective-aware decomposition constraints shared by TaaS Studio and Core.

The contract is a conservative, reviewable intent frame, not an NLP proof system.
Relative dates remain explicit until a submission-time reference date and business
timezone are supplied by the caller. Business concepts absent from Theta are never
silently mapped to neighbouring ontology domains.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]


def _theta() -> dict[str, Any]:
    path = ROOT / "data" / "processed" / "theta.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _singularize(token: str) -> str:
    """Conservative English plural normalization; never strip arbitrary final 's'."""
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 3 and token.endswith("s") and not token.endswith(("ss", "us", "is")):
        return token[:-1]
    return token


def _temporal_scope(lower: str, reference_date: date | datetime | str | None) -> dict[str, Any] | None:
    """Describe a temporal expression without guessing the business timezone."""
    patterns = (
        (r"\b(this year|current year|cette année|cette annee)\b", "calendar_year", "this_year"),
        (r"\b(last year|previous year|l’année dernière|l annee derniere|année dernière|annee derniere)\b", "calendar_year", "last_year"),
        (r"\b(year to date|ytd)\b", "year_to_date", "year_to_date"),
        (r"\b(this month|current month|ce mois|ce mois-ci)\b", "calendar_month", "this_month"),
        (r"\b(last month|previous month|mois dernier|le mois dernier)\b", "calendar_month", "last_month"),
        (r"\b(this week|current week|cette semaine)\b", "calendar_week", "this_week"),
        (r"\b(last week|previous week|semaine dernière|semaine derniere|la semaine dernière|la semaine derniere)\b", "calendar_week", "last_week"),
        (r"\b(today|yesterday|aujourd’hui|aujourd hui|hier)\b", "relative_day", "relative_day"),
    )
    for pattern, kind, expression in patterns:
        match = re.search(pattern, lower)
        if match:
            anchor = None
            if reference_date is not None:
                if isinstance(reference_date, datetime):
                    anchor = reference_date.date().isoformat()
                elif isinstance(reference_date, date):
                    anchor = reference_date.isoformat()
                else:
                    anchor = date.fromisoformat(str(reference_date)[:10]).isoformat()
            return {
                "kind": kind,
                "expression": expression,
                "matched_text": match.group(0),
                "reference_date": anchor,
                "anchor_required": anchor is None,
                "business_timezone_required": True,
                "start_inclusive": None,
                "end_exclusive": None,
                "resolution_status": "unresolved" if anchor is None else "anchored_not_materialized",
            }
    # Explicit ranges require date-shaped endpoints; "from the configured source"
    # is a source phrase, not a date range.
    month = (
        r"(?:january|february|march|april|may|june|july|august|september|"
        r"october|november|december|janvier|février|fevrier|mars|avril|mai|"
        r"juin|juillet|août|aout|septembre|octobre|novembre|décembre|decembre)"
    )
    date_atom = (
        rf"(?:\d{{4}}-\d{{1,2}}-\d{{1,2}}|"
        rf"\d{{1,2}}[/-]\d{{1,2}}[/-]\d{{2,4}}|"
        rf"(?:\d{{1,2}}(?:st|nd|rd|th)?\s+{month}|{month}\s+\d{{1,2}}(?:st|nd|rd|th)?))"
    )
    range_patterns = (
        (rf"\bbetween\s+{date_atom}\s+(?:and|to)\s+{date_atom}\b", "between"),
        (rf"\bfrom\s+{date_atom}\s+to\s+{date_atom}\b", "from_to"),
        (rf"\bdu\s+{date_atom}\s+au\s+{date_atom}\b", "du_au"),
        (rf"\bentre\s+{date_atom}\s+et\s+{date_atom}\b", "entre"),
    )
    for pattern, expression in range_patterns:
        match = re.search(pattern, lower)
        if match:
            anchor = None
            if reference_date is not None:
                if isinstance(reference_date, datetime):
                    anchor = reference_date.date().isoformat()
                elif isinstance(reference_date, date):
                    anchor = reference_date.isoformat()
                else:
                    anchor = date.fromisoformat(str(reference_date)[:10]).isoformat()
            return {
                "kind": "explicit_range",
                "expression": expression,
                "matched_text": match.group(0),
                "reference_date": anchor,
                "anchor_required": anchor is None,
                "business_timezone_required": True,
                "start_inclusive": None,
                "end_exclusive": None,
                "resolution_status": "unresolved" if anchor is None else "anchored_not_materialized",
            }
    return None


def derive_objective_contract(
    objective: str,
    reference_date: date | datetime | str | None = None,
) -> dict[str, Any]:
    """Derive explicit, reviewable constraints from common objective operators."""
    text = (objective or "").strip()
    lower = text.casefold()
    total = bool(re.search(r"\b(sum|summation|total|aggregate|average|avg|mean|median|minimum|maximum|calculate\s+(?:the\s+)?(?:total|average)|somme|totaliser|calculer\s+(?:le\s+)?(?:total|la\s+somme|la\s+moyenne)|moyenne|médiane|mediane)\b", lower))
    count = bool(re.search(r"\b(count|how many|number of|compter|combien de|nombre de)\b", lower))
    summary = bool(re.search(r"\b(summarize|summarise|summary|résumer|resumer|résumé|resume|synthétiser|synthetiser)\b", lower))
    compare = bool(re.search(r"\b(compare|comparison|versus|vs|comparer|comparaison)\b", lower))
    search_intent = bool(re.search(r"\b(search|look\s+up|find|discover|research|chercher|rechercher|trouver|étudier|etudier)\b", lower))
    retrieval_intent = bool(re.search(r"\b(retrieve|fetch|load|collect|list|show|get|récupérer|recuperer|charger|collecter|lister|afficher|obtenir)\b", lower))
    operation = (
        "aggregate" if total else "count" if count else "summarise" if summary
        else "compare" if compare else "search" if search_intent
        else "retrieve" if retrieval_intent else "general"
    )
    grouped_aggregation = bool(total and re.search(r"\b(by|per|group(?:ed)? by|par)\b", lower))

    all_scope = bool(re.search(r"\b(all|every|each|entire|complete|tous|toutes|chaque|ensemble complet)\b", lower))
    temporal = _temporal_scope(lower, reference_date)
    recency_scope = bool(re.search(r"\b(latest|recent|newest|current|up[- ]to[- ]date|dernier|dernière|derniere|récent|recent|actuel|actuelle)\b", lower))
    multi_source_intent = bool(re.search(
        r"\b(?:from|across|à partir de|a partir de)\s+"
        r"(?:multiple|several|various|different|many|plusieurs|diverses|différentes|differentes)\s+"
        r"(?:(?:external|online|public|independent|relevant|externes?|en ligne|publiques?)\s+){0,3}"
        r"(?:data\s+)?sources?\b",
        lower,
    ))
    # Detect both common word orders: "this paragraph" and
    # "the document supplied in the prompt". A content noun alone is
    # insufficient; an explicit user-supplied/attached/provided cue is needed.
    content_noun = r"(?:text|paragraph|document|file|dataset|data|records?|report|image|audio|video|architecture|design|option|alternative|proposal|example|candidate)s?"
    supplied_marker = r"(?:user[- ]?)?(?:supplied|provided|attached|uploaded|given)"
    user_supplied_content = bool(re.search(
        rf"\b(?:this|these|following|provided|attached|uploaded|above|below|selected|given|supplied)\s+{content_noun}\b"
        rf"|\b{supplied_marker}\s+(?:[a-z][a-z0-9_-]*\s+){{0,3}}{content_noun}\b"
        rf"|\b{content_noun}\s+(?:that\s+is\s+)?{supplied_marker}\b"
        rf"|\b{content_noun}\b.{{0,40}}\b{supplied_marker}\s+(?:in|with|by)\s+(?:the\s+)?(?:prompt|request|message|user)\b",
        lower,
    ))
    explicit_external_source = bool(re.search(
        r"\b(web|website|webpage|online|internet|external\s+sources?|external\s+data|database|api|repository)\b",
        lower,
    ))
    acquisition_requested = bool(search_intent or retrieval_intent or multi_source_intent)
    source_data_required = bool(
        (acquisition_requested and (not user_supplied_content or explicit_external_source))
        or ((total or count or all_scope or temporal or recency_scope) and not user_supplied_content)
    )
    required: list[str] = []
    web_fetch_intent = bool(
        re.search(r"\b(fetch|retrieve|open)\b", lower)
        and re.search(r"\b(web|website|webpage|online|url|internet|browser)\b", lower)
    )
    if search_intent:
        required.append("search")
    elif web_fetch_intent:
        required.append("fetch_web")
    elif source_data_required:
        required.append("retrieve")
    for cue, cls in (
        (total, "aggregate"), (count, "count"), (summary, "summarise"),
        (compare, "compare"),
        (bool(re.search(r"\b(classify|categorize|categorise|label|detect|identify\s+anomalies|classer|classifier|catégoriser|categoriser|détecter|detecter)\b", lower)), "classify"),
        (bool(re.search(r"\b(extract|parse|identify\s+entities|extraire|analyser)\b", lower)), "extract"),
        (bool(re.search(r"\b(translate|translation|traduire|traduction)\b", lower)), "translate"),
        (bool(re.search(r"\b(convert\s+format|reformat|format\s+as)\b", lower)), "convert_format"),
        (bool(re.search(r"\b(write|draft|compose|author|rédiger|rediger|écrire|ecrire)\b", lower)), "write"),
        (bool(re.search(r"\b(plan|planning|design\s+a\s+workflow|planifier|concevoir)\b", lower)), "plan"),
        (bool(re.search(r"\b(synthesi[sz]e|combine\s+(?:findings|sources|data)|integrate\s+(?:findings|sources|data)|consolidate\s+(?:findings|sources|data)|synthétiser|synthetiser)\b", lower)), "synthesise"),
        (bool(re.search(r"\b(answer|explain|respond|describe|define|expliquer|décrire|decrire|définir|definir)\b", lower)), "answer"),
        (bool(re.search(r"\b(save|store|persist|write\s+to|enregistrer|sauvegarder|stocker)\b", lower)), "store"),
        (bool(re.search(r"\b(send|email|notify|message\s+to|envoyer|transmettre|notifier)\b", lower)), "send"),
        (bool(re.search(r"\b(book|reserve|purchase|pay|transfer\s+funds|réserver|reserver|acheter|payer|transférer|transferer)\b", lower)), "transact"),
        (bool(re.search(r"\b(execute|run\s+(?:the\s+)?(?:script|command|query)|deploy|exécuter|executer|lancer|déployer|deployer)\b", lower)), "execute"),
        (bool(re.search(r"\b(browse|navigate\s+to|open\s+(?:the\s+)?website|click\s+through|naviguer|parcourir|ouvrir\s+(?:le\s+)?site|cliquer)\b", lower)), "navigate_browser"),
        (bool(re.search(r"\b(generate|create|draw|render|générer|generer|créer|creer)\s+(?:(?:an?|un|une)\s+)?(?:image|picture|video|audio|diagram|chart|illustration|schéma|schema)\b", lower)), "render_media"),
        (bool(re.search(r"\b(create|generate|produce|build|write|créer|creer|générer|generer|rédiger|rediger)\b.*\b(report|document|file|presentation|spreadsheet|rapport|fichier|présentation)\b", lower)), "create_document"),
        (bool(re.search(r"\b(edit|revise|update|modifier|éditer|editer|réviser|reviser)\b.*\b(document|report|file|presentation|rapport|fichier)\b", lower)), "edit_document"),
        (bool(re.search(r"\b(randomly|at\s+random|shuffle|random\s+sample|aléatoirement|aleatoirement|mélanger|melanger)\b", lower)), "random"),
    ):
        if cue and cls not in required:
            required.append(cls)

    theta = _theta()
    domains = set(theta.get("domains", []))
    theta_kinds = set(theta.get("kinds", []))
    # Match only literal declared domain names. No synonym inference is performed.
    matched_domains = sorted(d for d in domains if re.search(rf"\b{re.escape(d)}s?\b", lower))

    stop = {
        "calculate", "total", "value", "all", "every", "each", "please", "show",
        "find", "get", "give", "what", "how", "many", "number", "sum", "count",
        "the", "for", "from", "with", "and", "that", "this", "these", "those", "two", "three", "four", "last", "current",
        "week", "month", "year", "of", "is", "are", "was", "were", "to", "in",
        "on", "by", "per", "today", "yesterday", "issued", "created", "generated",
        "received", "supplied", "provided", "attached", "uploaded", "between", "ytd", "summarize", "summarise", "summary",
        "payments", "payment", "invoices", "invoice", "architecture", "design", "option", "alternative", "proposal", "example", "candidate",
        "amount", "financial", "aggregate", "aggregation", "compare", "comparison",
        "versus", "configured", "matching", "provided", "given", "selected",
        "query", "source", "relevant", "specific", "retrieving", "retrieved",
        "records", "record",
    }
    stop.update({
        "compter", "combien", "nombre", "tous", "toutes", "chaque", "les", "des",
        "une", "un", "pour", "dans", "sur", "par", "cette", "année", "annee",
        "rechercher", "chercher", "trouver", "récupérer", "recuperer", "résumer",
        "resumer", "comparer", "traduire", "expliquer", "décrire", "decrire",
        "enregistrer", "sauvegarder", "envoyer", "transmettre", "exécuter",
        "executer", "lancer", "générer", "generer", "créer", "creer",
    })
    stop.update({
        "explain", "describe", "define", "answer", "classify", "categorize",
        "categorise", "label", "detect", "identify", "extract", "parse",
        "translate", "translation", "convert", "reformat", "write", "draft",
        "compose", "author", "plan", "planning", "design", "synthesize",
        "synthesise", "combine", "integrate", "consolidate", "save", "store",
        "persist", "send", "email", "notify", "message", "book", "reserve",
        "purchase", "pay", "transfer", "execute", "run", "deploy", "browse",
        "navigate", "open", "click", "generate", "create", "draw", "render",
        "edit", "revise", "update", "randomly", "shuffle", "sample", "search",
        "look", "discover", "research", "retrieve", "fetch", "load", "collect",
        "list", "get", "latest", "recent", "newest", "up", "date", "current",
        "word", "words", "paragraph", "text", "document", "file", "report",
        "image", "picture", "video", "audio", "diagram", "chart", "data",
        "dataset", "source", "sources", "record", "records", "result", "results",
        "output", "input", "task", "objective", "prompt", "texte", "paragraphe",
        "fichier", "rapport", "données", "donnees", "émises", "emises",
    })
    business_terms = re.findall(r"\b[a-z][a-z0-9_-]{2,}\b", lower)
    unresolved = set()
    for word in business_terms:
        normalized = _singularize(word)
        if normalized in stop or normalized in domains or normalized in theta_kinds:
            continue
        unresolved.add(normalized)

    financial_domain = bool(re.search(
        r"\b(transaction|transactions|payment|payments|invoice|invoices|financial)\b",
        lower,
    ))
    amount_operation = operation == "aggregate" and bool(re.search(
        r"\b(amount|value|price|cost|balance|quantity|financial|transaction|transactions|payment|payments|invoice|invoices)\b",
        lower,
    ))
    currency_explicit = bool(re.search(
        r"\b(usd|eur|gbp|tnd|currency|currencies|convert|conversion|exchange rate)\b",
        lower,
    ))
    currency_ambiguity = amount_operation and financial_domain and not currency_explicit

    # Objective Contract v2 is additive: retain the v1 keys consumed by the
    # current Studio/API while representing every detected operation as an
    # independent required outcome. These are rule-derived hypotheses, not a
    # proof that the natural-language objective has been fully understood.
    outcomes = [
        {
            "id": f"outcome_{index + 1}",
            "goal_class": goal_class,
            "required": True,
            "interpretation": "lexical_rule",
        }
        for index, goal_class in enumerate(required)
    ]
    constraints = {
        "inputs": {
            "source_data_required": source_data_required,
            "user_supplied_content": user_supplied_content,
        },
        "scope": {
            "all_matching_items": all_scope,
            "date_or_range_constraint": temporal is not None,
        },
        "computation": {
            "numeric_result_required": bool(count or (total and not grouped_aggregation)),
            "grouped_result_required": grouped_aggregation,
            "exactness_required": "exact" if total or count else None,
        },
        "temporal": temporal,
        "unresolved_concepts": sorted(unresolved),
        "ambiguities": ["currency_policy"] if currency_ambiguity else [],
    }

    return {
        "contract_version": "2.0",
        "objective": text,
        "outcomes": outcomes,
        "constraints": constraints,
        "review": {
            # Human review is a platform invariant, including apparently simple
            # objectives; lexical rules never certify semantic correctness.
            "required": True,
            "reasons": [
                "human_review_mandatory",
                *([ "unresolved_business_concepts" ] if unresolved else []),
                *([ "unresolved_ambiguity" ] if currency_ambiguity else []),
                *([ "temporal_scope_requires_resolution" ] if temporal is not None else []),
            ],
            "semantic_correctness_verified": False,
            "interpretation_method": "deterministic_lexical_rules",
        },
        "operation": operation,
        "required_goal_classes": required,
        "numeric_result_required": bool(count or (total and not grouped_aggregation)),
        "grouped_result_required": grouped_aggregation,
        "exactness_required": "exact" if total or count else None,
        "scope": {
            "all_matching_items": all_scope,
            "date_or_range_constraint": temporal is not None,
        },
        "temporal_scope": temporal,
        "source_data_required": source_data_required,
        "user_supplied_content": user_supplied_content,
        "theta_domain_candidates": matched_domains,
        "unresolved_business_concepts": sorted(unresolved),
        "ambiguities": (["currency_policy"] if currency_ambiguity else []),
        "limitations": [
            "Lexical objective analysis is a constraint hint, not proof of semantic equivalence.",
            "A declared Theta domain is never inferred from an undeclared synonym.",
            "Relative dates require a submission-time reference date and business timezone before execution.",
            "A temporal phrase does not identify the source field that represents the business event date.",
        ],
    }



def build_outcome_coverage(objective: str, spec: dict[str, Any] | None) -> dict[str, Any]:
    """Map v2 required outcomes to matching GoalSpec operation classes.

    Supplied inputs are not operation evidence. Class coverage is structural
    only and does not establish semantic equivalence, source availability,
    tool capability, authorization or success.
    """
    contract = derive_objective_contract(objective)
    candidate = spec if isinstance(spec, dict) else {}
    goals = [goal for goal in candidate.get("goals", []) if isinstance(goal, dict)]
    coverage = []
    for outcome in contract["outcomes"]:
        required_class = outcome["goal_class"]
        equivalents = {required_class}
        if required_class == "aggregate":
            equivalents.add("compute_exact")
        matched = [
            str(goal.get("id", ""))
            for goal in goals
            if str(goal.get("class", "")).casefold() in equivalents
        ]
        # An input proves that data was supplied; it does not prove that a
        # requested operation (including search/retrieval) was performed.
        if matched:
            status = "covered_by_goal"
        else:
            status = "missing"
        coverage.append({
            **outcome,
            "status": status,
            "goal_ids": matched,
            "input_types": [],
            "coverage_level": "goal_class_only" if matched else "uncovered",
            "semantic_conformance": "not_assessed",
        })
    counts = {
        "required": len(coverage),
        "covered": sum(item["status"] != "missing" for item in coverage),
        "missing": sum(item["status"] == "missing" for item in coverage),
    }
    return {
        "contract_version": contract["contract_version"],
        "outcomes": coverage,
        "summary": counts,
        "semantic_correctness_verified": False,
        "coverage_semantics": "goal_class_only; semantic conformance is not assessed",
    }


def build_objective_context(objective: str) -> str:
    contract = derive_objective_contract(objective)
    return (
        "TaaS Core Objective Contract v2 (deterministically derived; preserve every outcome and constraint):\n"
        + json.dumps(contract, ensure_ascii=False, indent=2)
        + "\nUse only declared Theta types. prompt_inputs describe user-supplied input types, "
          "not business nouns from the objective. Use text for a natural-language request unless "
          "the user actually supplies typed data. If a business concept is unresolved, use a generic "
          "record type only where appropriate and leave source-schema mapping explicit for Core discovery. "
          "Do not claim the source exists or that all records can be retrieved."
    )


def diagnose_objective_alignment(objective: str, spec: dict[str, Any]) -> list[dict[str, str]]:
    """Check operation, exactness, temporal scope and data-flow constraints."""
    contract = derive_objective_contract(objective)
    goals = [g for g in spec.get("goals", []) if isinstance(g, dict)]
    classes = {str(g.get("class", "")).casefold() for g in goals}
    diagnostics: list[dict[str, str]] = []

    for cls in contract["required_goal_classes"]:
        present = cls in classes or (cls == "aggregate" and "compute_exact" in classes)
        if not present:
            diagnostics.append({
                "code": "objective_operation_missing", "severity": "error",
                "message": f"The objective requires a {cls} operation, but no {cls} goal exists.",
                "suggestion": f"Add a {cls} goal; do not replace the requested operation with a different class.",
            })

    acquisitions = [g for g in goals if str(g.get("class", "")).casefold()
                    in {"retrieve", "search", "fetch_web"}]
    if contract["source_data_required"]:
        if not acquisitions:
            diagnostics.append({
                "code": "objective_data_source_missing", "severity": "error",
                "message": "The objective requires external source data, but no data-acquisition goal is present. Supplied inputs do not prove external retrieval.",
                "suggestion": "Add a retrieval/search goal for the external source. Do not invent a source or treat supplied content as acquired data.",
            })

    numeric_ops = [g for g in goals if str(g.get("class", "")).casefold()
                   in {"aggregate", "compute_exact", "count"}]
    required_numeric_classes = set(contract["required_goal_classes"]) & {"aggregate", "count"}
    required_numeric_goals = [
        g for g in numeric_ops
        if str(g.get("class", "")).casefold() in required_numeric_classes
        or (str(g.get("class", "")).casefold() == "compute_exact" and "aggregate" in required_numeric_classes)
    ]
    if contract["numeric_result_required"]:
        if numeric_ops and not any(str(g.get("out", "")).casefold() == "number" for g in numeric_ops):
            diagnostics.append({
                "code": "objective_numeric_output_missing", "severity": "error",
                "message": "The requested calculation/count does not produce a number.",
                "suggestion": "Declare a numeric output for each required numeric operation.",
            })
    for goal in required_numeric_goals:
        goal_class = str(goal.get("class", "")).casefold()
        if goal_class == "count" and str(goal.get("out", "")).casefold() != "number":
            diagnostics.append({
                "code": "objective_count_output_missing", "severity": "error",
                "message": f"Count goal {goal.get('id', '<unknown>')} must produce a number.",
                "suggestion": "Declare number as the count goal output.",
            })
        if goal_class in {"aggregate", "compute_exact"} and not contract.get("grouped_result_required") and str(goal.get("out", "")).casefold() != "number":
            diagnostics.append({
                "code": "objective_aggregate_output_missing", "severity": "error",
                "message": f"Aggregate goal {goal.get('id', '<unknown>')} must produce a number for this objective.",
                "suggestion": "Declare number as the aggregate output.",
            })
    if contract.get("grouped_result_required"):
        aggregate_goals = [g for g in required_numeric_goals
                           if str(g.get("class", "")).casefold() in {"aggregate", "compute_exact"}]
        if aggregate_goals and any(str(g.get("out", "")).casefold() not in {"table", "record[]"}
                                   for g in aggregate_goals):
            diagnostics.append({
                "code": "objective_grouped_output_missing", "severity": "error",
                "message": "The grouped aggregation does not produce a tabular result.",
                "suggestion": "Declare a table (or a declared row collection) output for the grouped numeric result.",
            })
    if contract["exactness_required"] == "exact":
        for goal in required_numeric_goals:
            if str(goal.get("exactness", "tolerant")).casefold() != "exact":
                diagnostics.append({
                    "code": "objective_exactness_not_preserved", "severity": "error",
                    "message": f"The objective requires exact numeric operations, but goal {goal.get('id', '<unknown>')} is not marked exact.",
                    "suggestion": "Set exactness to exact for every requested count and aggregate; do not approximate.",
                })

    if acquisitions and required_numeric_goals:
        acquisition_ids = {str(g.get("id")) for g in acquisitions}
        disconnected = [g for g in required_numeric_goals
                        if not acquisition_ids.intersection(str(d) for d in g.get("deps", []))]
        if disconnected:
            diagnostics.append({
                "code": "objective_dataflow_disconnected", "severity": "error",
                "message": "Every required count/aggregate goal must depend on the relevant data-acquisition goal.",
                "suggestion": "Connect each numeric operation to the retrieval goal and consume its declared output type.",
            })

    if contract["scope"]["all_matching_items"] and acquisitions:
        if not any(re.search(r"\b(all|every|each|complete|entire|tous|toutes|chaque|complet|complète|completement)\b",
                             str(g.get("desc", "")).casefold()) for g in acquisitions):
            diagnostics.append({
                "code": "objective_scope_not_preserved", "severity": "error",
                "message": "The objective requests all matching items, but the acquisition description does not preserve that scope.",
                "suggestion": "State all matching records in the acquisition goal; do not replace it with a top-N sample.",
            })

    temporal = contract["temporal_scope"]
    if temporal and acquisitions:
        phrase = str(temporal.get("matched_text", "")).casefold()
        if phrase and not any(phrase in str(g.get("desc", "")).casefold() for g in acquisitions):
            diagnostics.append({
                "code": "objective_temporal_scope_not_preserved", "severity": "error",
                "message": f"The objective's temporal constraint {phrase!r} is missing from the acquisition goal.",
                "suggestion": "Preserve the temporal phrase in the acquisition description; resolve its concrete date bounds and business timezone before discovery/execution.",
            })
        diagnostics.append({
            "code": "objective_temporal_field_unresolved", "severity": "warning",
            "message": "The temporal period is recognized, but the source field representing the business event date is not established.",
            "suggestion": "Resolve the source field that represents the requested business event date, including its timezone and semantics, during Discovery; do not invent a field name.",
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
            "message": "The financial aggregation does not specify how mixed currencies are handled.",
            "suggestion": "Clarify whether to reject mixed currencies, group totals by currency, or apply an explicitly supplied conversion policy.",
        })

    # Boundary-crossing operations must declare their effects explicitly.
    effect_requirements = {
        "retrieve": (("read(",), "read(*)"),
        "search": (("read(", "egress("), "read(*) or egress(*)"),
        "fetch_web": (("egress(",), "egress(*)"),
        "navigate_browser": (("egress(",), "egress(*)"),
        "store": (("write(",), "write(*)"),
        "create_document": (("write(",), "write(*)"),
        "edit_document": (("write(",), "write(*)"),
        "send": (("egress(",), "egress(*)"),
        "render_media": (("egress(",), "egress(*)"),
        "transact": (("money", "write(", "egress("), "money or an appropriate write/egress effect"),
        "execute": (("exec",), "exec"),
    }
    for goal in goals:
        cls = str(goal.get("class", "")).casefold()
        if cls not in effect_requirements:
            continue
        required_effects, example = effect_requirements[cls]
        effects = [str(effect).casefold() for effect in goal.get("eff", [])]
        if not any(
            effect == required or effect.startswith(required)
            for effect in effects for required in required_effects
        ):
            diagnostics.append({
                "code": "objective_effect_not_declared",
                "severity": "error",
                "message": f"Goal {goal.get('id', '<unknown>')} uses boundary-crossing class {cls!r} without declaring its required effect.",
                "suggestion": f"Declare the appropriate effect (for example {example!r}); policy authorization remains a separate gate.",
            })
    return diagnostics
