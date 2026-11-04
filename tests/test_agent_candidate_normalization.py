import pytest
from fastapi import HTTPException

from taas.studio.api import (
    canonicalize_declared_plural_types,
    prepare_agent_candidate,
    validate_studio_goal_spec,
)
from taas.studio.analyst_contract import build_analyst_system_prompt, build_refinement_context


def test_declared_plural_type_is_canonicalized_without_mutating_model_object():
    spec = {
        "prompt_inputs": ["text"],
        "goals": [{
            "id": "g1", "class": "retrieve", "desc": "Retrieve records",
            "in": ["query"], "out": "records[]", "deps": [],
        }],
    }
    normalized, events = canonicalize_declared_plural_types(spec)
    assert normalized["goals"][0]["out"] == "record[]"
    assert events[0]["from"] == "records[]"
    assert events[0]["to"] == "record[]"
    assert spec["goals"][0]["out"] == "records[]"


def test_undeclared_plural_type_is_not_guessed():
    spec = {
        "prompt_inputs": ["text"],
        "goals": [{
            "id": "g1", "class": "retrieve", "desc": "Retrieve widgets",
            "in": ["query"], "out": "widgets[]", "deps": [],
        }],
    }
    normalized, events = canonicalize_declared_plural_types(spec)
    assert normalized["goals"][0]["out"] == "widgets[]"
    assert events == []


def test_exact_user_objective_replaces_truncated_model_echo():
    objective = "Retrieve records matching the provided query from the configured source."
    candidate = {
        "text": "model raw output",
        "goal_spec": {
            "prompt": "Retrieve records matching the provided query from the configured sourc",
            "prompt_inputs": ["text"],
            "goals": [{
                "id": "g1", "class": "retrieve", "desc": "Retrieve records",
                "in": ["query"], "out": "records[]", "deps": [],
            }],
        },
    }
    prepared = prepare_agent_candidate(candidate, objective)
    assert prepared["goal_spec"]["prompt"] == objective
    assert prepared["objective_prompt_preserved"] is True
    assert prepared["normalization_events"][0]["to"] == "record[]"
    assert candidate["goal_spec"]["prompt"].endswith("sourc")


def _retrieval_goal_spec(effects):
    return {
        "prompt": "Retrieve records matching the provided query from the configured source.",
        "prompt_inputs": ["text"],
        "goals": [{
            "id": "retrieve_records",
            "desc": "Retrieve records matching the provided query from the configured source",
            "class": "retrieve",
            "in": ["query"],
            "out": "record[]",
            "eff": effects,
            "sigma": "data",
            "n": 100,
            "exactness": "tolerant",
            "deps": [],
            "lang": "en",
            "optional": False,
        }],
    }


def test_retrieval_effect_contract_accepts_read_without_internal_exec():
    validate_studio_goal_spec(_retrieval_goal_spec(["read(source)"]))


def test_execute_query_is_rejected_as_an_invalid_effect():
    with pytest.raises(HTTPException, match="invalid effect 'execute(query)'"):
        validate_studio_goal_spec(_retrieval_goal_spec(["read(source)", "execute(query)"]))


def test_analyst_prompt_and_refinement_explain_retrieval_effect_semantics():
    prompt = build_analyst_system_prompt()
    refinement = build_refinement_context(
        "Retrieve records matching the provided query from the configured source.",
        '{"eff":["execute(query)"]}',
        [{"code": "goalspec_structural_nonconformance", "severity": "error",
          "message": "invalid effect execute(query)"}],
    )
    for text in (prompt, refinement):
        assert "execute(query)" in text
        assert "read(source)" in text
        assert "backend implementation details" in text
