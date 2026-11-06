"""Hybrid semantic and structural retrieval over an eligibility-restricted index (Eqs. 3–5).

* s_lex  : BM25 between r(g) and the tool's name, class and description;
* s_den  : cosine between dense vectors. The paper uses BGE-M3 [42]; it cannot be downloaded in
           the build environment, so the default ``LSAEncoder`` (TF-IDF word+char n-grams → SVD)
           stands in. Any ``encode(list[str]) -> np.ndarray`` object can replace it.
* s_str  : Eq. (4) 1[H(e) <: out(g)] · κ_H(e) · |T(e) ∩ reach| / |T(e)|.
* fusion : Eq. (5) reciprocal-rank fusion with k0 = 60.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable, Iterable, Protocol, Sequence

import numpy as np

from .contracts import CapabilityContract
from .types import SemType, subtype

_TOK = re.compile(r"[a-z0-9]+|[一-鿿]")


def tokenize(s: str) -> list[str]:
    s = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", s or "").lower().replace("_", " ").replace("-", " ")
    return _TOK.findall(s)


class BM25:
    def __init__(self, docs: Sequence[str], k1: float = 1.5, b: float = 0.75) -> None:
        self.toks = [tokenize(d) for d in docs]
        self.k1, self.b = k1, b
        self.avgdl = sum(len(t) for t in self.toks) / max(1, len(self.toks))
        df: Counter[str] = Counter()
        for t in self.toks:
            df.update(set(t))
        n = len(self.toks)
        self.idf = {w: math.log(1 + (n - f + 0.5) / (f + 0.5)) for w, f in df.items()}
        self.tf = [Counter(t) for t in self.toks]

    def scores(self, query: str, idx: Iterable[int] | None = None) -> dict[int, float]:
        q = tokenize(query)
        idx = range(len(self.toks)) if idx is None else idx
        out = {}
        for i in idx:
            tf, dl = self.tf[i], len(self.toks[i])
            s = 0.0
            for w in q:
                f = tf.get(w, 0)
                if f:
                    s += self.idf.get(w, 0.0) * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
            out[i] = s
        return out


class Encoder(Protocol):
    def fit(self, docs: Sequence[str]) -> "Encoder": ...
    def encode(self, texts: Sequence[str]) -> np.ndarray: ...


class LSAEncoder:
    """Local dense encoder: TF-IDF → truncated SVD → L2.

    Degenerate corpora (one document or zero across-document variance) use normalized
    TF-IDF vectors directly. This avoids sklearn's undefined explained-variance ratio
    while preserving a finite, query-compatible representation.
    """

    def __init__(self, dim: int = 128, seed: int = 0) -> None:
        self.dim, self.seed = dim, seed

    def fit(self, docs: Sequence[str]) -> "LSAEncoder":
        from scipy.sparse import hstack
        from sklearn.decomposition import TruncatedSVD
        from sklearn.feature_extraction.text import TfidfVectorizer

        if not docs:
            raise ValueError("LSAEncoder.fit requires at least one document")
        self.w = TfidfVectorizer(tokenizer=tokenize, token_pattern=None, ngram_range=(1, 2),
                                 sublinear_tf=True, min_df=1)
        self.c = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True, min_df=1)
        X = hstack([self.w.fit_transform(docs), self.c.fit_transform(docs)]).tocsr()

        # TruncatedSVD.explained_variance_ratio_ divides by total feature variance.
        # That denominator is zero for a one-row or identical-document corpus.
        mean = np.asarray(X.mean(axis=0)).ravel()
        mean_sq = np.asarray(X.multiply(X).mean(axis=0)).ravel()
        total_variance = float(np.maximum(mean_sq - mean * mean, 0.0).sum())
        self._use_svd = X.shape[0] >= 2 and X.shape[1] >= 2 and total_variance > 1e-12
        if self._use_svd:
            k = min(self.dim, X.shape[0] - 1, X.shape[1] - 1)
            self.svd = TruncatedSVD(k, random_state=self.seed).fit(X)
        else:
            self.svd = None
        return self

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        from scipy.sparse import hstack

        X = hstack([self.w.transform(texts), self.c.transform(texts)]).tocsr()
        V = self.svd.transform(X) if self._use_svd else X.toarray()
        return V / (np.linalg.norm(V, axis=1, keepdims=True) + 1e-12)


def structural_score(head: SemType, kappa: float, tail: Sequence[SemType], goal_out: SemType,
                     reach: set[SemType], kappa_min: float, match: bool | None = None) -> float:
    """Eq. (4); zero unless the head is a certain subtype of out(g) (or ``match`` for effect goals)."""
    ok = subtype(head, goal_out) if match is None else match
    if not ok or kappa < kappa_min:
        return 0.0
    frac = 1.0 if not tail else sum(1 for t in tail if any(subtype(s, t) for s in reach)) / len(tail)
    return kappa * frac


@dataclass
class HybridRetriever:
    """ϱ(g, H|Elig, K): fuse lexical, dense and structural rankings by reciprocal rank."""

    k0: int = 60
    kappa_min: float = 0.5
    components: tuple[str, ...] = ("lex", "den", "str")
    encoder: Encoder = field(default_factory=LSAEncoder)
    ids: list[str] = field(default_factory=list)

    def fit(self, contracts: Sequence[CapabilityContract]) -> "HybridRetriever":
        self.contracts = {c.tool: c for c in contracts}
        self.ids = [c.tool for c in contracts]
        self.pos = {t: i for i, t in enumerate(self.ids)}
        docs = [c.rendering() for c in contracts]
        self.bm25 = BM25(docs)
        self.encoder.fit(docs)
        self.vecs = self.encoder.encode(docs)
        return self

    def add(self, c: CapabilityContract) -> None:
        """Incremental insertion (index follows registry events without refitting the encoder)."""
        self.contracts[c.tool] = c
        if c.tool in self.pos:
            i = self.pos[c.tool]
            self.vecs[i] = self.encoder.encode([c.rendering()])[0]
        else:
            self.pos[c.tool] = len(self.ids)
            self.ids.append(c.tool)
            self.vecs = np.vstack([self.vecs, self.encoder.encode([c.rendering()])])
        self.bm25 = BM25([self.contracts[t].rendering() for t in self.ids])

    def scores(self, query: str, goal_out: SemType | None, eligible: Iterable[str], reach: set[SemType],
               components: Sequence[str] | None = None,
               matcher: Callable[[CapabilityContract], bool] | None = None) -> dict[str, float]:
        comps = tuple(components or self.components)
        elig = [t for t in eligible if t in self.pos]
        if not elig:
            return {}
        idx = [self.pos[t] for t in elig]
        rankings: list[dict[str, float]] = []
        if "lex" in comps:
            s = self.bm25.scores(query, idx)
            rankings.append({self.ids[i]: v for i, v in s.items()})
        if "den" in comps:
            q = self.encoder.encode([query])[0]
            sims = self.vecs[idx] @ q
            rankings.append({t: float(v) for t, v in zip(elig, sims)})
        if "str" in comps and goal_out is not None:
            rankings.append({t: structural_score(self.contracts[t].head, self.contracts[t].out.confidence,
                                                 self.contracts[t].tail, goal_out, reach, self.kappa_min,
                                                 matcher(self.contracts[t]) if matcher else None)
                             for t in elig})
        fused: dict[str, float] = {t: 0.0 for t in elig}
        for r in rankings:
            order = sorted(r.items(), key=lambda kv: (-kv[1], kv[0]))
            for rank, (t, v) in enumerate(order, start=1):
                if v > 0 or len(rankings) == 1:
                    fused[t] += 1.0 / (self.k0 + rank)
        return fused

    def retrieve(self, query: str, goal_out: SemType | None, eligible: Iterable[str], reach: set[SemType], k: int,
                 type_filter: bool = True, components: Sequence[str] | None = None,
                 matcher: Callable[[CapabilityContract], bool] | None = None) -> list[tuple[str, float]]:
        """Top-K eligible edges; with ``type_filter`` only edges that serve the goal with certain typing."""
        s = self.scores(query, goal_out, eligible, reach, components, matcher)
        items = sorted(s.items(), key=lambda kv: (-kv[1], kv[0]))
        if type_filter and goal_out is not None:
            ok = matcher or (lambda c: subtype(c.head, goal_out))
            items = [(t, v) for t, v in items
                     if ok(self.contracts[t]) and self.contracts[t].out.confidence >= self.kappa_min]
        return items[:k]
