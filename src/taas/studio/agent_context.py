"""Build a deterministic, auditable Agent Intelligence Context for decomposition.

Instructions and skills influence LLM planning only. They never grant capabilities,
change authorization, or bypass the canonical GoalSpec/Core contract.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def build_agent_intelligence_context(
    manifest: dict[str, Any],
    objective: str,
    *,
    manifest_sha256: str | None = None,
    lifecycle_state: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Resolve Agent instructions and objective-triggered skills.

    Skill selection is intentionally deterministic: a skill is selected only
    when at least one declared trigger phrase occurs in the original objective,
    case-insensitively. This is a transparent first resolver, not semantic proof.
    """
    metadata = manifest.get("metadata", {})
    spec = manifest.get("spec", {})
    instructions = str(spec.get("instructions", "")).strip()
    objective_folded = objective.casefold()
    selected: list[dict[str, Any]] = []
    skill_trace: list[dict[str, Any]] = []

    for skill in spec.get("skills", []):
        if not isinstance(skill, dict):
            continue
        triggers = [str(value) for value in skill.get("trigger_phrases", [])]
        matched = [value for value in triggers if value.casefold() in objective_folded]
        skill_text = str(skill.get("instructions", "")).strip()
        skill_id = str(skill.get("id", ""))
        skill_version = str(skill.get("version", ""))
        digest = _sha256(skill_text)
        is_selected = bool(matched and skill_text)
        skill_trace.append({
            "id": skill_id,
            "version": skill_version,
            "instructions_sha256": digest,
            "selected": is_selected,
            "matched_triggers": matched,
            "selection_policy": "declared_trigger_phrase_substring_v1",
        })
        if is_selected:
            selected.append({
                "id": skill_id,
                "name": str(skill.get("name", "")),
                "description": str(skill.get("description", "")),
                "instructions": skill_text,
            })

    context = {
        "instructions": instructions,
        "skills": selected,
    }
    effective_context = json.dumps(
        context, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    trace = {
        "schema": "taas.agent-intelligence-context/v1",
        "status": "injected" if instructions or selected else "empty",
        "agent_id": metadata.get("id"),
        "agent_version": metadata.get("version"),
        "agent_lifecycle_state": lifecycle_state,
        "manifest_sha256": manifest_sha256,
        "instructions_sha256": _sha256(instructions) if instructions else None,
        "effective_context_sha256": _sha256(effective_context) if instructions or selected else None,
        "instructions_injected": bool(instructions),
        "skills": skill_trace,
        "selected_skill_ids": [item["id"] for item in selected],
        "selection_policy": "declared_trigger_phrase_substring_v1",
        "context_authority": "guidance_only_core_contract_and_governance_remain_authoritative",
    }
    return context, trace
