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

CANARY = "PAMCPREV1INJECTIONCANARY"
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
        "current_name_canary_leaks": 0,
        "current_argument_key_canary_leaks": 0,
        "alias_manifest_canary_leaks": 0,
        "alias_binding_canary_occurrences_server_side": 0,
    }
    examples = []
    for contract in contracts:
        attacked = copy.deepcopy(contract)
        attacked.description = (attacked.description or "") + "\\n" + CANARY
        attacked.name = f"{CANARY}_{attacked.name}"
        attacked.args = tuple(replace(a, name=f"{CANARY}_{a.name}") for a in attacked.args)

        current = json.dumps(sanitise(attacked), sort_keys=True)
        if CANARY in (attacked.description or "") and CANARY in current:
            counts["current_description_canary_leaks"] += 1
        if CANARY in current:
            counts["current_name_canary_leaks"] += 1
        if CANARY in current:
            counts["current_argument_key_canary_leaks"] += 1

        visible, binding_map = alias_manifest([attacked])
        visible_json = json.dumps(visible, sort_keys=True)
        binding_json = json.dumps(binding_map, sort_keys=True)
        if CANARY in visible_json:
            counts["alias_manifest_canary_leaks"] += 1
        if CANARY in binding_json:
            counts["alias_binding_canary_occurrences_server_side"] += 1
        if len(examples) < 3:
            examples.append({
                "tool_id": contract.tool,
                "current_manifest_name": sanitise(attacked)["name"],
                "current_manifest_has_canary": CANARY in current,
                "alias_manifest_has_canary": CANARY in visible_json,
            })

    result = {
        "evidence_class": "LOCAL_TRANSFORMATION_TEST_NOT_RUNTIME_ATTACK_EVALUATION",
        "canary": CANARY,
        "counts": counts,
        "examples": examples,
        "interpretation": (
            "The current sanitizer reconstructs descriptions from contract fields, but provider-controlled "
            "tool names and argument keys remain in the model-visible JSON. The alias-manifest prototype "
            "keeps the reverse mapping server-side and excludes those raw identifiers from the visible payload. "
            "This test does not assess model behaviour, indirect prompt injection, runtime calls or the adapter."
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