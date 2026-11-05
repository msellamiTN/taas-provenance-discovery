"""Resolve exact published Skill Registry references for immutable Agent versions.

A reusable Skill is planning guidance only. Resolution never grants tools,
permissions, data access, authorization, or execution rights.
"""
from __future__ import annotations

import copy
from typing import Any

from taas.studio import skill_registry


class AgentSkillBindingError(RuntimeError):
    pass


class AgentSkillBindingNotFound(AgentSkillBindingError):
    pass


class AgentSkillBindingConflict(AgentSkillBindingError):
    pass


def resolve_agent_skill_references(manifest: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Return a copy with exact published registry Skills materialized for context.

    Each Agent reference pins both semantic version and the registry manifest digest.
    Mutable aliases/latest tags are deliberately unsupported.
    """
    resolved_manifest = copy.deepcopy(manifest)
    spec = resolved_manifest.get("spec", {})
    references = spec.get("skill_refs", [])
    if not references:
        return resolved_manifest, []

    embedded_ids = {
        str(skill.get("id"))
        for skill in spec.get("skills", [])
        if isinstance(skill, dict)
    }
    resolved: list[dict[str, Any]] = []
    external_skills: list[dict[str, Any]] = []

    for reference in references:
        skill_id = str(reference["id"])
        version = str(reference["version"])
        try:
            resource = skill_registry.get_version(skill_id, version)
        except skill_registry.SkillRegistryNotFound as exc:
            raise AgentSkillBindingNotFound(
                f"Referenced Skill {skill_id}@{version} does not exist"
            ) from exc

        if resource.get("lifecycle_state") != "published":
            raise AgentSkillBindingConflict(
                f"Referenced Skill {skill_id}@{version} must be published; "
                f"current state is {resource.get('lifecycle_state')!r}"
            )
        actual_digest = resource.get("manifest_sha256")
        if actual_digest != reference.get("manifest_sha256"):
            raise AgentSkillBindingConflict(
                f"Referenced Skill {skill_id}@{version} manifest digest does not match the pinned digest"
            )

        skill_manifest = resource["manifest"]
        metadata = skill_manifest["metadata"]
        skill_spec = skill_manifest["spec"]
        if metadata.get("id") != skill_id or metadata.get("version") != version:
            raise AgentSkillBindingConflict("Skill Registry returned a mismatched immutable identity")
        if skill_id in embedded_ids:
            raise AgentSkillBindingConflict(
                f"Skill {skill_id} is defined both as an embedded Skill and a reusable reference"
            )

        external_skills.append({
            "id": skill_id,
            "name": metadata["name"],
            "version": version,
            "description": metadata.get("description", ""),
            "instructions": skill_spec["instructions"],
            "trigger_phrases": list(skill_spec["trigger_phrases"]),
        })
        resolved.append({
            "id": skill_id,
            "version": version,
            "manifest_sha256": actual_digest,
            "lifecycle_state": resource["lifecycle_state"],
            "source": "skill_registry",
        })

    spec.setdefault("skills", []).extend(external_skills)
    return resolved_manifest, resolved
