"""Resolve exact published Skill Registry references for immutable Agent versions.

A reusable Skill is planning guidance only. Resolution never grants tools,
permissions, data access, authorization, or execution rights.
"""
from __future__ import annotations

import copy
from typing import Any

from taas.studio import skill_dependency_graph


class AgentSkillBindingError(RuntimeError):
    pass


class AgentSkillBindingNotFound(AgentSkillBindingError):
    pass


class AgentSkillBindingConflict(AgentSkillBindingError):
    pass


def resolve_agent_skill_references(
    manifest: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Materialize exact published Skill DAGs in deterministic dependency-first order.

    Agent references pin the root Skill ID, version and manifest digest. Every
    transitive dependency is independently pinned by its parent manifest.
    """
    resolved_manifest = copy.deepcopy(manifest)
    spec = resolved_manifest.get("spec", {})
    references = spec.get("skill_refs", [])
    if not references:
        return resolved_manifest, []

    embedded = [
        skill for skill in spec.get("skills", [])
        if isinstance(skill, dict)
    ]
    embedded_ids = {str(skill.get("id")) for skill in embedded}
    resolved: list[dict[str, Any]] = []
    materialized: dict[str, dict[str, Any]] = {}
    materialized_pins: dict[str, tuple[str, str]] = {}

    for reference in references:
        skill_id = str(reference["id"])
        version = str(reference["version"])
        try:
            graph = skill_dependency_graph.resolve_skill_dependency_graph(
                skill_id,
                version,
                str(reference["manifest_sha256"]),
            )
        except skill_dependency_graph.SkillDependencyNotFound as exc:
            raise AgentSkillBindingNotFound(str(exc)) from exc
        except skill_dependency_graph.SkillDependencyGraphError as exc:
            raise AgentSkillBindingConflict(str(exc)) from exc

        for node in graph["nodes"]:
            node_id = node["id"]
            pin = (node["version"], node["manifest_sha256"])
            if node_id in embedded_ids:
                raise AgentSkillBindingConflict(
                    f"Skill {node_id} is defined both as an embedded Skill and a reusable dependency"
                )
            prior_pin = materialized_pins.get(node_id)
            if prior_pin is not None and prior_pin != pin:
                raise AgentSkillBindingConflict(
                    f"Agent references conflicting versions or digests for Skill {node_id}"
                )
            materialized_pins[node_id] = pin
            if node_id not in materialized:
                materialized[node_id] = {
                    "id": node_id,
                    "name": node["name"],
                    "version": node["version"],
                    "description": node.get("description", ""),
                    "instructions": node["instructions"],
                    "trigger_phrases": list(node["trigger_phrases"]),
                }

        root_record = {
            "id": skill_id,
            "version": version,
            "manifest_sha256": reference["manifest_sha256"],
            "lifecycle_state": "published",
            "source": "skill_registry",
        }
        if len(graph["nodes"]) > 1:
            root_record["dependency_graph_sha256"] = graph["graph_sha256"]
            root_record["resolved_dependencies"] = [
                {
                    "id": node["id"],
                    "version": node["version"],
                    "manifest_sha256": node["manifest_sha256"],
                }
                for node in graph["nodes"]
                if (node["id"], node["version"]) != (skill_id, version)
            ]
        resolved.append(root_record)

    combined_skills = embedded + list(materialized.values())
    if len(combined_skills) > 32:
        raise AgentSkillBindingConflict(
            "Resolved embedded and reusable Skills exceed the Agent limit of 32"
        )
    instruction_chars = sum(
        len(str(skill.get("instructions", ""))) for skill in combined_skills
    )
    if instruction_chars > 24000:
        raise AgentSkillBindingConflict(
            "Resolved Skill instructions exceed the Agent limit of 24000 characters"
        )
    if len(str(spec.get("instructions", ""))) + instruction_chars > 36000:
        raise AgentSkillBindingConflict(
            "Resolved Agent and Skill instructions exceed the 36000-character context limit"
        )

    # Dict insertion order follows deterministic dependency-first topological
    # order from each graph. Shared nodes are materialized once.
    spec.setdefault("skills", []).extend(materialized.values())
    return resolved_manifest, resolved
