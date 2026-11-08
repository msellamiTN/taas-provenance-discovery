"""Run corrected E3 effects evaluation without requiring raw MCPToolBench++ source files.

This runner uses only the committed merged registry and the recorded, hash-pinned
label sets A and B. It does not execute MCP tools or servers.
"""
from __future__ import annotations

import sys

import fe
from e01_e03_registry_typing_effects import e3

LABEL_INPUTS = [
    "data/llm_records/silver_labels.json",
    "data/llm_records/reference_labels_opus_part0.jsonl",
    "data/llm_records/reference_labels_opus_part1.jsonl",
    "data/llm_records/reference_labels_opus_part2.jsonl",
]


def main() -> None:
    output = fe.RES / "E3_effects_tristate.json"
    if output.exists() and "--replace" not in sys.argv:
        raise SystemExit(
            f"Refusing to overwrite {output}; archive it first, then rerun with --replace."
        )

    result = e3()
    path = fe.save(
        "E3_effects_tristate",
        {"results": result},
        "LABELLED (LLM labels A/B); observed effects BLOCKED",
        inputs=LABEL_INPUTS,
        notes=(
            "Missing readOnlyHint values remain unknown. Confusion metrics are conditional on "
            "hint coverage; unknown unsafe/safe counts and full-reference unsafe capture are explicit. "
            "This is a dataset-only relabelling analysis, not observed server execution."
        ),
    )
    declared = result["declared_vs_B"]
    print(f"saved: {path}")
    print(f"registry tools: {result['n']}")
    print(f"reference unsafe (B): {result['reference_unsafe_B']}")
    print(
        "declared coverage:",
        f"{declared['n_evaluated']}/{declared['n_total']} ({declared['coverage']:.3%})",
    )
    print(
        "unknown unsafe/safe:",
        declared["unknown_unsafe"],
        declared["unknown_safe"],
    )
    print(
        "covered-only TP/FP/FN/TN:",
        declared["tp"],
        declared["fp"],
        declared["fn"],
        declared["tn"],
    )
    print(
        "unsafe reference coverage / capture:",
        declared["unsafe_reference_coverage"],
        declared["unsafe_capture_rate_all"],
    )
    print("manifest input hashes:", path)


if __name__ == "__main__":
    main()
