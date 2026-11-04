"""Typed, provenance-preserving Objective Contract v3 projection.

This module is deliberately conservative. It projects only uncomplicated v2
lexical hypotheses with exact source spans. Modality-sensitive prompts are
held for clarification rather than flattened into required operations.
"""
from __future__ import annotations

import re
from typing import Any

from taas.studio.objective_contract import derive_objective_contract

_SCHEMA = "taas.objective-contract/v3"
_EVIDENCE_PATTERNS: dict[str, tuple[str, ...]] = {
    "search": (r"\bsearch(?:ing)?\b", r"\bresearch(?:ing)?\b", r"\blook\s+up\b", r"\bfind\b", r"\b(re)?chercher\b", r"\btrouver\b"),
    "retrieve": (r"\bretrieve(?:d|s|ing)?\b", r"\bfetch(?:ed|es|ing)?\b", r"\bload(?:ed|s|ing)?\b", r"\bcollect(?:ed|s|ing)?\b", r"\brécupérer\b", r"\brecuperer\b", r"\bcharger\b"),
    "aggregate": (r"\baggregate\b", r"\baggregation\b", r"\bsum\b", r"\btotal(?:s|ise|ize)?\b", r"\baverage\b", r"\bmean\b", r"\bmedian\b", r"\bcalculate\b", r"\bcalculer\b", r"\bmoyenne\b", r"\bsomme\b"),
    "count": (r"\bcount\b", r"\bhow many\b", r"\bnumber of\b", r"\bcompter\b", r"\bcombien de\b"),
    "summarise": (r"\bsummar(?:y|ise|ize|ising|izing)\b", r"\bsynthétiser\b", r"\bsynthetiser\b", r"\brésumer\b", r"\bresumer\b"),
    "compare": (r"\bcompar(?:e|ison|ing)\b", r"\bversus\b", r"\bvs\.?\b", r"\bcomparer\b", r"\bcomparaison\b"),
    "classify": (r"\bclassif(?:y|ication|ying)\b", r"\bcategor(?:ize|ise|ization|isation)\b", r"\blabel\b", r"\bdetect\b", r"\bclassifier\b"),
    "extract": (r"\bextract(?:ion|ed|ing)?\b", r"\bparse\b", r"\bextraire\b"),
    "translate": (r"\btranslat(?:e|ion|ing)\b", r"\btradu(?:ire|ction)\b"),
    "write": (r"\bwrite\b", r"\bdraft\b", r"\bcompose\b", r"\bauthor\b", r"\brédiger\b", r"\brediger\b", r"\bécrire\b", r"\becrire\b"),
    "plan": (r"\bplan(?:ning)?\b", r"\bplanifier\b", r"\bconcevoir\b"),
    "synthesise": (r"\bsynthesi[sz]e\b", r"\bcombine\b", r"\bintegrate\b", r"\bconsolidate\b"),
    "answer": (r"\banswer\b", r"\bexplain\b", r"\brespond\b", r"\bdescribe\b", r"\bdefine\b", r"\bexpliquer\b", r"\bdécrire\b", r"\bdecrire\b"),
    "store": (r"\bsave\b", r"\bstor(?:e|age)\b", r"\bpersist\b", r"\benregistrer\b", r"\bsauvegarder\b"),
    "send": (r"\bsend\b", r"\bemail\b", r"\bnotify\b", r"\benvoyer\b", r"\bnotifier\b"),
    "transact": (r"\bbook\b", r"\breserve\b", r"\bpurchase\b", r"\bpay\b", r"\bréserver\b", r"\breserver\b", r"\bacheter\b", r"\bpayer\b"),
    "execute": (r"\bexecute\b", r"\brun\b", r"\bdeploy\b", r"\bexécuter\b", r"\bexecuter\b", r"\bdéployer\b", r"\bdeployer\b"),
    "navigate_browser": (r"\bbrowse\b", r"\bnavigate\b", r"\bclick\b", r"\bnaviguer\b", r"\bparcourir\b", r"\bcliquer\b"),
    "render_media": (r"\b(?:generate|create|draw|render|générer|generer|créer|creer)\s+(?:an?\s+|un(?:e)?\s+)?(?:image|picture|video|audio|diagram|chart|illustration|schéma|schema)\b",),
    "create_document": (r"\b(?:create|generate|produce|build|write|créer|creer|générer|generer|rédiger|rediger)\b.{0,50}\b(?:report|document|file|presentation|spreadsheet|rapport|fichier|présentation)\b",),
    "edit_document": (r"\b(?:edit|revise|update|modifier|éditer|editer|réviser|reviser)\b.{0,50}\b(?:document|report|file|presentation|rapport|fichier)\b",),
    "random": (r"\b(?:randomly|at\s+random|shuffle|random\s+sample|aléatoirement|aleatoirement|mélanger|melanger)\b",),
}

# These markers require scope analysis. Until the parser can bind them to
# individual clauses reliably, the whole candidate set is sent to clarification.
_MODALITY_MARKERS = re.compile(
    r"\b(?:not|never|don't|do\s+not|cannot|can't|without|unless|except|if|when|"
    r"only\s+if|optionally|optional|may|might|either|or|alternatively|"
    r"ne\s+pas|ne\s+jamais|sans|sauf|si|éventuellement|eventuellement|"
    r"ou|soit)\b",
    re.IGNORECASE,
)


