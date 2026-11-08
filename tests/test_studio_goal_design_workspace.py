from pathlib import Path


def _studio_html() -> str:
    return (Path(__file__).parents[1] / "src/taas/studio/static/index.html").read_text(encoding="utf-8")


def test_goal_design_exposes_graph_and_equivalent_dependency_table():
    html = _studio_html()
    for marker in (
        'id="goal-view-graph"',
        'id="goal-view-table"',
        'id="goal-dependency-graph"',
        'id="goal-dependency-table-panel"',
        'id="goal-dependency-table-body"',
        'aria-label="Text equivalent of dependency graph"',
        "Arrows point from prerequisite to dependent goal.",
    ):
        assert marker in html


def test_goal_dependency_projection_uses_dom_text_and_declared_dependencies_only():
    html = _studio_html()
    start = html.index("// UX-2: display-only projections of declared GoalSpec dependencies.")
    end = html.index("const validateGoalSpecLocal = () => {", start)
    feature = html[start:end]
    assert "goalSpecState.goals" in feature
    assert "g.deps" in feature
    assert "textContent" in feature
    assert "createElementNS" in feature
    assert "replaceChildren" in feature
    assert "innerHTML" not in feature
    assert "not proof of data compatibility" in feature


def test_goal_template_catalog_requires_explicit_load_and_invalidate_review():
    html = _studio_html()
    for marker in (
        'id="goal-template"',
        'id="goal-template-load"',
        'id="goal-template-retry"',
        'id="goal-template-card"',
        'id="goal-template-status"',
    ):
        assert marker in html
    start = html.index('const GOAL_TEMPLATE_LIST_SCHEMA="taas.goalspec-template-list/v1"')
    end = html.index("const validateGoalSpecLocal = () => {", start)
    feature = html[start:end]
    assert '"/api/v1/goalspec/templates"' in feature
    assert '"/api/v1/goalspec/templates/"+encodeURIComponent(id)' in feature
    assert "GOAL_TEMPLATE_SCHEMA" in feature
    assert "authored_draft_catalog_not_validation_not_evidence_not_authorization" in feature
    assert "authored_draft_not_validation_not_evidence_not_authorization" in feature
    assert "UNAVAILABLE" in feature
    # Load path writes the catalog draft into editor state and invalidates review.
    load = feature.split('$("goal-template-load").addEventListener("click"', 1)[1]
    assert "goalSpecState=" in load
    assert "invalidateHumanReview()" in load
    assert "renderGoalEditor()" in load
    assert "syncGoalSpec()" in load
    assert "authored draft" in load


def test_goal_dependency_views_refresh_when_the_draft_changes():
    html = _studio_html()
    sync_body = html.split("const syncGoalSpec = () => {", 1)[1].split("};", 1)[0]
    assert "try{getGoalSpec();renderGoalDependencyViews();" in sync_body
    assert 'goalViewState.mode="table"' in html
    assert 'goalViewState.mode="graph"' in html


def test_goal_editor_render_refreshes_dependency_views():
    html = _studio_html()
    start = html.index("const renderGoalEditor = () => {")
    end = html.index("// UX-2: display-only projections of declared GoalSpec dependencies.", start)
    assert "renderGoalDependencyViews();" in html[start:end]
