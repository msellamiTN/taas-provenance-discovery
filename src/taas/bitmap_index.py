"""Bitmap eligibility index (Section 5 and 6.1).

E_a^(ℓ) = {t | θ_a(λ(t,a)) ≥ ℓ} is stored as a bitmap over tool slots for every property a
and every level ℓ of the ladder. Python integers serve as uncompressed bitmaps (word-level
AND/OR); deleted tools leave a cleared slot excluded by the live-slot bitmap.

* Eq. (3)  Elig = ⋂_{a∈P} E_a^(ℓmin) ∩ V                 (positive encoding)
* Eq. (2)  CW_ℓ(C, F) = C \\ ⋃_{f∈F} E_f^(ℓ)              (closed-world encoding)
* Lemma 1  B_V^(ℓ) = B^(ℓ) ∩ V: authorisation is a projection, retrieval and
           authorisation commute.
* Prop. 3  cached eligible sets are invalidated exactly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .contracts import CapabilityContract
from .provenance import LEVELS, NEGATIVE_PROPS, POSITIVE_PROPS, TrustPolicy, DEFAULT_TRUST

ALL_PROPS = POSITIVE_PROPS + NEGATIVE_PROPS


def popcount(x: int) -> int:
    return x.bit_count()


def bits(x: int) -> Iterable[int]:
    while x:
        low = x & -x
        yield low.bit_length() - 1
        x ^= low


@dataclass
class BitmapIndex:
    trust: TrustPolicy = field(default_factory=lambda: DEFAULT_TRUST)
    levels: dict[str, float] = field(default_factory=lambda: dict(LEVELS))
    slot_of: dict[str, int] = field(default_factory=dict)
    tool_at: list[str | None] = field(default_factory=list)
    live: int = 0
    E: dict[tuple[str, float], int] = field(default_factory=dict)
    strengths: dict[str, dict[str, float]] = field(default_factory=dict)  # per tool, per property
    # cache Q: (frozenset(props), level, visibility-key) -> bitmap
    cache: dict[tuple[frozenset[str], float, int], int] = field(default_factory=dict)
    stats: dict[str, int] = field(default_factory=lambda: {"cache_hits": 0, "cache_misses": 0, "invalidations": 0})

    # ------------------------------------------------------------------ build
    def _ladder(self, extra: Iterable[float] = ()) -> list[float]:
        return sorted(set(self.levels.values()) | set(extra))

    def insert(self, c: CapabilityContract) -> int:
        """Insert (or re-insert) tool c; returns its slot. Invalidates the cache exactly (Prop. 3)."""
        if c.tool in self.slot_of:
            self.delete(c.tool)
        slot = len(self.tool_at)
        self.tool_at.append(c.tool)
        self.slot_of[c.tool] = slot
        self.live |= 1 << slot
        st = {a: c.strength(a, self.trust) for a in ALL_PROPS}
        self.strengths[c.tool] = st
        for a in ALL_PROPS:
            for l in self._ladder():
                if st[a] >= l:
                    self.E[(a, l)] = self.E.get((a, l), 0) | (1 << slot)
        # Prop. 3 (insert): Q^(ℓ) changes iff g asserts every a ∈ Q at level ≥ ℓ
        for key in list(self.cache):
            props, l, _ = key
            if all(st.get(a, 0.0) >= l for a in props):
                del self.cache[key]
                self.stats["invalidations"] += 1
        return slot

    def delete(self, tool: str) -> None:
        slot = self.slot_of.pop(tool, None)
        if slot is None:
            return
        mask = ~(1 << slot)
        self.live &= mask
        for k in self.E:
            self.E[k] &= mask
        self.tool_at[slot] = None
        self.strengths.pop(tool, None)
        # Prop. 3 (delete): Q^(ℓ) changes iff g ∈ Q^(ℓ)
        for key in list(self.cache):
            if (self.cache[key] >> slot) & 1:
                del self.cache[key]
                self.stats["invalidations"] += 1

    # --------------------------------------------------------------- queries
    def prop_bitmap(self, a: str, level: float) -> int:
        """E_a^(ℓ); off-ladder levels are answered by a scan over stored strengths."""
        if (a, level) in self.E or level in self._ladder():
            return self.E.get((a, level), 0) & self.live
        out = 0
        for t, st in self.strengths.items():
            if st.get(a, 0.0) >= level:
                out |= 1 << self.slot_of[t]
        return out

    def visibility_bitmap(self, visible: Iterable[str] | None) -> int:
        if visible is None:
            return self.live
        out = 0
        for t in visible:
            s = self.slot_of.get(t)
            if s is not None:
                out |= 1 << s
        return out & self.live

    def eligible_positive(self, props: Iterable[str], level: float, visible: Iterable[str] | None = None,
                          use_cache: bool = True) -> int:
        """Eq. (3). The cache stores B^(ℓ) unprojected; V is applied after (Lemma 1)."""
        props = frozenset(props)
        key = (props, level, 0)
        if use_cache and key in self.cache:
            self.stats["cache_hits"] += 1
            b = self.cache[key]
        else:
            self.stats["cache_misses"] += 1
            b = self.live
            for a in props:
                b &= self.prop_bitmap(a, level)
            if use_cache:
                self.cache[key] = b
        return b & self.visibility_bitmap(visible)

    def eligible_closed_world(self, forbidden: Iterable[str], level: float, candidates: int | None = None,
                              visible: Iterable[str] | None = None) -> int:
        """Eq. (2): CW_ℓ(C, F) = C \\ ⋃_f E_f^(ℓ)."""
        c = self.live if candidates is None else candidates
        removed = 0
        for f in forbidden:
            removed |= self.prop_bitmap(f, level)
        return c & ~removed & self.visibility_bitmap(visible)

    def to_ids(self, bm: int) -> list[str]:
        return [self.tool_at[s] for s in bits(bm) if self.tool_at[s] is not None]

    def __len__(self) -> int:
        return popcount(self.live)
