import csv
import json

from taas.experiments.mcpverse_adapter import adapt_mcpverse_csv


def test_mcpverse_adapter_keeps_tool_labels_and_answers_out_of_discovery(tmp_path):
    source = tmp_path / "mcpverse.csv"
    with source.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=[
            "question_id", "question", "MCP", "tool", "complexity", "answer",
            "eval_method", "time-sensitive",
        ])
        writer.writeheader()
        writer.writerow({
            "question_id": "Q1", "question": "Find a station",
            "MCP": "maps", "tool": "search_station", "complexity": "L1",
            "answer": "Central station", "eval_method": "llm_as_a_judge",
            "time-sensitive": "No",
        })
    manifest = adapt_mcpverse_csv(source, tmp_path / "out")
    task = json.loads((tmp_path / "out/discovery/tasks.json").read_text())[0]
    ref = json.loads((tmp_path / "out/evaluator/task_references.json").read_text())[0]
    assert "annotated_tool_id" not in task
    assert "reference_answer" not in task
    assert ref["annotated_tool_id"] == "maps::search_station"
    assert ref["native_eval_method"] == "llm_as_a_judge"
    assert manifest["limitations"]


def test_mcpverse_adapter_rejects_missing_required_columns(tmp_path):
    source = tmp_path / "bad.csv"
    source.write_text("question_id,question\nQ1,hello\n", encoding="utf-8")
    try:
        adapt_mcpverse_csv(source, tmp_path / "out")
    except ValueError as exc:
        assert "missing columns" in str(exc)
    else:
        raise AssertionError("Expected invalid MCPVerse CSV to fail")
