#!/usr/bin/env python3
"""E3 synthetic trace-fixture harness.

This is a software-validation fixture generator, NOT an MCP server probe and NOT
empirical E3 evidence. It creates deterministic event records, applies a small
transparent event-to-effect adapter, and checks that expected fixture labels
are recovered. Never merge these outputs into definitive E3 results.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

EFFECTS = (
    "read", "write", "delete", "exec", "egress",
    "financial", "permission_change", "unknown",
)

# Fixture events are abstract evidence records, not OS/network observations.
FIXTURES = [
    ("FX-READ", ["data_read"], ["read"]),
    ("FX-WRITE", ["state_created"], ["write"]),
    ("FX-DELETE", ["state_removed"], ["delete"]),
    ("FX-EXEC", ["process_started"], ["exec"]),
    ("FX-EGRESS", ["controlled_destination_send"], ["egress"]),
    ("FX-FINANCIAL", ["mock_payment_ledger_entry"], ["financial"]),
    ("FX-PERMISSION", ["acl_changed"], ["permission_change"]),
    ("FX-UNKNOWN", ["insufficient_evidence"], ["unknown"]),
    ("FX-READ-EGRESS", ["data_read", "controlled_destination_send"], ["read", "egress"]),
    ("FX-WRITE-EXEC", ["state_created", "process_started"], ["write", "exec"]),
    ("FX-DELETE-PERMISSION", ["state_removed", "acl_changed"], ["delete", "permission_change"]),
    ("FX-READ-UNKNOWN", ["data_read", "insufficient_evidence"], ["read", "unknown"]),
]

EVENT_TO_EFFECT = {
    "data_read": "read",
    "state_created": "write",
    "state_modified": "write",
    "state_removed": "delete",
    "process_started": "exec",
    "controlled_destination_send": "egress",
    "mock_payment_ledger_entry": "financial",
    "acl_changed": "permission_change",
    "insufficient_evidence": "unknown",
}

def infer_effects(events: list[str]) -> list[str]:
    """Transparent fixture adapter; no model inference or live observation."""
    found = {EVENT_TO_EFFECT[e] for e in events if e in EVENT_TO_EFFECT}
    if not found:
        found.add("unknown")
    return sorted(found, key=EFFECTS.index)

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def run(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for fixture_id, events, expected in FIXTURES:
        inferred = infer_effects(events)
        rows.append({
            "fixture_id": fixture_id,
            "event_types": "|".join(events),
            "expected_effects": "|".join(expected),
            "adapter_effects": "|".join(inferred),
            "exact_match": str(sorted(expected, key=EFFECTS.index) == inferred).lower(),
            "evidence_kind": "synthetic_fixture",
            "empirical_observation": "false",
        })

    failures = [r for r in rows if r["exact_match"] != "true"]
    with (output / "e3_simulated_trace_fixtures.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    counts = Counter()
    for row in rows:
        for label in row["expected_effects"].split("|"):
            counts[label] += 1

    # A coverage chart of fixture cases, not a performance/accuracy chart.
    bars = []
    max_count = max(counts.values())
    for i, effect in enumerate(EFFECTS):
        value = counts[effect]
        y = 42 + i * 34
        width = round(420 * value / max_count) if max_count else 0
        bars.append(
            f'<text x="12" y="{y+16}" font-size="13">{effect}</text>'
            f'<rect x="150" y="{y}" width="{width}" height="22" fill="#64748b"/>'
            f'<text x="{160+width}" y="{y+16}" font-size="12">{value}</text>'
        )
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="650" height="340" viewBox="0 0 650 340">'
        '<rect width="100%" height="100%" fill="white"/>'
        '<text x="12" y="22" font-size="16" font-weight="bold">E3 synthetic fixture coverage</text>'
        '<text x="12" y="36" font-size="10" fill="#b91c1c">SIMULATION ONLY — NOT EMPIRICAL TOOL EFFECTS</text>'
        + "".join(bars) +
        '<text x="12" y="326" font-size="10" fill="#475569">Count = fixture cases containing the effect; cases may be multi-label.</text>'
        '</svg>'
    )
    (output / "e3_synthetic_fixture_coverage.svg").write_text(svg, encoding="utf-8")

    manifest = {
        "experiment": "E3",
        "artifact_type": "synthetic_fixture_validation",
        "status": "software_validation_only",
        "empirical_evidence": False,
        "live_mcp_calls": 0,
        "sandbox_used": False,
        "seed": None,
        "fixture_count": len(rows),
        "fixture_exact_matches": len(rows) - len(failures),
        "fixture_failures": [r["fixture_id"] for r in failures],
        "effect_fixture_coverage": {k: counts[k] for k in EFFECTS},
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "limitations": [
            "No MCP server was started or invoked.",
            "No filesystem, database, process, network, payment, or ACL event was observed.",
            "Event records are hand-authored synthetic fixtures.",
            "The adapter is a deterministic fixture parser, not an E3 baseline or classifier.",
            "These artifacts must never be promoted to definitive E3 results.",
        ],
    }
    manifest_path = output / "e3_simulation_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    manifest["artifact_sha256"] = {
        p.name: sha256(p) for p in sorted(output.iterdir()) if p.is_file() and p != manifest_path
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    if failures:
        raise SystemExit(f"E3 fixture validation failed: {[r['fixture_id'] for r in failures]}")
    return manifest

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/e3_simulation"))
    args = parser.parse_args()
    result = run(args.output)
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
