"""Resolve exact published Skill dependencies as a bounded, deterministic DAG.

Dependency edges are planning-composition relationships only. They do not
create tool grants, trust attestations, authorization, or execution rights.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from taas.studio import skill_registry


class SkillDependencyGraphError(RuntimeError):
    """Base class for fail-closed dependency graph resolution errors."""


class SkillDependencyNotFound(SkillDependencyGraphError):
    pass


class SkillDependencyConflict(SkillDependencyGraphError):
    pass


class SkillDependencyCycle(SkillDependencyConflict):
    pass


class SkillDependencyLimitExceeded(SkillDependencyConflict):
    pass


def _canonical_digest(value: dict[str, Any]) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def resolve_skill_dependency_graph(
    skill_id: str,
    version: str,
    manifest_sha256: str,
    *,
    max_nodes: int = 32,
    max_depth: int = 16,
    max_edges: int = 128,
    allow_revoked: bool = False,
) -> dict[str, Any]:
    """Resolve a published root Skill and all exact pinned dependencies.

    Nodes are returned in deterministic dependency-first topological order.
    Every node must be published and match its pinned canonical manifest
    digest. Multiple versions of one Skill ID are rejected to avoid ambiguous
    composition. Cycles and resource-bound violations fail closed.
    """
    if max_nodes < 1 or max_depth < 0 or max_edges < 0:
        raise ValueError("graph bounds must be non-negative and max_nodes must be positive")

    root = {
        "id": skill_id,
        "version": version,
        "manifest_sha256": manifest_sha256,
    }
    nodes: dict[tuple[str, str], dict[str, Any]] = {}
    versions_by_id: dict[str, str] = {}
    edges: set[tuple[str, str, str, str]] = set()
    visiting: list[tuple[str, str]] = []
    visited: set[tuple[str, str]] = set()
    ordered: list[tuple[str, str]] = []

    def visit(reference: dict[str, str], depth: int) -> None:
        node_id = reference["id"]
        node_version = reference["version"]
        key = (node_id, node_version)

        if depth > max_depth:
            raise SkillDependencyLimitExceeded(
                f"Skill dependency depth exceeds configured maximum {max_depth}"
            )
        prior_version = versions_by_id.get(node_id)
        if prior_version is not None and prior_version != node_version:
            raise SkillDependencyConflict(
                f"Dependency graph contains conflicting versions for Skill {node_id}: "
                f"{prior_version} and {node_version}"
            )
        versions_by_id[node_id] = node_version

        if key in visiting:
            cycle_start = visiting.index(key)
            cycle = visiting[cycle_start:] + [key]
            rendered = " -> ".join(f"{item[0]}@{item[1]}" for item in cycle)
            raise SkillDependencyCycle(f"Skill dependency cycle detected: {rendered}")
        if key in visited:
            existing = nodes[key]
            if existing["manifest_sha256"] != reference["manifest_sha256"]:
                raise SkillDependencyConflict(
                    f"Conflicting digest pins for Skill {node_id}@{node_version}"
                )
            return

        if len(nodes) >= max_nodes:
            raise SkillDependencyLimitExceeded(
                f"Skill dependency graph exceeds configured maximum {max_nodes} nodes"
            )

        try:
            resource = skill_registry.get_version(node_id, node_version)
        except skill_registry.SkillRegistryNotFound as exc:
            raise SkillDependencyNotFound(
                f"Referenced Skill {node_id}@{node_version} does not exist"
            ) from exc

        if resource.get("lifecycle_state") != "published":
            raise SkillDependencyConflict(
                f"Referenced Skill {node_id}@{node_version} must be published; "
                f"current state is {resource.get('lifecycle_state')!r}"
            )
        if resource.get("revoked") and not allow_revoked:
            raise SkillDependencyConflict(
                f"Referenced Skill {node_id}@{node_version} has been revoked and "
                "cannot be resolved for binding"
            )
        actual_digest = resource.get("manifest_sha256")
        if actual_digest != reference["manifest_sha256"]:
            raise SkillDependencyConflict(
                f"Referenced Skill {node_id}@{node_version} manifest digest does not match "
                "the pinned digest"
            )

        manifest = resource.get("manifest")
        metadata = manifest.get("metadata", {}) if isinstance(manifest, dict) else {}
        spec = manifest.get("spec", {}) if isinstance(manifest, dict) else {}
        if metadata.get("id") != node_id or metadata.get("version") != node_version:
            raise SkillDependencyConflict(
                f"Skill Registry returned a mismatched immutable identity for {node_id}@{node_version}"
            )
        dependencies = spec.get("dependencies", [])
        if not isinstance(dependencies, list):
            raise SkillDependencyConflict(
                f"Skill {node_id}@{node_version} has malformed dependencies"
            )

        visiting.append(key)
        nodes[key] = {
            "id": node_id,
            "version": node_version,
            "manifest_sha256": actual_digest,
            "lifecycle_state": resource["lifecycle_state"],
            "revoked": bool(resource.get("revoked")),
            "name": metadata.get("name", node_id),
            "description": metadata.get("description", ""),
            "instructions": spec.get("instructions", ""),
            "trigger_phrases": list(spec.get("trigger_phrases", [])),
            "source": "skill_registry",
        }
        for dependency in dependencies:
            if not isinstance(dependency, dict):
                raise SkillDependencyConflict(
                    f"Skill {node_id}@{node_version} contains a malformed dependency reference"
                )
            required = ("id", "version", "manifest_sha256")
            if any(not isinstance(dependency.get(field), str) for field in required):
                raise SkillDependencyConflict(
                    f"Skill {node_id}@{node_version} dependency references must pin id, version and digest"
                )
            target = (dependency["id"], dependency["version"])
            edges.add((node_id, node_version, target[0], target[1]))
            if len(edges) > max_edges:
                raise SkillDependencyLimitExceeded(
                    f"Skill dependency graph exceeds configured maximum {max_edges} edges"
                )
            visit(dependency, depth + 1)
        visiting.pop()
        visited.add(key)
        ordered.append(key)

    visit(root, 0)

    ordered_nodes = [nodes[key] for key in ordered]
    ordered_edges = [
        {
            "from": {"id": source_id, "version": source_version},
            "to": {"id": target_id, "version": target_version},
            "relation": "depends_on",
        }
        for source_id, source_version, target_id, target_version in sorted(edges)
    ]
    digest_payload = {
        "root": root,
        "nodes": [
            {key: node[key] for key in ("id", "version", "manifest_sha256")}
            for node in ordered_nodes
        ],
        "edges": ordered_edges,
        "topological_order": [
            {"id": key[0], "version": key[1]} for key in ordered
        ],
    }
    return {
        "root": root,
        "nodes": ordered_nodes,
        "edges": ordered_edges,
        "topological_order": digest_payload["topological_order"],
        "graph_sha256": _canonical_digest(digest_payload),
        "limits": {
            "max_nodes": max_nodes,
            "max_depth": max_depth,
            "max_edges": max_edges,
        },
        "semantic_correctness_verified": False,
        "tools_authorized": False,
        "execution_enabled": False,
    }
