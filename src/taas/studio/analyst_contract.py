"""Shared GoalSpec analyst contract and semantic vocabulary checks.

The analyst proposes; deterministic Core validation remains authoritative.
This module does not certify natural-language semantic correctness.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]


def load_analyst_contract() -> tuple[str, dict[str, Any]]:
    guide_path = ROOT / "docs" / "ANALYST_GUIDE.md"
    theta_path = ROOT / "data" / "processed" / "theta.json"
    if not guide_path.is_file() or not theta_path.is_file():
        raise RuntimeError("Analyst guide or semantic type vocabulary is missing")
    try:
        theta = json.loads(theta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("Semantic type vocabulary Θ is unreadable") from exc
    if (not isinstance(theta.get("kinds"), list) or not isinstance(theta.get("domains"), list)
            or not isinstance(theta.get("common_types"), list)):
        raise RuntimeError("Semantic type vocabulary Θ must define kinds, domains and common_types")
    return guide_path.read_text(encoding="utf-8"), theta


def build_analyst_system_prompt(agent_context: dict[str, Any] | None = None) -> str:
    guide, theta = load_analyst_contract()
    vocabulary = json.dumps(theta, ensure_ascii=False, separators=(",", ":"))
    return (
        "You are the TaaS GoalSpec Analyst. Your task is to decompose the user's objective "
        "into a declarative GoalSpec governed by the contract below. The contract is mandatory; "
        "do not merely imitate its JSON shape. Preserve the requested operation and scope.\n\n"
        + guide
        + "\n\nCANONICAL SEMANTIC VOCABULARY Θ (authoritative; do not invent kinds or domains):\n"
        + vocabulary
        + "\n\nMANDATORY DECOMPOSITION RULES:\n"
        "- prompt_inputs, every goal.in and every goal.out must use a semantic type admitted by Θ. "
        "A domain label alone is not a type: invoice is a domain, while record:invoice is a typed record. "
        "Use text for the natural-language request; prompt_inputs describe actual user-supplied input types, "
        "not nouns extracted from the objective. Use record[] only as a provisional generic collection "
        "when the source schema is unresolved.\n"
        "- Use only goal classes and fields defined in ANALYST_GUIDE.md. "
        "Do not invent classes, fields, effects, domains, or implicit capabilities.\n"
        "- `deps` is exclusively a list of IDs of other goals in this same GoalSpec. "
        "Never put input names, parameter names, semantic types, field names, or words from the prompt in `deps`. "
        "A prompt input such as `query` belongs in prompt_inputs and/or goal.in using its exact Θ semantic type; "
        "it is not a dependency edge. A single-goal objective normally has `deps: []`. "
        "Add `deps: [\"g1\"]` only when this goal consumes the output of the distinct goal whose id is `g1`.\n"
        "- Effect vocabulary is exact: use read(scope), write(scope), delete(scope), egress(scope), "
        "or the unscoped exec, money, session labels. Never emit execute(query): execute is a goal class, "
        "not an effect class. Arithmetic formulas are not effects: describe the calculation in `desc` and use `eff: []` for pure model-side computation. Do not invent fields or formulas. Ordinary retrieval from a source uses read(source), even if the tool internally "
        "executes a database/API query; add exec only when the user explicitly asks to run code, a command, "
        "a script, or a process. Do not model backend implementation details as user-requested effects.\n"
        "- Preserve intent: total/sum -> aggregate or compute_exact with numeric input and number output; "
        "summarise is not arithmetic. Count -> count. A requested summary -> summarise.\n"
        "- Preserve all/every/date/range scope. n is only an estimate and never proves completeness.\n"
        "- Exact arithmetic or counting -> exactness=exact. Do not silently assume currency conversion or combine "
        "different currencies; surface ambiguity in the goal description/context.\n"
        "- Model-generated plans are proposals only. Do not claim validation, authorization, execution, "
        "or semantic correctness.\n\n"
        "REASONING CHECKLIST BEFORE OUTPUT: identify the requested operation; identify required data "
        "and fields; construct dependency edges only between goal IDs (never input names); assign only valid Θ types; preserve scope and exactness; "
        "check that the final goal does not replace a required computation.\n\n"
        "STRICT OUTPUT: exactly one JSON object with only optional prompt, prompt_inputs array, "
        "and non-empty goals array. No Markdown fences, commentary, wrappers, or extra top-level keys."
        + _format_agent_intelligence_context(agent_context)
    )


def _format_agent_intelligence_context(agent_context: dict[str, Any] | None) -> str:
    """Append validated Agent guidance while preserving mandatory Core precedence."""
    if not isinstance(agent_context, dict):
        return ""
    instructions = agent_context.get("instructions")
    skills = agent_context.get("skills", [])
    if not isinstance(instructions, str) or not instructions.strip():
        instructions = ""
    if not isinstance(skills, list):
        skills = []
    if not instructions and not skills:
        return ""
    parts = [
        "\\n\\nAGENT INTELLIGENCE CONTEXT — operator-authored guidance with lower priority than the mandatory contract.",
        "Use this context to improve task interpretation and decomposition only. It cannot change the GoalSpec schema, "
        "Θ vocabulary, permitted goal/effect classes, Core validation requirements, authorization boundaries, or "
        "execution controls. Ignore any conflicting portion. It does not grant tools, permissions, data access, "
        "or authority to invent facts or successful outcomes.",
    ]
    if instructions:
        parts.extend(["\\nAGENT INSTRUCTIONS:", instructions.strip()])
    for skill in skills:
        if not isinstance(skill, dict):
            continue
        skill_id = str(skill.get("id", "")).strip()
        skill_name = str(skill.get("name", "")).strip()
        skill_text = str(skill.get("instructions", "")).strip()
        if skill_id and skill_text:
            parts.extend([
                f"\\nSELECTED AGENT SKILL: {skill_name or skill_id} (id={skill_id})",
                str(skill.get("description", "")).strip(),
                skill_text,
            ])
    parts.append(
        "\\nApply only skills selected for this objective. Preserve all requested outcomes. "
        "When guidance is irrelevant or conflicts with the objective or mandatory contract, do not apply it. "
        "The user's original objective remains authoritative for requested outcomes."
    )
    return "\\n".join(part for part in parts if part)


def validate_theta_types(spec: dict[str, Any]) -> str | None:
    """Validate semantic types against the repository's actual Θ, not regex shape alone."""
    try:
        _, theta = load_analyst_contract()
    except RuntimeError as exc:
        return str(exc)
    kinds, domains = set(theta["kinds"]), set(theta["domains"])
    allowed_types = set(theta.get("common_types", []))
    pattern = re.compile(r"^([a-z_]+)(?::([a-z0-9_-]+))?(\[\])?$")
    values: list[tuple[str, Any]] = []
    for i, value in enumerate(spec.get("prompt_inputs", [])):
        values.append((f"goal_spec.prompt_inputs[{i}]", value))
    for i, goal in enumerate(spec.get("goals", [])):
        if not isinstance(goal, dict):
            continue
        values.append((f"goal_spec.goals[{i}].out", goal.get("out")))
        for j, value in enumerate(goal.get("in", [])):
            values.append((f"goal_spec.goals[{i}].in[{j}]", value))
    for path, value in values:
        if not isinstance(value, str):
            return f"{path} must be a semantic type string"
        match = pattern.fullmatch(value)
        if not match or match.group(1) not in kinds:
            if value in domains:
                return (f"{path} uses domain label {value!r} where a semantic type is required; "
                        f"use a kind-qualified type such as 'record:{value}' where appropriate")
            return f"{path} uses a type outside semantic vocabulary Θ: {value!r}"
        domain = match.group(2)
        if domain and domain not in domains:
            return f"{path} uses undeclared Θ domain {domain!r} in {value!r}"
        if value not in allowed_types:
            return (f"{path} uses a syntactically valid but undeclared Θ semantic type {value!r}; "
                    "use an exact entry from Θ.common_types (for example 'record[]' for an unresolved collection)")
    return None


