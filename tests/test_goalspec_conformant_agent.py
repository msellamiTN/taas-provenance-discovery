from __future__ import annotations

import pytest

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
            "class": "retrieve", "eff": ["read(*)"],
            "in": ["query"],
            "out": "record[]",
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
            "class": "retrieve", "eff": ["read(*)"], "in": ["query"], "out": "record[]",
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
            "id": "g1", "class": "retrieve", "eff": ["read(*)"], "desc": "Retrieve all transactions",
            "in": ["query"], "out": "record[]", "n": 100,
        }, {
            "id": "g2", "class": "summarise", "desc": "Summarise retrieved transactions",
            "in": ["record[]"], "out": "text", "n": 1,
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
        "in": ["record[]"], "out": "number", "exactness": "exact",
    }]}
    diagnostics = diagnose_goal_spec("Calculate the total value of all payments", candidate)
    assert any(item["code"] == "currency_policy_unspecified" for item in diagnostics)


def test_objective_contract_derives_operation_scope_and_unmapped_domain():
    from taas.studio.objective_contract import derive_objective_contract

    frame = derive_objective_contract("Calculate the total value of all transactions")
    assert frame["operation"] == "aggregate"
    assert frame["required_goal_classes"] == ["retrieve", "aggregate"]
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
            "id": "g1", "class": "retrieve", "eff": ["read(*)"], "desc": "Retrieve recent transactions",
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


def test_this_year_is_preserved_as_an_explicit_temporal_constraint():
    from taas.studio.objective_contract import derive_objective_contract

    frame = derive_objective_contract("Count all invoices issued this year.")
    assert frame["scope"]["all_matching_items"] is True
    assert frame["scope"]["date_or_range_constraint"] is True
    assert frame["temporal_scope"]["expression"] == "this_year"
    assert frame["temporal_scope"]["anchor_required"] is True
    assert frame["temporal_scope"]["business_timezone_required"] is True
    assert "thi" not in frame["unresolved_business_concepts"]
    assert "year" not in frame["unresolved_business_concepts"]
    assert "issued" not in frame["unresolved_business_concepts"]


def test_relative_year_can_be_anchored_without_guessing_timezone():
    from taas.studio.objective_contract import derive_objective_contract

    frame = derive_objective_contract(
        "Count all invoices issued this year.", reference_date="2026-11-04"
    )
    assert frame["temporal_scope"]["reference_date"] == "2026-11-04"
    assert frame["temporal_scope"]["anchor_required"] is False
    assert frame["temporal_scope"]["business_timezone_required"] is True
    assert frame["temporal_scope"]["resolution_status"] == "anchored_not_materialized"


def test_currency_policy_is_not_required_for_invoice_count():
    from taas.studio.objective_contract import derive_objective_contract

    frame = derive_objective_contract("Count all invoices issued this year.")
    assert frame["operation"] == "count"
    assert "currency_policy" not in frame["ambiguities"]


def test_currency_policy_remains_required_for_monetary_invoice_aggregation():
    from taas.studio.objective_contract import derive_objective_contract

    frame = derive_objective_contract("Calculate the total value of all invoices.")
    assert frame["operation"] == "aggregate"
    assert "currency_policy" in frame["ambiguities"]


def test_count_alignment_requires_numeric_exact_result_and_retrieval_dependency():
    from taas.studio.objective_contract import diagnose_objective_alignment

    objective = "Count all invoices issued this year."
    bad = {
        "prompt_inputs": ["text"],
        "goals": [
            {"id": "g1", "class": "retrieve", "eff": ["read(*)"], "desc": "Retrieve all invoices issued this year",
             "in": ["query"], "out": "record[]", "deps": [], "n": 100},
            {"id": "g2", "class": "count", "desc": "Count retrieved invoices",
             "in": ["record[]"], "out": "text", "exactness": "tolerant", "deps": ["g1"]},
        ],
    }
    codes = {item["code"] for item in diagnose_objective_alignment(objective, bad)}
    assert "objective_numeric_output_missing" in codes
    assert "objective_exactness_not_preserved" in codes
    assert "objective_temporal_field_unresolved" in codes
    assert "objective_dataflow_disconnected" not in codes


