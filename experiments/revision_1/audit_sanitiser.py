"""Audit model-visible fields in the current manifest sanitizer and a safe-alias prototype.

This is a transformation-level test. It does not execute an MCP server or agent.
The server-side reverse map is deliberately not serialized into the model-visible manifest.
"""
from __future__ import annotations

import copy
import json
import os
from dataclasses import replace
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments"))
sys.path.insert(0, str(ROOT / "src"))

import fe  # noqa: E402
from taas.manifest import sanitise  # noqa: E402

DESC_CANARY = "PAMCPREV1DESCRIPTIONCANARY"
NAME_CANARY = "PAMCPREV1TOOLNAMECANARY"
ARG_CANARY = "PAMCPREV1ARGUMENTCANARY"
SAFE_CLASSES = {
    "classify", "extract", "summarise", "summarize", "translate", "convert_format",
    "aggregate", "compute_exactly", "retrieve", "write", "search", "other",
}


def alias_manifest(contracts):
    """Return (model_visible_manifest, server_only_binding_map)."""
    visible = []
    bindings = {}
    for i, contract in enumerate(sorted(contracts, key=lambda c: c.tool)):
        tool_alias = f"tool_{i + 1:04d}"
        args_schema = {}
        arg_bindings = {}
        for j, arg in enumerate(contract.args):
            arg_alias = f"arg_{j + 1:03d}"
            kind = arg.type.kind
            json_type = "number" if kind == "number" else "boolean" if kind == "boolean" else "string"
            args_schema[arg_alias] = {"type": json_type, "description": str(arg.type)}
            arg_bindings[arg_alias] = arg.name
        tool_class = contract.tool_class if contract.tool_class in SAFE_CLASSES else "other"
        desc = (f"{tool_class}: consumes "
                f"{', '.join(str(a.type) for a in contract.args if a.required) or 'no required arguments'} "
                f"and produces {contract.head}.")
        visible.append({
            "name": tool_alias,
            "description": desc,
            "inputSchema": {
                "type": "object",
                "properties": args_schema,
                "required": [f"arg_{j + 1:03d}" for j, a in enumerate(contract.args) if a.required],
            },
        })
        bindings[tool_alias] = {"tool_id": contract.tool, "argument_map": arg_bindings}
    return {"tools": visible}, bindings


def main() -> None:
    contracts = fe.contracts_cached("declared")
    counts = {
        "n_tools": len(contracts),
        "current_description_canary_leaks": 0,
        "current_tool_name_canary_leaks": 0,
        "current_argument_key_canary_leaks": 0,
        "alias_manifest_canary_leaks": 0,
        "alias_binding_canary_occurrences_server_side": 0,
    }
    examples = []
    for contract in contracts:
        attacked = copy.deepcopy(contract)
        attacked.description = (attacked.description or "") + "\\n" + DESC_CANARY
        attacked.name = f"{NAME_CANARY}_{attacked.name}"
        attacked.args = tuple(replace(a, name=f"{ARG_CANARY}_{a.name}") for a in attacked.args)

        current_obj = sanitise(attacked)
        current = json.dumps(current_obj, sort_keys=True)
        counts["current_description_canary_leaks"] += int(DESC_CANARY in current)
        counts["current_tool_name_canary_leaks"] += int(NAME_CANARY in current)
        counts["current_argument_key_canary_leaks"] += int(ARG_CANARY in current)

        visible, binding_map = alias_manifest([attacked])
        visible_json = json.dumps(visible, sort_keys=True)
        binding_json = json.dumps(binding_map, sort_keys=True)
        counts["alias_manifest_canary_leaks"] += int(
            any(marker in visible_json for marker in (DESC_CANARY, NAME_CANARY, ARG_CANARY))
        )
        counts["alias_binding_canary_occurrences_server_side"] += sum(
            binding_json.count(marker) for marker in (DESC_CANARY, NAME_CANARY, ARG_CANARY)
        )
        if len(examples) < 3:
            examples.append({
                "tool_id": contract.tool,
                "current_name_has_name_canary": NAME_CANARY in current,
                "current_schema_has_argument_canary": ARG_CANARY in current,
                "current_description_has_description_canary": DESC_CANARY in current,
                "alias_manifest_has_any_canary": any(
                    marker in visible_json for marker in (DESC_CANARY, NAME_CANARY, ARG_CANARY)
                ),
            })

    result = {
        "evidence_class": "LOCAL_TRANSFORMATION_TEST_NOT_RUNTIME_ATTACK_EVALUATION",
        "canaries": {
            "description": DESC_CANARY,
            "tool_name": NAME_CANARY,
            "argument_key": ARG_CANARY,
        },
        "counts": counts,
        "examples": examples,
        "interpretation": (
            "The current sanitizer rebuilds the description rather than copying provider prose, but it retains "
            "provider-controlled tool names and argument keys in the model-visible JSON. The alias-manifest "
            "prototype excludes these raw identifiers from its visible payload and keeps the reverse mapping "
            "server-side. This test does not assess model behaviour, indirect prompt injection, runtime calls or "
            "the adapter that must translate aliases back to provider identifiers."
        ),
    }
    out_dir = Path(os.environ.get("PAMCP_REVISION_RESULTS", ROOT / "results" / "revision_1"))
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "sanitiser_audit.json"
    path.write_text(json.dumps(result, indent=2) + "\\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()