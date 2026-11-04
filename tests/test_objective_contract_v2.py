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
