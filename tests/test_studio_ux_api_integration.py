"""UX API-integration wiring tests for devin/studio-ux-integration-v1.

Covers the M3 increment that connects the previously static UX-7/UX-8/UX-9
surfaces to the real authenticated Core endpoints while preserving every
execution boundary (no invoke route, no fabricated operational data).
"""

from fastapi.testclient import TestClient

from taas.studio.api import app

client = TestClient(app)


def _studio_html() -> str:
    response = client.get("/")
    assert response.status_code == 200
    return response.text


def test_ux7_diagnostics_panel_queries_real_runtime_endpoints():
    html = _studio_html()
    assert 'id="ux7-diag-refresh"' in html
    assert "apiGet('/api/v1/runtime/status')" in html
    assert "apiGet('/api/v1/runtime/hardware')" in html
    assert "apiGet('/api/v1/models/runtime')" in html
    # Diagnostics must remain labeled as observations, not execution evidence.
    assert "not execution evidence" in html


def test_ux7_diagnostics_does_not_fabricate_operational_data():
    html = _studio_html()
    # Sessions, logs, traces and metrics still honestly report that no
    # runtime integration exists — the diagnostics wiring must not invent
    # session records or worker telemetry.
    assert "No execution sessions" in html
    assert "No runtime logs" in html
    assert "No distributed traces" in html
    assert "No runtime metrics" in html
    # The execution-disabled banner and unavailable run control are preserved.
    assert "Execution is disabled" in html


def test_ux8_governance_tab_wires_real_core_endpoints():
    html = _studio_html()
    assert 'id="ux8-tab-governance"' in html
    assert 'id="ux8-panel-governance"' in html
    assert "'/release-readiness'" in html
    assert "'/approvals'" in html
    assert "'/authorization/preflight'" in html
    assert "'/api/v1/policy/evaluate'" in html
    assert 'id="ux8-agents-list"' in html
    assert "apiGet('/api/v1/agents?limit=50')" in html


def test_ux8_governance_distinguishes_approval_readiness_authorization_execution():
    html = _studio_html()
    assert "grant no execution rights" in html or "grants no execution" in html
    assert "never authorizes or invokes a tool" in html
    assert "a readiness verdict, not an authorization or execution" in html
    # Governance surface adds no mutation controls (approval ceremony POST is
    # not exposed — the workspace is read-only observation).
    governance_panel = html.split('id="ux8-panel-governance"', 1)[1].split("</section>", 1)[0]
    assert "approvals" in governance_panel
    assert "POST" not in governance_panel.split("<pre")[0]


def test_ux9_load_from_objective_uses_core_prepare():
    html = _studio_html()
    assert 'id="ux9-load-from-objective"' in html
    assert 'id="ux9-objective-input"' in html
    assert '"/api/v1/objectives/prepare"' in html
    assert "objective_skill_traceability" in html
    # Failure path must stay honest — the paste flow remains available.
    assert "pasting a traceability record still works" in html


def test_integration_adds_no_execution_or_invoke_route():
    html = _studio_html()
    # The wiring must not introduce tool-invocation affordances.
    assert "apiPost(\"/api/v1/tools" not in html
    assert "execution_performed:false" in html
    assert "execution_record:false" in html


def test_shared_apipost_helper_preserves_auth_and_error_handling():
    html = _studio_html()
    assert "const apiPost = async (path, body) =>" in html
    helper = html.split("const apiPost = async (path, body) => {", 1)[1].split("};", 1)[0]
    assert "Bearer " in helper
    assert "markStudioAuthRejected()" in helper
    assert "formatApiError" in helper


def test_ux10_release_center_queries_readonly_governance_endpoints():
    html = _studio_html()
    assert 'id="release-center"' in html
    assert 'id="ux10-refresh-all"' in html
    for suffix in ('"/policy-verdict"', '"/release-readiness"', '"/approvals"'):
        assert suffix in html
    section = html.split('id="release-center"', 1)[1].split("</section>", 1)[0]
    assert "NOT GRANTED" in section
    assert "GET requests only" in section
    assert "apiPost(" not in section


def test_ux11_operations_center_reports_honest_failures_and_no_execution():
    html = _studio_html()
    assert 'id="operations-command-center"' in html
    assert 'id="ux11-refresh"' in html
    for endpoint in (
        "/api/v1/runtime/status",
        "/api/v1/models/runtime",
        "/api/v1/discovery/runs?limit=50",
        "/api/v1/audit/verify",
    ):
        assert endpoint in html
    assert "No execution performed" in html