def test_count_alignment_accepts_exact_connected_temporal_plan():
    from taas.studio.objective_contract import diagnose_objective_alignment

    objective = "Count all invoices issued this year."
    spec = {
        "prompt_inputs": ["text"],
        "goals": [
            {"id": "g1", "class": "retrieve", "eff": ["read(*)"], "desc": "Retrieve all invoices issued this year",
             "in": ["query"], "out": "record[]", "deps": [], "n": 100},
            {"id": "g2", "class": "count", "desc": "Count invoice records exactly",
             "in": ["record[]"], "out": "number", "exactness": "exact", "deps": ["g1"]},
        ],
    }
    diagnostics = diagnose_objective_alignment(objective, spec)
    assert not [item for item in diagnostics if item["severity"] == "error"]
    assert any(item["code"] == "objective_temporal_field_unresolved" for item in diagnostics)


def test_model_runtime_does_not_request_currency_policy_for_counting_invoices():
    from taas.studio.model_runtime import diagnose_goal_spec

    spec = {"goals": [{"id": "g1", "class": "count", "desc": "Count invoices",
                       "out": "number", "exactness": "exact"}]}
    codes = {item["code"] for item in diagnose_goal_spec(
        "Count all invoices issued this year.", spec
    )}
    assert "currency_policy_unspecified" not in codes
    assert "count_not_exact" not in codes
    assert "missing_count" not in codes


def test_model_runtime_rejects_approximate_or_non_numeric_count():
    from taas.studio.model_runtime import diagnose_goal_spec

    spec = {"goals": [{"id": "g1", "class": "count", "desc": "Count invoices",
                       "out": "text", "exactness": "tolerant"}]}
    codes = {item["code"] for item in diagnose_goal_spec(
        "Count all invoices issued this year.", spec
    )}
    assert "count_output_not_numeric" in codes
    assert "count_not_exact" in codes


def test_studio_explains_that_invoice_domain_is_not_a_prompt_input_type():
    import pytest
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        api.validate_studio_goal_spec(_candidate("invoice"))
    assert "domain label 'invoice'" in str(exc.value.detail)
    assert "or 'text' for a natural-language prompt input" in str(exc.value.detail)


def test_finite_n_is_not_treated_as_complete_for_all_count_objectives():
    from taas.studio.model_runtime import diagnose_goal_spec

    spec = {"goals": [
        {"id": "g1", "class": "retrieve", "eff": ["read(*)"], "desc": "Retrieve all invoices issued this year",
         "out": "record[]", "n": 100},
        {"id": "g2", "class": "count", "desc": "Count retrieved invoices",
         "out": "number", "exactness": "exact", "deps": ["g1"]},
    ]}
    diagnostics = diagnose_goal_spec("Count all invoices issued this year.", spec)
    assert any(item["code"] == "scope_completeness_unproven"
               and item["severity"] == "warning" for item in diagnostics)


def test_theta_rejects_declared_domain_with_undeclared_collection_shape():
    candidate = _candidate()
    candidate["goals"][0]["out"] = "record:invoice[]"
    error = validate_theta_types(candidate)
    assert "syntactically valid but undeclared" in error
    assert "record[]" in error


def test_theta_accepts_declared_invoice_record_and_generic_collection():
    candidate = _candidate()
    candidate["goals"][0]["out"] = "record:invoice"
    assert validate_theta_types(candidate) is None
    candidate["goals"][0]["out"] = "record[]"
    assert validate_theta_types(candidate) is None


