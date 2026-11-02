"""The discovery layer (Fig. 5): offline capability modelling + the request path.

    1. capability modelling (contracts, evidence, hash, model edges → H, bitmaps)  [offline]
    2. goal specification and gap analysis (Algorithm 1)
    3. toolkit composition and certification (Algorithm 2)
    4. counterexample-guided refinement (Algorithm 3A)          → K, C, manifest  |  ABSTAIN(χ)
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Iterable

from .bitmap_index import BitmapIndex
from .certificate import CHI_PRIORITY, Certificate, Counterexample
from .composer import ComposeResult, Composer, ComposerConfig
from .contracts import CapabilityContract
from .goals import GapResult, GoalSpec, gap_analysis, parse_goal_spec
from .hypergraph import Hypergraph
from .manifest import manifest
from .model_profile import ModelProfile
from .policy import Policy
from .provenance import DEFAULT_TRUST, TrustPolicy
from .refinement import RefinementTrace, refine
from .retrieval import HybridRetriever, LSAEncoder


@dataclass
class EngineConfig:
    composer: ComposerConfig = field(default_factory=ComposerConfig)
    refine_k: int = 3
    ctx_mode: str = "all_predecessors"
    use_gap: bool = True          # ablation: False ⇒ every goal is in the gap (no model coverage)
    budget_items: int | None = None


@dataclass
class DiscoveryResult:
    spec: GoalSpec
    gap: GapResult
    compose: ComposeResult
    trace: RefinementTrace | None
    toolkit: list[str] | None
    certificate: Certificate | None
    counterexample: Counterexample | None
    manifest: dict | None
    time_s: float

    @property
    def abstained(self) -> bool:
        return self.toolkit is None


class DiscoveryEngine:
    def __init__(self, contracts: Iterable[CapabilityContract], profile: ModelProfile,
                 trust: TrustPolicy = DEFAULT_TRUST, cfg: EngineConfig | None = None,
                 pair_policy: Policy | None = None, encoder=None, assistant=None) -> None:
        self.cfg = cfg or EngineConfig()
        self.profile = profile
        self.trust = trust
        self.assistant = assistant
        contracts = list(contracts)
        self.index = BitmapIndex(trust=trust)
        self.H = Hypergraph()
        self.H.trust = trust  # type: ignore[attr-defined]
        for c in contracts:
            self.index.insert(c)
            self.H.contracts[c.tool] = c
            self.H.subst[Hypergraph.head_key(c.head)].add(c.tool)
        self.H.rebuild_pairs(pair_policy)
        self.retriever = HybridRetriever(encoder=encoder or LSAEncoder()).fit(contracts)
        self.composer = Composer(self.H, self.index, self.retriever, profile, self.cfg.composer)

    def gap(self, spec: GoalSpec) -> GapResult:
        gr = gap_analysis(spec, self.profile, self.cfg.ctx_mode, self.cfg.budget_items)
        if not self.cfg.use_gap and gr.clarify is None:
            for g in spec.goals:
                if g.sigma == "native":
                    g.sigma, g.sigma_reason = "data", "ablation: model coverage disabled"
            gr.gap = [g for g in spec.goals if not g.optional]
        return gr

    def discover(self, spec: GoalSpec | dict, policy: Policy, refine_on_failure: bool = True) -> DiscoveryResult:
        t0 = time.perf_counter()
        if isinstance(spec, dict):
            spec = parse_goal_spec(spec)
        gr = self.gap(spec)
        if gr.clarify is not None:
            chi = Counterexample("chi1", None, "CLARIFY", {"reason": gr.clarify})
            cr = ComposeResult(None, None, chi)
            return DiscoveryResult(spec, gr, cr, None, None, None, chi, None, time.perf_counter() - t0)
        if not gr.gap:
            # everything is covered by the model: the empty toolkit, still certified
            cr = self.composer.compose([], spec.goals, spec.prompt_inputs, policy)
        else:
            cr = self.composer.compose(gr.gap, spec.goals, spec.prompt_inputs, policy)
        trace = None
        if cr.counterexample is not None and refine_on_failure and self.cfg.refine_k > 0:
            cr, trace = refine(self.composer, gr, policy, self.profile, cr, self.cfg.refine_k, self.assistant)
        # Fail closed: a toolkit is selectable only when composition returned a complete,
        # valid pre-execution certificate. An empty list is valid for model-only coverage;
        # None remains the abstention sentinel.
        if cr.toolkit is not None and (cr.certificate is None or not cr.certificate.valid):
            failed = (["missing_certificate"] if cr.certificate is None else
                      [name for name in ("S", "C", "P", "E", "L", "V")
                       if cr.certificate.checks.get(name) is not True])
            # Type the counterexample by the failed check (Section 6.4) instead of reporting every
            # rejection as an uncovered capability: E/V -> χ2 (policy-blocked), L -> χ5 (flow),
            # S/C/P or a missing certificate -> χ1. The highest-priority kind wins.
            kinds = {"E": "chi2", "V": "chi2", "L": "chi5"}
            kind = max((kinds.get(name, "chi1") for name in failed), key=lambda k: CHI_PRIORITY[k])
            violations = (cr.certificate.witnesses.get("binding_integrity", {}).get("violations", [])
                          if cr.certificate is not None else [])
            chi = Counterexample(kind, violations[0]["goal"] if violations else None, "CERTIFICATE", {
                "reason": "selection requires a valid pre-execution certificate",
                "failed_checks": failed,
                "binding_violations": violations,
            })
            cr = ComposeResult(None, cr.certificate, chi, cr.candidates, cr.regime,
                               cr.stats | {"selection_rejected": "invalid_certificate"})
        man = manifest(self.H, cr.certificate) if cr.toolkit is not None and cr.certificate is not None else None
        toolkit = cr.toolkit
        if toolkit is not None and "sessions" in cr.stats:
            toolkit = sorted({t for s in cr.stats["sessions"] for t in s})
        return DiscoveryResult(spec, gr, cr, trace, toolkit, cr.certificate, cr.counterexample, man,
                               time.perf_counter() - t0)
