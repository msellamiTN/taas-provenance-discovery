from __future__ import annotations

from taas.studio.objective_contract import (
    build_objective_context,
    derive_objective_contract,
)


def test_v2_preserves_multiple_independent_outcomes_in_order():
    objective = (
        "Search for recent papers on formal concept analysis, compare the findings, "
        "synthesise the evidence, and create a report."
    )
    frame = derive_objective_contract(objective)

    assert frame["contract_version"] == "2.0"
    assert [item["goal_class"] for item in frame["outcomes"]] == [
        "search", "compare", "synthesise", "create_document"
    ]
    assert [item["id"] for item in frame["outcomes"]] == [
        "outcome_1", "outcome_2", "outcome_3", "outcome_4"
    ]
    assert all(item["required"] for item in frame["outcomes"])
    assert all(item["interpretation"] == "lexical_rule" for item in frame["outcomes"])
    assert frame["required_goal_classes"] == [
        item["goal_class"] for item in frame["outcomes"]
    ]


def test_v2_retains_legacy_fields_for_existing_consumers():
    frame = derive_objective_contract("Count all invoices issued this year.")

    assert frame["contract_version"] == "2.0"
    assert frame["operation"] == "count"
    assert frame["required_goal_classes"] == ["retrieve", "count"]
    assert frame["scope"]["all_matching_items"] is True
    assert frame["temporal_scope"]["expression"] == "this_year"
    assert frame["constraints"]["computation"]["exactness_required"] == "exact"
    assert frame["constraints"]["inputs"]["source_data_required"] is True


def test_v2_marks_lexical_interpretation_as_unverified():
    frame = derive_objective_contract(
        "Find recent articles about privacy engineering."
    )

    assert frame["review"]["semantic_correctness_verified"] is False
    assert frame["review"]["interpretation_method"] == "deterministic_lexical_rules"
    assert frame["review"]["required"] is True


def test_v2_does_not_force_retrieval_for_user_supplied_content():
    frame = derive_objective_contract("Translate this paragraph into French.")

    assert frame["outcomes"] == [{
        "id": "outcome_1",
        "goal_class": "translate",
        "required": True,
        "interpretation": "lexical_rule",
    }]
    assert frame["constraints"]["inputs"]["source_data_required"] is False
    assert frame["constraints"]["inputs"]["user_supplied_content"] is True


def test_objective_context_exposes_v2_outcomes_and_constraints():
    context = build_objective_context(
        "Search for recent papers and summarise the findings."
    )

    assert "Objective Contract v2" in context
    assert '"contract_version": "2.0"' in context
    assert '"outcomes"' in context
    assert '"constraints"' in context
    assert "preserve every outcome and constraint" in context



def test_v2_always_requires_human_review_even_for_simple_objectives():
    frame = derive_objective_contract("Translate this paragraph into French.")

    assert frame["review"]["required"] is True
    assert "human_review_mandatory" in frame["review"]["reasons"]
    assert frame["review"]["semantic_correctness_verified"] is False



def test_v2_outcome_coverage_maps_each_required_operation_to_goal_ids():
    from taas.studio.objective_contract import build_outcome_coverage

    objective = (
        "Search for recent papers on formal concept analysis, compare the findings, "
        "synthesise the evidence, and create a report."
    )
    spec = {"prompt_inputs": ["text"], "goals": [
        {"id": "g1", "class": "search"},
        {"id": "g2", "class": "compare"},
        {"id": "g3", "class": "synthesise"},
        {"id": "g4", "class": "create_document"},
    ]}
    coverage = build_outcome_coverage(objective, spec)

    assert coverage["summary"] == {"required": 4, "covered": 4, "missing": 0}
    assert [item["status"] for item in coverage["outcomes"]] == [
        "covered_by_goal", "covered_by_goal", "covered_by_goal", "covered_by_goal"
    ]
    assert [item["goal_ids"] for item in coverage["outcomes"]] == [
        ["g1"], ["g2"], ["g3"], ["g4"]
    ]
    assert coverage["semantic_correctness_verified"] is False


def test_v2_outcome_coverage_reports_missing_operations_without_guessing():
    from taas.studio.objective_contract import build_outcome_coverage

    objective = "Search for recent papers and summarise the findings."
    coverage = build_outcome_coverage(objective, {
        "prompt_inputs": ["text"],
        "goals": [{"id": "g1", "class": "search"}],
    })

    assert coverage["summary"] == {"required": 2, "covered": 1, "missing": 1}
    assert coverage["outcomes"][0]["status"] == "covered_by_goal"
    assert coverage["outcomes"][1]["status"] == "missing"
    assert coverage["outcomes"][1]["goal_ids"] == []


def test_v2_retrieval_outcome_can_be_covered_by_actual_supplied_data():
    from taas.studio.objective_contract import build_outcome_coverage

    coverage = build_outcome_coverage(
        "Search the supplied documents for references to privacy.",
        {"prompt_inputs": ["text"], "goals": []},
    )

    assert coverage["summary"] == {"required": 1, "covered": 1, "missing": 0}
    assert coverage["outcomes"][0]["status"] == "covered_by_supplied_input"
    assert coverage["outcomes"][0]["input_types"] == ["text"]
    frame = derive_objective_contract(
        "Search the supplied documents for references to privacy."
    )
    assert frame["source_data_required"] is False

    external = derive_objective_contract(
        "Search the web using this supplied document for current references."
    )
    assert external["user_supplied_content"] is True
    assert external["source_data_required"] is True
