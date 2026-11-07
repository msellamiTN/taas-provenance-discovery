"""Validate independent E1 annotation CSVs and report pre-adjudication agreement.

This utility never edits source sheets or adjudicates labels. It accepts only completed
binary labels under the approved E1 annotation guide.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

REQUIRED = {"annotation_unit_id", "tool_name", "non_read_only",
            "effect_classes", "confidence_0_1", "rationale"}
ALLOWED_EFFECTS = {"read", "write", "delete", "exec", "egress", "money", "session"}


class AnnotationValidationError(ValueError):
    """An annotation sheet violates the approved E1 intake contract."""


def load_sheet(path: str | Path, annotator: str) -> dict[str, dict[str, str]]:
    path = Path(path)
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if not reader.fieldnames:
                raise AnnotationValidationError(f"{annotator}: missing CSV header")
            missing = REQUIRED - set(reader.fieldnames)
            if missing:
                raise AnnotationValidationError(f"{annotator}: missing columns: {sorted(missing)}")
            rows: dict[str, dict[str, str]] = {}
            for line, raw in enumerate(reader, start=2):
                row = {k: (v or "").strip() for k, v in raw.items() if k is not None}
                unit = row.get("annotation_unit_id", "")
                if not unit:
                    raise AnnotationValidationError(f"{annotator}: blank annotation_unit_id at line {line}")
                if unit in rows:
                    raise AnnotationValidationError(f"{annotator}: duplicate annotation_unit_id {unit!r}")
                if row.get("non_read_only", "").lower() not in {"true", "false"}:
                    raise AnnotationValidationError(
                        f"{annotator}: non_read_only must be true/false for {unit!r}")
                effects = [x.strip().lower() for x in row.get("effect_classes", "").split(",") if x.strip()]
                if not effects or len(effects) != len(set(effects)) or set(effects) - ALLOWED_EFFECTS:
                    raise AnnotationValidationError(f"{annotator}: invalid effect_classes for {unit!r}")
                try:
                    confidence = float(row.get("confidence_0_1", ""))
                except ValueError as exc:
                    raise AnnotationValidationError(f"{annotator}: invalid confidence for {unit!r}") from exc
                if not math.isfinite(confidence) or not 0 <= confidence <= 1:
                    raise AnnotationValidationError(f"{annotator}: confidence outside [0,1] for {unit!r}")
                rationale = row.get("rationale", "")
                if len(rationale) < 12 or not row.get("tool_name", ""):
                    raise AnnotationValidationError(f"{annotator}: missing/insufficient rationale or tool_name for {unit!r}")
                row["_label"] = row["non_read_only"].lower()
                rows[unit] = row
    except UnicodeDecodeError as exc:
        raise AnnotationValidationError(f"{annotator}: CSV is not valid UTF-8") from exc
    return rows


def cohens_kappa(labels_a: list[str], labels_b: list[str]) -> float | None:
    """Return Cohen's kappa; None when expected agreement is one (degenerate)."""
    if not labels_a or len(labels_a) != len(labels_b):
        raise ValueError("Paired labels must be non-empty and equal length")
    n = len(labels_a)
    a, b = Counter(labels_a), Counter(labels_b)
    observed = sum(x == y for x, y in zip(labels_a, labels_b)) / n
    expected = sum((a[c] / n) * (b[c] / n) for c in ("true", "false"))
    if math.isclose(1.0 - expected, 0.0, abs_tol=1e-12):
        return None
    return (observed - expected) / (1.0 - expected)


def validate_pair(path_a: str | Path, path_b: str | Path) -> dict[str, Any]:
    a, b = load_sheet(path_a, "A"), load_sheet(path_b, "B")
    ids_a, ids_b = set(a), set(b)
    if ids_a != ids_b:
        only_a, only_b = sorted(ids_a - ids_b), sorted(ids_b - ids_a)
        raise AnnotationValidationError(
            f"Annotator unit sets differ (A-only={len(only_a)}, B-only={len(only_b)}); "
            f"A-only sample={only_a[:5]}, B-only sample={only_b[:5]}")
    for unit in sorted(ids_a):
        if a[unit].get("tool_name") != b[unit].get("tool_name"):
            raise AnnotationValidationError(f"tool_name context mismatch for {unit!r}")
    units = sorted(ids_a)
    la = [a[u]["_label"] for u in units]
    lb = [b[u]["_label"] for u in units]
    disagreements = [{"annotation_unit_id": u, "tool_name": a[u]["tool_name"],
                      "annotator_a": a[u]["_label"], "annotator_b": b[u]["_label"]}
                     for u in units if a[u]["_label"] != b[u]["_label"]]
    counts_a, counts_b = Counter(la), Counter(lb)
    return {
        "status": "validated_pre_adjudication",
        "n_units": len(units),
        "raw_agreement": sum(x == y for x, y in zip(la, lb)) / len(units),
        "cohens_kappa": cohens_kappa(la, lb),
        "kappa_status": "undefined_degenerate_marginals" if cohens_kappa(la, lb) is None else "defined",
        "annotator_a_counts": {k: counts_a.get(k, 0) for k in ("true", "false")},
        "annotator_b_counts": {k: counts_b.get(k, 0) for k in ("true", "false")},
        "disagreement_count": len(disagreements),
        "disagreements": disagreements,
        "adjudication_performed": False,
        "source_sheets_modified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate paired PaMCP E1 annotation sheets")
    parser.add_argument("annotator_a")
    parser.add_argument("annotator_b")
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--disagreements-out", type=Path)
    args = parser.parse_args()
    report = validate_pair(args.annotator_a, args.annotator_b)
    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(rendered)
    if args.json_out:
        args.json_out.write_text(rendered + "\\n", encoding="utf-8")
    if args.disagreements_out:
        fields = ["annotation_unit_id", "tool_name", "annotator_a", "annotator_b"]
        with args.disagreements_out.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(report["disagreements"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
