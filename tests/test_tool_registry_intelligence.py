from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import taas.studio.api as studio_api
from taas.data.registries import RawTool
from taas.studio import tool_registry


def _entry(tool: RawTool) -> dict:
    return {
        "server": tool.server, "name": tool.name, "description": tool.description,
        "input_schema": tool.input_schema, "output_schema": tool.output_schema,
        "annotations": tool.annotations, "source": tool.source, "category": tool.category,
        "extra": tool.extra, "id": tool.id, "hash": tool.definition_hash(),
    }


LOOKUP = RawTool(
    server="sample_registry", name="lookup_records",
    description="Look up records in the sample registry by query.",
    input_schema={"type": "object", "properties": {
        "query": {"type": "string", "description": "Search query"},
        "limit": {"type": "integer"},
    }, "required": ["query"]},
    annotations={"readOnlyHint": True},
    source="LiveMCPTool", category="registry",
)

DELETE = RawTool(
    server="sample_registry", name="delete_record",
    description="Permanently delete a record from the registry.",
    input_schema={"type": "object", "properties": {"id": {"type": "string"}},
                  "required": ["id"]},
    annotations={"destructiveHint": True},
    source="LiveMCPTool", category="registry",
)

SNAPSHOT = {"registry": [_entry(LOOKUP), _entry(DELETE)], "stats": {}}


@pytest.fixture(autouse=True)
def registry_snapshot(monkeypatch):
    monkeypatch.setattr(tool_registry, "load_processed", lambda: SNAPSHOT)
    tool_registry.reset_registry_caches()
    yield
    tool_registry.reset_registry_caches()


def test_search_filters_by_server_source_and_query():
    result = tool_registry.search_registry_tools(source="LiveMCPTool")
    assert result["schema"] == "taas.tool-identity/v1"
    assert result["total"] == 2
    assert result["annotations_are_trusted_evidence"] is False

    only_lookup = tool_registry.search_registry_tools(q="lookup")
    assert only_lookup["total"] == 1
    assert only_lookup["tools"][0]["tool_id"] == "sample_registry::lookup_records"
    assert only_lookup["tools"][0]["definition_hash"] == LOOKUP.definition_hash()

    assert tool_registry.search_registry_tools(server="nowhere")["total"] == 0


def test_resolve_verifies_stored_definition_hash():
    identity = tool_registry.resolve_registry_tool("sample_registry", "lookup_records")
    assert identity["definition_hash_verified"] is True
    assert identity["definition_hash"] == identity["definition_hash_recomputed"]
    assert identity["source"] == "LiveMCPTool"
    assert tool_registry.resolve_registry_tool("ghost", "nope") is None


def test_profile_exposes_structured_capability_and_evidence_axis():
    profile = tool_registry.build_capability_profile("sample_registry", "lookup_records")
    assert profile["schema"] == "taas.tool-capability-profile/v1"
    assert profile["identity"]["definition_hash_verified"] is True
    cap = profile["capability"]
    query = next(i for i in cap["inputs"] if i["argument"] == "query")
    assert query["required"] is True
    assert cap["tool_class"]
    assert "qos" in cap and "price" in cap["qos"]
    # readOnlyHint annotation: effects resolve to read-only with ann evidence
    assert profile["effects"]["evidence_kind"] in ("ann", "lex", "obs", "att")
    assert profile["effects"]["declared_effects"]

    ev = profile["evidence_summary"]
    assert ev["declared"]["annotations_present"] is True
    assert ev["declared"]["annotations_are_trusted_evidence"] is False
    assert ev["observed"]["evidence_store_wired"] is False
    assert ev["attested"]["status"] == "lookup_not_configured"
    assert profile["tool_invoked"] is False
    assert profile["execution_enabled"] is False
    assert profile["structural_profile_only"] is True


def test_observed_evidence_upgrades_contract_kind():
    from taas.provenance import EvidenceStore, ProvenanceRecord
    store = EvidenceStore()
    raw = LOOKUP
    h = raw.definition_hash()
    store.add(raw.id, h, "read_only", ProvenanceRecord("obs", "sandbox", 0.9, "probe"))
    store.set_observed_effects(raw.id, h, ["read(*)"])
    profile = tool_registry.build_capability_profile(
        "sample_registry", "lookup_records", evidence_store=store)
    assert profile["evidence_summary"]["observed"]["stored_property_records"] == 1
    assert profile["evidence_summary"]["observed"]["observed_effects_present"] is True
    assert profile["effects"]["evidence_kind"] == "obs"


def test_attestation_lookup_counts_verified_records():
    calls = []

    def lookup(binding):
        calls.append(binding)
        return {"valid": [{"id": "e1"}], "invalid": [], "count": 1}

    profile = tool_registry.build_capability_profile(
        "sample_registry", "lookup_records", attestation_lookup=lookup)
    att = profile["evidence_summary"]["attested"]
    assert att["status"] == "performed"
    assert att["verified_records"] == 1
    assert calls[0]["tool_id"] == "sample_registry::lookup_records"
    assert len(calls[0]["definition_hash"]) == 32


def test_tool_endpoints(monkeypatch):
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "tools-token")
    monkeypatch.setattr(studio_api.assurance_evidence, "list_verified_evidence_for_subject",
                        lambda binding: {"valid": [], "invalid": [], "count": 0})
    client = TestClient(studio_api.app)
    headers = {"Authorization": "Bearer tools-token"}

    search = client.get("/api/v1/tools?server=sample_registry", headers=headers)
    assert search.status_code == 200
    assert search.json()["total"] == 2

    resolved = client.get("/api/v1/tools/sample_registry/lookup_records", headers=headers)
    assert resolved.status_code == 200
    assert resolved.json()["definition_hash_verified"] is True

    profile = client.get("/api/v1/tools/sample_registry/lookup_records/intelligence", headers=headers)
    assert profile.status_code == 200
    body = profile.json()
    assert body["schema"] == "taas.tool-capability-profile/v1"
    assert body["evidence_summary"]["attested"]["verified_records"] == 0
    assert body["execution_enabled"] is False

    missing = client.get("/api/v1/tools/ghost/nothing", headers=headers)
    assert missing.status_code == 404
    missing_intel = client.get("/api/v1/tools/ghost/nothing/intelligence", headers=headers)
    assert missing_intel.status_code == 404
