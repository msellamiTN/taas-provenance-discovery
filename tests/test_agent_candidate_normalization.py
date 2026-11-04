from taas.studio.api import canonicalize_declared_plural_types, prepare_agent_candidate


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
