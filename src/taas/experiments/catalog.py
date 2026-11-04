"""PaMCP experiment catalog and variant integrity checks.

The runner never imports benchmark gold labels. Evaluation is a separate boundary.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
CATALOG_PATH = ROOT / "docs" / "experiment_design" / "pamcp_experiments_v1.json"


@dataclass(frozen=True)
class Variant:
    name: str
    G: int
    P: int
    S: int
    description: str


VARIANTS = {
    "Full_PaMCP": Variant("Full_PaMCP", 1, 1, 1,
        "Model-conditioned gap, provenance eligibility, set-level composition and certification."),
    "PaMCP_NoGap": Variant("PaMCP_NoGap", 0, 1, 1,
        "Delete model capability hyperedges; every subtask requires tools; preserve P and S."),
    "PaMCP_Declared": Variant("PaMCP_Declared", 1, 0, 1,
        "Metadata-only declared/lexical eligibility, no observed/attested evidence or trust policy; preserve G and S."),
    "PaMCP_NoCert": Variant("PaMCP_NoCert", 1, 1, 0,
        "Per-subgoal retrieval and union; disable backward closure, global set checks and certificate; preserve G and P."),
}

EXPECTED_FACTORIAL_NAMES = {
    (1, 1, 1): "Full_PaMCP",
    (0, 1, 1): "PaMCP_NoGap",
    (1, 0, 1): "PaMCP_Declared",
    (1, 1, 0): "PaMCP_NoCert",
    (1, 0, 0): "G1_P0_S0",
    (0, 1, 0): "G0_P1_S0",
    (0, 0, 1): "G0_P0_S1",
    (0, 0, 0): "G0_P0_S0",
}


def validate_factorial(data: dict[str, Any]) -> None:
    cells = data.get("factorial_design", {}).get("cells", [])
    got = {(x["G"], x["P"], x["S"]) for x in cells}
    if len(cells) != 8 or got != set(EXPECTED_FACTORIAL_NAMES):
        raise ValueError("Factorial cells are incomplete or duplicated")
    for cell in cells:
        key = (cell["G"], cell["P"], cell["S"])
        if cell.get("name") != EXPECTED_FACTORIAL_NAMES[key]:
            raise ValueError(f"Incorrect factorial variant label for {key}: {cell.get('name')}")


def load_catalog(path: Path = CATALOG_PATH) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != "1.0.0":
        raise ValueError("Unsupported experiment catalog schema")
    experiments = data.get("experiments")
    expected = [f"E{i}" for i in range(1, 23)]
    actual = [e.get("id") for e in experiments or []]
    if actual != expected:
        raise ValueError(f"Catalog must contain E1-E22 in order; got {actual}")
    if any(e.get("status") != "planned_not_run" for e in experiments):
        raise ValueError("New catalog entries must begin planned_not_run")
    validate_factorial(data)
    return data


def validate_variant(name: str, config: dict[str, Any]) -> Variant:
    if name not in VARIANTS:
        raise ValueError(f"Unknown PaMCP variant: {name}")
    expected = VARIANTS[name]
    factors = config.get("factors", {})
    observed = tuple(factors.get(k) for k in ("G", "P", "S"))
    wanted = (expected.G, expected.P, expected.S)
    if observed != wanted:
        raise ValueError(f"{name} factor mismatch: expected {wanted}, got {observed}")
    return expected
