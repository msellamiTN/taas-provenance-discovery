"""Reconcile independent E1 effect annotations without auto-adjudication.

The script freezes raw inter-annotator agreement, creates an adjudication
worklist for disagreements, and emits a reference-label JSON only when every
source definition has a final human decision. It never reads LLM silver labels.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sklearn.metrics import cohen_kappa_score


def read_csv(path: Path, required: set[str]) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = set(reader.fieldnames or [])
        missing = required - fields
        if missing:
            raise ValueError(f"{path.name}: missing columns {sorted(missing)}")
        rows = list(reader)
    if not rows:
        raise ValueError(f"{path.name}: no annotation rows")
    return rows


def parse_bool(value: str, field: str, unit: str) -> bool:
    normalized = (value or "").strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    raise ValueError(f"{unit}: {field} must be true/false; got {value!r}")


def digest_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def unique_index(rows: list[dict[str, str]], field: str, source: str) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        key = (row.get(field) or "").strip()
        if not key:
            raise ValueError(f"{source}: empty {field}")
        if key in result:
            raise ValueError(f"{source}: duplicate {field} {key}")
        result[key] = row
    return result


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def reconcile(
    annotator_a_path: str | Path,
    annotator_b_path: str | Path,
    mapping_path: str | Path,
    output_dir: str | Path,
    annotator_a_id: str,
    annotator_b_id: str,
    adjudicated_path: str | Path | None = None,
    adjudicator_id: str | None = None,
    adjudication_rule: str | None = None,
) -> Path:
    a_path, b_path, map_path = map(Path, (annotator_a_path, annotator_b_path, mapping_path))
    out = Path(output_dir)
    if out.exists():
        raise FileExistsError(f"Refusing to overwrite reconciliation directory: {out}")
    if not annotator_a_id.strip() or not annotator_b_id.strip() or annotator_a_id == annotator_b_id:
        raise ValueError("Provide two distinct non-empty annotator IDs")

    required_ann = {"annotation_unit_id", "non_read_only", "effect_classes", "confidence_0_1", "rationale"}
    a_rows = read_csv(a_path, required_ann)
    b_rows = read_csv(b_path, required_ann)
    mapping = read_csv(map_path, {"annotation_unit_id", "tool_id", "definition_hash", "registry_views"})
    a = unique_index(a_rows, "annotation_unit_id", "annotator A")
    b = unique_index(b_rows, "annotation_unit_id", "annotator B")
    m = unique_index(mapping, "annotation_unit_id", "restricted mapping")
    if set(a) != set(b):
        raise ValueError(f"Annotator coverage differs: A-only={len(set(a)-set(b))}, B-only={len(set(b)-set(a))}")
    if set(a) != set(m):
        raise ValueError(f"Annotation/mapping coverage differs: missing mapping={len(set(a)-set(m))}, extra mapping={len(set(m)-set(a))}")

    labels_a: list[bool] = []
    labels_b: list[bool] = []
    combined: list[dict[str, Any]] = []
    for unit_id in sorted(a):
        ar, br, mr = a[unit_id], b[unit_id], m[unit_id]
        tool_id = (mr.get("tool_id") or "").strip()
        definition_hash = (mr.get("definition_hash") or "").strip().lower()
        if not tool_id or len(definition_hash) != 64 or any(ch not in "0123456789abcdef" for ch in definition_hash):
            raise ValueError(f"{unit_id}: mapping needs tool_id and full SHA-256 definition_hash")
        if (ar.get("tool_name") or "").strip() != (br.get("tool_name") or "").strip():
            raise ValueError(f"{unit_id}: annotators have mismatched tool_name context")
        av = parse_bool(ar.get("non_read_only", ""), "non_read_only", unit_id)
        bv = parse_bool(br.get("non_read_only", ""), "non_read_only", unit_id)
        for source, row in (("A", ar), ("B", br)):
            try:
                confidence = float(row.get("confidence_0_1", ""))
            except ValueError as exc:
                raise ValueError(f"{unit_id}: annotator {source} confidence must be numeric") from exc
            if not 0.0 <= confidence <= 1.0:
                raise ValueError(f"{unit_id}: annotator {source} confidence must be in [0,1]")
            if not (row.get("rationale") or "").strip():
                raise ValueError(f"{unit_id}: annotator {source} rationale is required")
        labels_a.append(av)
        labels_b.append(bv)
        combined.append({
            "annotation_unit_id": unit_id,
            "tool_id": tool_id,
            "definition_hash": definition_hash,
            "registry_views": mr.get("registry_views", ""),
            "tool_name": ar.get("tool_name", ""),
            "annotator_a_non_read_only": av,
            "annotator_b_non_read_only": bv,
            "agreement": av == bv,
            "annotator_a_effect_classes": ar.get("effect_classes", ""),
            "annotator_b_effect_classes": br.get("effect_classes", ""),
            "annotator_a_rationale": ar.get("rationale", ""),
            "annotator_b_rationale": br.get("rationale", ""),
        })

    kapp = cohen_kappa_score(labels_a, labels_b)
    kapp_value = None if math.isnan(float(kapp)) else float(kapp)
    agree_n = sum(1 for row in combined if row["agreement"])
    disagree_n = len(combined) - agree_n

    out.mkdir(parents=True)
    disagreement_rows = [row for row in combined if not row["agreement"]]
    _write_csv(
        out / "disagreements.csv", disagreement_rows,
        list(combined[0]) if combined else [],
    )

    adjudication_fields = [
        "annotation_unit_id", "tool_id", "definition_hash", "tool_name",
        "annotator_a_non_read_only", "annotator_b_non_read_only",
        "adjudicated_non_read_only", "adjudicator_rationale",
    ]
    adjudication_template = []
    for row in combined:
        adjudication_template.append({
            "annotation_unit_id": row["annotation_unit_id"],
            "tool_id": row["tool_id"],
            "definition_hash": row["definition_hash"],
            "tool_name": row["tool_name"],
            "annotator_a_non_read_only": str(row["annotator_a_non_read_only"]).lower(),
            "annotator_b_non_read_only": str(row["annotator_b_non_read_only"]).lower(),
            "adjudicated_non_read_only": "",
            "adjudicator_rationale": "",
        })
    _write_csv(out / "adjudication_template.csv", adjudication_template, adjudication_fields)

    final_labels: dict[str, bool] | None = None
    adjudication_metadata: dict[str, Any] | None = None
    if disagree_n == 0:
        final_labels = {
            row["annotation_unit_id"]: row["annotator_a_non_read_only"]
            for row in combined
        }
        decision_rule = "unanimous_independent_annotator_agreement"
    elif adjudicated_path is not None:
        if not adjudicator_id or not adjudication_rule:
            raise ValueError("Adjudicator ID and frozen adjudication rule are required with adjudicated CSV")
        adjud_rows = read_csv(
            Path(adjudicated_path),
            {"annotation_unit_id", "adjudicated_non_read_only", "adjudicator_rationale"},
        )
        adjud = unique_index(adjud_rows, "annotation_unit_id", "adjudication file")
        if set(adjud) != set(a):
            raise ValueError("Adjudication file must cover every annotation unit exactly once")
        final_labels = {}
        for row in combined:
            unit = row["annotation_unit_id"]
            decision = parse_bool(adjud[unit].get("adjudicated_non_read_only", ""), "adjudicated_non_read_only", unit)
            rationale = (adjud[unit].get("adjudicator_rationale") or "").strip()
            if row["agreement"] and decision != row["annotator_a_non_read_only"] and not rationale:
                raise ValueError(f"{unit}: overriding annotator agreement requires rationale")
            if not row["agreement"] and not rationale:
                raise ValueError(f"{unit}: resolving disagreement requires adjudicator rationale")
            final_labels[unit] = decision
        decision_rule = "human_adjudicated"
        adjudication_metadata = {
            "adjudicator_id": adjudicator_id,
            "rule": adjudication_rule,
            "adjudicated_csv_sha256": digest_file(Path(adjudicated_path)),
        }

    agreement = {
        "annotator_a_id": annotator_a_id,
        "annotator_b_id": annotator_b_id,
        "annotation_units": len(combined),
        "agreement_count": agree_n,
        "disagreement_count": disagree_n,
        "raw_cohen_kappa": kapp_value,
        "raw_agreement_rate": agree_n / len(combined),
        "interpretation": "computed before adjudication; no disagreements are automatically resolved",
    }
    (out / "agreement.json").write_text(json.dumps(agreement, indent=2) + "\n", encoding="utf-8")

    if final_labels is not None:
        by_unit = {row["annotation_unit_id"]: row for row in combined}
        label_rows = []
        for unit, value in sorted(final_labels.items()):
            row = by_unit[unit]
            label_rows.append({
                "tool_id": row["tool_id"],
                "definition_hash": row["definition_hash"],
                "non_read_only": value,
            })
        # A tool definition can appear in multiple registry views but only one unique
        # tool_id + definition_hash key is admissible in the merged reference set.
        keys = [(r["tool_id"], r["definition_hash"]) for r in label_rows]
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate tool_id + definition_hash keys; resolve mapping before export")
        label_document = {
            "schema_version": "1.0.0",
            "label_source": "independent_human_reference",
            "independent_of_silver_labels": True,
            "generated_by_model": False,
            "annotation_method": "two_independent_human_annotators",
            "annotators": [annotator_a_id, annotator_b_id],
            "agreement": agreement,
            "decision_rule": decision_rule,
            "adjudication": adjudication_metadata,
            "labels": label_rows,
        }
        (out / "reference_labels.json").write_text(
            json.dumps(label_document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    manifest = {
        "artifact_kind": "E1_reference_annotation_reconciliation",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "ready_for_adjudication" if disagree_n else "reference_labels_ready",
        "source_hashes": {
            "annotator_a_sha256": digest_file(a_path),
            "annotator_b_sha256": digest_file(b_path),
            "restricted_mapping_sha256": digest_file(map_path),
            "adjudicated_csv_sha256": digest_file(Path(adjudicated_path)) if adjudicated_path else None,
        },
        "agreement": agreement,
        "decision_rule": "human_adjudicated" if adjudicated_path else ("unanimous_independent_annotator_agreement" if not disagree_n else None),
        "reference_labels_emitted": final_labels is not None,
        "reference_label_count": len(final_labels) if final_labels is not None else 0,
        "silver_labels_read": False,
        "model_predictions_read": False,
        "mcp_servers_executed": False,
    }
    (out / "RECONCILIATION_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    checks = {
        p.name: digest_file(p)
        for p in sorted(out.iterdir()) if p.is_file() and p.name != "SHA256SUMS.json"
    }
    (out / "SHA256SUMS.json").write_text(json.dumps(checks, indent=2) + "\n", encoding="utf-8")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconcile two blinded E1 reference annotation CSVs")
    parser.add_argument("--annotator-a", required=True)
    parser.add_argument("--annotator-b", required=True)
    parser.add_argument("--mapping", required=True, help="Restricted owner-only join mapping")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--annotator-a-id", required=True)
    parser.add_argument("--annotator-b-id", required=True)
    parser.add_argument("--adjudicated-csv")
    parser.add_argument("--adjudicator-id")
    parser.add_argument("--adjudication-rule")
    args = parser.parse_args()
    result = reconcile(
        args.annotator_a, args.annotator_b, args.mapping, args.output_dir,
        args.annotator_a_id, args.annotator_b_id,
        args.adjudicated_csv, args.adjudicator_id, args.adjudication_rule,
    )
    manifest = json.loads((result / "RECONCILIATION_MANIFEST.json").read_text())
    print(json.dumps({
        "status": manifest["status"],
        "agreement": manifest["agreement"],
        "reference_labels_emitted": manifest["reference_labels_emitted"],
        "output_dir": str(result),
    }, indent=2))


if __name__ == "__main__":
    main()
