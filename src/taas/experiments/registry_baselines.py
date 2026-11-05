"""Registry-side typing and effect baseline adapters for E2/E3."""
from __future__ import annotations

from typing import Any, Sequence

from taas.data.registries import RawTool
from taas.effects import lexical_effects
from taas.types import KINDS, parse_type, tau_arg, tau_out


def _schema_type(schema: dict[str, Any] | None):
    schema = schema if isinstance(schema, dict) else {}
    kind = schema.get("type")
    fmt = schema.get("format")
    if kind == "array":
        inner = _schema_type(schema.get("items") or {})
        return parse_type(str(inner) + "[]")
    if kind == "object":
        return parse_type("record")
    if kind in {"integer", "number"}:
        return parse_type("number")
    if kind == "boolean":
        return parse_type("boolean")
    if kind == "string":
        if fmt in {"uri", "url", "uri-reference"}:
            return parse_type("url")
        if fmt in {"date-time", "date", "time"}:
            return parse_type("datetime")
        if fmt in {"binary", "byte"}:
            return parse_type("media")
        return parse_type("text")
    return parse_type("none")


def run_typing_baseline(baseline_id: str, tools: Sequence[RawTool]) -> dict[str, Any]:
    """Predict semantic types from declarations without reading evaluator labels."""
    if baseline_id not in {"typing_structural", "typing_schema_lexical"}:
        raise KeyError(f"Unsupported typing baseline: {baseline_id}")
    predictions = []
    for tool in tools:
        props = (tool.input_schema or {}).get("properties", {}) or {}
        required = set((tool.input_schema or {}).get("required", []) or [])
        inputs = {}
        for name, schema in props.items():
            if baseline_id == "typing_structural":
                value = _schema_type(schema if isinstance(schema, dict) else {})
            else:
                value = tau_arg(name, schema if isinstance(schema, dict) else {}, tool.description).type
            inputs[name] = str(value)
        out_schema = tool.output_schema if isinstance(tool.output_schema, dict) else {}
        if baseline_id == "typing_structural":
            output = str(_schema_type(out_schema))
        else:
            output = str(tau_out(tool.name, tool.description, tool.output_schema).type)
        predictions.append({
            "tool_id": tool.id,
            "inputs": inputs,
            "required_inputs": sorted(required),
            "output": output,
            "method": baseline_id,
        })
    return {
        "baseline_id": baseline_id,
        "status": "completed",
        "prediction_count": len(predictions),
        "predictions": predictions,
        "evaluator_labels_read": False,
        "evidence_source": "tool schema only" if baseline_id == "typing_structural"
                           else "tool schema + name + description",
    }


def _declared_effects(tool: RawTool) -> dict[str, Any]:
    """Preserve MCP annotation claims without converting them into observed effects.

    In particular, readOnlyHint=False is not evidence of a write operation.
    """
    annotations = tool.annotations or {}
    return {
        "read_only_hint": annotations.get("readOnlyHint"),
        "destructive_hint": annotations.get("destructiveHint"),
        "open_world_hint": annotations.get("openWorldHint"),
        "evidence_class": "declared",
        "observed_effects": None,
        "effect_claims": [],
    }


def run_effect_baseline(baseline_id: str, tools: Sequence[RawTool]) -> dict[str, Any]:
    """Return declaration- or lexical-only effect predictions for E3."""
    rows = []
    if baseline_id not in {"effects_declared", "effects_lexical"}:
        if baseline_id == "effects_probe":
            return {
                "baseline_id": baseline_id,
                "status": "blocked_runtime_probe_not_implemented",
                "prediction_count": 0,
                "predictions": [],
                "reason": "Requires isolated live MCP server execution, state snapshots and trace capture.",
                "evaluator_labels_read": False,
            }
        raise KeyError(f"Unsupported effect baseline: {baseline_id}")
    for tool in tools:
        if baseline_id == "effects_declared":
            declared = _declared_effects(tool)
            effects = []
            source = "MCP annotations (declarations only; not observed effects)"
        else:
            effects = sorted(str(e) for e in lexical_effects(
                tool.name, tool.description,
                list(((tool.input_schema or {}).get("properties") or {}).keys())))
            source = "name + description + argument names"
        row = {"tool_id": tool.id, "effects": effects, "evidence_source": source}
        if baseline_id == "effects_declared":
            row.update(declared)
        else:
            row["evidence_class"] = "inferred"
            row["observed_effects"] = None
        rows.append(row)
    return {
        "baseline_id": baseline_id,
        "status": "completed",
        "prediction_count": len(rows),
        "predictions": rows,
        "evaluator_labels_read": False,
    }
