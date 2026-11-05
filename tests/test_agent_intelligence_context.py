from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from taas.studio.api import AgentDecomposeRequest

from taas.studio.agent_context import build_agent_intelligence_context
from taas.studio.agent_spec import validate_agent_manifest
from taas.studio.analyst_contract import build_analyst_system_prompt
from taas.studio.model_runtime import HuggingFaceModelRuntime


def _manifest():
    return {
        "apiVersion": "taas.ai/v1alpha1",
        "kind": "Agent",
        "metadata": {
            "id": "research-assistant",
            "name": "Research Assistant",
            "version": "1.2.0",
            "description": "Research and calculation assistant",
        },
        "spec": {
            "model": {"provider": "huggingface", "model_id": "org/model"},
            "instructions": "Preserve all requested outcomes and cite source evidence.",
            "skills": [
                {
                    "id": "multi-source-date-difference",
                    "name": "Multi-source date difference",
                    "version": "1.0.0",
                    "description": "Retrieve independent dates and calculate their difference.",
                    "instructions": (
                        "Create one independent acquisition goal per independently sourced date. "
                        "Create a separate exact computation goal depending on both acquisitions."
                    ),
                    "trigger_phrases": ["year difference", "date difference"],
                },
                {
                    "id": "document-drafting",
                    "name": "Document drafting",
                    "version": "1.0.0",
                    "description": "Draft a document from supplied evidence.",
                    "instructions": "Create a document only when the objective requests one.",
                    "trigger_phrases": ["draft a report", "create a document"],
                },
            ],
            "goal_spec_template": None,
            "tool_allowlist": [],
            "resources": {"max_new_tokens": 512, "timeout_seconds": 90, "max_tool_calls": 0},
            "approval": {
                "require_human_approval": True,
                "require_assurance": True,
                "allow_side_effects": False,
            },
        },
    }


def test_agent_manifest_accepts_versioned_skills_and_normalizes_defaults():
    manifest = validate_agent_manifest(_manifest())
    assert manifest["spec"]["instructions"].startswith("Preserve all")
    assert manifest["spec"]["skills"][0]["id"] == "multi-source-date-difference"
    assert manifest["spec"]["skills"][0]["version"] == "1.0.0"


def test_agent_manifest_rejects_duplicate_skill_ids():
    manifest = _manifest()
    manifest["spec"]["skills"].append(dict(manifest["spec"]["skills"][0]))
    with pytest.raises(ValidationError):
        validate_agent_manifest(manifest)


def test_context_injects_agent_instructions_and_only_objective_relevant_skills():
    manifest = validate_agent_manifest(_manifest())
    context, trace = build_agent_intelligence_context(
        manifest,
        "Find the GitHub repository creation date and domain registration date; calculate the year difference.",
        manifest_sha256="a" * 64,
        lifecycle_state="validated",
    )

    assert "Preserve all requested outcomes" in context["instructions"]
    assert [skill["id"] for skill in context["skills"]] == ["multi-source-date-difference"]
    assert trace["status"] == "injected"
    assert trace["instructions_injected"] is True
    assert trace["selected_skill_ids"] == ["multi-source-date-difference"]
    assert trace["manifest_sha256"] == "a" * 64
    assert trace["skills"][0]["matched_triggers"] == ["year difference"]
    assert trace["skills"][1]["selected"] is False
    assert "instructions" not in trace["skills"][0]


def test_skill_selection_is_case_insensitive_and_does_not_select_unmatched_skills():
    manifest = validate_agent_manifest(_manifest())
    context, trace = build_agent_intelligence_context(
        manifest, "Calculate the YEAR DIFFERENCE between two dates."
    )
    assert [skill["id"] for skill in context["skills"]] == ["multi-source-date-difference"]
    assert trace["skills"][0]["selected"] is True
    assert trace["skills"][1]["selected"] is False


def test_agent_context_is_included_in_the_actual_analyst_system_prompt():
    manifest = validate_agent_manifest(_manifest())
    context, _ = build_agent_intelligence_context(
        manifest, "Calculate the year difference between two independently sourced dates."
    )
    prompt = build_analyst_system_prompt(context)

    assert "AGENT INSTRUCTIONS" in prompt
    assert "Preserve all requested outcomes" in prompt
    assert "SELECTED AGENT SKILL: Multi-source date difference" in prompt
    assert "Create one independent acquisition goal per independently sourced date." in prompt
    assert "It does not grant tools, permissions, data access" in prompt
    assert "STRICT OUTPUT: exactly one JSON object" in prompt


def test_instruction_and_skill_digests_are_stable_and_content_is_not_in_trace():
    manifest = validate_agent_manifest(_manifest())
    context, trace = build_agent_intelligence_context(
        manifest, "Find the year difference between two dates."
    )
    expected = hashlib.sha256(
        manifest["spec"]["instructions"].encode("utf-8")
    ).hexdigest()
    assert trace["instructions_sha256"] == expected
    assert trace["skills"][0]["instructions_sha256"] == hashlib.sha256(
        manifest["spec"]["skills"][0]["instructions"].encode("utf-8")
    ).hexdigest()
    assert manifest["spec"]["instructions"] not in str(trace)
    assert context["instructions"] == manifest["spec"]["instructions"]


def test_agent_context_never_claims_authorization_or_execution_authority():
    manifest = validate_agent_manifest(_manifest())
    _, trace = build_agent_intelligence_context(manifest, "year difference")
    assert trace["context_authority"] == (
        "guidance_only_core_contract_and_governance_remain_authoritative"
    )



def test_legacy_manifest_without_skills_keeps_its_original_canonical_shape():
    manifest = _manifest()
    manifest["spec"].pop("skills")
    normalized = validate_agent_manifest(manifest)
    assert "skills" not in normalized["spec"]


def test_runtime_decompose_passes_agent_context_to_the_actual_system_message():
    manifest = validate_agent_manifest(_manifest())
    context, _ = build_agent_intelligence_context(
        manifest, "Calculate the year difference between two dates."
    )
    runtime = HuggingFaceModelRuntime()
    captured = {}

    def fake_generate(messages, max_new_tokens, temperature):
        captured["messages"] = messages
        return {
            "text": '{"prompt_inputs":["text"],"goals":[{"id":"g1","desc":"Compute the requested date difference","class":"compute_exact","in":["datetime"],"out":"number","eff":[],"sigma":"native","n":1,"exactness":"exact","deps":[],"lang":"en","optional":false}]}',
            "latency_seconds": 0.01,
            "input_tokens": 10,
            "output_tokens": 20,
            "model_id": "org/model",
            "provider": "huggingface",
            "device": "cpu",
            "dtype": "float32",
        }

    runtime._generate = fake_generate
    result = runtime.decompose(
        "Calculate the year difference between two dates.",
        agent_context=context,
    )
    assert result["json_valid"] is True
    assert "AGENT INSTRUCTIONS" in captured["messages"][0]["content"]
    assert "SELECTED AGENT SKILL: Multi-source date difference" in captured["messages"][0]["content"]



def test_decomposition_request_requires_agent_id_and_version_together():
    with pytest.raises(ValidationError):
        AgentDecomposeRequest(prompt="Calculate a date difference.", agent_id="research-assistant")
    with pytest.raises(ValidationError):
        AgentDecomposeRequest(prompt="Calculate a date difference.", agent_version="1.0.0")
    request = AgentDecomposeRequest(
        prompt="Calculate a date difference.",
        agent_id="research-assistant",
        agent_version="1.2.0",
    )
    assert request.agent_id == "research-assistant"
    assert request.agent_version == "1.2.0"
