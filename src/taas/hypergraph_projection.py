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
            "fired_in_reachability": model.id in reach.fired,
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
