"""E4 supplement: unsafe tools admitted by each read-only encoding (set level, labels B), coverage 1.
Complements Exp@k, which depends on pool size (a single admitted unsafe tool in a 44-tool pool reaches many
top-5 lists)."""
import fe
import e04_e07_exposure as X
from taas.realreg import build_contracts


def main():
    A, B = fe.labels_A(), fe.labels_B()
    raw = fe.raw()
    cs = build_contracts(raw, None)
    el = X.eligibility(raw, cs, X.verifier_decisions(raw, A, rho=1.0, seed=0))
    unsafe = {t for t in B if B[t].unsafe_read_only}
    out = {e: {"eligible": len(s), "unsafe_admitted": len(s & unsafe), "unsafe_total": len(unsafe),
               "exposure_share": len(s & unsafe) / len(unsafe), "unsafe_ids": sorted(s & unsafe)[:20]}
           for e, s in el.items()}
    fe.save("E4_admitted", {"results": out}, "SIMULATED evidence (labels A), scored against labels B",
            config={"rho": 1.0, "far": 0.0, "seed": 0})
    for e, v in out.items():
        print(e, v["eligible"], v["unsafe_admitted"], round(v["exposure_share"], 3))


if __name__ == "__main__":
    main()
