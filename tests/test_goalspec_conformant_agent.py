from __future__ import annotations

from taas.studio.analyst_contract import (
    build_analyst_system_prompt,
    build_refinement_context,
    validate_theta_types,
)
from taas.studio import api


def _candidate(prompt_input: str = "text") -> dict:
    return {
        "prompt": "Calculate total value of all transactions",
        "prompt_inputs": [prompt_input],
        "goals": [{
            "id": "g1",
            "desc": "Retrieve transaction records and their numeric amount fields",
            "class": "retrieve",
            "in": ["query"],
            "out": "record:payment[]",
            "eff": ["read(db)"],
            "sigma": "data",
            "n": 1,
            "exactness": "exact",
            "deps": [],
            "optional": False,
        }],
    }


def test_theta_rejects_business_noun_as_prompt_input():
    assert "outside semantic vocabulary" in validate_theta_types(_candidate("transactions"))


def test_theta_rejects_undeclared_domain_even_when_syntax_is_valid():
    candidate = _candidate()
    candidate["goals"][0]["out"] = "record:transaction[]"
    assert "undeclared Θ domain" in validate_theta_types(candidate)


def test_theta_accepts_declared_domain_and_collection():
    assert validate_theta_types(_candidate("text")) is None


def test_analyst_prompt_makes_goal_contract_mandatory():
    prompt = build_analyst_system_prompt()
    assert "contract is mandatory" in prompt
    assert "Do not invent classes, fields, effects, domains" in prompt
    assert "summarise is not arithmetic" in prompt
    assert "n is only an estimate" in prompt
    assert "CANONICAL SEMANTIC VOCABULARY Θ" in prompt


def test_refinement_repeats_immutable_objective_and_diagnostics():
    objective = "Calculate the total value of all transactions"
    context = build_refinement_context(
        objective,
        '{"prompt_inputs":["transactions"]}',
        [{"code": "bad_type", "severity": "error", "message": "invalid Θ type"}],
    )
    assert objective in context
    assert '"transactions"' in context
    assert "do not narrow, reinterpret, or replace it" in context
    assert "severity" in context


def test_agent_decompose_performs_only_one_bounded_refinement(monkeypatch):
    class FakeRuntime:
        def __init__(self):
            self.calls = []

        def decompose(self, prompt, context="", max_new_tokens=1200):
            self.calls.append((prompt, context, max_new_tokens))
            spec = _candidate("transactions" if len(self.calls) == 1 else "text")
            return {
                "text": '{"candidate": true}',
                "goal_spec": spec,
                "json_valid": True,
                "parse_error": None,
                "semantic_diagnostics": [],
                "semantic_correctness_verified": False,
            }

    runtime = FakeRuntime()
    monkeypatch.setattr(api, "get_model_runtime", lambda: runtime)
    response = api.agent_decompose(api.AgentDecomposeRequest(
        prompt="Calculate the total value of all transactions",
        provider="huggingface",
    ))
    assert len(runtime.calls) == 2
    assert runtime.calls[0][0] == runtime.calls[1][0]
    assert "Original objective" in runtime.calls[1][1]
    assert response["conformance"]["attempts"] == 2
    assert response["conformance"]["accepted_for_human_review"] is True
    assert response["conformance"]["auto_applied"] is False
    assert response["conformance"]["semantic_correctness_verified"] is False


def test_agent_decompose_does_not_retry_after_second_failure(monkeypatch):
    class FakeRuntime:
        def __init__(self):
            self.calls = 0

        def decompose(self, prompt, context="", max_new_tokens=1200):
            self.calls += 1
            return {
                "text": "{}",
                "goal_spec": _candidate("transactions"),
                "json_valid": True,
                "parse_error": None,
                "semantic_diagnostics": [],
                "semantic_correctness_verified": False,
            }

    runtime = FakeRuntime()
    monkeypatch.setattr(api, "get_model_runtime", lambda: runtime)
    response = api.agent_decompose(api.AgentDecomposeRequest(
        prompt="Calculate the total value of all transactions",
        provider="huggingface",
    ))
    assert runtime.calls == 2
    assert response["conformance"]["attempts"] == 2
    assert response["conformance"]["accepted_for_human_review"] is False
    assert response["conformance"]["unresolved_errors"]
    assert response["conformance"]["auto_applied"] is False
