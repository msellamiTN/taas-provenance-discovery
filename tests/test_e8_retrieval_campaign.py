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


def test_mcp_toolbench_track_uses_only_single_resolved_target(monkeypatch, tmp_path):
    tools = [
        RawTool("s1", "search", "Search", {}, None, None, "MCPToolBench++", "web"),
        RawTool("s2", "write", "Write", {}, None, None, "MCPToolBench++", "web"),
        RawTool("s2", "find", "Find", {}, None, None, "MCPToolBench++", "web"),
    ]
    tasks = [
        Task("one", "search a record", "MCPToolBench++", "web", ["s1::search"], [], 1),
        Task("multi", "search and write", "MCPToolBench++", "web", ["s1::search", "s2::write"], [], 2),
        Task("unknown", "search unknown", "MCPToolBench++", "web", ["unknown::missing"], [], 1),
        Task("ambig", "search ambiguous", "MCPToolBench++", "web", ["s1::search|s2::search"], [], 1),
    ]
    monkeypatch.setattr(e8, "load_mcptoolbenchpp", lambda _: (tools, tasks))
    (tmp_path / "SOURCES.txt").write_text("MCPToolBenchPP test revision\\n")
    raw_category = tmp_path / "mcptoolbenchpp"
    raw_category.mkdir()
    (raw_category / "web.json").write_text(json.dumps([{
        "uuid": "one", "mcp_tools_dict": {"s1": ["search"], "s2": ["find"]},
        "function_call_label": [{
            "name": "search", "mcp_server": "s1",
            "similar_tools": [{"name": "find", "mcp_server": "s2"}],
        }],
    }]))
    track = e8.load_mcptoolbenchpp_track(tmp_path)
    assert [x.task_id for x in track.tasks] == ["web::one"]
    assert track.qrels == {"web::one": {"s1::search": 1.0}}
    assert track.secondary_qrels == {"web::one": {"s1::search": 1.0, "s2::find": 1.0}}
    assert track.exclusions["similar_tools_total"] == 1
    assert track.exclusions["similar_tools_resolved"] == 1
    assert track.exclusions["not_single_gold_tool"] == 1
    assert track.exclusions["unresolved_or_ambiguous_gold"] == 2


def test_rank_scores_are_deterministic_under_ties():
    ids = ["tool-b", "tool-a", "tool-c"]
    import numpy as np
    scores = np.array([1.0, 1.0, 0.0])
    assert e8._rank_scores(scores, ids) == ["tool-a", "tool-b", "tool-c"]
    assert e8._rank_scores(scores, ids, top_k=1) == ["tool-a"]
    assert e8._rank_scores(scores, ids, top_k=2) == ["tool-a", "tool-b"]
    assert e8._rank_scores(scores, ids, top_k=0) == []


def test_random_baseline_is_task_stable_and_top_k_bounded():
    docs = [e8.ToolDocument(f"tool::{i}", f"tool {i}", "c", "s") for i in range(100)]
    tasks = [e8.DiscoveryTask("q1", "find one", "c"), e8.DiscoveryTask("q2", "find two", "c")]
    first = e8._random_rankings(docs, tasks, 5, 123)
    second = e8._random_rankings(docs, tasks, 5, 123)
    assert first == second
    assert all(len(values) == 5 and len(set(values)) == 5 for values in first.values())
    assert first["q1"] != first["q2"]


def test_lsa_query_scoring_can_be_chunked():
    docs = [
        e8.ToolDocument("s::a", "search customer records by name", "c", "s"),
        e8.ToolDocument("s::b", "write customer record", "c", "s"),
        e8.ToolDocument("s::c", "delete customer record", "c", "s"),
        e8.ToolDocument("s::d", "read invoice document", "c", "s"),
    ]
    tasks = [
        e8.DiscoveryTask("q1", "search customer", "c"),
        e8.DiscoveryTask("q2", "read invoice", "c"),
        e8.DiscoveryTask("q3", "write customer", "c"),
    ]
    whole = e8._lsa_rankings(docs, tasks, 2, dimension=2, query_chunk_size=10)
    chunked = e8._lsa_rankings(docs, tasks, 2, dimension=2, query_chunk_size=1)
    assert chunked == whole


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
    raw_category = tmp_path / "mcptoolbenchpp"
    raw_category.mkdir()
    (raw_category / "search.json").write_text(json.dumps([{
        "uuid": "q", "mcp_tools_dict": {"provider-z": ["lookup"]},
        "function_call_label": [{"name": "lookup", "mcp_server": "provider-z", "similar_tools": []}],
    }]))
    track = e8.load_mcptoolbenchpp_track(tmp_path)
    assert track.cluster_by_task == {"search::q": "provider-z"}


