"""E1 registry characterisation (three source views), E2 typing agreement (proxy: no human annotators),
E3 declared/lexical effects against the reference labels (observed effects BLOCKED: no runnable servers).

Run: python experiments/final/e01_e03_registry_typing_effects.py <path to raw dir with mcptoolbenchpp/*.json>
"""
from __future__ import annotations

import csv
import random
import statistics as st
import sys
from collections import Counter
from pathlib import Path

import fe
from effect_metrics import confusion_with_unknown
from taas.data.registries import load_mcptoolbenchpp
from taas.types import parse_type

STATE_CLASSES = {"write", "delete", "exec", "money"}

LABEL_INPUTS = [
    "data/llm_records/silver_labels.json",
    "data/llm_records/reference_labels_opus_part0.jsonl",
    "data/llm_records/reference_labels_opus_part1.jsonl",
    "data/llm_records/reference_labels_opus_part2.jsonl",
]


def view_stats(tools: list[dict], name: str) -> dict:
    A, B = fe.labels_A(), fe.labels_B()
    srv = Counter(t["server"] for t in tools)
    L = [len(t["description"] or "") for t in tools]
    ann = [t for t in tools if t.get("annotations")]
    ro = [t for t in ann if (t["annotations"] or {}).get("readOnlyHint") is True]
    ids = [t["id"] for t in tools]
    cats = Counter(f"{t['source']}:{t['category']}" for t in tools)
    out = {"view": name, "tools": len(tools), "servers": len(srv),
           "tools_per_server": {"median": st.median(srv.values()), "mean": st.mean(srv.values()),
                                "max": max(srv.values())},
           "categories": dict(sorted(cats.items())), "n_categories": len(cats),
           "annotated": len(ann), "annotated_share": len(ann) / len(tools),
           "declared_read_only": len(ro), "declared_read_only_share": len(ro) / len(tools),
           "description_chars": {"mean": st.mean(L), "median": st.median(L),
                                 "p90": sorted(L)[int(0.9 * (len(L) - 1))], "empty": sum(1 for x in L if x == 0)},
           "non_read_only_B": sum(B[i].unsafe_read_only for i in ids if i in B),
           "non_read_only_A": sum(A[i].unsafe_read_only for i in ids if i in A),
           "labelled": sum(1 for i in ids if i in B)}
    out["non_read_only_B_share"] = out["non_read_only_B"] / out["labelled"] if out["labelled"] else float("nan")
    out["non_read_only_B_ci"] = fe.wilson(out["non_read_only_B"], out["labelled"])
    out["annotated_but_unsafe_B"] = [t["id"] for t in ro if t["id"] in B and B[t["id"]].unsafe_read_only]
    return out


def e1(raw_dir: Path) -> dict:
    reg = list(fe.reg().values())
    pp_tools, _ = load_mcptoolbenchpp(raw_dir)
    R = fe.reg()
    pp = []
    for t in pp_tools:
        d = R.get(t.id)
        pp.append({"id": t.id, "server": t.server, "description": t.description, "annotations": t.annotations,
                   "source": "MCPToolBench++", "category": getattr(t, "category", "") or (d or {}).get("category", "")})
    views = {"LiveMCPTool": [t for t in reg if t["source"] == "LiveMCPTool"], "MCPToolBench++ (original 87)": pp,
             "merged": reg}
    res = {k: view_stats(v, k) for k, v in views.items()}
    res["overlap"] = {"tools_in_both": len({t["id"] for t in pp} & {t["id"] for t in views["LiveMCPTool"]}),
                      "servers_in_both": len({t["server"] for t in pp} & {t["server"] for t in views["LiveMCPTool"]})}
    res["raw_inputs"] = {p.name: fe.sha256(p) for p in sorted((raw_dir / "mcptoolbenchpp").glob("*.json"))}
    return res


def kind(s: str) -> str:
    try:
        return parse_type(s).kind
    except Exception:
        return "invalid"


