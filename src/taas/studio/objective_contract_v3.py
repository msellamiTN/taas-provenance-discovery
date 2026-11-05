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
    "send": (r"\bsend\b", r"\bnotify\b", r"\bmessage\b", r"\benvoyer\b", r"\bnotifier\b"),
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


def _clause_bounds(text: str, position: int) -> tuple[int, int]:
    """Return conservative punctuation-delimited clause bounds around a source offset."""
    left = max((text.rfind(mark, 0, position) for mark in (";", ".", "!", "?", "\n")), default=-1) + 1
    right_candidates = [text.find(mark, position) for mark in (";", ".", "!", "?", "\n")]
    right_candidates = [value for value in right_candidates if value >= 0]
    right = min(right_candidates) if right_candidates else len(text)
    return left, right


def _clause_modality(text: str, evidence: dict[str, Any]) -> list[re.Match[str]]:
    start, end = _clause_bounds(text, evidence["start"])
    return list(_MODALITY_MARKERS.finditer(text, start, end))


def _source_clauses(text: str) -> list[dict[str, Any]]:
    """Segment punctuation-delimited clauses with exact original offsets."""
    clauses: list[dict[str, Any]] = []
    start = 0
    for index, char in enumerate(text):
        if char in ";.!?\n":
            end = index
            left = start
            while left < end and text[left].isspace():
                left += 1
            right = end
            while right > left and text[right - 1].isspace():
                right -= 1
            if left < right:
                clauses.append({"id": f"clause_{len(clauses) + 1}", "span": {"start": left, "end": right}, "text": text[left:right], "outcome_refs": [], "clarification_refs": []})
            start = index + 1
    left = start
    while left < len(text) and text[left].isspace():
        left += 1
    right = len(text)
    while right > left and text[right - 1].isspace():
        right -= 1
    if left < right:
        clauses.append({"id": f"clause_{len(clauses) + 1}", "span": {"start": left, "end": right}, "text": text[left:right], "outcome_refs": [], "clarification_refs": []})
    return clauses

def _clause_for_offset(clauses: list[dict[str, Any]], offset: int) -> dict[str, Any] | None:
    return next((item for item in clauses if item["span"]["start"] <= offset < item["span"]["end"]), None)

def derive_objective_contract_v3(
    objective: str,
    reference_date: Any = None,
    locale: str | None = None,
) -> dict[str, Any]:
    """Build a conservative v3 typed projection; never authorizes discovery."""
    original = objective if isinstance(objective, str) else str(objective or "")
    v2 = derive_objective_contract(original, reference_date=reference_date)
    candidates = list(v2.get("required_goal_classes", []))
    clarifications: list[dict[str, Any]] = []
    outcomes: list[dict[str, Any]] = []
    clauses = _source_clauses(original)

    for index, goal_class in enumerate(candidates, start=1):
        evidence = _source_evidence(original, goal_class)
        clause_ref = None
        if evidence:
            source_clause = _clause_for_offset(clauses, evidence[0]["start"])
            clause_ref = source_clause["id"] if source_clause else None
        if not evidence:
            clarifications.append({
                "id": f"clarification_{len(clarifications) + 1}",
                "question": f"Confirm whether '{goal_class}' is an intended operation.",
                "reason": "no_direct_source_evidence",
                "affected_goal_classes": [goal_class],
                "clause_ref": clause_ref,
                "blocking": True,
                "source_evidence": [],
            })
            continue

        local_markers = _clause_modality(original, evidence[0])
        if local_markers:
            for marker in local_markers:
                clarifications.append({
                    "id": f"clarification_{len(clarifications) + 1}",
                    "question": "Clarify the scope of negation, condition, optionality, or alternatives for this clause.",
                    "reason": "clause_modality_scope_not_resolved",
                    "affected_goal_classes": [goal_class],
                    "blocking": True,
                    "source_evidence": [{
                        "start": marker.start(),
                        "end": marker.end(),
                        "text": original[marker.start():marker.end()],
                        "cue": "modality_marker",
                        "offset_unit": "unicode_code_point",
                    }],
                    "clause_ref": clause_ref,
                    "clause_span": {
                        "start": _clause_bounds(original, evidence[0]["start"])[0],
                        "end": _clause_bounds(original, evidence[0]["start"])[1],
                    },
                })
            continue

        outcomes.append({
            "id": f"outcome_{index}",
            "goal_class": goal_class,
            "clause_ref": clause_ref,
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

    for outcome in outcomes:
        clause = next((item for item in clauses if item["id"] == outcome["clause_ref"]), None)
        if clause: clause["outcome_refs"].append(outcome["id"])
    for clarification in clarifications:
        clause = next((item for item in clauses if item["id"] == clarification.get("clause_ref")), None)
        if clause: clause["clarification_refs"].append(clarification["id"])

    return {
        "schema": _SCHEMA,
        "contract_version": "3.0",
        "objective": {
            "text": original,
            "locale": locale or "und",
            "normalization": "none",
        },
        "clauses": clauses,
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
    clauses = contract.get("clauses", [])
    clause_ids: set[str] = set()
    for clause in clauses:
        clause_id = clause.get("id")
        if not clause_id or clause_id in clause_ids: errors.append("clause_id_missing_or_duplicate")
        clause_ids.add(clause_id)
        span = clause.get("span", {})
        start, end = span.get("start"), span.get("end")
        if not isinstance(start, int) or not isinstance(end, int) or start < 0 or end <= start or end > len(original):
            errors.append("clause_span_out_of_bounds")
        elif original[start:end] != clause.get("text"): errors.append("clause_span_text_mismatch")
    ids: set[str] = set()
    for outcome in contract.get("outcomes", []):
        outcome_id = outcome.get("id")
        if not outcome_id or outcome_id in ids:
            errors.append("outcome_id_missing_or_duplicate")
        ids.add(outcome_id)
        if outcome.get("clause_ref") not in clause_ids: errors.append("outcome_clause_ref_invalid")
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
    for clause in clauses:
        for outcome_ref in clause.get("outcome_refs", []):
            outcome = next((item for item in contract.get("outcomes", []) if item.get("id") == outcome_ref), None)
            if outcome is None or outcome.get("clause_ref") != clause.get("id"): errors.append("clause_outcome_reference_inconsistent")
        for clarification_ref in clause.get("clarification_refs", []):
            clarification = next((item for item in contract.get("clarifications", []) if item.get("id") == clarification_ref), None)
            if clarification is None or clarification.get("clause_ref") != clause.get("id"): errors.append("clause_clarification_reference_inconsistent")
    if contract.get("review", {}).get("required") is not True:
        errors.append("human_review_not_required")
    if contract.get("review", {}).get("semantic_correctness_verified") is not False:
        errors.append("semantic_correctness_must_remain_unverified")
    if contract.get("review", {}).get("discovery_blocked") is not True:
        errors.append("discovery_must_remain_blocked")
    return errors