def test_search_prompt_requires_search_goal_and_preserves_topic():
    from taas.studio.objective_contract import derive_objective_contract, diagnose_objective_alignment

    prompt = "Find the latest research papers about federated learning."
    frame = derive_objective_contract(prompt)
    assert frame["required_goal_classes"] == ["search"]
    assert frame["source_data_required"] is True
    spec = {"prompt_inputs": ["text"], "goals": [
        {"id": "g1", "class": "summarise", "desc": "Summarise federated learning",
         "in": ["text"], "out": "text", "deps": []}
    ]}
    codes = {item["code"] for item in diagnose_objective_alignment(prompt, spec)}
    assert "objective_operation_missing" in codes
    assert "objective_data_source_missing" in codes


def test_search_and_summary_prompt_requires_both_stages():
    from taas.studio.objective_contract import derive_objective_contract, diagnose_objective_alignment

    prompt = "Search for recent papers on formal concept analysis and summarise the findings."
    frame = derive_objective_contract(prompt)
    assert frame["required_goal_classes"] == ["search", "summarise"]
    spec = {"prompt_inputs": ["text"], "goals": [
        {"id": "g1", "class": "search", "eff": ["read(*)"], "desc": "Search for recent papers on formal concept analysis",
         "in": ["query"], "out": "record[]", "deps": []}
    ]}
    codes = {item["code"] for item in diagnose_objective_alignment(prompt, spec)}
    assert "objective_operation_missing" in codes
    assert "objective_data_source_missing" not in codes


def test_translation_prompt_does_not_force_tool_retrieval():
    from taas.studio.objective_contract import derive_objective_contract

    frame = derive_objective_contract("Translate this paragraph into French.")
    assert frame["required_goal_classes"] == ["translate"]
    assert frame["source_data_required"] is False


def test_objective_context_uses_real_newlines_and_is_not_domain_specific():
    from taas.studio.objective_contract import build_objective_context

    context = build_objective_context("Find the latest research papers about federated learning.")
    assert "\\n" not in context
    assert "\nUse only declared Theta types." in context
    assert "invoice" not in context.casefold()


def test_temporal_diagnostic_is_domain_agnostic():
    from taas.studio.objective_contract import diagnose_objective_alignment

    spec = {"prompt_inputs": ["text"], "goals": [
        {"id": "g1", "class": "retrieve", "eff": ["read(*)"], "desc": "Retrieve all research papers published this year",
         "in": ["query"], "out": "record[]", "deps": []}
    ]}
    diagnostics = diagnose_objective_alignment("Find all research papers published this year.", spec)
    temporal = next(item for item in diagnostics if item["code"] == "objective_temporal_field_unresolved")
    assert "source field" in temporal["suggestion"]
    assert "invoice" not in temporal["suggestion"].casefold()


def test_api_rejects_theta_type_combination_not_in_common_types():
    import pytest
    from fastapi import HTTPException

    candidate = _candidate()
    candidate["goals"][0]["out"] = "record:invoice[]"
    with pytest.raises(HTTPException) as exc:
        api.validate_studio_goal_spec(candidate)
    assert "syntactically valid" in str(exc.value.detail)
    assert "Θ.common_types" in str(exc.value.detail)


@pytest.mark.parametrize(
    ("prompt", "expected_class"),
    [
        ("Save the final report to the project workspace.", "store"),
        ("Send an email notification to the project owner.", "send"),
        ("Book a meeting for the engineering team.", "transact"),
        ("Execute the deployment script.", "execute"),
        ("Browse the vendor documentation website.", "navigate_browser"),
        ("Generate an image illustrating the architecture.", "render_media"),
        ("Create a project status report.", "create_document"),
        ("Edit the project status report.", "edit_document"),
        ("Générer une image pour illustrer l’architecture.", "render_media"),
        ("Créer un rapport de suivi du projet.", "create_document"),
        ("Modifier le rapport de suivi.", "edit_document"),
    ],
)
def test_objective_contract_covers_boundary_and_artifact_operations(prompt, expected_class):
    from taas.studio.objective_contract import derive_objective_contract

    contract = derive_objective_contract(prompt)
    assert expected_class in contract["required_goal_classes"]


