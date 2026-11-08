"""Unit tests for fail-closed task effect-scope semantics."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments"))
sys.path.insert(0, str(ROOT / "src"))

from scope_policy import (  # noqa: E402
    TaskEffectRequirements,
    classify_effect,
    parse_effect_list,
    parse_task_effect_requirements,
)


def test_exact_write_scope_permitted():
    req = TaskEffectRequirements(parse_effect_list(["write(/reports)"]), frozenset(), ("write(/reports)",))
    assert classify_effect(parse_effect_list(["write(/reports/monthly.csv)"])[0], req) == "permitted"


def test_other_write_scope_is_violation():
    req = TaskEffectRequirements(parse_effect_list(["write(/reports)"]), frozenset(), ("write(/reports)",))
    assert classify_effect(parse_effect_list(["write(/secrets)"])[0], req) == "violation"


def test_unknown_wildcard_tool_scope_is_indeterminate_for_scoped_permission():
    req = TaskEffectRequirements(parse_effect_list(["write(/reports)"]), frozenset(), ("write(/reports)",))
    assert classify_effect(parse_effect_list(["write(*)"])[0], req) == "indeterminate"


def test_task_bare_write_does_not_become_global_permission():
    parsed = parse_task_effect_requirements({"goals": [{"eff": ["write"]}]})
    assert "write" in parsed.ambiguous_classes
    assert not parsed.required
    assert classify_effect(parse_effect_list(["write(/reports)"])[0], parsed) == "indeterminate"


def test_missing_effect_requirement_is_violation():
    parsed = parse_task_effect_requirements({"goals": [{"eff": []}]})
    assert classify_effect(parse_effect_list(["delete(/repo)"])[0], parsed) == "violation"


def test_read_only_policy_does_not_inherit_goal_effects():
    parsed = parse_task_effect_requirements({"goals": [{"eff": ["write(/reports)"]}]}, read_only=True)
    assert not parsed.required
    assert not parsed.ambiguous_classes