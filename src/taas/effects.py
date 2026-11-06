"""Scoped effect labels E, information-flow labels L and flow transformers (Section 5).

Effects are written ``class(scope)``: ``read(db)``, ``write(/reports)``,
``delete(github)``, ``exec``, ``egress(*.slack.com)``, ``money``, ``session``.
A policy's allowed set A contains patterns; an effect is allowed if some pattern
*covers* it (same class and the pattern scope is ``*`` or a prefix/glob of the scope).
"""
from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass
from typing import Iterable, Sequence

EFFECT_CLASSES = ("read", "write", "delete", "exec", "egress", "money", "session")
# classes that modify persistent, shared or external state (Table 1, "modify ... state")
STATE_MODIFYING = frozenset({"write", "delete", "exec", "money"})

_EFF_RE = re.compile(r"^(?P<cls>[a-z]+)(?:\((?P<scope>[^)]*)\))?$")


@dataclass(frozen=True, order=True)
class Effect:
    cls: str
    scope: str = "*"

    def __str__(self) -> str:
        return self.cls if self.scope in ("*", "") and self.cls in ("exec", "money", "session") \
            else f"{self.cls}({self.scope})"

    def covered_by(self, pattern: "Effect") -> bool:
        if self.cls != pattern.cls:
            return False
        if pattern.scope in ("*", ""):
            return True
        if self.scope in ("*", ""):
            return False  # an unscoped effect is only covered by an unscoped allowance
        return (self.scope == pattern.scope or self.scope.startswith(pattern.scope.rstrip("*"))
                or fnmatch.fnmatch(self.scope, pattern.scope))


def parse_effect(s: str | Effect) -> Effect:
    if isinstance(s, Effect):
        return s
    m = _EFF_RE.match(s.strip().lower().replace(" ", ""))
    if not m or m.group("cls") not in EFFECT_CLASSES:
        raise ValueError(f"bad effect {s!r}")
    return Effect(m.group("cls"), m.group("scope") or "*")


def parse_effects(xs: Iterable[str | Effect]) -> frozenset[Effect]:
    return frozenset(parse_effect(x) for x in xs)


def within(effects: Iterable[Effect], allowed: Iterable[Effect]) -> bool:
    """⋃eff ⊆ A under scope coverage."""
    allowed = list(allowed)
    return all(any(e.covered_by(a) for a in allowed) for e in effects)


def violations(effects: Iterable[Effect], allowed: Iterable[Effect]) -> list[Effect]:
    allowed = list(allowed)
    return [e for e in effects if not any(e.covered_by(a) for a in allowed)]


def modifies_state(effects: Iterable[Effect]) -> bool:
    return any(e.cls in STATE_MODIFYING for e in effects)


# ---------------------------------------------------------------------------
# Information-flow labels: a total order public < internal < private < secret.
# ---------------------------------------------------------------------------
LABELS = ("public", "internal", "private", "secret")
_RANK = {l: i for i, l in enumerate(LABELS)}


def label_rank(l: str) -> int:
    return _RANK[l]


def join(labels: Sequence[str]) -> str:
    return max(labels, key=label_rank) if labels else "public"


def leq(a: str, b: str) -> bool:
    return _RANK[a] <= _RANK[b]


@dataclass(frozen=True)
class FlowTransformer:
    """flow(t): L^|in| → L. Default: join of the argument labels, raised by the
    tool's own source label (a tool reading private data outputs ≥ private)."""

    source_label: str = "public"
    narrowed_args: frozenset[str] = frozenset()  # args shown by traces not to reach the output

    def apply(self, arg_labels: dict[str, str]) -> str:
        ls = [l for a, l in arg_labels.items() if a not in self.narrowed_args]
        return join(ls + [self.source_label])


# ---------------------------------------------------------------------------
# Lexical effect labelling (provenance type lex): name operation class, first
# verb of the description, argument names. Deliberately simple and auditable.
# ---------------------------------------------------------------------------
_W = r"(?:^|[_\-\s.])"
_LEX = [
    ("delete", re.compile(_W + r"(delete|remove|rm|drop|destroy|purge|unlink|erase|clear|kill|uninstall|revoke)", re.I)),
    ("money", re.compile(_W + r"(pay|payment|charge|refund|invoice|purchase|buy|order|checkout|transfer|subscription|payout)", re.I)),
    ("exec", re.compile(_W + r"(exec|execute|run|eval|shell|command|script|terminal|spawn|process|docker|start_process|interact)", re.I)),
    # "record" is a write verb only as a complete token. In particular, the noun
    # "records" in lookup_records / "return records" must not imply a state change.
    ("write", re.compile(_W + r"(write|create|add|insert|update|edit|modify|set|save|put|post|upload|append|move|rename|copy|mkdir|make|generate_file|commit|push|merge|install|replace|format_|apply|fill|type|click|navigate|press|drag|select|hover|close|new|convert|export|record(?![a-z]))", re.I)),
    ("egress", re.compile(_W + r"(send|email|mail|post|publish|share|notify|tweet|message|fetch|http|request|download|search|browse|navigate|web|url|api)", re.I)),
]


def lexical_effects(name: str, description: str, arg_names: Sequence[str]) -> frozenset[Effect]:
    """Effects inferred from the name, the first sentence of the description and arg names."""
    first = re.split(r"[.\n]", (description or "").strip(), maxsplit=1)[0]
    text = f"{name} {first} {' '.join(arg_names)}"
    out: set[Effect] = set()
    for cls, pat in _LEX:
        if pat.search(" " + name) or pat.search(" " + first[:80]):
            out.add(Effect(cls, "*"))
    if any(re.search(r"(url|uri|endpoint|host)", a, re.I) for a in arg_names):
        out.add(Effect("egress", "*"))
    if not out or not (out & {Effect(c, "*") for c in ("write", "delete", "exec", "money")}):
        out.add(Effect("read", "*"))
    _ = text
    return frozenset(out)
