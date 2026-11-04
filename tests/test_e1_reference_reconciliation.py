import csv
import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "experiments/e1/reconcile_reference_annotations.py"
SPEC = importlib.util.spec_from_file_location("e1_reconcile", SCRIPT)
assert SPEC and SPEC.loader
RECON = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RECON)


def write_rows(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def fixture(tmp_path: Path, a_labels: list[str], b_labels: list[str]):
    ids = [f"unit-{i}" for i in range(len(a_labels))]
    ann_fields = ["annotation_unit_id", "tool_name", "non_read_only", "effect_classes", "confidence_0_1", "rationale"]
    a = [{"annotation_unit_id": unit, "tool_name": f"tool{i}", "non_read_only": a_labels[i],
          "effect_classes": "read", "confidence_0_1": "0.9", "rationale": "checked source"} for i, unit in enumerate(ids)]
    b = [{"annotation_unit_id": unit, "tool_name": f"tool{i}", "non_read_only": b_labels[i],
          "effect_classes": "read", "confidence_0_1": "0.8", "rationale": "checked docs"} for i, unit in enumerate(ids)]
    mapping = [{"annotation_unit_id": unit, "tool_id": f"srv::tool{i}",
                "definition_hash": f"{i:064x}", "registry_views": "merged"} for i, unit in enumerate(ids)]
    write_rows(tmp_path / "A.csv", a, ann_fields)
    write_rows(tmp_path / "B.csv", b, ann_fields)
    write_rows(tmp_path / "map.csv", mapping, ["annotation_unit_id", "tool_id", "definition_hash", "registry_views"])
    return tmp_path / "A.csv", tmp_path / "B.csv", tmp_path / "map.csv"


def test_unanimous_independent_annotations_emit_reference_json(tmp_path):
    a, b, m = fixture(tmp_path, ["false", "true", "false"], ["false", "true", "false"])
    out = RECON.reconcile(a, b, m, tmp_path / "out", "annotator-A", "annotator-B")
    ref = json.loads((out / "reference_labels.json").read_text())
    report = json.loads((out / "agreement.json").read_text())
    assert len(ref["labels"]) == 3
    assert ref["decision_rule"] == "unanimous_independent_annotator_agreement"
    assert report["raw_agreement_rate"] == 1.0
    assert json.loads((out / "RECONCILIATION_MANIFEST.json").read_text())["silver_labels_read"] is False


def test_disagreements_do_not_auto_emit_reference_labels(tmp_path):
    a, b, m = fixture(tmp_path, ["false", "true"], ["true", "true"])
    out = RECON.reconcile(a, b, m, tmp_path / "out", "A", "B")
    assert not (out / "reference_labels.json").exists()
    assert len(list(csv.DictReader((out / "disagreements.csv").open()))) == 1
    assert len(list(csv.DictReader((out / "adjudication_template.csv").open()))) == 2
    manifest = json.loads((out / "RECONCILIATION_MANIFEST.json").read_text())
    assert manifest["status"] == "ready_for_adjudication"


def test_adjudication_requires_rationale_and_complete_coverage(tmp_path):
    a, b, m = fixture(tmp_path, ["false", "true"], ["true", "true"])
    adjud = tmp_path / "adjudicated.csv"
    fields = ["annotation_unit_id", "adjudicated_non_read_only", "adjudicator_rationale"]
    write_rows(adjud, [
        {"annotation_unit_id": "unit-0", "adjudicated_non_read_only": "false", "adjudicator_rationale": ""},
        {"annotation_unit_id": "unit-1", "adjudicated_non_read_only": "true", "adjudicator_rationale": ""},
    ], fields)
    with pytest.raises(ValueError, match="rationale"):
        RECON.reconcile(a, b, m, tmp_path / "out", "A", "B", adjud, "C", "review both evidence sources")


def test_mismatched_annotation_unit_coverage_is_rejected(tmp_path):
    a, b, m = fixture(tmp_path, ["false", "true"], ["false", "true"])
    with (tmp_path / "B.csv").open("w", encoding="utf-8", newline="") as f:
        f.write("annotation_unit_id,tool_name,non_read_only,effect_classes,confidence_0_1,rationale\nunit-x,t,false,read,0.9,ok\n")
    with pytest.raises(ValueError, match="Annotator coverage differs"):
        RECON.reconcile(a, b, m, tmp_path / "out", "A", "B")
