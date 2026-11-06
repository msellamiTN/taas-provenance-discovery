from __future__ import annotations

from taas.studio.model_runtime import parse_goal_spec_response


def test_goal_spec_parser_accepts_canonical_json():
    raw = """```json
    {"prompt":"Explain precision and recall","prompt_inputs":["text"],"goals":[
      {"id":"g1","class":"answer","in":["text"],"out":"text","eff":[],
       "sigma":"native","n":1,"exactness":"tolerant","deps":[],
       "desc":"Explain precision and recall","optional":false}
    ]}
    ```"""
    spec, error = parse_goal_spec_response(raw)
    assert error is None
    assert spec is not None
    assert spec["prompt"] == "Explain precision and recall"
    assert len(spec["goals"]) == 1


def test_goal_spec_parser_rejects_generic_id_query_context_wrapper():
    spec, error = parse_goal_spec_response(
        '{"id":"studio-agent","query":"Find papers","context":""}'
    )
    assert spec is None
    assert "canonical prompt_inputs/goals" in error


def test_goal_spec_parser_rejects_invalid_json_without_greedy_brace_capture():
    spec, error = parse_goal_spec_response('prefix {"prompt":"x","prompt_inputs":[} suffix')
    assert spec is None
    assert "Invalid JSON" in error


def test_goal_spec_parser_rejects_extra_top_level_fields():
    spec, error = parse_goal_spec_response(
        '{"prompt":"x","prompt_inputs":["text"],"goals":[],"debug":"leak"}'
    )
    assert spec is None
    assert "Unsupported top-level field" in error


def test_goal_spec_parser_rejects_trailing_second_object():
    spec, error = parse_goal_spec_response(
        '{"prompt":"x","prompt_inputs":["text"],"goals":[]} {"query":"other"}'
    )
    assert spec is None
    assert "Unexpected content follows" in error


def test_goal_spec_diagnostics_catch_summary_substituted_for_financial_sum():
    from taas.studio.model_runtime import diagnose_goal_spec

    proposal = {
        "prompt": "Calculate the total value of all transactions.",
        "goals": [
            {"id": "g1", "class": "retrieve", "in": ["query"],
             "out": "record:transaction[]", "n": 100, "desc": "Retrieve all transactions"},
            {"id": "g2", "class": "summarise", "in": ["record:transaction[]"],
             "out": "text", "deps": ["g1"], "desc": "Summarize transactions"},
        ],
    }
    diagnostics = diagnose_goal_spec(proposal["prompt"], proposal)
    codes = {item["code"] for item in diagnostics}
    assert "missing_aggregation" in codes
    assert "summary_substituted_for_calculation" in codes
    assert "scope_completeness_unproven" in codes
    assert "currency_policy_unspecified" in codes


def test_goal_spec_diagnostics_accept_explicit_exact_numeric_aggregation():
    from taas.studio.model_runtime import diagnose_goal_spec

    proposal = {
        "prompt": "Calculate the total value of all transactions.",
        "goals": [
            {"id": "g1", "class": "retrieve", "in": ["query"],
             "out": "record:transaction[]", "n": 100, "desc": "Retrieve all transactions"},
            {"id": "g2", "class": "aggregate", "in": ["record:transaction[]"],
             "out": "number", "deps": ["g1"], "exactness": "exact",
             "desc": "Sum transaction amounts"},
        ],
    }
    codes = {item["code"] for item in diagnose_goal_spec(proposal["prompt"], proposal)}
    assert "missing_aggregation" not in codes
    assert "aggregation_output_not_numeric" not in codes
    assert "aggregation_not_exact" not in codes
    assert "summary_substituted_for_calculation" not in codes
