"""Audit the JA/JB unsafe-set relation; outputs are machine-label diagnostics, not ground truth."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments"))
import fe  # noqa: E402


def cohen_kappa(a: set[str], b: set[str], universe: set[str]) -> float:
    if not universe:
        return float("nan")
    n = len(universe)
    po = sum((x in a) == (x in b) for x in universe) / n
    pa, pb = len(a & universe) / n, len(b & universe) / n
    pe = pa * pb + (1.0 - pa) * (1.0 - pb)
    return 1.0 if pe == 1.0 and po == 1.0 else (po - pe) / (1.0 - pe) if pe < 1.0 else 0.0


def main() -> None:
    labels_a = fe.labels_A()
    labels_b = fe.labels_B()
    universe = set(labels_a) & set(labels_b)
    unsafe_a = {t for t in universe if labels_a[t].unsafe_read_only}
    unsafe_b = {t for t in universe if labels_b[t].unsafe_read_only}
    b_not_in_a = sorted(unsafe_b - unsafe_a)
    a_not_in_b = sorted(unsafe_a - unsafe_b)
    result = {
        "evidence_class": "LLM_LABEL_AUDIT_NOT_HUMAN_GROUND_TRUTH",
        "n_common_tools": len(universe),
        "unsafe_A": len(unsafe_a),
        "unsafe_B": len(unsafe_b),
        "intersection": len(unsafe_a & unsafe_b),
        "B_unsafe_not_in_A": b_not_in_a,
        "A_unsafe_not_in_B": a_not_in_b,
        "B_unsafe_subset_A_unsafe": not b_not_in_a,
        "cohen_kappa_binary_unsafe": cohen_kappa(unsafe_a, unsafe_b, universe),
        "interpretation": (
            "If B_unsafe_subset_A_unsafe is true, an error-free simulated verifier "
            "that admits exactly A-safe tools cannot admit a B-unsafe tool. Its zero "
            "false-admission result is therefore construction-dependent, not an "
            "independent empirical verifier-accuracy result."
        ),
    }
    out_dir = Path(os.environ.get("PAMCP_REVISION_RESULTS", ROOT / "results" / "revision_1"))
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "label_overlap_audit.json"
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()