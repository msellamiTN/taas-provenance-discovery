"""Core API gap closures from the lifecycle megaplan.

A5 audit cursor pagination + full-ledger verify, A3 /tools facets and
discovery-run diff, A2 agent version diff + sign/revoke parity, A4 verdict
history + evidence freshness batch.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import taas.studio.api as studio_api
from taas.studio import agent_registry, audit_ledger, discovery_runs


@pytest.fixture(autouse=True)
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("TAAS_AUDIT_LEDGER_PATH", str(tmp_path / "audit.sqlite3"))
    monkeypatch.setenv("TAAS_AGENT_REGISTRY_PATH", str(tmp_path / "agents.sqlite3"))
    monkeypatch.setenv("TAAS_DISCOVERY_RUNS_PATH", str(tmp_path / "runs.sqlite3"))
    monkeypatch.setenv("TAAS_WORKSPACES_PATH", str(tmp_path / "workspaces.sqlite3"))
    monkeypatch.setenv("TAAS_EVIDENCE_DB_PATH", str(tmp_path / "evidence.sqlite3"))
    monkeypatch.setenv("TAAS_EVIDENCE_ATTESTATION_KEY", "x" * 40)
    monkeypatch.setenv("TAAS_STUDIO_API_TOKEN", "gap-token")
    yield


@pytest.fixture()
def client():
    return TestClient(studio_api.app)


@pytest.fixture()
def headers():
    return {"Authorization": "Bearer gap-token"}


# ---------- A5: audit cursor pagination + full-ledger verify ----------

def test_audit_events_cursor_pagination(client, headers):
    for i in range(7):
        audit_ledger.append_event("evidence", {"i": i}, {})
    page1 = client.get("/api/v1/audit/events?limit=3", headers=headers).json()
    assert page1["count"] == 3 and page1["has_more"] is True
    cursor = page1["next_cursor"]
    assert isinstance(cursor, int)
    page2 = client.get(
        f"/api/v1/audit/events?limit=3&after_seq={cursor}", headers=headers).json()
    assert page2["count"] == 3
    assert page2["events"][0]["seq"] == page1["events"][-1]["seq"] + 1
    page3 = client.get(
        f"/api/v1/audit/events?limit=3&after_seq={page2['next_cursor']}",
        headers=headers).json()
    assert page3["count"] == 1 and page3["has_more"] is False
    seqs = [e["seq"] for p in (page1, page2, page3) for e in p["events"]]
    assert seqs == sorted(seqs) and len(set(seqs)) == 7


def test_audit_verify_scans_full_ledger():
    for i in range(5):
        audit_ledger.append_event("evidence", {"i": i}, {})
    result = audit_ledger.verify_chain()
    assert result["chain_valid"] is True
    assert result["event_count"] == 5
    assert result["scan_scope"] == "full_ledger"


# ---------- A3: /tools facets + discovery-run diff ----------

def test_tools_search_returns_deterministic_facets(client, headers):
    response = client.get("/api/v1/tools?limit=5", headers=headers)
    assert response.status_code == 200
    body = response.json()
    facets = body["facets"]
    assert set(facets) == {"server", "source", "category"}
    for field, counts in facets.items():
        assert list(counts) == sorted(counts)
        assert sum(counts.values()) == body["total"]


def test_tools_facets_reflect_filters(client, headers):
    response = client.get("/api/v1/tools?limit=1&server=nonexistent-server",
                          headers=headers)
    body = response.json()
    assert body["total"] == 0
    assert all(v == {} for v in body["facets"].values())


def test_tools_category_filter_matches_facet_values(client, headers):
    base = client.get("/api/v1/tools?limit=1", headers=headers).json()
    category = next(iter(base["facets"]["category"]))
    filtered = client.get(f"/api/v1/tools?limit=50&category={category}",
                          headers=headers).json()
    assert filtered["total"] == base["facets"]["category"][category]
    assert all(t["category"] == category for t in filtered["tools"])
    assert list(filtered["facets"]["category"]) == [category]


def _record_run(status, tool_ids, tool_hashes=None, certificate=None):
    return discovery_runs.record_discovery_run(
        goal_spec={"goals": [{"id": "g1"}]},
        request={"goal": "g"},
        tool_source="test",
        tool_ids=tool_ids,
        tool_hashes=tool_hashes or {},
        policy_fingerprint="policy-x",
        status=status,
        certificate=certificate,
        hypergraph_projection={"nodes": 2},
    )


def test_discovery_run_diff(client, headers):
    run_a = _record_run("selected", ["s::a", "s::b"], {"s::a": "h1", "s::b": "h2"})
    run_b = _record_run("abstained", ["s::b", "s::c"], {"s::b": "h3", "s::c": "h4"})
    response = client.get(f"/api/v1/discovery/runs/{run_a}/diff/{run_b}",
                          headers=headers)
    assert response.status_code == 200
    diff = response.json()
    assert diff["schema"] == "taas.discovery-run-diff/v1"
    assert diff["tools"]["added_in_b"] == ["s::c"]
    assert diff["tools"]["removed_in_b"] == ["s::a"]
    assert diff["tools"]["definition_hash_changed"] == ["s::b"]
    assert diff["status"]["same"] is False
    assert diff["digests"]["goal_spec_sha256"]["same"] is True
    assert diff["record_semantics"].endswith("not_execution")
    assert diff["execution_record"] is False


def test_discovery_run_diff_unknown_run(client, headers):
    run_a = _record_run("selected", ["s::a"])
    response = client.get(f"/api/v1/discovery/runs/{run_a}/diff/missing",
                          headers=headers)
    assert response.status_code == 404


# ---------- A2: agent version diff + sign/revoke parity ----------

def _agent_manifest(agent_id="acc-diff", version="1.0.0", tools=None):
    return {
        "apiVersion": "taas.ai/v1alpha1",
        "kind": "Agent",
        "metadata": {"id": agent_id, "version": version, "name": "Diff Agent"},
        "spec": {
            "model": {"provider": "huggingface", "model_id": "Qwen/Qwen2.5-0.5B-Instruct"},
            "instructions": "Decompose objectives conservatively.",
            "tool_allowlist": tools or [],
        },
    }


def _create_publish(client, headers, agent_id, version, tools=None):
    create = client.post("/api/v1/agents", headers=headers,
                         json=_agent_manifest(agent_id, version, tools))
    assert create.status_code == 201, create.text
    assert client.post(
        f"/api/v1/agents/{agent_id}/versions/{version}/validate",
        headers=headers).status_code == 200
    publish = client.post(
        f"/api/v1/agents/{agent_id}/versions/{version}/publish",
        headers=headers, json={})
    assert publish.status_code == 200, publish.text


def test_agent_version_diff(client, headers):
    _create_publish(client, headers, "acc-diff", "1.0.0")
    _create_publish(client, headers, "acc-diff", "2.0.0")
    response = client.get(
        "/api/v1/agents/acc-diff/versions/1.0.0/diff/2.0.0", headers=headers)
    assert response.status_code == 200
    diff = response.json()
    assert diff["schema"] == "taas.agent-version-diff/v1"
    assert diff["manifest_sha256"]["same"] is False
    changed_paths = [c["path"] for c in diff["changes"]["changed_paths"]]
    assert "metadata.version" in changed_paths
    assert diff["execution_record"] is False


def test_agent_version_diff_unknown(client, headers):
    _create_publish(client, headers, "acc-diff2", "1.0.0")
    response = client.get(
        "/api/v1/agents/acc-diff2/versions/1.0.0/diff/9.9.9", headers=headers)
    assert response.status_code == 404


def test_agent_sign_and_signature_status(client, headers):
    _create_publish(client, headers, "acc-sign", "1.0.0")
    sign = client.post("/api/v1/agents/acc-sign/versions/1.0.0/sign",
                       headers=headers,
                       json={"publisher_id": "pub-1", "statement": "release"})
    assert sign.status_code == 201, sign.text
    body = sign.json()
    assert body["signature"]["publisher_id"] == "pub-1"
    assert body["signature_scope"] == "registry_attested_not_portable_identity"
    assert body["tools_authorized"] is False and body["execution_enabled"] is False
    status = client.get("/api/v1/agents/acc-sign/versions/1.0.0/signature",
                        headers=headers)
    assert status.status_code == 200
    assert status.json()["verified"] is True
    assert status.json()["signatures"][0]["publisher_id"] == "pub-1"


def test_agent_sign_requires_published(client, headers):
    create = client.post("/api/v1/agents", headers=headers,
                         json=_agent_manifest("draft-agent", "1.0.0"))
    assert create.status_code == 201
    sign = client.post("/api/v1/agents/draft-agent/versions/1.0.0/sign",
                       headers=headers, json={})
    assert sign.status_code == 409


def test_agent_revoke_blocks_sign_and_is_immutable(client, headers):
    _create_publish(client, headers, "acc-rev", "1.0.0")
    revoke = client.post("/api/v1/agents/acc-rev/versions/1.0.0/revoke",
                         headers=headers, json={"reason": "supply-chain issue"})
    assert revoke.status_code == 200, revoke.text
    assert revoke.json()["revoked"] is True
    status = client.get("/api/v1/agents/acc-rev/versions/1.0.0/revocation",
                        headers=headers).json()
    assert status["revoked"] is True
    assert status["revocation"]["reason"] == "supply-chain issue"
    again = client.post("/api/v1/agents/acc-rev/versions/1.0.0/revoke",
                        headers=headers, json={"reason": "twice"})
    assert again.status_code == 409
    sign = client.post("/api/v1/agents/acc-rev/versions/1.0.0/sign",
                       headers=headers, json={})
    assert sign.status_code == 409
    detail = client.get("/api/v1/agents/acc-rev/versions/1.0.0",
                        headers=headers).json()
    assert detail["revoked"] is True


def test_agent_revoke_requires_non_draft(client, headers):
    client.post("/api/v1/agents", headers=headers,
                json=_agent_manifest("draft-rev", "1.0.0"))
    revoke = client.post("/api/v1/agents/draft-rev/versions/1.0.0/revoke",
                         headers=headers, json={"reason": "too early"})
    assert revoke.status_code == 409


# ---------- A4: verdict history + evidence freshness batch ----------

def test_policy_verdict_persisted_and_history(client, headers):
    _create_publish(client, headers, "acc-hist", "1.0.0")
    first = client.get("/api/v1/agents/acc-hist/versions/1.0.0/policy-verdict",
                       headers=headers)
    assert first.status_code == 200
    history = client.get(
        "/api/v1/agents/acc-hist/versions/1.0.0/policy-verdict/history",
        headers=headers)
    assert history.status_code == 200
    body = history.json()
    assert body["schema"] == "taas.policy-verdict-history/v1"
    assert body["count"] >= 1
    assert body["verdicts"][0]["decision"] == first.json()["decision"]
    assert body["record_semantics"].endswith("not_authorization_or_execution")
    other = client.get(
        "/api/v1/agents/acc-hist/versions/9.9.9/policy-verdict/history",
        headers=headers)
    assert other.status_code == 404


def test_evidence_freshness_batch(client, headers):
    _create_publish(client, headers, "acc-fresh", "1.0.0")
    client.post("/api/v1/agents/acc-fresh/versions/1.0.0/sign",
                headers=headers, json={"publisher_id": "pub-fresh"})
    resource = client.get("/api/v1/agents/acc-fresh/versions/1.0.0",
                          headers=headers).json()
    binding = {"agent_id": "acc-fresh", "version": "1.0.0",
               "manifest_sha256": resource["manifest_sha256"]}
    response = client.post("/api/v1/assurance/evidence/freshness",
                           headers=headers,
                           json={"bindings": [binding, {"agent_id": "nobody"}],
                                 "evidence_type": "publisher_signature"})
    assert response.status_code == 200
    body = response.json()
    assert body["schema"] == "taas.evidence-freshness/v1"
    assert body["count"] == 2
    assert body["results"][0]["status"] == "verified"
    assert body["results"][0]["verified_records"] == 1
    assert body["results"][1]["verified_records"] == 0
    assert body["assessor_claim_truth_verified"] is False
    bad = client.post("/api/v1/assurance/evidence/freshness",
                      headers=headers, json={"bindings": []})
    assert bad.status_code == 422


# ---------- A1: workspace revision provenance ----------

def test_workspace_revision_history_records_field_level_edits(client, headers):
    create = client.post("/api/v1/workspaces", headers=headers,
                         json={"name": "draft-1",
                               "draft": {"goal": "a", "constraints": {"x": 1}}})
    assert create.status_code == 201
    wid = create.json()["workspace_id"]
    update = client.put(f"/api/v1/workspaces/{wid}", headers=headers,
                        json={"revision": 1,
                              "draft": {"goal": "b", "constraints": {"x": 1, "y": 2}}})
    assert update.status_code == 200
    history = client.get(f"/api/v1/workspaces/{wid}/revisions",
                         headers=headers)
    assert history.status_code == 200
    body = history.json()
    assert body["schema"] == "taas.workspace-revision-history/v1"
    assert body["count"] == 2
    rev2 = next(r for r in body["revisions"] if r["revision"] == 2)
    assert rev2["actor"] == "studio-api"
    changed_paths = [c["path"] for c in rev2["changes"]["changed_paths"]]
    assert "goal" in changed_paths
    assert rev2["changes"]["added_paths"] == ["constraints.y"]
    assert rev2["changes"]["removed_paths"] == []
    rev1 = next(r for r in body["revisions"] if r["revision"] == 1)
    assert rev1["changes"]["kind"] == "created"
    assert body["record_semantics"].endswith("not_correctness_not_execution")
    unknown = client.get("/api/v1/workspaces/nope/revisions", headers=headers)
    assert unknown.status_code == 404
    # Deleting a draft cascades its revision history.
    assert client.delete(f"/api/v1/workspaces/{wid}", headers=headers).status_code == 200
    assert client.get(f"/api/v1/workspaces/{wid}/revisions",
                      headers=headers).status_code == 404


# ---------- A1: GoalSpec template catalog ----------

def test_goalspec_template_catalog_lists_and_details(client, headers):
    resp = client.get("/api/v1/goalspec/templates", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["schema"] == "taas.goalspec-template-list/v1"
    assert body["count"] >= 3
    ids = [t["id"] for t in body["templates"]]
    assert ids == sorted(ids)
    assert all("goal_spec" not in t for t in body["templates"])  # metadata only
    assert all(len(t["spec_sha256"]) == 64 for t in body["templates"])
    assert "not_authorization" in body["semantics"]

    detail = client.get(f"/api/v1/goalspec/templates/{ids[0]}", headers=headers)
    assert detail.status_code == 200
    d = detail.json()
    assert d["schema"] == "taas.goalspec-template/v1"
    assert "goals" in d["template"]["goal_spec"]
    assert "not_validation" in d["semantics"]

    missing = client.get("/api/v1/goalspec/templates/nope", headers=headers)
    assert missing.status_code == 404


def test_goalspec_template_draft_validates_through_goals_validate(client, headers):
    # Every catalog draft must pass the canonical validation path it claims to feed.
    resp = client.get("/api/v1/goalspec/templates", headers=headers)
    for t in resp.json()["templates"]:
        detail = client.get(f"/api/v1/goalspec/templates/{t['id']}",
                            headers=headers).json()
        val = client.post("/api/v1/goals/validate", headers=headers,
                          json=detail["template"]["goal_spec"])
        assert val.status_code == 200, t["id"]
        assert val.json()["valid"] is True


# ---------- A5: per-agent recorded activity ----------

def test_agent_version_activity_reports_only_recorded_data(client, headers):
    _create_publish(client, headers, "act-agent", "1.0.0")
    _create_publish(client, headers, "act-agent", "2.0.0")

    resp = client.get("/api/v1/agents/act-agent/versions/1.0.0/activity",
                      headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["schema"] == "taas.agent-version-activity/v1"
    assert body["lifecycle_state"] == "published"

    # Lifecycle counts are version-scoped from the persisted event column —
    # version 1.0.0 shows created+validated+published, never version 2.0.0's.
    events = body["recorded_activity"]["lifecycle_events"]
    assert events["state"] == "recorded"
    assert events["count"] == 3
    assert events["latest"]["to_state"] == "published"
    assert events["latest"]["version"] == "1.0.0"

    # No verdicts or approvals recorded yet — counts are zero, not synthetic.
    assert body["recorded_activity"]["policy_verdicts"]["count"] == 0
    assert body["recorded_activity"]["human_approvals"]["verified_count"] == 0
    assert body["recorded_activity"]["revocation"]["state"] == "recorded"
    assert body["recorded_activity"]["revocation"]["record"] is None

    # Unsupported metrics stay explicitly unavailable with the architectural reason.
    assert "per-agent latency" in body["unsupported_metrics"]
    assert "execution/run count" in body["unsupported_metrics"]
    assert "governed execution" in body["unavailable_reason"]
    assert body["semantics"].endswith("not_execution_proof")
    assert body["authorization_granted"] is False
    assert body["execution_performed"] is False


def test_agent_version_activity_counts_verdicts_and_approvals_separately(client, headers):
    _create_publish(client, headers, "act-verdict", "1.0.0")

    verdict = client.get("/api/v1/agents/act-verdict/versions/1.0.0/policy-verdict",
                         headers=headers)
    assert verdict.status_code == 200

    approval = client.post("/api/v1/agents/act-verdict/versions/1.0.0/approvals",
                           headers=headers, json={"note": "release check"})
    assert approval.status_code == 201, approval.text

    resp = client.get("/api/v1/agents/act-verdict/versions/1.0.0/activity",
                      headers=headers)
    body = resp.json()
    ra = body["recorded_activity"]
    assert ra["policy_verdicts"]["count"] == 1
    assert ra["policy_verdicts"]["latest_recorded_at"] is not None
    # Approvals come only from human_approval evidence records.
    assert ra["human_approvals"]["verified_count"] == 1
    assert ra["human_approvals"]["audit_approval_events"]["count"] == 1
    # Verified evidence of other types is reported separately, never as approval.
    assert ra["evidence_records"]["verified_non_approval_count"] == 0


def test_agent_version_activity_404_and_auth(client, headers):
    assert client.get("/api/v1/agents/ghost/versions/1.0.0/activity",
                      headers=headers).status_code == 404
    _create_publish(client, headers, "act-auth", "1.0.0")
    assert client.get("/api/v1/agents/act-auth/versions/1.0.0/activity").status_code == 401


def test_list_events_version_filter_is_exact_match(monkeypatch, tmp_path):
    monkeypatch.setenv("TAAS_AGENT_REGISTRY_PATH", str(tmp_path / "a.sqlite3"))
    manifest = _agent_manifest("vfilter", "1.0.0")
    agent_registry.create_draft(manifest)
    manifest2 = _agent_manifest("vfilter", "2.0.0")
    manifest2["metadata"]["version"] = "2.0.0"
    agent_registry.create_draft(manifest2)

    v1 = agent_registry.list_events(agent_id="vfilter", version="1.0.0")
    assert v1["count"] == 1
    assert all(e["version"] == "1.0.0" for e in v1["events"])
    none = agent_registry.list_events(agent_id="vfilter", version="9.9.9")
    assert none["count"] == 0
    all_events = agent_registry.list_events(agent_id="vfilter")
    assert all_events["count"] == 2


def test_agent_version_activity_reports_unavailable_not_zero_on_source_failure(client, headers, monkeypatch):
    """An unreadable evidence store must surface state=unavailable, never a
    synthesized count: 'no approvals' and 'cannot check' are different claims."""
    from taas.studio import assurance_evidence

    _create_publish(client, headers, "act-unavail", "1.0.0")

    def _boom(*args, **kwargs):
        raise assurance_evidence.EvidenceError("evidence store unavailable")

    monkeypatch.setattr(assurance_evidence, "list_verified_evidence_for_subject", _boom)
    resp = client.get("/api/v1/agents/act-unavail/versions/1.0.0/activity",
                      headers=headers)
    assert resp.status_code == 200
    ra = resp.json()["recorded_activity"]
    # Evidence-backed blocks report unavailable, not zero.
    assert ra["human_approvals"]["state"] == "unavailable"
    assert "verified_count" not in ra["human_approvals"] or ra["human_approvals"]["verified_count"] is None
    assert "reason" in ra["human_approvals"]
    assert ra["evidence_records"]["state"] == "unavailable"
    # Independent sources still report recorded values.
    assert ra["lifecycle_events"]["state"] == "recorded"
    assert ra["lifecycle_events"]["count"] == 3
    assert ra["policy_verdicts"]["state"] == "recorded"
