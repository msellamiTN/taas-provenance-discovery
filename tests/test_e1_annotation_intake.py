import csv
import pytest

from experiments.e1.validate_annotation_pair import (
    AnnotationValidationError, cohens_kappa, load_sheet, validate_pair,
)


FIELDS = ["annotation_unit_id", "tool_name", "description", "input_schema_json",
          "non_read_only", "effect_classes", "confidence_0_1", "rationale"]


def write_sheet(path, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def row(unit, label="false", name="tool", effects="read"):
    return {"annotation_unit_id": unit, "tool_name": name, "description": "desc",
            "input_schema_json": "{}", "non_read_only": label, "effect_classes": effects,
            "confidence_0_1": "0.9", "rationale": "The documented operation only reads data."}


def test_valid_pair_reports_agreement_without_adjudicating(tmp_path):
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    write_sheet(a, [row("u1"), row("u2", "true", effects="write")])
    write_sheet(b, [row("u2", "true", effects="write"), row("u1")])
    result = validate_pair(a, b)
    assert result["n_units"] == 2
    assert result["raw_agreement"] == 1
    assert result["cohens_kappa"] == 1
    assert result["disagreement_count"] == 0
    assert result["adjudication_performed"] is False
    assert result["source_sheets_modified"] is False


def test_disagreement_is_reported_not_resolved(tmp_path):
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    write_sheet(a, [row("u1", "true", effects="write")])
    write_sheet(b, [row("u1", "false")])
    result = validate_pair(a, b)
    assert result["disagreement_count"] == 1
    assert result["disagreements"][0]["annotation_unit_id"] == "u1"


def test_rejects_duplicate_ids(tmp_path):
    p = tmp_path / "a.csv"
    write_sheet(p, [row("u1"), row("u1")])
    with pytest.raises(AnnotationValidationError, match="duplicate"):
        load_sheet(p, "A")


def test_rejects_missing_annotation(tmp_path):
    p = tmp_path / "a.csv"
    r = row("u1")
    r["non_read_only"] = ""
    write_sheet(p, [r])
    with pytest.raises(AnnotationValidationError, match="true/false"):
        load_sheet(p, "A")


def test_rejects_invalid_effect_and_confidence(tmp_path):
    p = tmp_path / "a.csv"
    r = row("u1", effects="read,magic")
    write_sheet(p, [r])
    with pytest.raises(AnnotationValidationError, match="effect_classes"):
        load_sheet(p, "A")
    r = row("u1")
    r["confidence_0_1"] = "1.1"
    write_sheet(p, [r])
    with pytest.raises(AnnotationValidationError, match="confidence"):
        load_sheet(p, "A")


def test_rejects_different_unit_sets_and_context(tmp_path):
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    write_sheet(a, [row("u1")])
    write_sheet(b, [row("u2")])
    with pytest.raises(AnnotationValidationError, match="unit sets differ"):
        validate_pair(a, b)
    write_sheet(b, [row("u1", name="different")])
    with pytest.raises(AnnotationValidationError, match="context mismatch"):
        validate_pair(a, b)


def test_kappa_is_undefined_for_degenerate_marginals():
    assert cohens_kappa(["true", "true"], ["true", "true"]) is None


def test_kappa_known_example():
    assert cohens_kappa(["true", "false"], ["true", "true"]) == pytest.approx(0.0)