@pytest.mark.parametrize(
    ("goal_class", "prompt", "effect"),
    [
        ("store", "Save the report.", "write(*)"),
        ("send", "Send an email.", "egress(*)"),
        ("transact", "Transfer funds to the vendor.", "money"),
        ("execute", "Execute the script.", "exec"),
        ("retrieve", "Retrieve records.", "read(*)"),
        ("search", "Search records.", "read(*)"),
        ("fetch_web", "Fetch the official website page.", "egress(*)"),
        ("navigate_browser", "Browse the vendor website.", "egress(*)"),
        ("create_document", "Create a project report.", "write(*)"),
        ("edit_document", "Edit the project report.", "write(*)"),
        ("render_media", "Generate an image for the project.", "egress(*)"),
    ],
)
def test_boundary_operations_require_explicit_effect_declarations(goal_class, prompt, effect):
    from taas.studio.objective_contract import diagnose_objective_alignment

    spec = {"prompt_inputs": ["text"], "goals": [
        {"id": "g1", "class": goal_class, "desc": prompt, "in": ["text"],
         "out": "none", "eff": [], "deps": []}
    ]}
    diagnostics = diagnose_objective_alignment(prompt, spec)
    assert any(item["code"] == "objective_effect_not_declared"
               and item["severity"] == "error" for item in diagnostics)
    spec["goals"][0]["eff"] = [effect]
    diagnostics = diagnose_objective_alignment(prompt, spec)
    assert not any(item["code"] == "objective_effect_not_declared"
                   for item in diagnostics)


def test_analyst_guide_example_uses_a_declared_generic_collection_type():
    from taas.studio.analyst_contract import build_analyst_system_prompt

    prompt = build_analyst_system_prompt()
    assert '"out": "record[]"' in prompt
    assert "exact kind/domain/cardinality combination" in prompt


def test_objective_contract_covers_web_fetch_and_random_operations():
    from taas.studio.objective_contract import derive_objective_contract

    web = derive_objective_contract("Fetch the official website page for the API reference.")
    assert "fetch_web" in web["required_goal_classes"]
    random = derive_objective_contract("Randomly select five records from the supplied dataset.")
    assert "random" in random["required_goal_classes"]


def test_goal_effect_errors_block_objective_acceptance():
    from taas.studio.objective_contract import diagnose_objective_alignment

    prompt = "Send an email notification to the project owner."
    spec = {"prompt_inputs": ["text"], "goals": [
        {"id": "g1", "class": "send", "desc": "Send the notification",
         "in": ["text"], "out": "none", "eff": [], "deps": []}
    ]}
    diagnostics = diagnose_objective_alignment(prompt, spec)
    assert any(item["code"] == "objective_effect_not_declared"
               and item["severity"] == "error" for item in diagnostics)


def test_french_objectives_preserve_count_and_relative_year_intent():
    from taas.studio.objective_contract import derive_objective_contract

    contract = derive_objective_contract("Compter toutes les factures émises cette année.")
    assert contract["operation"] == "count"
    assert contract["required_goal_classes"] == ["retrieve", "count"]
    assert contract["scope"]["all_matching_items"] is True
    assert contract["temporal_scope"]["expression"] == "this_year"
    assert contract["exactness_required"] == "exact"


def test_average_by_region_requires_grouped_tabular_aggregate():
    from taas.studio.objective_contract import derive_objective_contract, diagnose_objective_alignment

    prompt = "Calculate average sales by region."
    contract = derive_objective_contract(prompt)
    assert contract["operation"] == "aggregate"
    assert contract["grouped_result_required"] is True
    assert contract["numeric_result_required"] is False

    spec = {"prompt_inputs": ["text"], "goals": [
        {"id": "g1", "class": "retrieve", "eff": ["read(*)"], "desc": "Retrieve sales records",
         "in": ["query"], "out": "record[]", "deps": []},
        {"id": "g2", "class": "aggregate", "desc": "Calculate average sales by region",
         "in": ["record[]"], "out": "text", "exactness": "exact", "deps": ["g1"]},
    ]}
    codes = {item["code"] for item in diagnose_objective_alignment(prompt, spec)}
    assert "objective_grouped_output_missing" in codes

    spec["goals"][1]["out"] = "table"
    codes = {item["code"] for item in diagnose_objective_alignment(prompt, spec)}
    assert "objective_grouped_output_missing" not in codes


