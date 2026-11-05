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


def test_supplied_input_does_not_count_as_performed_search_or_retrieval():
    from taas.studio.objective_contract import build_outcome_coverage

    for objective in (
        "Search the supplied documents for references to privacy.",
        "Retrieve records from the configured source.",
    ):
        coverage = build_outcome_coverage(
            objective,
            {"prompt_inputs": ["text", "record[]"], "goals": []},
        )
        assert coverage["summary"]["missing"] >= 1
        assert all(item["status"] == "missing" for item in coverage["outcomes"])
        assert all(item["input_types"] == [] for item in coverage["outcomes"])
        assert coverage["semantic_correctness_verified"] is False
        assert coverage["coverage_semantics"].startswith("goal_class_only")

    frame = derive_objective_contract(
        "Search the supplied documents for references to privacy."
    )
    assert frame["source_data_required"] is False

    external = derive_objective_contract(
        "Search the web using the following document for current references."
    )
    assert external["user_supplied_content"] is True
    assert external["source_data_required"] is True


def test_search_outcome_requires_a_search_goal_even_when_documents_are_supplied():
    from taas.studio.objective_contract import build_outcome_coverage

    coverage = build_outcome_coverage(
        "Search the supplied documents for references to privacy.",
        {"prompt_inputs": ["text"], "goals": [{"id": "g1", "class": "search"}]},
    )
    assert coverage["summary"] == {"required": 1, "covered": 1, "missing": 0}
    assert coverage["outcomes"][0]["status"] == "covered_by_goal"
    assert coverage["outcomes"][0]["goal_ids"] == ["g1"]
    assert coverage["outcomes"][0]["semantic_conformance"] == "not_assessed"

def test_v2_recognizes_qualified_multi_source_acquisition_requests():
    examples = [
        "Create a report from several external sources.",
        "Create a report across multiple independent data sources.",
        "Create a report from various online sources.",
        "Create a report from several public sources.",
    ]
    for objective in examples:
        frame = derive_objective_contract(objective)
        assert "create_document" in frame["required_goal_classes"] or "synthesise" in frame["required_goal_classes"], (objective, frame)
        assert frame["source_data_required"] is True, (objective, frame)
        assert frame["user_supplied_content"] is False, (objective, frame)


def test_v2_external_source_phrase_requires_acquisition_without_search_verb():
    examples = [
        "Create a report from external sources.",
        "Create a report from several sources.",
        "Create a report from multiple sources.",
    ]
    for objective in examples:
        frame = derive_objective_contract(objective)
        assert frame["source_data_required"] is True, (objective, frame)


def test_v2_external_sources_override_supplied_prompt_content():
    objective = "Create a report from several external sources using the supplied document."
    frame = derive_objective_contract(objective)

    assert frame["user_supplied_content"] is True
    assert frame["source_data_required"] is True


def test_v2_recognizes_supplied_content_with_descriptive_modifiers():
    examples = [
        "Identify anomalies in the supplied sensor data.",
        "Classify the provided raw telemetry data.",
        "Summarise the attached financial transaction records.",
    ]
    for objective in examples:
        frame = derive_objective_contract(objective)
        assert frame["user_supplied_content"] is True, (objective, frame)
        assert frame["source_data_required"] is False, (objective, frame)



def test_retrieval_from_configured_source_is_not_misread_as_a_date_range():
    objective = "Retrieve records matching the provided query from the configured source."
    frame = derive_objective_contract(objective)

    assert frame["operation"] == "retrieve"
    assert frame["temporal_scope"] is None
    assert frame["constraints"]["temporal"] is None
    assert not ({"configured", "matching", "query", "source"} & set(frame["unresolved_business_concepts"]))


def test_explicit_english_and_french_date_ranges_are_recognized():
    examples = [
        ("Retrieve records from 1 January to 31 January.", "from_to"),
        ("Retrieve records between January 1 and January 31.", "between"),
        ("Récupérer les dossiers du 1 janvier au 31 janvier.", "du_au"),
        ("Retrieve records between 2026-01-01 and 2026-01-31.", "between"),
        ("Retrieve records from 01/01/2026 to 31/01/2026.", "from_to"),
    ]
    for objective, expression in examples:
        frame = derive_objective_contract(objective)
        assert frame["temporal_scope"] is not None, (objective, frame)
        assert frame["temporal_scope"]["kind"] == "explicit_range"
        assert frame["temporal_scope"]["expression"] == expression


def test_retrieval_from_database_is_not_a_temporal_constraint():
    frame = derive_objective_contract("Retrieve customer records from the database.")

    assert frame["operation"] == "retrieve"
    assert frame["temporal_scope"] is None
    assert "customer" in frame["unresolved_business_concepts"]


def test_search_operation_is_reflected_in_primary_operation_and_outcomes():
    frame = derive_objective_contract("Search the web for recent research papers.")

    assert frame["operation"] == "search"
    assert "search" in frame["required_goal_classes"]


def test_alignment_does_not_treat_supplied_input_as_a_performed_operation():
    from taas.studio.objective_contract import diagnose_objective_alignment

    diagnostics = diagnose_objective_alignment(
        "Search the supplied documents for references to privacy.",
        {"prompt_inputs": ["text"], "goals": []},
    )
    assert any(
        item["code"] == "objective_operation_missing"
        and "search" in item["message"]
        for item in diagnostics
    )


def test_external_acquisition_requires_an_acquisition_goal_even_with_an_input():
    from taas.studio.objective_contract import diagnose_objective_alignment

    diagnostics = diagnose_objective_alignment(
        "Search the web using the following document for current references.",
        {"prompt_inputs": ["text"], "goals": []},
    )
    assert any(item["code"] == "objective_operation_missing" for item in diagnostics)
    assert any(item["code"] == "objective_data_source_missing" for item in diagnostics)


def test_year_difference_requires_retrieval_and_exact_numeric_computation():
    objective = (
        "Can you get me the year difference between the creation date of the "
        "AssaultCube repository and the domain registration date of its official site?"
    )
    frame = derive_objective_contract(objective)

    assert frame["operation"] == "compute_exact"
    assert frame["required_goal_classes"] == ["retrieve", "compute_exact"]
    assert [outcome["goal_class"] for outcome in frame["outcomes"]] == [
        "retrieve", "compute_exact"
    ]
    assert frame["numeric_result_required"] is True
    assert frame["exactness_required"] == "exact"
    assert frame["constraints"]["computation"]["numeric_result_required"] is True
    assert frame["constraints"]["computation"]["exactness_required"] == "exact"
    assert frame["source_data_required"] is True


def test_year_difference_is_not_covered_by_retrieval_goals_alone():
    from taas.studio.objective_contract import build_outcome_coverage, diagnose_objective_alignment

    objective = (
        "Get me the year difference between the repository creation date "
        "and the official domain registration date."
    )
    spec = {
        "prompt_inputs": ["text"],
        "goals": [
            {"id": "g1", "class": "retrieve", "out": "record[]"},
            {"id": "g2", "class": "retrieve", "out": "record[]", "deps": ["g1"]},
        ],
    }
    coverage = build_outcome_coverage(objective, spec)
    diagnostics = diagnose_objective_alignment(objective, spec)

    assert coverage["summary"] == {"required": 2, "covered": 1, "missing": 1}
    assert coverage["outcomes"][1]["goal_class"] == "compute_exact"
    assert coverage["outcomes"][1]["status"] == "missing"
    assert any(
        item["code"] == "objective_operation_missing"
        and "compute_exact" in item["message"]
        for item in diagnostics
    )
