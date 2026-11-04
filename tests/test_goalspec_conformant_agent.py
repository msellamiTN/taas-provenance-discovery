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


def _conformant_candidate() -> dict:
    return {
        "prompt": "Calculate the total value of all transactions",
        "prompt_inputs": ["text"],
        "goals": [{
            "id": "g1", "desc": "Retrieve all matching transaction records from the source identified during Discovery",
            "class": "retrieve", "in": ["query"], "out": "record[]",
            "eff": ["read(db)"], "sigma": "data", "n": 1,
            "exactness": "exact", "deps": [], "optional": False,
        }, {
            "id": "g2", "desc": "Calculate the exact sum of the amount/value field for every retrieved record",
            "class": "aggregate", "in": ["record[]"], "out": "number",
            "eff": [], "sigma": "unreliable", "n": 1,
            "exactness": "exact", "deps": ["g1"], "optional": False,
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
            spec = _candidate("transactions") if len(self.calls) == 1 else _conformant_candidate()
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
    assert response["core_analysis"]["status"] == "capability_gap_detected"
    assert response["core_analysis"]["goal_order"] == ["g1", "g2"]
    assert response["objective_contract"]["operation"] == "aggregate"
    assert len(response["attempt_history"]) == 2


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


def test_total_objective_requires_aggregation_and_preserves_all_scope():
    from taas.studio.model_runtime import diagnose_goal_spec

    candidate = {
        "goals": [{
            "id": "g1", "class": "retrieve", "desc": "Retrieve all transactions",
            "in": ["query"], "out": "record:payment[]", "n": 100,
        }, {
            "id": "g2", "class": "summarise", "desc": "Summarise retrieved transactions",
            "in": ["record:payment[]"], "out": "text", "n": 1,
        }],
    }
    codes = {item["code"] for item in diagnose_goal_spec(
        "Calculate the total value of all transactions", candidate
    )}
    assert "missing_aggregation" in codes
    assert "summary_substituted_for_calculation" in codes
    assert "scope_completeness_unproven" in codes


def test_count_objective_requires_count_goal():
    from taas.studio.model_runtime import diagnose_goal_spec

    candidate = {"goals": [{"id": "g1", "class": "summarise", "out": "text"}]}
    diagnostics = diagnose_goal_spec("How many orders were created?", candidate)
    assert any(item["code"] == "missing_count" and item["severity"] == "error"
               for item in diagnostics)


def test_valid_aggregate_still_surfaces_missing_currency_policy():
    from taas.studio.model_runtime import diagnose_goal_spec

    candidate = {"goals": [{
        "id": "g1", "class": "aggregate", "desc": "Sum transaction amount",
        "in": ["record:payment[]"], "out": "number", "exactness": "exact",
    }]}
    diagnostics = diagnose_goal_spec("Calculate the total value of all payments", candidate)
    assert any(item["code"] == "currency_policy_unspecified" for item in diagnostics)


def test_objective_contract_derives_operation_scope_and_unmapped_domain():
    from taas.studio.objective_contract import derive_objective_contract

    frame = derive_objective_contract("Calculate the total value of all transactions")
    assert frame["operation"] == "aggregate"
    assert frame["required_goal_classes"] == ["aggregate"]
    assert frame["numeric_result_required"] is True
    assert frame["exactness_required"] == "exact"
    assert frame["scope"]["all_matching_items"] is True
    assert "transaction" in frame["unresolved_business_concepts"]
    assert "currency_policy" in frame["ambiguities"]


def test_objective_alignment_rejects_summary_without_data_and_aggregation():
    from taas.studio.objective_contract import diagnose_objective_alignment

    diagnostics = diagnose_objective_alignment(
        "Calculate the total value of all transactions",
        {"prompt_inputs": ["text"], "goals": [{
            "id": "g1", "class": "summarise", "desc": "Summarise transactions",
            "in": ["text"], "out": "text", "deps": [],
        }]},
    )
    codes = {item["code"] for item in diagnostics}
    assert "objective_operation_missing" in codes
    assert "objective_data_source_missing" in codes


def test_objective_alignment_requires_complete_scope_and_connected_aggregation():
    from taas.studio.objective_contract import diagnose_objective_alignment

    spec = {
        "prompt_inputs": ["text"],
        "goals": [{
            "id": "g1", "class": "retrieve", "desc": "Retrieve recent transactions",
            "in": ["query"], "out": "record[]", "deps": [],
        }, {
            "id": "g2", "class": "aggregate", "desc": "Sum amount",
            "in": ["record[]"], "out": "number", "exactness": "exact", "deps": [],
        }],
    }
    codes = {item["code"] for item in diagnose_objective_alignment(
        "Calculate the total value of all transactions", spec
    )}
    assert "objective_dataflow_disconnected" in codes
    assert "objective_scope_not_preserved" in codes


def test_objective_alignment_accepts_connected_all_scope_plan_with_warnings_only():
    from taas.studio.objective_contract import diagnose_objective_alignment

    spec = _conformant_candidate()
    diagnostics = diagnose_objective_alignment(
        "Calculate the total value of all transactions", spec
    )
    assert not [item for item in diagnostics if item["severity"] == "error"]
    assert any(item["code"] == "objective_concept_not_mapped_to_theta" for item in diagnostics)


def test_compute_exact_is_valid_aggregate_operation_alternative():
    from taas.studio.objective_contract import diagnose_objective_alignment

    spec = _conformant_candidate()
    spec["goals"][1]["class"] = "compute_exact"
    diagnostics = diagnose_objective_alignment(
        "Calculate the total value of all transactions", spec
    )
    assert not [item for item in diagnostics if item["severity"] == "error"]
