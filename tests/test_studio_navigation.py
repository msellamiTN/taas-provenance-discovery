from html.parser import HTMLParser
from pathlib import Path


STUDIO_HTML = Path(__file__).parents[1] / "src" / "taas" / "studio" / "static" / "index.html"


class StudioMarkup(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.nav_hrefs = []
        self.pipeline_hrefs = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag == "a" and attrs.get("href", "").startswith("#"):
            if "studio-nav" in attrs.get("class", "").split():
                self.nav_hrefs.append(attrs["href"])
            if "pipeline-step" in attrs.get("class", "").split():
                self.pipeline_hrefs.append(attrs["href"])


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
    assert 'data-studio-nav-hidden="true"' in html
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
