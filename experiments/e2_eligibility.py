"""E2 — H2: provenance-sound eligibility removes unsafe tools under forged and missing metadata,
while exposure grows with the verifier's false-accept rate (Prop. 2, Observation 1).

Policy: read-only (the property MCP's readOnlyHint claims). Ground truth: silver labels J.
Attack: a fraction α of servers forge readOnlyHint=true and launder their descriptions; the
verifier (sandbox, outside the attacker's control) accepts a false read-only claim with prob. FAR.

Encodings compared (all through the same bitmap index):
  ann+      MCP default: admit declared read-only tools only            (positive, ℓann)
  ann-cw    read a missing/false hint as safe: forbid declared writers    (closed-world, ℓann)
  lex+      admit tools whose name/description look read-only             (positive, ℓlex)
  lex-cw    forbid tools whose name/description look like writers         (closed-world, ℓlex)
  obs+      admit tools verified read-only in the sandbox                 (positive, ℓobs)  ← paper
  att+      admit tools attested read-only by a trusted signer            (positive, ℓatt)
Metrics: exposure = |Elig ∩ Unsafe| / |Unsafe|, unsafe share of Elig, safe retention.
"""
from __future__ import annotations

from common import SEEDS, banner, mean_ci, save

from taas.bitmap_index import BitmapIndex
from taas.provenance import LEVELS
from taas.realreg import build_contracts, raw_registry, truth
from taas.simulation import Verifier, attack_registry

ENCODINGS = {
    "ann+": ("positive", {"read_only"}, LEVELS["ann"]),
    "ann-cw": ("closed_world", {"writes", "deletes", "execs", "pays"}, LEVELS["ann"]),
    "lex+": ("positive", {"read_only"}, LEVELS["lex"] * 0.99),
    "lex-cw": ("closed_world", {"writes", "deletes", "execs", "pays"}, LEVELS["lex"] * 0.99),
    "obs+": ("positive", {"read_only"}, LEVELS["obs"]),
    "att+": ("positive", {"read_only"}, LEVELS["att"]),
}


METADATA_ONLY = {"ann+", "ann-cw", "lex+", "lex-cw"}


def evaluate(index: BitmapIndex, J, ids: list[str], meta_index: BitmapIndex | None = None) -> dict:
    """Metadata-only encodings are evaluated on ``meta_index`` (what an MCP client holds: lexical cues
    and published annotations); evidence encodings on ``index`` (registry with sandbox/attestation)."""
    unsafe = {t for t in ids if J[t].unsafe_read_only}
    safe = set(ids) - unsafe
    out = {}
    for name, (enc, props, lvl) in ENCODINGS.items():
        idx = meta_index if (meta_index is not None and name in METADATA_ONLY) else index
        bm = idx.eligible_positive(props, lvl, use_cache=False) if enc == "positive" else \
            idx.eligible_closed_world(props, lvl)
        el = set(idx.to_ids(bm))
        out[name] = {"eligible": len(el), "exposure": len(el & unsafe) / max(1, len(unsafe)),
                     "unsafe_share": len(el & unsafe) / max(1, len(el)),
                     "safe_retention": len(el & safe) / max(1, len(safe)), "unsafe_admitted": len(el & unsafe)}
    return out


def main(alphas=(0.0, 0.1, 0.25, 0.5), fars=(0.0, 0.01, 0.05, 0.1, 0.2), runnable=1.0, attest=0.3) -> dict:
    banner("E2 / H2: which eligibility encodings stay sound when servers forge or omit metadata "
           "(expected: ann+/lex+ admit forged tools; obs+ exposure = 0 at FAR=0 and grows with FAR)")
    raw0 = raw_registry()
    J = truth()
    rows = []
    metas: dict = {}
    for a in alphas:
        for far in fars:
            for s in SEEDS:
                raw, adv = attack_registry(raw0, a, seed=s)
                store = Verifier(far=far, runnable=runnable, seed=100 + s).run(raw, J, attest=attest)
                cs = build_contracts(raw, store)
                idx = BitmapIndex()
                for c in cs:
                    idx.insert(c)
                if (a, s) not in metas:
                    metas[(a, s)] = BitmapIndex()
                    for c in build_contracts(raw, None):
                        metas[(a, s)].insert(c)
                ev = evaluate(idx, J, [c.tool for c in cs], metas[(a, s)])
                for enc, m in ev.items():
                    rows.append({"alpha": a, "far": far, "seed": s, "encoding": enc, **m})
    summary = {}
    for a in alphas:
        for far in fars:
            for enc in ENCODINGS:
                sel = [r for r in rows if r["alpha"] == a and r["far"] == far and r["encoding"] == enc]
                summary[f"a={a}|far={far}|{enc}"] = {k: mean_ci(r[k] for r in sel)
                                                    for k in ("exposure", "unsafe_share", "safe_retention", "eligible")}
    # coverage sweep: verifier runs only a fraction of tools (credential-free servers), FAR=0.05, α=0.25
    cov = []
    for runnable_frac in (0.25, 0.5, 0.75, 1.0):
        for s in SEEDS:
            raw, _ = attack_registry(raw0, 0.25, seed=s)
            store = Verifier(far=0.05, runnable=runnable_frac, seed=200 + s).run(raw, J, attest=0.0)
            idx = BitmapIndex()
            for c in build_contracts(raw, store):
                idx.insert(c)
            m = evaluate(idx, J, [t.id for t in raw])["obs+"]
            cov.append({"runnable": runnable_frac, "seed": s, **m})
    res = {"rows": rows, "summary": summary, "coverage": cov}
    print(f"{'alpha':>5} {'far':>5} " + " ".join(f"{e:>14s}" for e in ENCODINGS))
    for a in alphas:
        for far in fars:
            cells = [summary[f'a={a}|far={far}|{e}']['exposure']['mean'] for e in ENCODINGS]
            print(f"{a:5.2f} {far:5.2f} " + " ".join(f"{x:14.3f}" for x in cells))
    print("(cells = exposure: share of truly unsafe tools admitted under a read-only policy)")
    for e in ENCODINGS:
        m = summary[f"a=0.25|far=0.05|{e}"]
        print(f"  α=0.25 FAR=0.05 {e:7s} unsafe share of Elig={m['unsafe_share']['mean']:.3f} "
              f"safe retention={m['safe_retention']['mean']:.3f} |Elig|={m['eligible']['mean']:.0f}")
    save("e2_eligibility", res)
    return res


if __name__ == "__main__":
    main()