def test_ux12_provenance_inspector_fails_closed_on_malformed_ids():
    html = _studio_html()
    assert 'id="provenance-inspector"' in html
    assert 'id="ux12-inspect"' in html
    assert "No request was sent" in html
    assert "failed closed" in html
    assert "NOT VERIFIED" in html


def test_ux13_ux14_lifecycle_centers_list_registry_versions():
    html = _studio_html()
    assert 'id="agent-lifecycle-center"' in html
    assert 'id="skill-lifecycle-center"' in html
    assert 'id="ux13-refresh"' in html
    assert 'id="ux14-refresh"' in html
    assert "/api/v1/agents?limit=500" in html
    assert "/api/v1/skills?limit=500" in html


def test_vocabulary_drawer_and_policy_presets_are_reference_only():
    html = _studio_html()
    assert 'id="vocab-load"' in html
    assert 'id="vocab-filter"' in html
    assert '"/api/v1/reference/vocabulary"' in html
    assert "not verified evidence" in html
    for preset in ("read-only", "egress-limited", "strict-evidence"):
        assert f'data-policy-preset="{preset}"' in html
    assert "grants no authorization" in html
    assert "invalidateHumanReview" in html


def test_workspace_drafts_ui_uses_explicit_save_restore():
    html = _studio_html()
    assert 'id="ws-save"' in html
    assert 'id="ws-refresh"' in html
    assert 'id="ws-name"' in html
    assert '"/api/v1/workspaces' in html
    assert "not an execution record" in html or "execution record" in html
    # Draft restore must keep the human-review gate invalid.
    assert "restore rewrites the request JSON" in html.lower() or "restored into the request JSON" in html


def test_reproducibility_envelope_links_certificate_to_run_record():
    html = _studio_html()
    assert 'id="repro-panel"' in html
    assert 'id="repro-inspect"' in html
    assert "discovery_run_id" in html
    assert '"/api/v1/discovery/runs/"+encodeURIComponent(runId)' in html
    assert "not tool invocation" in html


def test_ux15_tool_registry_governance_center_uses_read_only_endpoints():
    html = _studio_html()
    assert 'id="tool-registry-governance-center"' in html
    assert 'id="ux15-refresh"' in html
    assert 'id="ux15-refresh-snapshots"' in html
    assert "/api/v1/tools?" in html
    assert '"/api/v1/mcp/servers"' in html
    assert '"/api/v1/mcp/registry/snapshots' in html
    # UX-15 is an inventory/inspection surface — no tool invocation.
    section = html[html.index('id="tool-registry-governance-center"'):html.index("</section>", html.index('id="tool-registry-governance-center"'))]
    assert "No MCP connection, tool call" in section


def test_ux16_selection_workbench_wires_retrieval_eligibility_compare():
    html = _studio_html()
    assert 'id="ux16-tool-selection-workbench"' in html
    assert 'id="ux16-retrieve"' in html
    assert 'id="ux16-eligibility"' in html
    assert 'id="ux16-compare"' in html
    assert "/api/v1/tools/retrieve" in html
    assert "/api/v1/tools/eligibility" in html
    assert "/api/v1/tools/compare" in html
    # Honest capability semantics disclaimer on the candidate table.
    assert "not quality or permission" in html and "Structural analysis is not authorization" in html


def test_ux17_policy_designer_is_evaluation_only():
    html = _studio_html()
    assert 'id="ux17-policy-governance"' in html
    assert 'id="ux17-evaluate"' in html
    assert "/api/v1/policy/evaluate" in html
    section = html[html.index('id="ux17-policy-governance"'):html.index("</section>", html.index('id="ux17-policy-governance"'))]
    assert "not authorization" in section


def test_ux18_policy_test_workbench_persists_nothing():
    html = _studio_html()
    assert 'id="ux18-policy-test-workbench"' in html
    assert 'id="ux18-run"' in html
    section = html[html.index('id="ux18-policy-test-workbench"'):html.index("</section>", html.index('id="ux18-policy-test-workbench"'))]
    assert "not persisted" in section
    # Verdict results must be labeled MATCH/MISMATCH/ERROR, not executed.
    assert "MATCH" in html and "MISMATCH" in html