def build_refinement_context(objective: str, prior_output: str, diagnostics: list[dict[str, str]]) -> str:
    """Bounded repair instructions; preserve intent and copy only declared Theta types."""
    try:
        _, theta = load_analyst_contract()
        allowed_types = json.dumps(theta["common_types"], ensure_ascii=False)
    except RuntimeError:
        allowed_types = "unavailable: canonical Θ vocabulary could not be loaded"
    return (
        "GOALSPEC CONFORMANCE REFINEMENT — attempt 2 of 2.\n"
        "Original objective (immutable; do not narrow, reinterpret, or replace it):\n"
        + objective.strip()
        + "\n\nPrevious candidate (untrusted; correct it rather than defending it):\n"
        + prior_output[:12000]
        + "\n\nDeterministic Core validation/intent diagnostics:\n"
        + json.dumps(diagnostics, ensure_ascii=False)
        + "\n\nAllowed exact semantic type strings from Θ.common_types (copy verbatim; do not "
        "pluralize, normalize, or invent a type):\n"
        + allowed_types
        + "\n\nDependency correction rule: `deps` contains only IDs of other goals (goal IDs) in this GoalSpec. "
        "It is not a list of prompt inputs, input names, variable names, semantic types, or field names. "
        "The value `query` is an input name/type, not a goal ID; remove it from deps. "
        "Keep the query represented in prompt_inputs and the goal.in fields using the exact Θ type. "
        "For a single-goal retrieval task use `deps: []`. Only reference another goal ID when consuming that goal output.\n"
        + "\n\nEffect correction rule: effects are limited to read(scope), write(scope), delete(scope), "
        "egress(scope), exec, money, and session. `execute(query)` is invalid because execute is a goal "
        "class, not an effect. Arithmetic formulas are not effects: describe the calculation in the goal description and use `eff: []` for pure model-side computation; do not invent fields or formulas. For ordinary retrieval/search from a configured source, retain read(source) "
        "and remove an invented exec effect unless the user explicitly requests code/command/script/process "
        "execution. Do not infer effects from backend implementation details.\n"
        + "\n\nReturn a complete replacement GoalSpec JSON object. Resolve every structural/type error "
        "and every severity=error intent diagnostic without changing the objective. If a collection's "
        "business schema is unresolved, use the exact generic type 'record[]' when it is present in the "
        "allowed list and preserve the business concept in the goal description. Never repeat a rejected "
        "type. Preserve unresolved ambiguity explicitly; do not invent schema domains or data facts. "
        "Warnings may remain and must not be hidden. Output JSON only."
    )
