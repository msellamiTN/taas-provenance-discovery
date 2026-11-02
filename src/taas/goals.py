"""Goal contracts (Definition 1) and Algorithm 1: goal specification and capability-gap analysis.

Resolution of an ambiguity in Algorithm 1 (docs/PAPER_ANALYSIS.md, A4): line 8 tests whether
out(g) is text-derivable from in(g) ∩ ctx, and line 15 adds only *native* outputs to ctx.
Read literally, every native goal downstream of a data goal is demoted (in the running example
g2–g4 consume Review[] produced by g1 ∈ Γ), contradicting Section 6.2. Because every tool result
returns to the model's context, we add the outputs of *all* predecessor goals to ctx
(``ctx_mode="all_predecessors"``, default); ``ctx_mode="literal"`` reproduces the literal reading.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

from .effects import EFFECT_CLASSES, Effect, parse_effect
from .hypergraph import EXTRACT_TARGETS, FREE_KINDS
from .model_profile import EXTERNAL_CLASSES, ModelProfile
from .types import _TYPE_RE, KINDS, SemType, parse_type, subtype

SIGMAS = ("native", "data", "effect", "unreliable")
GENERATIVE = frozenset({"write", "plan", "summarise", "synthesise", "translate", "convert_format", "classify",
                        "extract", "compare", "answer", "aggregate", "count", "compute_exact"})


@dataclass
class GoalContract:
    """g = (in(g), out(g), eff+(g), σ(g), n_g, ε_g) plus class, language and dependencies."""

    id: str
    cls: str
    inputs: list[SemType]
    out: SemType
    eff_plus: list[Effect] = field(default_factory=list)
    sigma: str = "native"
    n: int = 1
    exactness: str = "tolerant"
    lang: str = "en"
    deps: list[str] = field(default_factory=list)
    optional: bool = False
    desc: str = ""
    sigma_claimed: str = ""
    sigma_reason: str = ""
    dropped_effects: list[str] = field(default_factory=list)

    def rendering(self) -> str:
        """r(g): natural-language rendering (class, output kind, domain terms)."""
        dom = self.out.domain or ""
        ins = " ".join(f"{t.kind} {t.domain or ''}" for t in self.inputs)
        effs = " ".join(e.cls + " " + e.scope for e in self.eff_plus)
        return f"{self.desc} {self.cls.replace('_', ' ')} {self.out.kind} {dom} {ins} {effs}".strip()


@dataclass
class GoalSpec:
    goals: list[GoalContract]
    prompt_inputs: list[SemType]
    prompt: str = ""

    def by_id(self) -> dict[str, GoalContract]:
        return {g.id: g for g in self.goals}

    def order(self) -> list[GoalContract] | None:
        """Topological order of ≺ (None if cyclic)."""
        ids = self.by_id()
        indeg = {g.id: sum(1 for d in g.deps if d in ids) for g in self.goals}
        ready = [g.id for g in self.goals if indeg[g.id] == 0]
        out = []
        while ready:
            i = ready.pop(0)
            out.append(ids[i])
            for g in self.goals:
                if i in g.deps:
                    indeg[g.id] -= 1
                    if indeg[g.id] == 0:
                        ready.append(g.id)
        return out if len(out) == len(self.goals) else None


# Effect classes LLM analysts commonly write for the engine's closed set (Section 5). Only
# unambiguous synonyms are mapped; anything else is kept in GoalContract.dropped_effects so the
# loss is visible in traces instead of silent.
EFFECT_ALIASES = {"execute": "exec", "execution": "exec", "run": "exec", "shell": "exec",
                  "transact": "money", "transaction": "money", "pay": "money", "payment": "money",
                  "purchase": "money"}
_EFF_WORD = re.compile(r"^\s*([A-Za-z_]+)\s*(?:\(([^)]*)\))?\s*$")


def normalise_effect(e: str) -> Effect | None:
    """Parse an effect label, mapping known synonyms (execute(*) -> exec, transact(*) -> money)."""
    try:
        return parse_effect(e)
    except ValueError:
        pass
    m = _EFF_WORD.match(str(e))
    if not m:
        return None
    cls = EFFECT_ALIASES.get(m.group(1).lower())
    if cls is None:
        return None
    scope = (m.group(2) or "*").strip() or "*"
    return Effect(cls, "*" if cls in ("exec", "money", "session") else scope)


def vocabulary_report(d: dict) -> dict:
    """Which parts of an analyst GoalSpec fall outside the engine's vocabulary.

    ``aliased_effects`` were mapped by EFFECT_ALIASES; ``unknown_effects`` are dropped;
    ``unknown_type_kinds`` parse to ``text:<word>`` (collection markers are lost) and will rarely
    match a tool's head type."""
    aliased, unknown, kinds = [], [], []
    types = list(d.get("prompt_inputs", []) or [])
    for g in d.get("goals", []) or []:
        for e in g.get("eff", []) or []:
            try:
                parse_effect(e)
            except ValueError:
                (aliased if normalise_effect(e) is not None else unknown).append(str(e))
        types += list(g.get("in", []) or []) + [g.get("out", "text")]
    for t in types:
        m = _TYPE_RE.match(str(t or "none").strip().lower().replace(" ", "_"))
        if not m or m.group("kind") not in KINDS:
            kinds.append(str(t))
    return {"aliased_effects": aliased, "unknown_effects": unknown, "unknown_type_kinds": kinds,
            "effect_classes": list(EFFECT_CLASSES), "type_kinds": list(KINDS)}


