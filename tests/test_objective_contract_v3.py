from hypothesis import given, strategies as st

from taas.studio.objective_contract_v3 import (
    derive_objective_contract_v3,
    validate_objective_contract_v3,
)


def test_v3_preserves_original_text_and_unicode_evidence_offsets():
    objective = "Résumer les dossiers clients et créer un rapport."
    contract = derive_objective_contract_v3(objective, locale="fr")

    assert contract["objective"] == {
        "text": objective,
        "locale": "fr",
        "normalization": "none",
    }
    assert contract["outcomes"]
    for outcome in contract["outcomes"]:
        for evidence in outcome["source_evidence"]:
            assert objective[evidence["start"]:evidence["end"]] == evidence["text"]
    assert validate_objective_contract_v3(contract) == []


def test_v3_does_not_promote_negated_or_modality_sensitive_actions():
    examples = [
        "If validation fails, notify the owner.",
        "Optionally create a chart.",
        "Create either a PDF or a presentation, not both.",
        "Ne pas envoyer le rapport.",
    ]
    for objective in examples:
        contract = derive_objective_contract_v3(objective)
        assert contract["outcomes"] == []
        assert contract["clarifications"]
        assert all(item["blocking"] for item in contract["clarifications"])
        assert contract["review"]["discovery_blocked"] is True


def test_v3_modality_is_scoped_to_its_clause_without_erasing_unrelated_outcomes():
    contract = derive_objective_contract_v3("Draft the email; do not send it.")
    assert any(item["goal_class"] == "write" for item in contract["outcomes"])
    assert not any(item["goal_class"] == "send" for item in contract["outcomes"])
    send_clarifications = [
        item for item in contract["clarifications"]
        if "send" in item["affected_goal_classes"]
    ]
    assert send_clarifications
    assert all(item["reason"] == "clause_modality_scope_not_resolved" for item in send_clarifications)
    assert contract["review"]["discovery_blocked"] is True


def test_v3_newline_is_a_clause_boundary_for_modality_scope():
    contract = derive_objective_contract_v3("Draft the email\nDo not send it.")
    assert any(item["goal_class"] == "write" for item in contract["outcomes"])
    assert not any(item["goal_class"] == "send" for item in contract["outcomes"])
    assert any("send" in item["affected_goal_classes"] for item in contract["clarifications"])


def test_v3_modality_in_one_clause_does_not_block_an_unrelated_search_clause():
    contract = derive_objective_contract_v3(
        "Search the web for the source; optionally create a chart."
    )
    assert any(item["goal_class"] == "search" for item in contract["outcomes"])
    assert not any(item["goal_class"] == "render_media" for item in contract["outcomes"])
    assert contract["clarifications"]
    assert all("render_media" in item["affected_goal_classes"] for item in contract["clarifications"])


def test_v3_keeps_semantic_correctness_unverified_and_review_mandatory():
    contract = derive_objective_contract_v3("Search the web for recent research papers.")
    assert contract["review"]["required"] is True
    assert contract["review"]["semantic_correctness_verified"] is False
    assert contract["review"]["discovery_blocked"] is True
    assert validate_objective_contract_v3(contract) == []


@given(st.text(min_size=1, max_size=300))
def test_v3_any_emitted_evidence_is_an_exact_slice_of_original_unicode_text(objective):
    contract = derive_objective_contract_v3(objective)
    for outcome in contract["outcomes"]:
        for evidence in outcome["source_evidence"]:
            assert objective[evidence["start"]:evidence["end"]] == evidence["text"]


def test_v3_validator_rejects_forged_evidence_span():
    contract = derive_objective_contract_v3("Search the web for papers.")
    contract["outcomes"][0]["source_evidence"][0]["text"] = "forged"
    assert "evidence_span_text_mismatch" in validate_objective_contract_v3(contract)


def test_v3_validator_rejects_discovery_authorization():
    contract = derive_objective_contract_v3("Search the web for papers.")
    contract["review"]["discovery_blocked"] = False
    assert "discovery_must_remain_blocked" in validate_objective_contract_v3(contract)