def test_mcp_toolbench_similar_tools_are_sensitivity_only(tmp_path):
    task = e8.DiscoveryTask("web::q", "search a record", "web")
    primary = {"web::q": {"s1::search": 1.0}}
    secondary = {"web::q": {"s1::search": 1.0, "s2::find": 1.0}}
    track = e8.DatasetTrack(
        "mcptoolbenchpp_single_target",
        [task],
        [
            e8.ToolDocument("s1::search", "search", "web", "s1"),
            e8.ToolDocument("s2::find", "find", "web", "s2"),
        ],
        primary,
        {"web::q": "s1"},
        {},
        {},
        secondary,
    )
    rankings = {"test_ranker": {"web::q": ["s2::find"]}}
    result = e8.evaluate_track(track, rankings, {}, tmp_path)
    primary_hit = result["metrics"]["test_ranker"]["metrics"]["overall"]["metrics"]["1"]["hit@1"]["value"]
    sensitivity_hit = result["similar_tools_sensitivity_metrics"]["test_ranker"]["metrics"]["1"]["hit@1"]["value"]
    assert primary_hit == 0.0
    assert sensitivity_hit == 1.0


def _cross_encoder_fixture():
    docs = [
        e8.ToolDocument("s::a", "search document", "c", "s"),
        e8.ToolDocument("s::b", "lookup record", "c", "s"),
    ]
    tasks = [
        e8.DiscoveryTask(f"q{i}", f"query {i}", "c")
        for i in range(5)
    ]
    candidates = {task.task_id: ["s::a", "s::b"] for task in tasks}
    return docs, tasks, candidates


def test_cross_encoder_checkpoints_resume_completed_task_batches(tmp_path):
    import numpy as np

    docs, tasks, candidates = _cross_encoder_fixture()

    class InterruptingReranker:
        def __init__(self):
            self.calls = 0

        def predict(self, pairs, batch_size=64, show_progress_bar=False):
            self.calls += 1
            if self.calls == 2:
                raise RuntimeError("simulated Colab interruption")
            return np.arange(len(pairs), dtype=float)

    interrupted = InterruptingReranker()
    checkpoint_dir = tmp_path / "cross_encoder_batches"
    with pytest.raises(RuntimeError, match="simulated Colab interruption"):
        e8._cross_encoder_rankings(
            docs, tasks, candidates, interrupted, 1,
            checkpoint_dir=checkpoint_dir,
            checkpoint_key="fixture-v1",
            task_chunk_size=2,
        )

    assert interrupted.calls == 2
    assert (checkpoint_dir / "batch_00000.json").is_file()
    assert not (checkpoint_dir / "batch_00001.json").exists()

    class CountingReranker:
        def __init__(self):
            self.calls = 0

        def predict(self, pairs, batch_size=64, show_progress_bar=False):
            self.calls += 1
            return np.arange(len(pairs), dtype=float)

    resumed = CountingReranker()
    stats = {}
    rankings = e8._cross_encoder_rankings(
        docs, tasks, candidates, resumed, 1,
        checkpoint_dir=checkpoint_dir,
        checkpoint_key="fixture-v1",
        task_chunk_size=2,
        checkpoint_stats=stats,
    )

    assert set(rankings) == {task.task_id for task in tasks}
    assert resumed.calls == 2  # The first of three batches was restored.
    assert stats == {
        "task_chunk_size": 2,
        "total_batches": 3,
        "reused_batches": 1,
        "computed_batches": 2,
        "checkpoint_dir": str(checkpoint_dir),
    }

    no_work = CountingReranker()
    all_cached_stats = {}
    cached_rankings = e8._cross_encoder_rankings(
        docs, tasks, candidates, no_work, 1,
        checkpoint_dir=checkpoint_dir,
        checkpoint_key="fixture-v1",
        task_chunk_size=2,
        checkpoint_stats=all_cached_stats,
    )
    assert cached_rankings == rankings
    assert no_work.calls == 0
    assert all_cached_stats["reused_batches"] == 3
    assert all_cached_stats["computed_batches"] == 0


def test_cross_encoder_checkpoint_rejects_fingerprint_mismatch(tmp_path):
    import numpy as np

    docs, tasks, candidates = _cross_encoder_fixture()

    class Reranker:
        def predict(self, pairs, batch_size=64, show_progress_bar=False):
            return np.arange(len(pairs), dtype=float)

    checkpoint_dir = tmp_path / "cross_encoder_batches"
    e8._cross_encoder_rankings(
        docs, tasks, candidates, Reranker(), 1,
        checkpoint_dir=checkpoint_dir,
        checkpoint_key="fixture-v1",
        task_chunk_size=2,
    )
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        e8._cross_encoder_rankings(
            docs, tasks, candidates, Reranker(), 1,
            checkpoint_dir=checkpoint_dir,
            checkpoint_key="fixture-v2",
            task_chunk_size=2,
        )
