"""Fail-closed parsing and scope classification for Revision 1 security re-analysis."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Sequence

from taas.effects import Effect, parse_effect

SCOPED_CLASSES = frozenset({"write", "delete", "egress"})
_CLASS_PREFIX = re.compile(r"^\s*([a-z]+)")


@dataclass(frozen=True)
class TaskEffectRequirements:
    required: tuple[Effect, ...]
    ambiguous_classes: frozenset[str]
    raw_requirements: tuple[str, ...]


def parse_task_effect_requirements(record: dict, *, read_only: bool = False) -> TaskEffectRequirements:
    """Parse exact task effect scopes; never widen a bare scoped class to '*'.

    Bare 'write', 'delete' and 'egress' are treated as ambiguous because the
    record does not identify the permitted target. 'exec' and 'money' are
    inherently unscoped in this project vocabulary and may be parsed directly.
    """
    if read_only:
        return TaskEffectRequirements((), frozenset(), ())
    required: list[Effect] = []
    ambiguous: set[str] = set()
    raw_values: list[str] = []
    for goal in record.get("goals", []) or []:
        for item in goal.get("eff", []) or []:
            raw = str(item).strip().lower()
            if not raw:
                continue
            raw_values.append(raw)
            match = _CLASS_PREFIX.match(raw)
            cls = match.group(1) if match else ""
            if cls in SCOPED_CLASSES and "(" not in raw:
                ambiguous.add(cls)
                continue
            try:
                required.append(parse_effect(raw))
            except ValueError:
                if cls:
                    ambiguous.add(cls)
    # Stable de-duplication, retaining the immutable effect objects.
    return TaskEffectRequirements(
        required=tuple(sorted(set(required))),
        ambiguous_classes=frozenset(ambiguous),
        raw_requirements=tuple(raw_values),
    )


def classify_effect(effect: Effect, requirements: TaskEffectRequirements) -> str:
    """Return 'permitted', 'violation' or 'indeterminate'.

    A wildcard tool effect cannot be certified against a narrower explicit scope.
    If a task's requirement for the same class omitted its target, the result is
    indeterminate rather than silently authorised.
    """
    same_class = [r for r in requirements.required if r.cls == effect.cls]
    if not same_class:
        if effect.cls in requirements.ambiguous_classes:
            return "indeterminate"
        return "violation"

    # The labels in the current scoring set often retain only an effect class,
    # represented as scope='*'. Do not mistake that loss of scope information for
    # proof that the tool's target is authorised by a narrower task requirement.
    if effect.cls in SCOPED_CLASSES and effect.scope in ("", "*"):
        if not any(r.scope in ("", "*") for r in same_class):
            return "indeterminate"

    if any(effect.covered_by(allowed) for allowed in same_class):
        return "permitted"
    return "violation"


def classify_effects(effects: Iterable[Effect], requirements: TaskEffectRequirements) -> dict:
    statuses = {"permitted": [], "violation": [], "indeterminate": []}
    for effect in sorted(set(effects)):
        statuses[classify_effect(effect, requirements)].append(str(effect))
    return statuses


def parse_effect_list(values: Sequence[str]) -> tuple[Effect, ...]:
    """Strict parser for tests and small explicit policies."""
    return tuple(parse_effect(v) for v in values)