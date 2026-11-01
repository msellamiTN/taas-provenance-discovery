"""The merged public registry (Table 1) as contracts, with the silver ground truth J kept apart.

* ``build_contracts`` extracts c(t) for the 569 tools using LLM-assisted typing (in/out/class) and the
  evidence a registry would hold: lexical cues and published annotations, plus whatever obs/att
  evidence is put in the ``EvidenceStore`` (by the sandbox probe or the simulated verifier).
* ``truth`` returns J: the silver effect labels (never used as evidence).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .contracts import CapabilityContract, extract_contract
from .data.registries import ROOT, RawTool, load_processed, raw_tools_from_processed
from .effects import Effect, modifies_state, parse_effects
from .provenance import EvidenceStore

LABELS = ROOT / "data" / "llm_records" / "silver_labels.json"


@dataclass(frozen=True)
class Truth:
    effects: frozenset[Effect]
    modifies_state: bool
    private_source: bool
    tool_class: str

    @property
    def unsafe_read_only(self) -> bool:
        """Violates read-only (the property MCP's readOnlyHint claims)."""
        return self.modifies_state or modifies_state(self.effects)


@lru_cache(maxsize=1)
def silver() -> dict[str, dict]:
    return json.load(open(LABELS)) if LABELS.exists() else {}


def truth() -> dict[str, Truth]:
    out = {}
    for t, d in silver().items():
        try:
            effs = parse_effects(d.get("effects", []))
        except ValueError:
            effs = frozenset()
        out[t] = Truth(effs, bool(d.get("modifies_state")), bool(d.get("private_source")), d.get("class", "other"))
    return out


def typing_for(tool_id: str) -> dict | None:
    d = silver().get(tool_id)
    if d is None:
        return None
    return {"in": d.get("in", {}), "out": d.get("out", "text"), "class": d.get("class", "other")}


def raw_registry() -> list[RawTool]:
    return raw_tools_from_processed(load_processed())


def build_contracts(raw: list[RawTool] | None = None, store: EvidenceStore | None = None,
                    use_llm_typing: bool = True) -> list[CapabilityContract]:
    raw = raw if raw is not None else raw_registry()
    tr = truth()
    out = []
    for t in raw:
        ty = typing_for(t.id) if use_llm_typing else None
        # the flow source label comes from the contract's evidence, not from J; private sources are
        # those whose (observed or declared) effects read local/private stores
        c = extract_contract(t, ty, store)
        if use_llm_typing and t.id in tr and tr[t.id].private_source and c.eff_record.ptype in ("obs", "att"):
            c.flow = type(c.flow)("private")
        out.append(c)
    return out
