from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "experiments" / "colab" / "e1_registry_characterization.py"
SPEC = importlib.util.spec_from_file_location("e1_registry_characterization", RUNNER_PATH)
assert SPEC and SPEC.loader
E1 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(E1)


def _fixture(root: Path, *, status: str = "planned_not_run") -> None:
    (root / "data" / "processed").mkdir(parents=True)
    (root / "data" / "raw").mkdir(parents=True)
    (root / "docs" / "experiment_design").mkdir(parents=True)
    tool = {
        "server": "srv-a",
        "name": "read_rows",
        "description": "Read rows from a table",
        "input_schema": {
            "type": "object",
            "properties": {"table": {"type": "string"}},
            "required": ["table"],
        },
        "output_schema": {"type": "array", "items": {"type": "object"}},
        "annotations": {"readOnlyHint": True, "destructiveHint": False},
        "source": "fixture-source-a",
        "category": "database",
        "extra": None,
    }
    tool["id"] = "srv-a::read_rows"
    tool["hash"] = E1.canonical_definition_hash(tool)
    second = {
        "server": "srv-b",
        "name": "write_rows",
        "description": "",
        "input_schema": {},
        "output_schema": None,
        "annotations": None,
        "source": "fixture-source-b",
        "category": "other",
        "extra": None,
        "id": "srv-b::write_rows",
    }
    (root / "data" / "processed" / "registry_merged.json").write_text(
        json.dumps({"registry": [tool, second]}), encoding="utf-8"
    )
    (root / "data" / "raw" / "SOURCES.txt").write_text(
        "fixture-source-a revision-a\nfixture-source-b revision-b\n", encoding="utf-8"
    )
    (root / "docs" / "experiment_design" / "pamcp_experiments_v1.json").write_text(
        json.dumps({
            "experiments": [{
                "id": "E1",
                "title": "Registry characterization",
                "status": status,
            }]
        }),
        encoding="utf-8",
    )


def test_e1_writes_frozen_inputs_summary_tables_and_manifest(tmp_path: Path):
    _fixture(tmp_path)
    run_dir = E1.run_e1(tmp_path, tmp_path / "runs", run_id="synthetic-e1")
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    manifest = json.loads((run_dir / "MANIFEST.json").read_text(encoding="utf-8"))

    assert summary["registry"]["tool_rows"] == 2
    assert summary["metadata_completeness"]["published_hash_mismatches"] == 0
    assert summary["guardrails"]["silver_labels_read"] is False
    assert summary["guardrails"]["task_gold_labels_read"] is False
    assert manifest["experiment"]["catalog_status_before_run"] == "planned_not_run"
    assert (run_dir / "category_by_source.csv").is_file()
    assert (run_dir / "annotation_hint_distribution.csv").is_file()
    assert (run_dir / "category_by_source.png").is_file()

    frozen = run_dir / "inputs" / "registry_merged.json.gz"
    with gzip.open(frozen, "rb") as stream:
        original = stream.read()
    source_path = tmp_path / "data" / "processed" / "registry_merged.json"
    assert hashlib.sha256(original).hexdigest() == hashlib.sha256(source_path.read_bytes()).hexdigest()
    assert manifest["inputs"]["registry_sha256"] == hashlib.sha256(source_path.read_bytes()).hexdigest()


def test_e1_refuses_to_run_if_catalog_status_is_not_planned(tmp_path: Path):
    _fixture(tmp_path, status="completed")
    with pytest.raises(ValueError, match="planned_not_run"):
        E1.run_e1(tmp_path, tmp_path / "runs", run_id="must-not-run")


def test_e1_does_not_overwrite_an_existing_run_directory(tmp_path: Path):
    _fixture(tmp_path)
    E1.run_e1(tmp_path, tmp_path / "runs", run_id="fixed-run")
    with pytest.raises(FileExistsError):
        E1.run_e1(tmp_path, tmp_path / "runs", run_id="fixed-run")
