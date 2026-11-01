"""Algorithm 3, Part B: hypergraph, index and cache maintenance on ``notifications/tools/list_changed``.

A changed definition hash is a deletion followed by an insertion; observed and attested evidence is
restored only for (t, h(t)) pairs seen before; cached eligible sets and toolkits are invalidated
exactly (Proposition 3).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable

from .bitmap_index import BitmapIndex
from .contracts import CapabilityContract, extract_contract
from .data.registries import RawTool
from .hypergraph import Hypergraph
from .provenance import EvidenceStore
from .retrieval import HybridRetriever
from .types import subtype


@dataclass
class CachedToolkit:
    key: tuple
    toolkit: list[str]
    heads: list[str]
    costs: dict[str, float]
    model_id: str


@dataclass
class ToolkitCache:
    entries: dict[tuple, CachedToolkit] = field(default_factory=dict)
    invalidated: int = 0

    def put(self, e: CachedToolkit) -> None:
        self.entries[e.key] = e

    def get(self, key: tuple) -> CachedToolkit | None:
        return self.entries.get(key)

    def drop_containing(self, tool: str) -> None:
        for k in [k for k, e in self.entries.items() if tool in e.toolkit]:
            del self.entries[k]
            self.invalidated += 1

    def drop_improvable(self, c: CapabilityContract, cost_of: Callable[[CapabilityContract], float],
                        eligible: Callable[[str], bool]) -> None:
        """Stale iff an inserted eligible tool reaches a head type used by K at lower cost."""
        if not eligible(c.tool):
            return
        for k in list(self.entries):
            e = self.entries[k]
            for t, h in zip(e.toolkit, e.heads):
                if subtype(c.head, h) and cost_of(c) < e.costs.get(t, float("inf")):
                    del self.entries[k]
                    self.invalidated += 1
                    break

    def drop_model(self, model_id: str) -> None:
        for k in [k for k, e in self.entries.items() if e.model_id == model_id]:
            del self.entries[k]
            self.invalidated += 1


@dataclass
class Maintainer:
    H: Hypergraph
    index: BitmapIndex
    retriever: HybridRetriever | None
    store: EvidenceStore
    cache: ToolkitCache = field(default_factory=ToolkitCache)
    typing: dict[str, dict] = field(default_factory=dict)
    seen_hashes: dict[str, str] = field(default_factory=dict)
    log: list[dict] = field(default_factory=list)

    def on_list_changed(self, server: str, new_list: Iterable[RawTool], policy=None,
                        cost_of: Callable[[CapabilityContract], float] | None = None,
                        eligible: Callable[[str], bool] | None = None) -> dict:
        new = {t.id: t for t in new_list}
        current = {t for t, c in self.H.contracts.items() if c.server == server}
        D = {t for t in current if t not in new or new[t].definition_hash() != self.H.contracts[t].h}
        A = {t for t in new if t not in current or t in D}
        for t in D:
            self.index.delete(t)
            self.H.remove(t)
            self.cache.drop_containing(t)
        restored = 0
        for t in A:
            raw = new[t]
            c = extract_contract(raw, self.typing.get(t), self.store)
            if self.store.get(t, c.h):
                restored += 1
            self.index.insert(c)
            self.H.add(c, policy)
            if self.retriever is not None:
                self.retriever.add(c)
            self.seen_hashes[t] = c.h
            if cost_of is not None:
                self.cache.drop_improvable(c, cost_of, eligible or (lambda _t: True))
        rec = {"server": server, "deleted": sorted(D - A), "changed": sorted(D & A), "inserted": sorted(A - D),
               "evidence_restored": restored}
        self.log.append(rec)
        return rec

    def on_model_change(self, model_id: str) -> None:
        self.cache.drop_model(model_id)
