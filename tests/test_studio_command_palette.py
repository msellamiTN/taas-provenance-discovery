from pathlib import Path
import re

ROOT = Path(__file__).parents[1]
HTML = ROOT / "src" / "taas" / "studio" / "static" / "index.html"


def test_command_palette_has_accessible_trigger_dialog_and_search():
    html = HTML.read_text(encoding="utf-8")
    assert 'id="command-palette-open"' in html
    assert 'aria-haspopup="dialog"' in html
    assert 'id="studio-command-palette"' in html
    assert "<dialog" in html
    assert 'aria-labelledby="command-palette-title"' in html
    assert 'id="command-palette-search"' in html
    assert 'role="listbox"' in html


def test_command_palette_derives_destinations_from_existing_navigation():
    html = HTML.read_text(encoding="utf-8")
    assert 'document.querySelectorAll(".studio-nav a[href^=\'#\']")' in html
    assert "const collectCommandDestinations" in html
    assert "commandDestinations = collectCommandDestinations()" in html
    assert "window.location.hash = item.href" in html


def test_command_palette_supports_shortcut_search_and_keyboard_navigation():
    html = HTML.read_text(encoding="utf-8")
    assert '(event.ctrlKey || event.metaKey)' in html
    assert 'event.key.toLowerCase() === "k"' in html
    assert 'event.key === "ArrowDown"' in html
    assert 'event.key === "ArrowUp"' in html
    assert 'event.key === "Enter"' in html
    assert 'commandDialog.addEventListener("close"' in html


def test_command_palette_renders_untrusted_navigation_labels_as_text():
    html = HTML.read_text(encoding="utf-8")
    start = html.index("// UX-3: keyboard-accessible command palette")
    end = html.index("// Restore the last successful Core response", start)
    implementation = html[start:end]
    assert "label.textContent = item.label" in implementation
    assert "group.textContent = item.group" in implementation
    assert "innerHTML" not in implementation


def test_command_palette_respects_reduced_motion_and_is_responsive():
    html = HTML.read_text(encoding="utf-8")
    assert "prefers-reduced-motion: reduce" in html
    assert "@media(max-width:900px){.command-palette-trigger" in html
    assert ".command-palette::backdrop" in html
