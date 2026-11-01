from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.create_semantic_annotation_workpacks import build_workpacks
from taas.data.registries import RawTool


def _registry(path: Path):
    tool = RawTool(
        server="demo",
        name="lookup",
        description="Search public records by identifier.",
        input_schema={
            "type": "object",
            "properties": {"identifier": {"type": "string"}},
            "required": ["identifier"],
        },
        output_schema={"type": "object"},
        annotations={"readOnlyHint": True},
        source="unit-test",
        category="records",
    )
    payload = {
        "registry": [{
            "server": tool.server,
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.input_schema,
            "output_schema": tool.output_schema,
            "annotations": tool.annotations,
            "source": tool.source,
            "category": tool.category,
            "extra": None,
        }],
        # Deliberately present: the generator must ignore all benchmark task material.
        "tasks_livemcpbench": [{"query": "LEAK-ME", "gold_tools": ["demo::lookup"]}],
        "tasks_mcptoolbenchpp": [{"query": "LEAK-ME-TOO", "gold_tools": ["demo::lookup"]}],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return tool


def test_workpacks_are_two_perspectives_and_do_not_include_gold_tasks(tmp_path):
    registry = tmp_path / "registry.json"
    tool = _registry(registry)
    out = tmp_path / "workpacks"
    manifest = build_workpacks(registry, out, workers=4)

    assert manifest["n_tools"] == 1
    assert manifest["n_annotation_tasks"] == 2
    assert manifest["leakage_controls"]["benchmark_task_queries_loaded"] is False
    rows = []
    for shard in sorted(out.glob("worker_*.jsonl")):
        rows.extend(json.loads(line) for line in shard.read_text().splitlines() if line)
    assert {row["perspective"] for row in rows} == {
        "capability_semantics", "operational_security"
    }
    assert all(row["tool_id"] == tool.id for row in rows)
    serialized = "\n".join(json.dumps(row) for row in rows)
    assert "LEAK-ME" not in serialized
    assert all(row["definition_hash"] == tool.definition_hash() for row in rows)


def test_workpack_builder_refuses_to_overwrite(tmp_path):
    registry = tmp_path / "registry.json"
    _registry(registry)
    out = tmp_path / "existing"
    out.mkdir()
    (out / "keep.txt").write_text("preserve")
    with pytest.raises(FileExistsError):
        build_workpacks(registry, out, workers=2)
    assert (out / "keep.txt").read_text() == "preserve"