def parse_goal_spec(d: dict, prompt: str = "") -> GoalSpec:
    goals = []
    for i, g in enumerate(d.get("goals", [])):
        effs, dropped = [], []
        for e in g.get("eff", []) or []:
            x = normalise_effect(e)
            if x is None:
                dropped.append(str(e))
            else:
                effs.append(x)
        sigma = g.get("sigma", "native")
        sigma = sigma if sigma in SIGMAS else "data"
        goals.append(GoalContract(
            id=str(g.get("id", f"g{i + 1}")), cls=str(g.get("class", "answer")),
            inputs=[parse_type(t) for t in g.get("in", []) or []], out=parse_type(g.get("out", "text")),
            eff_plus=effs, sigma=sigma, n=int(g.get("n", 1) or 1), exactness=g.get("exactness", "tolerant"),
            lang=g.get("lang", "en"), deps=[str(x) for x in g.get("deps", []) or []],
            optional=bool(g.get("optional", False)), desc=g.get("desc", ""), sigma_claimed=sigma,
            dropped_effects=dropped))
    pin = [parse_type(t) for t in d.get("prompt_inputs", ["text"])] or [SemType("text")]
    if SemType("text") not in pin:
        pin.append(SemType("text"))
    return GoalSpec(goals, pin, prompt)


def text_derivable(g: GoalContract, ctx: Iterable[SemType]) -> bool:
    """Can the model produce out(g) from the inputs of g that are in its context?

    Data of a domain must come from context data of the same domain; generated text
    (summaries, plans, reports in text) needs only text-renderable inputs; parameters
    and identifiers can be extracted from any text.
    """
    ctx = list(ctx)
    if g.cls in EXTERNAL_CLASSES:
        return False
    if not g.out.is_text_renderable or g.out.kind in ("path", "url", "credential"):
        return False
    # every input must already be in context (as a subtype) or be a parameter writable from the prompt
    for t in g.inputs:
        if not (any(subtype(s, t) for s in ctx) or (t.kind in FREE_KINDS and t.domain is None)
                or (t.kind in EXTRACT_TARGETS and not t.collection)):
            return False
    if not all(any(subtype(s, t) for s in ctx) or t.is_text_renderable for t in g.inputs):
        return False
    if g.out.domain is None or g.out.kind in FREE_KINDS:
        return True
    if any(s.domain == g.out.domain for s in ctx):
        return True
    if g.out.kind in EXTRACT_TARGETS and not g.out.collection:
        return True  # an identifier/parameter mentioned in text
    # analytical and generative classes derive new records (stats, categories, findings, digests)
    # from *data already in context*; a look-up of a domain absent from context needs data
    has_data_input = any(t.kind in ("record", "table", "document") or t.domain is not None
                         for t in g.inputs if any(subtype(s, t) for s in ctx))
    return g.cls in ANALYTICAL and has_data_input


ANALYTICAL = frozenset({"classify", "extract", "summarise", "synthesise", "write", "plan", "translate",
                        "convert_format", "aggregate", "count", "compute_exact", "compare"})


@dataclass
class GapResult:
    spec: GoalSpec
    gap: list[GoalContract]
    shrink: list[GoalContract]
    clarify: str | None = None
    rho: dict[str, float] = field(default_factory=dict)


def gap_analysis(spec: GoalSpec, profile: ModelProfile, ctx_mode: str = "all_predecessors",
                 budget_items: int | None = None) -> GapResult:
    """Algorithm 1, lines 3–21 (the analyst call of line 2 happens in the LLM role)."""
    order = spec.order()
    if order is None:
        return GapResult(spec, [], [], clarify="dependency cycle")
    ids = spec.by_id()
    ctx: list[SemType] = list(spec.prompt_inputs)
    shrink: list[GoalContract] = []
    rhos: dict[str, float] = {}
    for g in order:
        preds = [ids[d].out for d in g.deps if d in ids]
        g.inputs = list(dict.fromkeys(list(g.inputs) + preds))
        r = profile.rho(g.cls, g.n, g.lang, g.exactness)
        rhos[g.id] = r
        derivable = text_derivable(g, ctx)
        over_budget = budget_items is not None and g.n > budget_items
        if g.sigma == "native":
            if not derivable:
                g.sigma, g.sigma_reason = "data", "refuted: out(g) not text-derivable from context"
            elif g.eff_plus:
                g.sigma, g.sigma_reason = "effect", "refuted: eff+(g) ≠ ∅"
            elif r < profile.tau or over_budget:
                g.sigma, g.sigma_reason = "unreliable", f"refuted: ρ={r:.2f} < τ={profile.tau}"
        elif r >= profile.tau and derivable and not g.eff_plus:
            shrink.append(g)  # challenged: candidate for shrinking (Δ)
        if g.sigma == "native" or ctx_mode == "all_predecessors":
            ctx.append(g.out)
    # line 18: unprovided inputs ⇒ CLARIFY (parameters/identifiers can come from the prompt text)
    for g in order:
        prov = set(spec.prompt_inputs) | {ids[d].out for d in g.deps if d in ids}
        for t in g.inputs:
            if not (any(subtype(s, t) for s in prov) or t.kind in FREE_KINDS or t.kind in EXTRACT_TARGETS
                    or any(subtype(o.out, t) for o in order)):
                return GapResult(spec, [], shrink, clarify=f"input {t} of {g.id} is not provided", rho=rhos)
    gap = [g for g in spec.goals if g.sigma != "native" and not g.optional]
    return GapResult(spec, gap, shrink, None, rhos)
