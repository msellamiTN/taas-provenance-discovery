import json

from taas.experiments.toolret_adapter import adapt_toolret_records


def test_toolret_adapter_uses_full_corpus_and_keeps_graded_qrels_separate(tmp_path):
    corpus = [
        {"id": "t1", "doc": {"name": "search", "description": "Search records",
                             "parameters": {"query": {"type": "string"}}}},
        {"id": "t2", "doc": {"name": "summarize", "description": "Summarize records",
                             "parameters": {}}},
        {"id": "t3", "doc": {"name": "translate", "description": "Translate text",
                             "parameters": {}}},
    ]
    tasks = [{
        "id": "q1", "query": "Search and summarize records",
        "labels": [{"id": "t1", "relevance": 2}, {"id": "t2", "relevance": 1}],
    }]
    manifest = adapt_toolret_records(tasks, corpus, tmp_path)
    discovery_tools = json.loads((tmp_path / "discovery" / "tools.json").read_text())
    discovery_tasks = json.loads((tmp_path / "discovery" / "tasks.json").read_text())
    references = json.loads((tmp_path / "evaluator" / "task_references.json").read_text())

    assert len(discovery_tools) == 3
    assert "labels" not in discovery_tasks[0]
    assert [x["relevance"] for x in references[0]["relevance_judgments"]] == [2, 1]
    assert manifest["counts"]["corpus_tools"] == 3


def test_toolret_adapter_rejects_qrel_outside_full_corpus(tmp_path):
    try:
        adapt_toolret_records(
            [{"id": "q1", "query": "Find a tool", "labels": [{"id": "missing"}]}],
            [{"id": "known", "doc": {"name": "known"}}],
            tmp_path,
        )
    except ValueError as exc:
        assert "absent from corpus" in str(exc)
    else:
        raise AssertionError("Expected missing qrel corpus document to fail")
