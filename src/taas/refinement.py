"""Algorithm 3, Part A: counterexample-guided refinement (Section 6.4).

Each failing check maps to one counterexample type and each type to a repair operator:

χ1 uncovered capability   → retrieve beyond top-K (2K, subsuming matches), else the assistant role
                             proposes a transformation / re-decomposition;
χ2 policy-blocked          → substitution within the SUBSTITUTES class toward higher evidence or
                             narrower effects, else UNSATISFIABLE(g, Π);
χ3 model overreach         → σ(g) ← unreliable, Γ ← Γ ∪ {g};
χ4 model under-use         → drop the tool, Γ ← Γ \\ {g};
χ5 combination / flow      → drop the wider-effect tool, insert an authorised declassifying step,
                             or split the task into two toolkits.

Refined goal specifications are recorded as blocking clauses; the loop abstains after k iterations.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field

from .certificate import Counterexample
from .composer import ComposeResult, Composer
from .goals import GapResult, GoalContract, GoalSpec, gap_analysis
from .hypergraph import goal_match
from .model_profile import ModelProfile
from .policy import Policy
from .types import SemType, parse_type


@dataclass
class RefinementTrace:
    steps: list[dict] = field(default_factory=list)
    outcome: str = ""

    def add(self, **kw) -> None:
        self.steps.append(kw)


def spec_signature(spec: GoalSpec, excluded: frozenset[str], gap_ids: tuple[str, ...]) -> tuple:
    return (tuple((g.id, g.cls, str(g.out), g.sigma) for g in spec.goals), excluded, gap_ids)


def refine(composer: Composer, gr: GapResult, policy: Policy, profile: ModelProfile, first: ComposeResult,
           k: int = 3, assistant=None) -> tuple[ComposeResult, RefinementTrace]:
    """Run the repair loop starting from the counterexample of ``first``."""
    trace = RefinementTrace()
    res = first
    spec = gr.spec
    gap = list(gr.gap)
    excluded: set[str] = set()
    blocking: set[tuple] = set()
    base_K = composer.cfg.K
    base_filter = composer.cfg.type_filter
    base_unc = composer.cfg.uncertain_ok
    for i in range(k):
        chi: Counterexample | None = res.counterexample
        if chi is None:
            trace.outcome = "repaired" if i else "valid"
            composer.cfg.K, composer.cfg.type_filter, composer.cfg.uncertain_ok = base_K, base_filter, base_unc
            return res, trace
        g = next((x for x in spec.goals if x.id == chi.goal), None)
        op = ""
        if chi.kind == "chi1":
            if composer.cfg.K < 2 * base_K:
                composer.cfg.K = 2 * base_K
                op = "retrieve 2K"
            elif not composer.cfg.uncertain_ok:
                composer.cfg.uncertain_ok = True  # admit uncertain (subsuming) matches, flagged in C
                op = "retrieve beyond certain typing (uncertain matches)"
            elif assistant is not None and g is not None:
                prop = assistant.repair(chi, spec)
                if prop and prop.get("goal_out"):
                    spec = copy.deepcopy(spec)
                    for x in spec.goals:
                        if x.id == g.id:
                            x.out = parse_type(prop["goal_out"])
                    gap = [next(y for y in spec.goals if y.id == x.id) for x in gap]
                    op = f"assistant transformation: out({g.id}) := {prop['goal_out']}"
            if not op:
                trace.add(iteration=i, chi=chi.to_dict(), op="ask user")
                break
        elif chi.kind == "chi2":
            if g is None:
                bad = chi.witness.get("tool")
                if bad:
                    excluded.add(bad)
                    op = f"exclude over-effect tool {bad}"
            else:
                producers = [c.tool for c in composer.H.contracts.values() if goal_match(c, g)]
                subs = set()
                for p in producers:
                    subs |= composer.H.substitutes(p)
                if not subs:
                    trace.add(iteration=i, chi=chi.to_dict(), op="UNSATISFIABLE")
                    trace.outcome = "unsatisfiable"
                    composer.cfg.K, composer.cfg.type_filter, composer.cfg.uncertain_ok = base_K, base_filter, base_unc
                    return res, trace
                composer.cfg.K = 2 * base_K
                op = "substitution class search"
        elif chi.kind == "chi3" and g is not None:
            g.sigma = "unreliable"
            gap = gap + [g]
            op = "add tool for overreaching goal"
        elif chi.kind == "chi4":
            if g is not None:
                gap = [x for x in gap if x.id != g.id]
            op = "drop tool covered by model edge"
        elif chi.kind == "chi5" and "violations" in chi.witness and composer.cfg.conservative_flow \
                and (sres := split_on_flow(composer, spec, policy)) is not None:
            trace.add(iteration=i, chi=chi.to_dict(), op="split into two toolkits")
            composer.cfg.K, composer.cfg.type_filter, composer.cfg.uncertain_ok = base_K, base_filter, base_unc
            trace.outcome = "repaired(split)"
            return sres, trace
        elif chi.kind == "chi5":
            w = chi.witness
            if "pair" in w:
                a, b = w["pair"]
                ca, cb = composer.H.contracts[a], composer.H.contracts[b]
                drop = a if len(ca.eff) >= len(cb.eff) else b
            else:
                drop = (w.get("violations") or [{}])[0].get("tool")
            if drop:
                excluded.add(drop)
                op = f"drop wider-effect tool {drop}"
        sig = spec_signature(spec, frozenset(excluded), tuple(x.id for x in gap))
        if sig in blocking:
            trace.add(iteration=i, chi=chi.to_dict(), op=op, blocked=True)
            continue
        blocking.add(sig)
        trace.add(iteration=i, chi=chi.to_dict(), op=op)
        res = composer.compose(gap, spec.goals, spec.prompt_inputs,
                               _without(policy, excluded, set(composer.H.contracts)))
    composer.cfg.K, composer.cfg.type_filter, composer.cfg.uncertain_ok = base_K, base_filter, base_unc
    if res.counterexample is None and res.toolkit is not None:
        trace.outcome = "repaired"
    else:
        trace.outcome = trace.outcome or "abstain"
    return res, trace


def _without(policy: Policy, excluded: set[str], universe: set[str]) -> Policy:
    """Exclusion is a projection of the visibility set (Lemma 1), so the index needs no change."""
    if not excluded:
        return policy
    p = copy.copy(policy)
    p.visible = frozenset((policy.visible if policy.visible is not None else frozenset(universe)) - excluded)
    return p


def split_on_flow(composer: Composer, spec: GoalSpec, policy: Policy) -> ComposeResult | None:
    """χ5 repair "split the task into two toolkits": session 1 serves every goal without egress;
    session 2 serves the egress goals from a hand-off of session-1 outputs carrying the label that
    session 1's reach graph assigns them (after authorised declassification). Each session is
    certified on its own, so in session 2 the context holds only the hand-off."""
    egress_goals = [g for g in spec.goals if any(e.cls == "egress" for e in g.eff_plus)]
    if not egress_goals or len(egress_goals) == len(spec.goals):
        return None
    eg_ids = {g.id for g in egress_goals}
    g1 = [copy.deepcopy(g) for g in spec.goals if g.id not in eg_ids]
    spec1 = GoalSpec(g1, list(spec.prompt_inputs), spec.prompt)
    gap1 = [g for g in g1 if g.sigma != "native" and not g.optional]
    r1 = composer.compose(gap1, g1, spec1.prompt_inputs, policy)
    if r1.toolkit is None or r1.certificate is None:
        return None
    labels = r1.certificate.witnesses["L"]["labels"]
    ids1 = {g.id: g for g in g1}
    handoff = []
    for g in egress_goals:
        for d in g.deps:
            if d in ids1:
                handoff.append(ids1[d].out)
    from .effects import join
    hl = join([labels.get(str(t), "public") for t in handoff]) if handoff else policy.prompt_label
    g2 = []
    for g in egress_goals:
        x = copy.deepcopy(g)
        x.deps = []
        g2.append(x)
    p2 = copy.copy(policy)
    p2.prompt_label = hl
    X2 = list(dict.fromkeys(list(spec.prompt_inputs) + handoff))
    gap2 = [g for g in g2 if g.sigma != "native"]
    r2 = composer.compose(gap2, g2, X2, p2)
    if r2.toolkit is None or r2.certificate is None:
        return None
    r1.stats["sessions"] = [r1.toolkit, r2.toolkit]
    r1.stats["split"] = {"toolkit2": r2.toolkit, "certificate2": r2.certificate.to_dict(),
                         "handoff": [str(t) for t in handoff], "handoff_label": hl}
    r1.regime = "split"
    return r1