def e2() -> dict:
    """Typing agreement on output types: τ (labels A, used by the engine), the structural/lexical typer of the
    engine without LLM labels (schema + name heuristics), and the independent labels B."""
    A = fe.silver_raw() if hasattr(fe, "silver_raw") else None
    from taas.realreg import silver
    S = silver()
    Bd = fe.labels_B_raw()
    from taas.types import tau_out
    R = fe.reg()
    rows = []
    for tid, t in R.items():
        a, b = S.get(tid, {}), Bd.get(tid, {})
        struct = tau_out(t["name"], t["description"] or "", t.get("output_schema"))
        rows.append({"id": tid, "tau": str(a.get("out", "")), "ref": str(b.get("out", "")),
                     "struct": str(struct.type), "struct_conf": struct.confidence, "conf_A": a.get("conf", 1.0),
                     "sure_B": b.get("sure", 1.0)})
    out = {"n": len(rows), "_rows": rows}
    for m in ("tau", "struct"):
        ka = [kind(r[m]) for r in rows]
        kb = [kind(r["ref"]) for r in rows]
        exact = [r[m].replace("[]", "") == r["ref"].replace("[]", "") for r in rows]
        out[m] = {"kind_agreement": sum(x == y for x, y in zip(ka, kb)) / len(rows), "kind_kappa": fe.kappa(ka, kb),
                  "type_agreement_no_collection": sum(exact) / len(rows)}
        # per-kind precision/recall/F1 against the reference kind
        per = {}
        for k in sorted(set(kb)):
            tp = sum(1 for x, y in zip(ka, kb) if x == k and y == k)
            fp = sum(1 for x, y in zip(ka, kb) if x == k and y != k)
            fn = sum(1 for x, y in zip(ka, kb) if x != k and y == k)
            p = tp / (tp + fp) if tp + fp else 0.0
            r_ = tp / (tp + fn) if tp + fn else 0.0
            per[k] = {"support": tp + fn, "precision": p, "recall": r_, "f1": 2 * p * r_ / (p + r_) if p + r_ else 0.0}
        out[m]["per_kind"] = per
        out[m]["macro_f1"] = sum(v["f1"] for v in per.values()) / len(per)
    # confidence thresholds (engine's typing confidence κ_e of the structural typer; uncertain = below)
    out["struct_thresholds"] = {}
    for th in (0.5, 0.7, 0.9):
        sel = [r for r in rows if r["struct_conf"] >= th]
        out["struct_thresholds"][str(th)] = {
            "certain_share": len(sel) / len(rows),
            "kind_agreement_certain": (sum(kind(r["struct"]) == kind(r["ref"]) for r in sel) / len(sel)) if sel else None}
    return out


def human_sheet(n: int = 150, seed: int = 11) -> Path:
    """Blank, stratified annotation sheet for the human E2/J study (protocol E2): by source and by whether
    labels A and B disagree, so disagreements are over-sampled. Columns for two annotators, no labels shown."""
    A, B = fe.labels_A(), fe.labels_B()
    R = fe.reg()
    rng = random.Random(seed)
    dis = [t for t in R if A[t].unsafe_read_only != B[t].unsafe_read_only or A[t].private_source != B[t].private_source]
    rest = [t for t in R if t not in dis]
    pick = dis + rng.sample(rest, n - len(dis))
    rng.shuffle(pick)
    p = fe.ROOT / "docs" / "annotation" / "E2_human_annotation_sheet.csv"
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["item", "tool_id", "description", "arguments", "annotator", "modifies_state", "effect_classes",
                    "private_output", "output_type", "input_types", "notes"])
        for i, t in enumerate(pick):
            d = R[t]
            args = "; ".join(((d["input_schema"] or {}).get("properties") or {}).keys())
            for ann in ("A1", "A2"):
                w.writerow([i, t, (d["description"] or "").replace("\n", " "), args, ann, "", "", "", "", "", ""])
    return p


