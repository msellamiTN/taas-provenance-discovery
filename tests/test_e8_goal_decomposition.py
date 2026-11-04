"""Tests for E8 prompt-to-GoalSpec semantic scoring."""
from experiments.e8_goal_decomposition import CASES, score_case


def test_bitcoin_report_rubric_requires_retrieval_reasoning_and_file_effect():
    case = CASES[0]
    good = {
        "goals": [
            {"id": "g1", "class": "search", "out": "record:market[]", "eff": ["egress(web)"], "desc": "Find current Bitcoin market information", "deps": []},
            {"id": "g2", "class": "summarise", "out": "text", "eff": [], "desc": "Write the Bitcoin market report", "deps": ["g1"]},
            {"id": "g3", "class": "create_document", "out": "path:file", "eff": ["write(fs)"], "desc": "Save Markdown report to /root/markdown/bitcoin.md", "deps": ["g2"]},
        ]
    }
    result = score_case(case, good)
    assert result["goal_recall"] == 1.0
    assert result["goal_precision"] == 1.0
    assert result["dag_valid"] is True
    assert result["dependency_valid"] is True
    assert result["missing_prompt_literals"] == []
    assert result["forbidden_effects"] == []


def test_missing_required_goal_reduces_recall():
    case = CASES[0]
    output = {"goals": [
        {"id": "g1", "class": "search", "out": "record:market[]", "eff": ["egress(web)"], "desc": "Find Bitcoin market", "deps": []},
    ]}
    result = score_case(case, output)
    assert result["goal_recall"] < 1.0


def test_semantic_scorer_flags_unauthorised_side_effect():
    case = CASES[4]
    output = {"goals": [
        {"id": "g1", "class": "answer", "out": "text", "eff": ["egress(web)"], "desc": "Explain precision recall example", "deps": []},
    ]}
    result = score_case(case, output)
    assert result["forbidden_effects"]


def test_semantic_scorer_rejects_dependency_cycles():
    case = CASES[4]
    output = {"goals": [
        {"id": "g1", "class": "answer", "out": "text", "eff": [], "desc": "Explain precision recall example", "deps": ["g2"]},
        {"id": "g2", "class": "write", "out": "text", "eff": [], "desc": "Explain example", "deps": ["g1"]},
    ]}
    result = score_case(case, output)
    assert result["dag_valid"] is False
