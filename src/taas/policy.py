"""The principal's policy Π = (P, ℓmin, V, A, D) and its encodings (Section 4, Prop. 2)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .effects import Effect, parse_effects
from .provenance import LEVELS


@dataclass(frozen=True)
class Declassification:
    """A rule in D: lowers ``label_from`` to ``label_to`` on edges authorised to do so.

    ``tool_classes``/``tools`` name the authorised edges; ``min_evidence`` and
    ``min_records`` encode the condition ("aggregation over at least k records by a
    tool at ℓobs lowers private to internal").
    """

    label_from: str
    label_to: str
    tool_classes: frozenset[str] = frozenset({"aggregate"})
    tools: frozenset[str] = frozenset()
    min_evidence: str = "obs"
    min_records: int = 10

    def authorises(self, tool_id: str, tool_class: str, evidence: float, n_records: int) -> bool:
        return ((tool_id in self.tools or tool_class in self.tool_classes)
                and evidence >= LEVELS[self.min_evidence] and n_records >= self.min_records)


@dataclass
class Policy:
    """Π = (P, ℓmin, V, A, D) plus the flow threshold and forbidden-pair templates.

    * ``required``      P: positive properties every tool must carry at ≥ ℓmin.
    * ``forbidden``     F: violation properties for the closed-world encoding (Eq. 2).
    * ``encoding``      ``positive`` (Prop. 2a) or ``closed_world`` (Prop. 2b).
    * ``visible``       V (None = every tool visible to the principal).
    * ``allowed``       A: allowed scoped effect patterns.
    * ``declass``       D.
    * ``egress_threshold``: highest label allowed into an egress edge (check L).
    * ``forbidden_pairs``: effect-class pairs that may not co-occur (FORBIDDEN_WITH templates),
      e.g. (read private, egress *) = exfiltration.
    """

    name: str = "default"
    required: frozenset[str] = frozenset()
    forbidden: frozenset[str] = frozenset()
    encoding: str = "positive"
    lmin: float = LEVELS["obs"]
    visible: frozenset[str] | None = None
    allowed: frozenset[Effect] = field(default_factory=lambda: parse_effects(
        ["read(*)", "egress(*)", "session"]))
    declass: tuple[Declassification, ...] = ()
    egress_threshold: str = "internal"
    forbidden_pairs: tuple[tuple[str, str], ...] = (("private_read", "egress_any"),)
    prompt_label: str = "public"
    credentials: frozenset[str] | None = None  # None = principal holds every credential

    @staticmethod
    def make(name: str, required: Iterable[str] = (), allowed: Iterable[str] = ("read(*)", "egress(*)", "session"),
             lmin: str | float = "obs", **kw) -> "Policy":
        lm = LEVELS[lmin] if isinstance(lmin, str) else float(lmin)
        return Policy(name=name, required=frozenset(required), allowed=parse_effects(allowed), lmin=lm, **kw)


# Ready-made policies used by the experiments and the paper's scenarios.
def read_only_policy(lmin: str | float = "obs", encoding: str = "positive") -> Policy:
    if encoding == "positive":
        return Policy.make("read-only", required={"read_only"}, lmin=lmin)
    return Policy.make("read-only-cw", forbidden={"writes", "deletes", "execs", "pays"}, encoding="closed_world",
                       lmin=lmin)


def no_destructive_policy(lmin: str | float = "obs") -> Policy:
    return Policy.make("no-destructive", required={"no_delete", "no_exec", "no_money"},
                       allowed=("read(*)", "egress(*)", "session", "write(fs)", "write(doc)", "write(memory)",
                                "write(browser)"), lmin=lmin)
