from pathlib import Path


def _studio_html() -> str:
    return (Path(__file__).parents[1] / "src/taas/studio/static/index.html").read_text(encoding="utf-8")


def test_tool_registry_exposes_detail_inspector_and_selection_basket():
    html = _studio_html()
    for marker in (
        'class="bench-tool-inspector"',
        'id="bench-tool-inspector-status"',
        'id="bench-tool-inspector-data"',
        'id="bench-selection-basket"',
        'id="bench-clear-tools"',
        'Replace discovery toolset with basket',
    ):
        assert marker in html


def test_inspector_displays_only_returned_schema_effect_and_provenance_metadata():
    html = _studio_html()
    start = html.index("const inspectBenchTool = tool => {")
    end = html.index("const invalidateBenchmarkTaskContext", start)
    feature = html[start:end]
    for field in ("input_schema", "output_schema", "declared_effects", "annotations", "source", "source_id", "dataset_id"):
        assert field in feature
    assert "textContent=JSON.stringify(detail,null,2)" in feature
    assert "Not reported" in feature


def test_registry_inspection_uses_safe_dom_rendering():
    html = _studio_html()
    start = html.index("const inspectBenchTool = tool => {")
    end = html.index("const invalidateBenchmarkTaskContext", start)
    feature = html[start:end]
    assert "innerHTML" not in feature
    assert "textContent" in feature
    assert "replaceChildren" in feature


def test_selection_basket_survives_registry_pagination_and_filtering():
    html = _studio_html()
    start = html.index("const loadTools = async () => {")
    end = html.index('$("bench-task-prev").addEventListener', start)
    loader = html[start:end]
    assert "bench.selectedTools.has(t.id)" in loader
    assert "bench.selectedTools.set(t.id,t)" in loader
    assert "renderBenchSelectionBasket()" in loader
    assert "bench.selectedTools.clear()" not in loader
    assert 'id="bench-tool-prev"' in html and 'id="bench-tool-next"' in html


def test_toolset_replacement_is_deterministic_and_replaces_not_appends():
    html = _studio_html()
    start = html.index("const syncBenchmarkToolsToRequest = () => {")
    end = html.index("const renderBenchSelectionBasket", start)
    sync = html[start:end]
    assert "bench.selectedTools.entries()" in sync
    assert ".sort(" in sync
    assert "body.tools=ordered.map" in sync
    assert "body.tools.push" not in sync
    assert "input_schema:t.input_schema||{}" in sync


def test_explicit_replace_invalidates_review_and_reports_replacement():
    html = _studio_html()
    start = html.index('$("bench-add-tools").addEventListener("click",()=>{')
    end = html.index('$("bench-clear-tools").addEventListener', start)
    handler = html[start:end]
    assert "syncBenchmarkToolsToRequest()" in handler
    assert "invalidateHumanReview()" in handler
    assert '$("bench-goal-review").checked=false' in handler
    assert "deterministically replaced" in handler
    assert "basket is empty" in handler.lower()


def test_basket_remove_and_clear_actions_update_selection_state():
    html = _studio_html()
    start = html.index("const renderBenchSelectionBasket = () => {")
    end = html.index("const inspectBenchTool = tool => {", start)
    basket = html[start:end]
    assert "bench.selectedTools.delete(id)" in basket
    assert "invalidateHumanReview()" in basket
    start = html.index('$("bench-clear-tools").addEventListener("click",()=>{')
    end = html.index("function showBenchError", start)
    clear = html[start:end]
    assert "bench.selectedTools.clear()" in clear
    assert "renderBenchSelectionBasket()" in clear
    assert '$("bench-goal-review").checked=false' in clear
