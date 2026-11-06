from pathlib import Path


def _studio_html() -> str:
    return (Path(__file__).parents[1] / "src" / "taas" / "studio" / "static" / "index.html").read_text(encoding="utf-8")


def test_ux6_workspace_is_linked_and_accessible():
    html = _studio_html()
    for marker in (
        'href="#evidence-diff-impact"',
        'id="evidence-diff-impact"',
        'id="ux6-snapshot-a"',
        'id="ux6-snapshot-b"',
        'id="ux6-compare"',
        'id="ux6-status"',
        'aria-live="polite"',
    ):
        assert marker in html


def test_ux6_accepts_only_ux5_alignment_evidence_exports():
    html = _studio_html()
    start = html.index("// UX-6: compare two user-selected")
    end = html.index("})();", start)
    feature = html[start:end]
    assert 'schema_version!=="taas.alignment-evidence.v1"' in feature
    assert 'Array.isArray(value.findings)' in feature
    assert 'value.fingerprints.goal_spec' in feature
    assert 'value.fingerprints.toolset' in feature
    assert 'value.semantics?.execution_performed!==false' in feature
    assert 'file.size>2*1024*1024' in feature


def test_ux6_diff_is_deterministic_on_finding_identity_and_classifies_changes():
    html = _studio_html()
    start = html.index("// UX-6: compare two user-selected")
    end = html.index("})();", start)
    feature = html[start:end]
    for marker in ('const keyOf=item=>', 'kind:"removed"', 'kind:"modified"',
                   'kind:"added"', 'counts:{added:', 'fingerprint_changes:'):
        assert marker in feature


def test_ux6_reports_alignment_impact_without_overclaiming():
    html = _studio_html()
    start = html.index("// UX-6: compare two user-selected")
    end = html.index("})();", start)
    feature = html[start:end]
    for marker in ('still_matched:', 'now_unmatched:', 'now_incompatible:',
                   'needs_review:', 'execution_performed:false',
                   'execution_record:false', 'authorization_granted:false',
                   'semantic_correctness_proven:false', 'goal_fulfilment_proven:false'):
        assert marker in feature
    assert 'not proof of semantic compatibility' in html


def test_ux6_export_is_user_triggered_and_local_only():
    html = _studio_html()
    start = html.index("// UX-6: compare two user-selected")
    end = html.index("})();", start)
    feature = html[start:end]
    assert 'addEventListener("click"' in feature
    assert 'taas-evidence-diff.json' in feature
    assert 'JSON.stringify(state.result,null,2)' in feature
    for forbidden in ('fetch(', 'apiGet(', 'apiPost(', 'runtimePost(', 'tools/call', 'execute('):
        assert forbidden not in feature


def test_ux6_uses_safe_text_nodes_and_supports_filter_reset():
    html = _studio_html()
    start = html.index("// UX-6: compare two user-selected")
    end = html.index("})();", start)
    feature = html[start:end]
    assert 'textContent=String(text??"")' in feature
    assert 'state.filter=id' in feature
    assert 'ux6-reset' in feature
    assert 'ux6-export' in feature


def test_ux6_does_not_mutate_ux5_snapshot_or_change_experimental_protocol():
    html = _studio_html()
    start = html.index("// UX-6: compare two user-selected")
    end = html.index("})();", start)
    feature = html[start:end]
    assert 'readSnapshot' in feature and 'compareSnapshots' in feature
    assert 'state.result=compareSnapshots(a,b)' in feature
    assert 'alignmentEvidenceSnapshot' not in feature