def test_multi_source_report_requires_retrieval_and_document_creation():
    from taas.studio.objective_contract import derive_objective_contract

    contract = derive_objective_contract("Create a report from several sources.")
    assert contract["source_data_required"] is True
    assert contract["required_goal_classes"] == ["retrieve", "create_document"]


def test_multi_source_synthesis_requires_retrieval_and_synthesis():
    from taas.studio.objective_contract import derive_objective_contract

    contract = derive_objective_contract("Synthesize findings from multiple sources.")
    assert contract["required_goal_classes"] == ["retrieve", "synthesise"]


def test_french_multi_source_report_is_recognized():
    from taas.studio.objective_contract import derive_objective_contract

    contract = derive_objective_contract("Créer un rapport à partir de plusieurs sources.")
    assert "retrieve" in contract["required_goal_classes"]
    assert "create_document" in contract["required_goal_classes"]


def test_user_supplied_content_does_not_force_external_tool_retrieval():
    from taas.studio.objective_contract import derive_objective_contract, diagnose_objective_alignment

    prompt = "Count all words in this paragraph."
    contract = derive_objective_contract(prompt)
    assert contract["user_supplied_content"] is True
    assert contract["source_data_required"] is False
    spec = {"prompt_inputs": ["text"], "goals": [
        {"id": "g1", "class": "count", "desc": "Count every word in the supplied paragraph",
         "in": ["text"], "out": "number", "exactness": "exact", "deps": []}
    ]}
    diagnostics = diagnose_objective_alignment(prompt, spec)
    assert not [item for item in diagnostics if item["severity"] == "error"]


def test_document_supplied_in_prompt_is_recognized_as_user_content():
    from taas.studio.objective_contract import derive_objective_contract, diagnose_objective_alignment

    prompt = "Summarise the document supplied in the prompt."
    contract = derive_objective_contract(prompt)
    assert contract["required_goal_classes"] == ["summarise"]
    assert contract["user_supplied_content"] is True
    assert contract["source_data_required"] is False
    assert "supplied" not in contract["unresolved_business_concepts"]

    spec = {"prompt_inputs": ["text"], "goals": [
        {"id": "g1", "class": "summarise", "desc": "Summarise the supplied document",
         "in": ["text"], "out": "text", "deps": []}
    ]}
    diagnostics = diagnose_objective_alignment(prompt, spec)
    assert not [item for item in diagnostics if item["severity"] == "error"]


def test_user_supplied_content_detection_supports_both_word_orders():
    from taas.studio.objective_contract import derive_objective_contract

    prompts = (
        "Summarise the document supplied in the prompt.",
        "Summarise the supplied document.",
        "Summarise the document provided by the user.",
        "Translate the paragraph attached to this request.",
    )
    for prompt in prompts:
        contract = derive_objective_contract(prompt)
        assert contract["user_supplied_content"] is True, (prompt, contract)
        assert contract["source_data_required"] is False, (prompt, contract)


def test_provided_architectures_are_recognized_as_user_supplied_content():
    from taas.studio.objective_contract import derive_objective_contract

    prompts = (
        "Compare these two provided architectures.",
        "Compare the two architectures provided by the user.",
        "Evaluate these provided design alternatives.",
    )
    for prompt in prompts:
        contract = derive_objective_contract(prompt)
        assert "compare" in contract["required_goal_classes"], (prompt, contract)
        assert contract["user_supplied_content"] is True, (prompt, contract)
        assert contract["source_data_required"] is False, (prompt, contract)
        assert not {"these", "two", "provided"}.intersection(
            contract["unresolved_business_concepts"]
        ), (prompt, contract)