def _source_evidence(objective: str, goal_class: str) -> list[dict[str, Any]]:
    # Search the original string: casefold() can change Unicode length (e.g. ß -> ss),
    # which would invalidate offsets into the original user text.
    for pattern in _EVIDENCE_PATTERNS.get(goal_class, ()):
        match = re.search(pattern, objective, flags=re.IGNORECASE)
        if match:
            start, end = match.span()
            return [{
                "start": start,
                "end": end,
                "text": objective[start:end],
                "cue": "operation_lexeme",
                "offset_unit": "unicode_code_point",
            }]
    return []


def derive_objective_contract_v3(
    objective: str,
    reference_date: Any = None,
    locale: str | None = None,
) -> dict[str, Any]:
    """Build a conservative v3 typed projection; never authorizes discovery."""
    original = objective if isinstance(objective, str) else str(objective or "")
    v2 = derive_objective_contract(original, reference_date=reference_date)
    candidates = list(v2.get("required_goal_classes", []))
    modality_matches = list(_MODALITY_MARKERS.finditer(original))
    clarifications: list[dict[str, Any]] = []
    outcomes: list[dict[str, Any]] = []

    if modality_matches and candidates:
        for match in modality_matches:
            clarifications.append({
                "id": f"clarification_{len(clarifications) + 1}",
                "question": "Clarify the scope of negation, condition, optionality, or alternatives before classifying the affected actions.",
                "reason": "modality_scope_not_resolved",
                "affected_goal_classes": candidates,
                "blocking": True,
                "source_evidence": [{
                    "start": match.start(),
                    "end": match.end(),
                    "text": original[match.start():match.end()],
                    "cue": "modality_marker",
                    "offset_unit": "unicode_code_point",
                }],
            })
    else:
        for index, goal_class in enumerate(candidates, start=1):
            evidence = _source_evidence(original, goal_class)
            if not evidence:
                clarifications.append({
                    "id": f"clarification_{len(clarifications) + 1}",
                    "question": f"Confirm whether '{goal_class}' is an intended operation.",
                    "reason": "no_direct_source_evidence",
                    "affected_goal_classes": [goal_class],
                    "blocking": True,
                    "source_evidence": [],
                })
                continue
            outcomes.append({
                "id": f"outcome_{index}",
                "goal_class": goal_class,
                "requirement": "required",
                "modality": "asserted",
                "source_evidence": evidence,
                "condition_ref": None,
                "alternative_group": None,
                "depends_on": [],
                "interpretation": {
                    "method": "deterministic_rule",
                    "confidence": None,
                    "semantic_correctness_verified": False,
                },
            })

    return {
        "schema": _SCHEMA,
        "contract_version": "3.0",
        "objective": {
            "text": original,
            "locale": locale or "und",
            "normalization": "none",
        },
        "outcomes": outcomes,
        "conditions": [],
        "alternatives": [],
        "dependencies": [],
        "inputs": [],
        "outputs": [],
        "constraints": v2.get("constraints", {}),
        "clarifications": clarifications,
        "review": {
            "required": True,
            "semantic_correctness_verified": False,
            "discovery_blocked": True,
        },
        "legacy": {
            "contract_version": v2.get("contract_version", "2.0"),
            "operation": v2.get("operation", "general"),
            "required_goal_classes": candidates,
        },
    }


def validate_objective_contract_v3(contract: dict[str, Any]) -> list[str]:
    """Return invariant violations; an empty list means structurally valid only."""
    errors: list[str] = []
    if contract.get("schema") != _SCHEMA or contract.get("contract_version") != "3.0":
        errors.append("unsupported_schema")
    objective = contract.get("objective", {})
    original = objective.get("text", "")
    if not isinstance(original, str):
        errors.append("objective_text_not_string")
        original = ""
    if objective.get("normalization") != "none":
        errors.append("original_text_must_remain_unnormalized")
    ids: set[str] = set()
    for outcome in contract.get("outcomes", []):
        outcome_id = outcome.get("id")
        if not outcome_id or outcome_id in ids:
            errors.append("outcome_id_missing_or_duplicate")
        ids.add(outcome_id)
        if outcome.get("requirement") not in {"required", "conditional", "optional", "alternative", "negated"}:
            errors.append("invalid_requirement")
        if outcome.get("modality") not in {"asserted", "conditional", "optional", "alternative", "negated"}:
            errors.append("invalid_modality")
        if not outcome.get("source_evidence"):
            errors.append("outcome_missing_source_evidence")
        for evidence in outcome.get("source_evidence", []):
            start, end = evidence.get("start"), evidence.get("end")
            if not isinstance(start, int) or not isinstance(end, int) or start < 0 or end <= start or end > len(original):
                errors.append("evidence_span_out_of_bounds")
                continue
            if original[start:end] != evidence.get("text"):
                errors.append("evidence_span_text_mismatch")
    if contract.get("review", {}).get("required") is not True:
        errors.append("human_review_not_required")
    if contract.get("review", {}).get("semantic_correctness_verified") is not False:
        errors.append("semantic_correctness_must_remain_unverified")
    if contract.get("review", {}).get("discovery_blocked") is not True:
        errors.append("discovery_must_remain_blocked")
    return errors
