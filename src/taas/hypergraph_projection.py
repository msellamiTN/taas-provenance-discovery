"""Read-only deterministic projection of the authoritative TaaS semantic hypergraph."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

from .hypergraph import Derivation, Hypergraph, ModelEdge, ReachResult

PROJECTION_SCHEMA = "taas.hypergraph-projection/v1"


def _stable_id(prefix: str, value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return f"{prefix}_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:20]}"


def _type_node(type_name: str, reachable: set[str], labels: dict[str, str],
               derivations: dict[str, Derivation]) -> dict[str, Any]:
    derivation = derivations.get(type_name)
    return {
        "id": f"type:{type_name}",
        "kind": "semantic_type",
        "semantic_type": type_name,
        "reachable": type_name in reachable,
        "information_label": labels.get(type_name),
        "derivation": None if derivation is None else {
            "edge_id": derivation.edge,
            "kind": derivation.kind,
            "inputs": list(derivation.inputs),
            "rho": derivation.rho,
        },
    }


def project_hypergraph(
    graph: Hypergraph,
    reach: ReachResult,
    *,
    selected_tools: Iterable[str] | None = None,
    model_edges: Iterable[ModelEdge] = (),
) -> dict[str, Any]:
    """Serialize core graph and reachability objects; never recompute their semantics.

    Unknown selected tool identifiers are rejected. Unreachable types remain visible
    with reachable=false, and missing labels remain null rather than being inferred.
    """
    tool_ids = sorted(graph.contracts if selected_tools is None else set(selected_tools))
    unknown = sorted(set(tool_ids) - set(graph.contracts))
    if unknown:
        raise ValueError(f"unknown tool identifiers: {', '.join(unknown)}")

    reachable = {str(item) for item in reach.types}
    vertices: dict[str, dict[str, Any]] = {}
    hyperedges: list[dict[str, Any]] = []

    for type_name in reachable:
        vertices[f"type:{type_name}"] = _type_node(
            type_name, reachable, reach.labels, reach.derivations
        )

    for tool_id in tool_ids:
        contract = graph.contracts[tool_id]
        tail = [str(item) for item in contract.tail]
        head = str(contract.head)
        for type_name in tail + [head]:
            vertices.setdefault(
                f"type:{type_name}",
                _type_node(type_name, reachable, reach.labels, reach.derivations),
            )
        forbidden = []
        for (left, right), reason in sorted(graph.forbidden.items()):
            if tool_id in (left, right):
                forbidden.append({
                    "tool_id": right if left == tool_id else left,
                    "reason": reason,
                })
        hyperedges.append({
            "id": f"tool:{tool_id}",
            "kind": "tool",
            "tool_id": tool_id,
            "name": contract.name,
            "server": contract.server,
            "description": contract.description,
            "tail": [
                {"type": str(arg.type), "argument": arg.name, "required": arg.required}
                for arg in contract.args
            ],
            "required_inputs": tail,
            "head": head,
            "effects": sorted(str(effect) for effect in contract.eff),
            "information_source_label": contract.flow.source_label,
            "tool_class": contract.tool_class,
            "contract_fingerprint": contract.h,
            "qos": {
                "price": contract.qos.price,
                "latency": contract.qos.latency,
                "failure_probability": contract.qos.fail,
            },
            "fired_in_reachability": tool_id in reach.fired,
            "forbidden_with": forbidden,
        })

    # Hypergraph.reach() intentionally removes LLM::* identifiers from ReachResult.fired.
    # Model execution is therefore evidenced by the recorded model derivation, not fired.
    model_derivation_edges = {
        derivation.edge
        for derivation in reach.derivations.values()
        if derivation.kind == "model"
    }
    model_edge_list = list(model_edges)
    for model in model_edge_list:
        tail = [str(item) for item in model.tail]
        head = str(model.head)
        for type_name in tail + [head]:
            vertices.setdefault(
                f"type:{type_name}",
                _type_node(type_name, reachable, reach.labels, reach.derivations),
            )
        hyperedges.append({
            "id": f"model:{model.id}",
            "kind": "model",
            "model_class": model.cls,
            "goal_id": model.goal,
            "tail": [{"type": item} for item in tail],
            "required_inputs": tail,
            "head": head,
            "rho": model.rho,
            "fired_in_reachability": model.id in model_derivation_edges,
        })

    bridges = []
    for index, bridge in enumerate(reach.bridges):
        bridge_id = _stable_id("bridge", {
            "edge": bridge.edge, "head": bridge.head,
            "inputs": list(bridge.inputs), "rho": bridge.rho, "index": index,
        })
        bridges.append({
            "id": bridge_id,
            "kind": "bridge",
            "operation": bridge.edge,
            "tail": list(bridge.inputs),
            "head": bridge.head,
            "rho": bridge.rho,
        })
        for type_name in list(bridge.inputs) + [bridge.head]:
            vertices.setdefault(
                f"type:{type_name}",
                _type_node(type_name, reachable, reach.labels, reach.derivations),
            )

    vertex_list = sorted(vertices.values(), key=lambda item: item["id"])
    hyperedges.sort(key=lambda item: item["id"])
    bridges.sort(key=lambda item: item["id"])
    body = {
        "schema": PROJECTION_SCHEMA,
        "vertices": vertex_list,
        "hyperedges": hyperedges,
        "bridges": bridges,
        "reachability": {
            "reachable_types": sorted(reachable),
            "fired_edges": sorted(reach.fired),
            "information_labels": dict(sorted(reach.labels.items())),
            "derivations": {
                key: {
                    "edge_id": value.edge,
                    "kind": value.kind,
                    "inputs": list(value.inputs),
                    "rho": value.rho,
                }
                for key, value in sorted(reach.derivations.items())
            },
        },
        "summary": {
            "vertex_count": len(vertex_list),
            "hyperedge_count": len(hyperedges),
            "bridge_count": len(bridges),
            "registered_tool_count": len(tool_ids),
            "reachable_type_count": len(reachable),
            "forbidden_pair_count": len(graph.forbidden),
        },
    }
    body["projection_id"] = _stable_id("hgp", body)
    return body



def project_skill_dependency_graph(skill_graph: dict[str, Any]) -> dict[str, Any]:
    """Project an exact-pin Skill DAG into the shared Hypergraph Explorer schema.

    Skill dependency relations are a distinct graph domain. They are not
    semantic-type reachability, tool capability edges, trust attestations,
    authorization grants, or execution paths.
    """
    root = skill_graph.get("root")
    nodes = skill_graph.get("nodes")
    edges = skill_graph.get("edges")
    if not isinstance(root, dict) or not isinstance(nodes, list) or not isinstance(edges, list):
        raise ValueError("invalid Skill dependency graph payload")
    if not nodes or len(nodes) > 32 or len(edges) > 128:
        raise ValueError("Skill dependency graph is empty or exceeds projection bounds")

    vertices: list[dict[str, Any]] = []
    node_keys: set[tuple[str, str]] = set()
    for node in nodes:
        if not isinstance(node, dict):
            raise ValueError("malformed Skill dependency node")
        skill_id, version, digest = node.get("id"), node.get("version"), node.get("manifest_sha256")
        if not all(isinstance(value, str) and value for value in (skill_id, version, digest)):
            raise ValueError("Skill dependency nodes require exact id, version and digest")
        key = (skill_id, version)
        if key in node_keys:
            raise ValueError("duplicate Skill dependency node")
        node_keys.add(key)
        vertices.append({
            "id": f"skill:{skill_id}@{version}",
            "kind": "skill",
            "skill_id": skill_id,
            "version": version,
            "manifest_sha256": digest,
            "lifecycle_state": node.get("lifecycle_state"),
            "name": node.get("name") or skill_id,
            "description": node.get("description") or "",
            "source": node.get("source") or "skill_registry",
            "root": key == (root.get("id"), root.get("version")),
        })

    hyperedges: list[dict[str, Any]] = []
    seen_edges: set[tuple[tuple[str, str], tuple[str, str]]] = set()
    for edge in edges:
        if not isinstance(edge, dict) or edge.get("relation") != "depends_on":
            raise ValueError("unsupported or malformed Skill dependency relation")
        source, target = edge.get("from"), edge.get("to")
        if not isinstance(source, dict) or not isinstance(target, dict):
            raise ValueError("Skill dependency edges require from/to pins")
        source_key = (source.get("id"), source.get("version"))
        target_key = (target.get("id"), target.get("version"))
        if source_key not in node_keys or target_key not in node_keys or source_key == target_key:
            raise ValueError("Skill dependency edge references an unknown or identical node")
        edge_key = (source_key, target_key)
        if edge_key in seen_edges:
            raise ValueError("duplicate Skill dependency edge")
        seen_edges.add(edge_key)
        hyperedges.append({
            "id": _stable_id("skilldep", {
                "from": {"id": source_key[0], "version": source_key[1]},
                "to": {"id": target_key[0], "version": target_key[1]},
                "relation": "depends_on",
            }),
            "kind": "skill_dependency",
            "from": {"id": source_key[0], "version": source_key[1]},
            "to": {"id": target_key[0], "version": target_key[1]},
            "source_vertex": f"skill:{source_key[0]}@{source_key[1]}",
            "target_vertex": f"skill:{target_key[0]}@{target_key[1]}",
            "relation": "depends_on",
            "authorization_effect": "none",
            "execution_effect": "none",
        })

    vertices.sort(key=lambda item: item["id"])
    hyperedges.sort(key=lambda item: item["id"])
    body = {
        "schema": PROJECTION_SCHEMA,
        "projection_domain": "skill_dependency_dag",
        "vertices": vertices,
        "hyperedges": hyperedges,
        "bridges": [],
        "graph_metadata": {
            "root": dict(root),
            "graph_sha256": skill_graph.get("graph_sha256"),
            "topological_order": list(skill_graph.get("topological_order", [])),
            "semantic_correctness_verified": False,
            "tools_authorized": False,
            "execution_enabled": False,
        },
        "summary": {
            "vertex_count": len(vertices),
            "hyperedge_count": len(hyperedges),
            "bridge_count": 0,
            "skill_count": len(vertices),
            "dependency_count": len(hyperedges),
            "root_skill_count": sum(1 for item in vertices if item["root"]),
        },
    }
    body["projection_id"] = _stable_id("hgp", body)
    return body
