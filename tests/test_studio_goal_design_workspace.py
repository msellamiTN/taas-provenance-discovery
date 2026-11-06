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


def test_goal_examples_require_explicit_replacement_and_invalidate_review():
    html = _studio_html()
    assert 'id="goal-example-load"' in html
    start = html.index('$("goal-example-load").addEventListener("click"')
    end = html.index("const validateGoalSpecLocal = () => {", start)
    handler = html[start:end]
    assert "GOAL_EXAMPLES" in handler
    assert "goalSpecState=" in handler
    assert "invalidateHumanReview()" in handler
    assert "renderGoalEditor()" in handler
    assert "syncGoalSpec()" in handler
    assert "Illustrative example loaded" in handler


def test_goal_dependency_views_refresh_when_the_draft_changes():
    html = _studio_html()
    assert 'const syncGoalSpec = () => {\n    try{getGoalSpec();renderGoalDependencyViews();' in html
    assert 'goalViewState.mode="table"' in html
    assert 'goalViewState.mode="graph"' in html


def test_goal_editor_render_refreshes_dependency_views():
    html = _studio_html()
    start = html.index("const renderGoalEditor = () => {")
    end = html.index("// UX-2: display-only projections of declared GoalSpec dependencies.", start)
    assert "renderGoalDependencyViews();" in html[start:end]
