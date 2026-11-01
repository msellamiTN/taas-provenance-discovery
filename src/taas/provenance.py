"""Evidence and provenance (Section 5): records λ(t,a) = (π, σ, κ), trust policies θ_a,
and the hash-bound evidence store W[(t, h)].

Provenance types are not totally ordered by reliability; strengths are. The default
trust policy orders lex < ann < obs < att for every property and scales obs by κ.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable

PTYPES = ("lex", "ann", "obs", "att")

# Default strength thresholds ℓ (a totally ordered ladder used by the bitmap index).
LEVELS: dict[str, float] = {"lex": 0.25, "ann": 0.50, "obs": 0.65, "att": 0.90}

# Safe (positive) properties and violation (negative) properties over effects.
POSITIVE_PROPS = ("read_only", "no_delete", "no_exec", "no_money", "no_egress")
NEGATIVE_PROPS = ("writes", "deletes", "execs", "pays", "egresses")
# a negative property f is the violation of the positive property ¬f
NEGATION = {"writes": "read_only", "deletes": "no_delete", "execs": "no_exec", "pays": "no_money",
            "egresses": "no_egress"}


@dataclass(frozen=True)
class ProvenanceRecord:
    """λ(t, a) = (π, σ, κ): provenance type, signer and confidence (probe coverage for obs)."""

    ptype: str
    signer: str | None = None
    kappa: float = 1.0
    method: str = ""

    def __post_init__(self) -> None:
        if self.ptype not in PTYPES:
            raise ValueError(self.ptype)
        if not 0.0 <= self.kappa <= 1.0:
            raise ValueError("kappa must be in [0,1]")


@dataclass
class TrustPolicy:
    """θ_a : (π, σ, κ) ↦ s ∈ [0, 1], property-specific.

    * ``trusted_signers``: attestations from these signers earn ``att_trusted``;
      others earn ``att_unknown`` (may be weaker than a full-coverage trace).
    * ``lex_by_property``: how far a lexical cue may be believed for property a
      (e.g. "delete" in a name is strong evidence for ``deletes``).
    """

    trusted_signers: frozenset[str] = frozenset({"registry-A"})
    lex: float = 0.25
    ann: float = 0.50
    obs_base: float = 0.55
    obs_scale: float = 0.20
    att_trusted: float = 1.00
    att_unknown: float = 0.60
    lex_by_property: dict[str, float] = field(default_factory=lambda: {"deletes": 0.5, "pays": 0.5, "execs": 0.45})
    custom: dict[str, Callable[[ProvenanceRecord], float]] = field(default_factory=dict)

    def strength(self, prop: str, rec: ProvenanceRecord) -> float:
        if prop in self.custom:
            return self.custom[prop](rec)
        if rec.ptype == "lex":
            return self.lex_by_property.get(prop, self.lex) * (0.5 + 0.5 * rec.kappa)
        if rec.ptype == "ann":
            return self.ann
        if rec.ptype == "obs":
            return self.obs_base + self.obs_scale * rec.kappa
        return self.att_trusted if rec.signer in self.trusted_signers else self.att_unknown

    def level(self, name: str) -> float:
        return LEVELS[name]


DEFAULT_TRUST = TrustPolicy()


@dataclass
class EvidenceStore:
    """W[(t, h)]: observed/attested evidence keyed by tool id and definition hash.

    Lexical and annotation evidence are re-derived from the definition; observed and
    attested evidence are restored only for (t, h(t)) pairs seen before (Alg. 3, line 26).
    """

    records: dict[tuple[str, str], dict[str, list[ProvenanceRecord]]] = field(default_factory=dict)
    observed_effects: dict[tuple[str, str], list[str]] = field(default_factory=dict)

    def add(self, tool: str, h: str, prop: str, rec: ProvenanceRecord) -> None:
        if rec.ptype in ("lex", "ann"):
            raise ValueError("only obs/att evidence is stored; lex/ann are re-derived from the definition")
        self.records.setdefault((tool, h), {}).setdefault(prop, []).append(rec)

    def set_observed_effects(self, tool: str, h: str, effects: Iterable[str]) -> None:
        self.observed_effects[(tool, h)] = sorted(effects)

    def get(self, tool: str, h: str) -> dict[str, list[ProvenanceRecord]]:
        return self.records.get((tool, h), {})

    def effects(self, tool: str, h: str) -> list[str] | None:
        return self.observed_effects.get((tool, h))
