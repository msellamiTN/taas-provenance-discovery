from pathlib import Path


def _studio_html() -> str:
    return (Path(__file__).parents[1] / "src/taas/studio/static/index.html").read_text(encoding="utf-8")


def test_goal_alignment_panel_is_read_only_and_has_accessible_status():
    html = _studio_html()
    for marker in (
        'id="goal-alignment-refresh"',
        'id="goal-alignment-summary"',
        'id="goal-alignment-body"',
        'aria-live="polite"',
        "Toolset-to-Goal alignment inspector",
    ):
        assert marker in html


def test_alignment_compares_only_explicit_taas_semantic_schema_extensions():
    html = _studio_html()
    start = html.index("// UX-4: conservative comparison of explicit TaaS semantic labels only.")
    end = html.index('const syncGoalSpec = () => {', start)
    feature = html[start:end]
    assert 'x-taas-semantic-type' in feature
    assert 'x-taas-semantic-types' in feature
    assert 'tool.input_schema' in feature
    assert 'tool.output_schema' in feature
    assert 'Object.keys(node.properties).sort()' in feature
    assert 'node.items' in feature
    assert 'node.prefixItems' in feature


def test_alignment_does_not_infer_semantics_from_json_schema_or_tool_text():
    html = _studio_html()
    start = html.index("// UX-4: conservative comparison of explicit TaaS semantic labels only.")
    end = html.index('const syncGoalSpec = () => {', start)
    feature = html[start:end]
    assert 'description' not in feature
    assert 'annotations' not in feature
    assert 'inputSet.has(tool.name)' not in feature
    assert 'outputSet.has(tool.name)' not in feature
    assert 'inputLabels.map(x=>x.type)' in feature
    assert 'outputLabels.map(x=>x.type)' in feature
    assert 'node.type' not in feature
    assert 'node.format' not in feature


def test_alignment_is_exact_label_only_and_keeps_inputs_and_outputs_separate():
    html = _studio_html()
    start = html.index("// UX-4: conservative comparison of explicit TaaS semantic labels only.")
    end = html.index('const syncGoalSpec = () => {', start)
    feature = html[start:end]
    assert 'inputSet=new Set(inputLabels.map(x=>x.type))' in feature
    assert 'outputSet=new Set(outputLabels.map(x=>x.type))' in feature
    assert 'inputSet.has(type)' in feature
    assert 'outputSet.has(out)' in feature
    assert 'includes(' not in feature


def test_alignment_uses_current_registry_basket_or_canonical_request_tools():
    html = _studio_html()
    start = html.index('const renderGoalToolAlignment = () => {')
    end = html.index('$("goal-alignment-refresh").addEventListener', start)
    feature = html[start:end]
    assert 'bench.selectedTools.values()' in feature
    assert 'request.tools' in feature
    assert 'readRequest()' in feature


def test_alignment_handles_empty_and_unlabelled_metadata_without_claiming_coverage():
    html = _studio_html()
    start = html.index('const renderGoalToolAlignment = () => {')
    end = html.index('$("goal-alignment-refresh").addEventListener', start)
    feature = html[start:end]
    assert 'No tool metadata supplied' in feature
    assert 'Not comparable: selected schemas contain no explicit TaaS semantic labels' in feature
    assert 'no exact output-label match' in feature
    assert 'No GoalSpec goals are available.' in feature


def test_alignment_disclaimer_rejects_semantic_correctness_and_execution_claims():
    html = _studio_html()
    start = html.index('class="goal-alignment-panel"')
    end = html.index('</section>', start)
    panel = html[start:end]
    for phrase in (
        "not proof of semantic compatibility",
        "tool correctness",
        "policy eligibility",
        "execution",
        "x-taas-semantic-type",
    ):
        assert phrase in panel


def test_alignment_adds_no_api_calls_or_execution_actions():
    html = _studio_html()
    start = html.index("// UX-4: conservative comparison of explicit TaaS semantic labels only.")
    end = html.index('const syncGoalSpec = () => {', start)
    feature = html[start:end]
    for forbidden in ("fetch(", "apiGet(", "apiPost(", "runtimePost(", "tools/call", "execute("):
        assert forbidden not in feature
