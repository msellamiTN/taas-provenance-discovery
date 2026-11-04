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
        "Draft the email; do not send it.",
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