def test_v3_builds_clause_provenance_graph_with_exact_source_spans():
    objective = "Search the web for papers; draft a summary.\nDo not send it."
    contract = derive_objective_contract_v3(objective)
    clauses = contract["clauses"]
    assert [item["text"] for item in clauses] == [
        "Search the web for papers", "draft a summary", "Do not send it"
    ]
    for clause in clauses:
        span = clause["span"]
        assert objective[span["start"]:span["end"]] == clause["text"]
    search = next(item for item in contract["outcomes"] if item["goal_class"] == "search")
    assert search["clause_ref"] == clauses[0]["id"]
    assert search["id"] in clauses[0]["outcome_refs"]
    assert any(item["clause_ref"] == clauses[2]["id"] for item in contract["clarifications"])
    assert validate_objective_contract_v3(contract) == []


def test_v3_validator_rejects_forged_clause_reference_and_span():
    contract = derive_objective_contract_v3("Search the web for papers.")
    contract["outcomes"][0]["clause_ref"] = "missing_clause"
    contract["clauses"][0]["text"] = "forged"
    errors = validate_objective_contract_v3(contract)
    assert "outcome_clause_ref_invalid" in errors
    assert "clause_span_text_mismatch" in errors



def test_v3_extracts_only_explicit_unambiguous_cross_clause_dependency():
    objective = "Search the sources. Then summarize the results."
    contract = derive_objective_contract_v3(objective)

    assert len(contract["dependencies"]) == 1
    relation = contract["dependencies"][0]
    assert relation["type"] == "precedes"
    assert relation["source_clause_refs"] == ["clause_1", "clause_2"]
    assert relation["from_outcome"] == "outcome_1"
    assert relation["to_outcome"] == "outcome_2"
    evidence = relation["source_evidence"][0]
    assert objective[evidence["start"]:evidence["end"]] == "Then"
    target = next(item for item in contract["outcomes"] if item["id"] == "outcome_2")
    assert target["depends_on"] == ["outcome_1"]
    assert contract["review"]["semantic_correctness_verified"] is False
    assert contract["review"]["discovery_blocked"] is True
    assert validate_objective_contract_v3(contract) == []


def test_v3_does_not_guess_dependency_endpoints_when_prior_clause_has_multiple_outcomes():
    contract = derive_objective_contract_v3(
        "Search and retrieve the sources. Then summarize the results."
    )
    assert contract["dependencies"] == []
    assert any(
        item["reason"] == "dependency_endpoints_ambiguous"
        for item in contract["clarifications"]
    )
    assert contract["review"]["discovery_blocked"] is True


def test_v3_validator_rejects_forged_dependency_evidence_and_dangling_endpoint():
    contract = derive_objective_contract_v3(
        "Search the sources. Then summarize the results."
    )
    contract["dependencies"][0]["source_evidence"][0]["text"] = "forged"
    contract["dependencies"][0]["to_outcome"] = "missing"
    errors = validate_objective_contract_v3(contract)
    assert "dependency_evidence_span_text_mismatch" in errors
    assert "dependency_outcome_ref_invalid" in errors



def test_v3_oncology_objective_preserves_clause_order_month_scope_and_article_dependencies():
    objective = (
        "For a report I have to prepare on oncology with machine learning, help me "
        "identify the last related study published on november 2024 containing the "
        "word cancer in its title and retrieve the abstract of the article. "
        "Translate only the title of the study into spanish while keeping the abstract "
        "of the study in its original language. Find the type of cancer discussed in "
        "the article and tell me who published the first literature and in which year."
    )
    contract = derive_objective_contract_v3(objective)

    assert [item["goal_class"] for item in contract["outcomes"]] == [
        "search", "translate", "extract"
    ]
    assert [item["clause_ref"] for item in contract["outcomes"]] == [
        "clause_1", "clause_2", "clause_3"
    ]
    temporal = contract["constraints"]["temporal"]
    assert temporal["start_inclusive"] == "2024-11-01"
    assert temporal["end_exclusive"] == "2024-12-01"
    selection = contract["constraints"]["selection"]
    assert selection["limit"] == 1
    assert selection["order"] == "descending"
    assert selection["order_by_concept"] == "publication_date"

    dependencies = contract["dependencies"]
    assert {(item["from_outcome"], item["to_outcome"]) for item in dependencies} == {
        ("outcome_1", "outcome_2"),
        ("outcome_1", "outcome_3"),
    }
    assert all(item["interpretation"]["semantic_correctness_verified"] is False for item in dependencies)
    for dependency in dependencies:
        evidence = dependency["source_evidence"][0]
        assert objective[evidence["start"]:evidence["end"]] == evidence["text"]
    assert contract["review"]["required"] is True
    assert contract["review"]["discovery_blocked"] is True
    assert contract["review"]["semantic_correctness_verified"] is False
    assert validate_objective_contract_v3(contract) == []