def test_ux19_audit_timeline_is_read_only_ledger_inspection():
    html = _studio_html()
    assert 'id="ux19-governance-audit-timeline"' in html
    assert 'id="ux19-load"' in html
    assert 'id="ux19-verify"' in html
    assert "/api/v1/audit/events" in html
    assert "/api/v1/audit/verify" in html
    section = html[html.index('id="ux19-governance-audit-timeline"'):html.index("</section>", html.index('id="ux19-governance-audit-timeline"'))]
    # Tamper-evidence is not truth/authorization/execution proof.
    assert "not proof of execution" in section
    assert "maximum 1,000" in section and "not necessarily complete" in html
    # Linked-evidence inspection reuses the real evidence route only for
    # exact SHA-256 ids found in stored records — no inferred references.
    assert "evidence_id" in html and "assurance/evidence/" in html
    assert "no reference inferred" in html or "No exact lowercase SHA-256" in html


def test_ux20_compliance_dashboard_keeps_demo_and_live_strictly_separated():
    html = _studio_html()
    assert 'id="ux20-compliance-dashboard"' in html
    assert 'id="ux20-demo-mode"' in html
    assert 'id="ux20-live-mode"' in html
    section = html[html.index('id="ux20-compliance-dashboard"'):html.index("</section>", html.index('id="ux20-compliance-dashboard"'))]
    # Demo provenance must be unmistakable.
    assert "DEMO DATA · ILLUSTRATIVE" in section
    assert "DEMO DATA — NOT LIVE / NOT VERIFIED" in section
    assert "not a compliance result" in section
    # Live mode must never estimate missing APIs.
    assert "never estimated" in section or "Unavailable" in html
    # Live mode only queries the two real audit endpoints.
    assert "/api/v1/audit/events?limit=1000" in html
    assert "/api/v1/audit/verify" in html
    assert "unsupported compliance panels remain unavailable" in html


def test_ux21_remediation_workbench_separates_demo_from_bounded_live():
    html = _studio_html()
    assert 'id="ux21-remediation-workbench"' in html
    assert 'id="ux21-demo-mode"' in html
    assert 'id="ux21-live-mode"' in html
    section = html[html.index('id="ux21-remediation-workbench"'):html.index("</section>", html.index('id="ux21-remediation-workbench"'))]
    assert "DEMO DATA · ILLUSTRATIVE" in section
    assert "DEMO DATA — NOT LIVE / NOT VERIFIED" in section
    assert "not a risk register" in section or "no general risk register" in section.lower()
    assert "No publish, activation, authorization or execution" in section
    # Live mode only queries the two real audit endpoints and marks the
    # unsupported risk/remediation panels unavailable rather than estimating.
    assert "/api/v1/audit/events?limit=1000" in html
    assert "/api/v1/audit/verify" in html
    assert "unsupported_live_capabilities" in html
    assert '"Unavailable"' in html


def test_ux22_agent_observability_bounded_live_and_hidden_demo():
    html = _studio_html()
    assert 'id="ux22-agent-observability"' in html
    assert 'id="ux22-demo-mode"' in html
    assert 'id="ux22-live-mode"' in html
    assert "DEMO DATA · ILLUSTRATIVE" in html
    # Live mode queries only real read-only routes.
    for path in ("/api/v1/agents?limit=500", "/api/v1/agents/events?limit=1000",
                 "/api/v1/discovery/runs?limit=100", "/api/v1/runtime/status",
                 "/api/v1/runtime/hardware", "/api/v1/models/runtime"):
        assert path in html
    # Demo visuals must be hidden in live mode (not merely overwritten).
    assert "u22-live-mode .u22-chart" in html and "display:none" in html
    # Boundary: no lifecycle mutation, deployment, invocation or execution.
    assert "No Agent registration, lifecycle mutation, deployment" in html or "not proof of Agent execution" in html


def test_ux23_discovery_composition_bounded_live_and_in_wrapper_scope():
    html = _studio_html()
    assert 'id="ux23-discovery-composition"' in html
    assert 'id="ux23-demo-mode"' in html
    assert 'id="ux23-live-mode"' in html
    assert "DEMO DATA · ILLUSTRATIVE" in html
    assert "/api/v1/discovery/runs?limit=100" in html
    # Strict record semantics: persisted runs are pre-execution observations.
    assert "observation_of_pre_execution_analysis_not_execution" in html
    assert "not execution outcomes" in html or "pre-execution analysis" in html
    # Scope regression: the UX-23 IIFE must sit inside the outer script
    # wrapper where readJsonResponse/formatApiError are defined (a top-level
    # placement renders live mode dead with "readJsonResponse is not defined").
    ux23 = html.index("// UX-23:")
    wrapper_close = html.rindex("})();", 0, html.index("</script>"))
    assert ux23 < wrapper_close
