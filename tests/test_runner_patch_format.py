"""Offline check that integrations/mcp-bench/runner.patch is a well-formed unified diff.

git apply treats a hunk whose leading and trailing context differ in length as anchored to the
start or end of the file, so a hand-written hunk with one line of leading context and none
trailing is rejected by `git apply --check` even when its lines are right. Validated against the
pinned upstream revision with: git apply --check integrations/mcp-bench/runner.patch
"""
import re
from pathlib import Path

PATCH = Path(__file__).resolve().parents[1] / "integrations" / "mcp-bench" / "runner.patch"


def hunks(text):
    out, cur = [], None
    for line in text.splitlines():
        m = re.match(r"@@ -(\d+),(\d+) \+(\d+),(\d+) @@", line)
        if m:
            cur = {"decl": tuple(int(x) for x in m.groups()), "lines": []}
            out.append(cur)
        elif cur is not None and line[:1] in (" ", "+", "-", ""):
            cur["lines"].append(line)
    return out


def test_runner_patch_hunks_are_consistent():
    hs = hunks(PATCH.read_text())
    assert hs, "no hunks found"
    for h in hs:
        old_start, old_n, new_start, new_n = h["decl"]
        body = [l if l else " " for l in h["lines"]]
        assert sum(1 for l in body if l[0] in " -") == old_n
        assert sum(1 for l in body if l[0] in " +") == new_n
        lead = next(i for i, l in enumerate(body) if l[0] != " ")
        trail = next(i for i, l in enumerate(reversed(body)) if l[0] != " ")
        assert lead == trail, f"hunk at -{old_start} has unequal context ({lead} leading, {trail} trailing)"
        assert lead >= 3, f"hunk at -{old_start} has only {lead} context lines"
