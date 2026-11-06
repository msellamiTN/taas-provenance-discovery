from html.parser import HTMLParser
from pathlib import Path


STUDIO_HTML = Path(__file__).parents[1] / "src" / "taas" / "studio" / "static" / "index.html"


class StudioMarkup(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.nav_hrefs = []
        self.pipeline_hrefs = []
        self.in_studio_nav = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "nav" and "studio-nav" in attrs.get("class", "").split():
            self.in_studio_nav = True
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag == "a" and attrs.get("href", "").startswith("#"):
            if self.in_studio_nav:
                self.nav_hrefs.append(attrs["href"])
            if "pipeline-step" in attrs.get("class", "").split():
                self.pipeline_hrefs.append(attrs["href"])

    def handle_endtag(self, tag):
        if tag == "nav":
            self.in_studio_nav = False


def studio_markup():
    parser = StudioMarkup()
    parser.feed(STUDIO_HTML.read_text(encoding="utf-8"))
    return parser


def test_every_studio_navigation_and_pipeline_destination_exists():
    parser = studio_markup()
    ids = set(parser.ids)
    assert len(parser.ids) == len(ids), "Studio element IDs must be unique"
    assert parser.nav_hrefs
    assert parser.pipeline_hrefs
    assert all(href[1:] in ids for href in parser.nav_hrefs)
    assert all(href[1:] in ids for href in parser.pipeline_hrefs)


def test_navigation_restores_only_visibility_flags_it_owns():
    html = STUDIO_HTML.read_text(encoding="utf-8")
    assert 'node.dataset.studioNavHidden = "true";' in html
    assert 'querySelectorAll("[data-studio-nav-hidden=\'true\']")' in html
    assert 'restoreNavigationVisibility();' in html
    assert 'delete node.dataset.studioNavHidden;' in html
    assert 'window.addEventListener("popstate", routeFromLocation);' in html
    assert 'window.addEventListener("hashchange", routeFromLocation);' in html
    assert 'history.pushState(' in html
    assert 'history.replaceState(' not in html


def test_runtime_overview_is_a_persistent_global_workspace_utility():
    html = STUDIO_HTML.read_text(encoding="utf-8")
    assert '<section id="runtime-overview" class="runtime-overview"' in html
    assert 'if (child.id === "runtime-overview") child.hidden = false;' in html


def test_benchmark_use_prompt_routes_to_goal_editor_not_hidden_discovery_panel():
    html = STUDIO_HTML.read_text(encoding="utf-8")
    assert 'const goalEditorLink = studioLinks.find(link => link.getAttribute("href") === "#goal-editor");' in html
    assert 'if (goalEditorLink) showStudioWorkspace(goalEditorLink);' in html
    assert 'document.querySelector("#discovery").scrollIntoView' not in html


def test_parent_workspace_navigation_unhides_panels_hidden_by_previous_child_route():
    html = STUDIO_HTML.read_text(encoding="utf-8")
    route = html[html.index("const showStudioWorkspace ="):html.index("const routeFromLocation =")]
    assert route.index("restoreNavigationVisibility();") < route.index("hideForNavigation(child)")
    assert 'while (branch && branch !== root)' in route
    assert 'if (branch && branch !== root)' not in route


def test_overview_navigation_shows_the_lifecycle_and_not_only_the_hero():
    html = STUDIO_HTML.read_text(encoding="utf-8")
    assert '<a href="#overview-workspace" aria-current="page">Overview</a>' in html
    assert '<div id="overview-workspace">' in html
    overview = html[html.index('<div id="overview-workspace">'):html.index('<section id="workspace"')]
    assert 'id="overview"' in overview
    assert 'class="taas-pipeline"' in overview


def test_tablet_and_mobile_navigation_use_compact_grid_layouts():
    html = STUDIO_HTML.read_text(encoding="utf-8")
    assert '@media(max-width:900px){.studio-nav{display:grid;grid-template-columns:repeat(3,minmax(0,1fr))' in html
    assert '@media(max-width:560px){.studio-nav{grid-template-columns:repeat(2,minmax(0,1fr))' in html


def test_discovery_routes_preserve_request_and_result_context_together():
    html = STUDIO_HTML.read_text(encoding="utf-8")
    route = html[html.index("const showStudioWorkspace ="):html.index("const routeFromLocation =")]
    assert 'if (root.id !== "discovery")' in route
    assert "GoalSpec,\n    // Hypergraph or Assurance would hide the Run action or the result context." in route
