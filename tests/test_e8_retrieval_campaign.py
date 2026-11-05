import json

import pytest

from taas.data.registries import RawTool, Task
import experiments.e8_retrieval_campaign as e8


def _tool(tool_id="source::search", category="web"):
    return {
        "tool_id": tool_id,
        "server_id": "source",
        "name": tool_id.split("::")[-1],
        "description": "Search records",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}},
        "output_schema": {},
        "annotations": {},
        "definition_hash": "a" * 64,
        "category": category,
    }


def _toolret_dir(root, include_label_in_discovery=False):
    (root / "discovery").mkdir(parents=True)
    (root / "evaluator").mkdir()
    tool = _tool()
    task = {"task_id": "q1", "prompt": "search a record", "category": "web"}
    if include_label_in_discovery:
        task["relevance_judgments"] = [{"tool_id": "source::search", "relevance": 1}]
    (root / "manifest.json").write_text(json.dumps({"dataset_id": "toolret"}))
    (root / "discovery" / "tools.json").write_text(json.dumps([tool]))
    (root / "discovery" / "tasks.json").write_text(json.dumps([task]))
    (root / "evaluator" / "task_references.json").write_text(json.dumps([
        {"task_id": "q1", "relevance_judgments": [{"tool_id": "source::search", "relevance": 2}]}
    ]))


def test_toolret_loader_keeps_discovery_and_evaluator_separate(tmp_path):
    _toolret_dir(tmp_path)
    track = e8.load_toolret_track(tmp_path)
    assert len(track.tools) == 1
    assert len(track.tasks) == 1
    assert track.tasks[0].query == "search a record"
    assert track.qrels == {"q1": {"source::search": 2.0}}
    assert track.exclusions["tasks_with_qrels"] == 1


def test_toolret_loader_rejects_qrels_leaked_into_discovery(tmp_path):
    _toolret_dir(tmp_path, include_label_in_discovery=True)
    with pytest.raises(ValueError, match="evaluator-only"):
        e8.load_toolret_track(tmp_path)


def test_toolret_loader_rejects_qrels_outside_full_corpus(tmp_path):
    _toolret_dir(tmp_path)
    refs = tmp_path / "evaluator" / "task_references.json"
    refs.write_text(json.dumps([
        {"task_id": "q1", "relevance_judgments": [{"tool_id": "not-in-corpus", "relevance": 1}]}
    ]))
    with pytest.raises(ValueError, match="outside the full corpus"):
        e8.load_toolret_track(tmp_path)


def test_mcp_toolbench_track_uses_only_single_resolved_target(monkeypatch):
    tools = [
        RawTool("s1", "search", "Search", {}, None, None, "MCPToolBench++", "web"),
        RawTool("s2", "write", "Write", {}, None, None, "MCPToolBench++", "web"),
    ]
    tasks = [
        Task("one", "search a record", "MCPToolBench++", "web", ["s1::search"], [], 1),
        Task("multi", "search and write", "MCPToolBench++", "web", ["s1::search", "s2::write"], [], 2),
        Task("unknown", "search unknown", "MCPToolBench++", "web", ["unknown::missing"], [], 1),
        Task("ambig", "search ambiguous", "MCPToolBench++", "web", ["s1::search|s2::search"], [], 1),
    ]
    monkeypatch.setattr(e8, "load_mcptoolbenchpp", lambda _: (tools, tasks))
    (tmp_path / "SOURCES.txt").write_text("MCPToolBenchPP test revision\\n")
    track = e8.load_mcptoolbenchpp_track(tmp_path)
    assert [x.task_id for x in track.tasks] == ["web::one"]
    assert track.qrels == {"web::one": {"s1::search": 1.0}}
    assert track.exclusions["not_single_gold_tool"] == 1
    assert track.exclusions["unresolved_or_ambiguous_gold"] == 2


def test_rank_scores_are_deterministic_under_ties():
    ids = ["tool-b", "tool-a", "tool-c"]
    import numpy as np
    assert e8._rank_scores(np.array([1.0, 1.0, 0.0]), ids) == ["tool-a", "tool-b", "tool-c"]


def test_paired_sign_flip_uses_exact_two_sided_test_for_small_n():
    result = e8._paired_sign_flip_pvalue({"a": 1.0, "b": 1.0}, {"a": 0.0, "b": 0.0}, None)
    assert result["method"] == "exact sign flip"
    assert result["n_independent_units"] == 2
    assert result["p_value_two_sided"] == pytest.approx(0.5)


def test_holm_adjustment_is_monotonic_and_bounded():
    rows = [
        {"p_value_raw": 0.03},
        {"p_value_raw": 0.01},
        {"p_value_raw": 0.02},
    ]
    e8._holm_adjust(rows)
    adjusted = [row["p_value_holm"] for row in rows]
    assert adjusted == pytest.approx([0.04, 0.03, 0.04])
    assert all(0 <= x <= 1 for x in adjusted)


def test_mcp_toolbench_cluster_mapping_uses_gold_server(monkeypatch, tmp_path):
    tools = [RawTool("provider-z", "lookup", "Lookup", {}, None, None, "MCPToolBench++", "search")]
    tasks = [Task("q", "lookup", "MCPToolBench++", "search", ["provider-z::lookup"], [], 1)]
    monkeypatch.setattr(e8, "load_mcptoolbenchpp", lambda _: (tools, tasks))
    (tmp_path / "SOURCES.txt").write_text("MCPToolBenchPP test revision\\n")
    track = e8.load_mcptoolbenchpp_track(tmp_path)
    assert track.cluster_by_task == {"search::q": "provider-z"}
