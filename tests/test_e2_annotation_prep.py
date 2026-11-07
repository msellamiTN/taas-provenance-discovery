import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "experiments/e2/prepare_annotation_tasks.py"
SPEC = importlib.util.spec_from_file_location("e2_prepare", SCRIPT)
assert SPEC and SPEC.loader
E2 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(E2)


def fixture_registry(path: Path):
    rows = []
    for i in range(12):
        rows.append({
            "id": f"server-{i % 3}::tool-{i}",
            "server": f"server-{i % 3}",
            "name": f"tool_{i}",
            "description": f"Tool {i} description",
            "input_schema": {
                "type": "object",
                "properties": {"record_id": {"type": "string", "description": "Record id"},
                               "limit": {"type": "integer"}},
                "required": ["record_id"],
            },
            "output_schema": {"type": "array", "items": {"type": "object"}} if i % 2 else None,
            "source": "source-a" if i % 2 else "source-b",
            "category": "database" if i % 3 else "search",
        })
    path.write_text(json.dumps({"registry": rows}), encoding="utf-8")


def test_prepare_generates_two_independent_blank_annotation_sheets(tmp_path):
    registry = tmp_path / "registry.json"
    fixture_registry(registry)
    out = E2.prepare_annotation_tasks(registry, tmp_path / "out", 8, 17, "simple_random")
    import csv
    with (out / "annotator_A.csv").open(encoding="utf-8", newline="") as f:
        a = list(csv.DictReader(f))
    with (out / "annotator_B.csv").open(encoding="utf-8", newline="") as f:
        b = list(csv.DictReader(f))
    assert len(a) == len(b) == 8 * 3
    assert {x["annotation_unit_id"] for x in a} == {x["annotation_unit_id"] for x in b}
    assert all(x["type_kind"] == "" and x["confidence_0_1"] == "" for x in a + b)
    assert [x["annotation_unit_id"] for x in a] != [x["annotation_unit_id"] for x in b]
    manifest = json.loads((out / "sample_manifest.json").read_text())
    assert manifest["status"] == "prepared_not_run"
    assert manifest["llm_silver_labels_used_as_gold"] is False
    assert (out / "restricted_mapping.csv").is_file()


def test_stratified_sample_requires_room_for_each_nonempty_stratum(tmp_path):
    registry = tmp_path / "registry.json"
    fixture_registry(registry)
    with pytest.raises(ValueError, match="one per non-empty"):
        E2.prepare_annotation_tasks(registry, tmp_path / "out", 2, 17,
                                    "stratified_source_category")


def test_annotation_package_refuses_overwrite(tmp_path):
    registry = tmp_path / "registry.json"
    fixture_registry(registry)
    out = E2.prepare_annotation_tasks(registry, tmp_path / "out", 4, 17, "simple_random")
    with pytest.raises(FileExistsError):
        E2.prepare_annotation_tasks(registry, out, 4, 17, "simple_random")


def test_sample_size_is_bounded(tmp_path):
    registry = tmp_path / "registry.json"
    fixture_registry(registry)
    with pytest.raises(ValueError, match="exceeds registry size"):
        E2.prepare_annotation_tasks(registry, tmp_path / "out", 99, 17, "simple_random")
