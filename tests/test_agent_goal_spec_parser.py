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
