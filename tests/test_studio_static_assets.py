from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

HTML_PATH = Path(__file__).parents[1] / "src" / "taas" / "studio" / "static" / "index.html"


class _TokenFormParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.form_depth = 0
        self.token_inside_form = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            self.form_depth += 1
        if tag == "input" and attrs.get("id") == "token" and self.form_depth > 0:
            self.token_inside_form = True

    def handle_endtag(self, tag):
        if tag == "form":
            self.form_depth = max(0, self.form_depth - 1)


def test_studio_api_token_input_is_inside_authentication_form():
    parser = _TokenFormParser()
    parser.feed(HTML_PATH.read_text(encoding="utf-8"))
    assert parser.token_inside_form


def test_studio_inline_javascript_parses_when_node_is_available():
    node = shutil.which("node")
    if node is None:
        import pytest
        pytest.skip("Node.js is not installed; browser/Colab acceptance covers script parsing")
    html = HTML_PATH.read_text(encoding="utf-8")
    match = re.search(r"<script\b[^>]*>(.*?)</script\s*>", html, flags=re.IGNORECASE | re.DOTALL)
    assert match, "Studio HTML must contain its application script"
    with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8") as source:
        source.write(match.group(1))
        source.flush()
        result = subprocess.run([node, "--check", source.name], text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
