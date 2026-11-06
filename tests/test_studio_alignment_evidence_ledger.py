from pathlib import Path


def _studio_html() -> str:
    return (Path(__file__).parents[1] / "src/taas/studio/static/index.html").read_text(encoding="utf-8")


def test_evidence_ledger_controls_are_present_and_accessible():
    html = _studio_html()
    for marker in (
        'id="goal-evidence-reviewer"',
        'id="goal-evidence-snapshot"',
        'id="goal-evidence-ack"',
        'id="goal-evidence-export"',
        'id="goal-evidence-status"',
        'id="goal-evidence-findings"',
        'aria-live="polite"',
        "Alignment review &amp; evidence ledger",
    ):
        assert marker in html


def test_snapshot_is_explicit_and_page_session_only():
    html = _studio_html()
    start = html.index("// UX-5: page-session evidence snapshots")
    end = html.index('const syncGoalSpec = () => {', start)
    feature = html[start:end]
    assert 'goal-evidence-snapshot' in feature
    assert 'not persisted by TaaS Core' in html
    assert 'schema_version:"taas.alignment-evidence.v1"' in feature
    assert 'captured_at:new Date().toISOString()' in feature


def test_fingerprints_cover_goal_contract_and_tool_schema_metadata():
    html = _studio_html()
    start = html.index("// UX-5: page-session evidence snapshots")
    end = html.index('const syncGoalSpec = () => {', start)
    feature = html[start:end]
    assert 'input_schema:tool.input_schema??null' in feature
    assert 'output_schema:tool.output_schema??null' in feature
    assert 'goal_spec:evidenceFingerprint' in feature
    assert 'toolset:evidenceFingerprint' in feature
    assert 'FNV-1a 32-bit (non-cryptographic)' in feature


def test_evidence_has_schema_path_and_source_traceability():
    html = _studio_html()
    start = html.index("// UX-5: page-session evidence snapshots")
    end = html.index('const syncGoalSpec = () => {', start)
    feature = html[start:end]
    for marker in ('schema_direction:item.direction', 'schema_path:item.path',
                   'semantic_label:item.type', 'source:inputs.source',
                   'goal_id:goalId', 'required_label:String(label)'):
        assert marker in feature


def test_acknowledgement_is_explicit_and_only_metadata_review():
    html = _studio_html()
    start = html.index("// UX-5: page-session evidence snapshots")
    end = html.index('const syncGoalSpec = () => {', start)
    feature = html[start:end]
    assert 'addEventListener("click"' in feature
    assert 'status:"acknowledged"' in feature
    assert 'acknowledged_at:new Date().toISOString()' in feature
    assert 'not authorization or proof' in feature


def test_changed_goal_or_toolset_invalidates_snapshot_before_ack_or_export():
    html = _studio_html()
    start = html.index("// UX-5: page-session evidence snapshots")
    end = html.index('const syncGoalSpec = () => {', start)
    feature = html[start:end]
    assert 'ensureEvidenceFresh' in feature
    assert 'current.goal_spec===captured.goal_spec&&current.toolset===captured.toolset' in feature
    assert 'invalidateAlignmentEvidence("GoalSpec editor changed")' in html
    assert 'invalidateAlignmentEvidence("GoalSpec or toolset changed since snapshot")' in html


def test_export_is_json_and_does_not_export_credentials_or_full_tool_payloads():
    html = _studio_html()
    start = html.index("// UX-5: page-session evidence snapshots")
    end = html.index('const syncGoalSpec = () => {', start)
    feature = html[start:end]
    assert 'JSON.stringify(payload,null,2)' in feature
    assert 'taas-alignment-evidence.json' in feature
    assert 'Authorization' not in feature
    assert 'token' not in feature.lower()
    assert 'evidence:matches.map' in feature


def test_evidence_semantics_never_claim_execution_or_authorization():
    html = _studio_html()
    start = html.index("// UX-5: page-session evidence snapshots")
    end = html.index('const syncGoalSpec = () => {', start)
    feature = html[start:end]
    for marker in ('execution_performed:false', 'execution_record:false',
                   'authorization_granted:false', 'semantic_correctness_proven:false',
                   'goal_fulfilment_proven:false'):
        assert marker in feature


def test_evidence_feature_adds_no_api_or_tool_execution_calls():
    html = _studio_html()
    start = html.index("// UX-5: page-session evidence snapshots")
    end = html.index('const syncGoalSpec = () => {', start)
    feature = html[start:end]
    for forbidden in ('fetch(', 'apiGet(', 'apiPost(', 'runtimePost(', 'tools/call', 'execute('):
        assert forbidden not in feature