def test_external_record_count_still_requires_retrieval():
    from taas.studio.objective_contract import derive_objective_contract

    contract = derive_objective_contract("Count all invoices issued this year.")
    assert contract["user_supplied_content"] is False
    assert contract["source_data_required"] is True
    assert "retrieve" in contract["required_goal_classes"]


def test_business_noun_alone_does_not_force_external_data_retrieval():
    from taas.studio.objective_contract import derive_objective_contract

    contract = derive_objective_contract("Explain what an invoice is.")
    assert contract["required_goal_classes"] == ["answer"]
    assert contract["source_data_required"] is False
    assert "explain" not in contract["unresolved_business_concepts"]
    assert "paragraph" not in contract["unresolved_business_concepts"]


def test_multi_operation_objective_checks_exactness_for_each_numeric_goal():
    from taas.studio.objective_contract import diagnose_objective_alignment, derive_objective_contract

    prompt = "Count all invoices and calculate their total value this year."
    contract = derive_objective_contract(prompt)
    assert {"retrieve", "count", "aggregate"}.issubset(set(contract["required_goal_classes"]))
    spec = {"prompt_inputs": ["text"], "goals": [
        {"id": "g1", "class": "retrieve", "eff": ["read(*)"], "desc": "Retrieve all invoices this year",
         "in": ["query"], "out": "record[]", "deps": []},
        {"id": "g2", "class": "aggregate", "desc": "Calculate exact total invoice value",
         "in": ["record[]"], "out": "number", "exactness": "exact", "deps": ["g1"]},
        {"id": "g3", "class": "count", "desc": "Count all retrieved invoices",
         "in": ["record[]"], "out": "number", "exactness": "tolerant", "deps": ["g1"]},
    ]}
    diagnostics = diagnose_objective_alignment(prompt, spec)
    assert any(item["code"] == "objective_exactness_not_preserved" for item in diagnostics)
    spec["goals"][2]["exactness"] = "exact"
    diagnostics = diagnose_objective_alignment(prompt, spec)
    assert not [item for item in diagnostics if item["severity"] == "error"]


def test_multi_operation_objective_requires_each_numeric_goal_to_depend_on_retrieval():
    from taas.studio.objective_contract import diagnose_objective_alignment

    prompt = "Count all invoices and calculate their total value this year."
    spec = {"prompt_inputs": ["text"], "goals": [
        {"id": "g1", "class": "retrieve", "eff": ["read(*)"], "desc": "Retrieve all invoices this year",
         "in": ["query"], "out": "record[]", "deps": []},
        {"id": "g2", "class": "aggregate", "desc": "Calculate exact total invoice value",
         "in": ["record[]"], "out": "number", "exactness": "exact", "deps": ["g1"]},
        {"id": "g3", "class": "count", "desc": "Count all retrieved invoices",
         "in": ["record[]"], "out": "number", "exactness": "exact", "deps": []},
    ]}
    diagnostics = diagnose_objective_alignment(prompt, spec)
    assert any(item["code"] == "objective_dataflow_disconnected" for item in diagnostics)


def test_count_combined_with_grouped_aggregate_keeps_both_output_contracts():
    from taas.studio.objective_contract import diagnose_objective_alignment, derive_objective_contract

    prompt = "Count all records and calculate average sales by region."
    contract = derive_objective_contract(prompt)
    assert contract["grouped_result_required"] is True
    assert contract["numeric_result_required"] is True
    spec = {"prompt_inputs": ["text"], "goals": [
        {"id": "g1", "class": "retrieve", "eff": ["read(*)"], "desc": "Retrieve all records",
         "in": ["query"], "out": "record[]", "deps": []},
        {"id": "g2", "class": "count", "desc": "Count all retrieved records",
         "in": ["record[]"], "out": "number", "exactness": "exact", "deps": ["g1"]},
        {"id": "g3", "class": "aggregate", "desc": "Calculate average sales by region",
         "in": ["record[]"], "out": "table", "exactness": "exact", "deps": ["g1"]},
    ]}
    diagnostics = diagnose_objective_alignment(prompt, spec)
    assert not [item for item in diagnostics if item["severity"] == "error"]