def e3() -> dict:
    """Declared (annotations) and lexical effect inference against labels B; labels A against B.
    Observed effects (sandbox traces) are BLOCKED: no runnable servers in this environment."""
    A, B = fe.labels_A(), fe.labels_B()
    cs = {c.tool: c for c in fe.contracts_cached("declared")}
    R = fe.reg()
    ids = sorted(R)
    ref = [B[t].unsafe_read_only for t in ids]

    declared = []
    for t in ids:
        an = R[t].get("annotations") or {}
        declared.append(None if "readOnlyHint" not in an else (not an["readOnlyHint"]))
    lexical = [any(cs[t].strength(p) >= 0.25 for p in ("writes", "deletes", "execs", "pays")) for t in ids]
    silverA = [A[t].unsafe_read_only for t in ids]
    out = {"n": len(ids), "reference_unsafe_B": sum(ref),
           "declared_vs_B": confusion_with_unknown(declared, ref),
           "lexical_vs_B": confusion_with_unknown(lexical, ref),
           "labelsA_vs_B": confusion_with_unknown(silverA, ref),
           "kappa_A_B_state": fe.kappa(silverA, ref),
           "kappa_A_B_private": fe.kappa([A[t].private_source for t in ids], [B[t].private_source for t in ids]),
           "class_agreement": {}}
    for c in ("write", "delete", "exec", "money", "egress"):
        a = [any(e.cls == c for e in A[t].effects) for t in ids]
        b = [any(e.cls == c for e in B[t].effects) for t in ids]
        out["class_agreement"][c] = {"A": sum(a), "B": sum(b), "kappa": fe.kappa(a, b)}
    out["observed"] = "BLOCKED: requires runnable credential-free MCP servers and probe traces"
    return out


def main(raw_dir: str) -> None:
    r1 = e1(Path(raw_dir))
    fe.save("E1_registry", {"results": r1}, "MEASURED (counts); LABELLED (non-read-only share, labels B)",
            inputs=LABEL_INPUTS, config={"views": ["LiveMCPTool", "MCPToolBench++ (original 87)", "merged"]},
            notes="Three views; categories are source-qualified (LiveMCPTool server categories and "
                  "MCPToolBench++ request categories are different taxonomies).")
    r2 = e2()
    rows2 = r2.pop("_rows")
    sheet = human_sheet()
    fe.save("E2_typing", {"results": r2, "human_sheet": str(sheet.relative_to(fe.ROOT)),
                          "human_sheet_sha256": fe.sha256(sheet)},
            "LABELLED (agreement with independent LLM labels B); human study BLOCKED (sheet prepared)",
            inputs=LABEL_INPUTS, notes="Agreement, not accuracy: neither labelling is human ground truth.",
            config={"thresholds": [0.5, 0.7, 0.9], "sheet_items": 150, "sheet_seed": 11},
            raw=fe.save_raw("E2_typing", rows2))
    r3 = e3()
    fe.save("E3_effects_tristate", {"results": r3}, "LABELLED (LLM labels A/B); observed effects BLOCKED",
            inputs=LABEL_INPUTS, notes="Declared = MCP readOnlyHint (missing = unknown); lexical = engine's lexical cues.")
    print({k: (v["tools"], v["servers"], v["annotated"], v["non_read_only_B"]) for k, v in r1.items()
           if isinstance(v, dict) and "tools" in v})
    print("E2", {m: (round(r2[m]["kind_agreement"], 3), round(r2[m]["kind_kappa"], 3), round(r2[m]["macro_f1"], 3))
                 for m in ("tau", "struct")})
    print("E3 kappa", round(r3["kappa_A_B_state"], 3), "lex", r3["lexical_vs_B"], "decl", r3["declared_vs_B"])


if __name__ == "__main__":
    main(sys.argv[1])
