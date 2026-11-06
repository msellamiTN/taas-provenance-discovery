from __future__ import annotations

import json

import pytest

from taas.provenance import EvidenceStore
from taas.studio import tool_registry, tool_service
from tests.test_tool_retrieval_explanation import TOOLS, SNAPSHOT


@pytest.fixture(autouse=True)
def registry_snapshot(monkeypatch):
    monkeypatch.setattr(tool_registry, "load_processed", lambda: SNAPSHOT)
    tool_registry.reset_registry_caches()
    tool_service.reset_tool_service_caches()
    yield
    tool_registry.reset_registry_caches()
    tool_service.reset_tool_service_caches()


_TOOLS_BY_ID = {t.id: t for t in TOOLS}


def _definition_hash(tool_id: str) -> str:
    return _TOOLS_BY_ID[tool_id].definition_hash()


def _write_store(tmp_path, records) -> str:
    path = tmp_path / "evidence.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")
    return str(path)


def test_loader_parses_obs_and_att_records(tmp_path):
    h = _definition_hash("sample_registry::lookup_records")
    path = _write_store(tmp_path, [
        {"tool": "sample_registry::lookup_records", "definition_hash": h,
         "prop": "read_only", "ptype": "obs", "kappa": 0.9, "method": "probe"},
        {"tool": "sample_registry::lookup_records", "definition_hash": h,
         "prop": "no_delete", "ptype": "att", "signer": "registry-A", "method": "attestation"},
        {"tool": "sample_registry::lookup_records", "definition_hash": h,
         "effects": ["read(db)"]},
        {"garbage": True},
        "not json at all",
    ])
    store = tool_service.load_evidence_store(path)
    props = store.get("sample_registry::lookup_records", h)
    assert props["read_only"][0].ptype == "obs"
    assert props["read_only"][0].kappa == 0.9
    assert props["no_delete"][0].ptype == "att"
    assert store.effects("sample_registry::lookup_records", h) == ["read(db)"]


def test_loader_rejects_lex_and_ann_records(tmp_path):
    h = _definition_hash("files::read_file")
    path = _write_store(tmp_path, [
        {"tool": "files::read_file", "definition_hash": h,
         "prop": "read_only", "ptype": "lex"},
        {"tool": "files::read_file", "definition_hash": h,
         "prop": "read_only", "ptype": "ann"},
    ])
    store = tool_service.load_evidence_store(path)
    assert store.get("files::read_file", h) == {}


def test_engine_contracts_upgrade_with_store(tmp_path, monkeypatch):
    h = _definition_hash("sample_registry::lookup_records")
    path = _write_store(tmp_path, [
        {"tool": "sample_registry::lookup_records", "definition_hash": h,
         "prop": "read_only", "ptype": "obs", "kappa": 1.0, "method": "probe"},
    ])
    path2 = _write_store(tmp_path, [
        {"tool": "sample_registry::lookup_records", "definition_hash": h,
         "prop": "read_only", "ptype": "obs", "kappa": 1.0, "method": "probe"},
        {"tool": "sample_registry::lookup_records", "definition_hash": h,
         "effects": ["read(query)"]},
    ])
    monkeypatch.setenv(tool_service.EVIDENCE_STORE_ENV, path2)
    tool_service.reset_tool_service_caches()
    engine = tool_service._tool_engine()
    contract = engine.retriever.contracts["sample_registry::lookup_records"]
    strengths = engine.index.strengths["sample_registry::lookup_records"]
    # obs at kappa=1.0 -> 0.55 + 0.20*1.0 = 0.75, exceeding bare lex strength
    assert strengths["read_only"] >= 0.7
    # observed effects upgrade the effect-clause provenance kind
    assert contract.eff_record.ptype == "obs"


def test_absent_store_keeps_current_behavior(tmp_path, monkeypatch):
    monkeypatch.delenv(tool_service.EVIDENCE_STORE_ENV, raising=False)
    tool_service.reset_tool_service_caches()
    assert tool_service.configured_evidence_store() is None
    result = tool_service.explainable_retrieve(
        "read records", None, policy=__import__("taas.policy", fromlist=["Policy"]).Policy.make("t"),
        k=2, type_filter=False)
    assert result["evidence_store_wired"] is False


def test_missing_file_reports_unwired(tmp_path, monkeypatch):
    monkeypatch.setenv(tool_service.EVIDENCE_STORE_ENV, str(tmp_path / "nope.jsonl"))
    tool_service.reset_tool_service_caches()
    assert tool_service.configured_evidence_store() is None


def test_responses_report_wired_flag(tmp_path, monkeypatch):
    h = _definition_hash("files::read_file")
    path = _write_store(tmp_path, [
        {"tool": "files::read_file", "definition_hash": h,
         "prop": "read_only", "ptype": "obs", "kappa": 0.8},
    ])
    monkeypatch.setenv(tool_service.EVIDENCE_STORE_ENV, path)
    tool_service.reset_tool_service_caches()
    from taas.policy import Policy
    result = tool_service.explainable_retrieve(
        "read", None, policy=Policy.make("t"), k=2, type_filter=False)
    assert result["evidence_store_wired"] is True
    elig = tool_service.eligibility_explain(Policy.make("t"), ["files::read_file"])
    assert elig["evidence_store_wired"] is True
