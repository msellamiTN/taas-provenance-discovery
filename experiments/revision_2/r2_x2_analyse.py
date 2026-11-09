"""Revision 2, X2 analysis: observed runtime effects of the MCP reference servers versus the two LLM labellings
(J_A Sonnet, J_B Opus), the providers' annotations, and the registry snapshot (definition drift).

Observed state change ("content" reading): a write, rename or delete of a user file in the sandbox, of the server's
own store (outside the sandbox, outside caches), or of version-control content (.git/objects, refs, HEAD); writes of
.git/index and lock files alone are incidental (index refresh) and are reported separately ("strict" reading).
Only calls that completed without error ("exercised") enter the label comparison. An observed effect is definitive;
a labelled effect that the probe did not trigger is "unconfirmed", not wrong.
Evidence class: OBSERVED (controlled execution of the reference servers), compared with LABELLED references.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "final"))
import fe  # noqa: E402
wilson = fe.wilson

REC = ROOT / "data" / "x2_probe"
STATE = {"write", "delete", "exec", "money"}


def norm(d):
    if isinstance(d, dict):
        return {k: norm(v) for k, v in d.items() if v is not None and k not in ("$schema", "title")}
    if isinstance(d, list):
        return [norm(x) for x in d]
    return d


def observed_state(o: dict) -> tuple[bool, bool]:
    paths = o.get("write", []) + o.get("delete", [])
    content = [p for p in paths if not (p.endswith("/.git/index") or p.endswith(".lock") or "/.git/index" in p)]
    return bool(paths), bool(content)


def main() -> None:
    probes = {}
    for line in (REC / "probes.jsonl").read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            probes[r["id"]] = r                      # last record per tool (re-probes after argument fixes)
    inv = json.loads((REC / "inventory.json").read_text())
    reg = {t["id"]: t for t in json.loads((ROOT / "data/processed/registry_merged.json").read_text())["registry"]}
    ja = json.loads((ROOT / "data/llm_records/silver_labels.json").read_text())
    jb = {}
    for k in range(3):
        for x in (ROOT / f"data/llm_records/reference_labels_opus_part{k}.jsonl").read_text().splitlines():
            if x.strip():
                r = json.loads(x)
                jb[r["id"]] = r
    rows, drift = [], []
    for srv, rec in sorted(inv.items()):
        live = {t["name"]: t for t in rec.get("tools", [])}
        for tid, t in sorted(reg.items()):
            if t["server"] != srv:
                continue
            lv = live.get(t["name"])
            drift.append({"id": tid, "present": lv is not None,
                          "description_changed": lv is not None and (lv["description"] or "") != (t["description"] or ""),
                          "schema_changed": lv is not None and norm(lv["input_schema"]) != norm(t["input_schema"]),
                          "schema_unpublished": lv is not None and not (lv["input_schema"] or {}).get("properties"),
                          "annotations_changed": lv is not None and norm(lv["annotations"] or {}) != norm(t["annotations"] or {})})
        for name in live:
            if f"{srv}::{name}" not in reg:
                drift.append({"id": f"{srv}::{name}", "present": True, "new_tool": True})
    live_ann = {f"{srv}::{t['name']}": (t.get("annotations") or {}) for srv, rec in inv.items()
                for t in rec.get("tools", [])}
    for tid, p in sorted(probes.items()):
        o = p.get("observed", {})
        strict, content = observed_state(o)
        a_cls = {e.split("(")[0] for e in ja.get(tid, {}).get("effects", [])}
        b_cls = set(jb.get(tid, {}).get("classes", []))
        ann = (reg.get(tid, {}).get("annotations") or {})
        rows.append({"id": tid, "server": p["server"], "status": p["status"], "exercised": p["status"] == "ok",
                     "obs_state_strict": strict, "obs_state": content, "obs_network": bool(o.get("network")),
                     "obs_exec_caller": bool(o.get("exec_caller")), "obs_exec_internal": bool(o.get("exec_internal")),
                     "obs_read_seed": bool(o.get("read_seed")),
                     "ja_state": bool(a_cls & STATE) or bool(ja.get(tid, {}).get("modifies_state")),
                     "jb_state": bool(b_cls & STATE) or bool(jb.get(tid, {}).get("state")),
                     "ja_network": bool(a_cls & {"egress"}) or any(e in ("read(api)", "read(web)") for e in ja.get(tid, {}).get("effects", [])),
                     "jb_network": bool(b_cls & {"egress", "egress_any"}),
                     "read_only_hint": ann.get("readOnlyHint"),
                     "live_read_only_hint": live_ann.get(tid, {}).get("readOnlyHint"),
                     "live_destructive_hint": live_ann.get(tid, {}).get("destructiveHint"),
                     "ann_state": live_ann.get(tid, {}).get("readOnlyHint") is not True,
                     "args": p.get("args"),
                     "result_head": (p.get("result_head") or "")[:160]})
    ex = [r for r in rows if r["exercised"]]

    def conf(lab: str, obs: str = "obs_state"):
        tp = sum(r[lab] and r[obs] for r in ex)
        fn = sum((not r[lab]) and r[obs] for r in ex)
        fp = sum(r[lab] and not r[obs] for r in ex)
        tn = sum((not r[lab]) and not r[obs] for r in ex)
        pos = tp + fn
        return {"tp": tp, "fn": fn, "fp_unconfirmed": fp, "tn": tn,
                "false_safe_rate": fn / pos if pos else None, "false_safe_ci": list(wilson(fn, pos)) if pos else None,
                "agreement": (tp + tn) / len(ex) if ex else None}

    by_server = {}
    for r in rows:
        s = by_server.setdefault(r["server"], {"probed": 0, "exercised": 0, "obs_state": 0, "obs_network": 0})
        s["probed"] += 1
        s["exercised"] += r["exercised"]
        s["obs_state"] += r["exercised"] and r["obs_state"]
        s["obs_network"] += r["obs_network"]
    n_reg = sum(1 for d in drift if not d.get("new_tool"))
    res = {
        "servers": {k: {"started": v.get("started"), "server_info": v.get("server_info"), "protocol": v.get("protocol"),
                        "live_tools": len(v.get("tools", [])), "schema_violations": len(v.get("schema_violations", [])),
                        "start_s": v.get("start_s")} for k, v in inv.items()},
        "probed": len(rows), "exercised": len(ex), "by_server": by_server,
        "observed_state_changing": sum(r["obs_state"] for r in ex),
        "observed_incidental_only": sum(r["obs_state_strict"] and not r["obs_state"] for r in ex),
        "labels_vs_observed_state": {"J_A": conf("ja_state"), "J_B": conf("jb_state"),
                                     "live_annotations": conf("ann_state")},
        "live_annotated": sum(r["live_read_only_hint"] is not None for r in rows),
        "labels_vs_observed_network": {"J_A": conf("ja_network", "obs_network"), "J_B": conf("jb_network", "obs_network")},
        "annotated": sum(r["read_only_hint"] is not None for r in rows),
        "drift": {"registry_tools": n_reg, "present": sum(d["present"] for d in drift if not d.get("new_tool")),
                  "removed": sum(not d["present"] for d in drift if not d.get("new_tool")),
                  "new_tools": sum(1 for d in drift if d.get("new_tool")),
                  "description_changed": sum(d.get("description_changed", False) for d in drift),
                  "schema_changed": sum(d.get("schema_changed", False) for d in drift),
                  "schema_unpublished": sum(d.get("schema_unpublished", False) for d in drift),
                  "annotations_changed": sum(d.get("annotations_changed", False) for d in drift),
                  "hash_invalidated": sum(d["present"] and (d.get("description_changed") or d.get("schema_changed")
                                                            or d.get("annotations_changed")) for d in drift
                                          if not d.get("new_tool"))},
        "disagreements": [r for r in ex if r["obs_state"] != r["ja_state"] or r["obs_state"] != r["jb_state"]],
    }
    fe.save("R2_X2_observed", res, "OBSERVED (strace + sandbox snapshots of the MCP reference servers) vs LABELLED",
            config={"servers": sorted(inv), "call_timeout_s": 25, "probe": "one call per tool, synthesised arguments"},
            raw=fe.save_raw("R2_X2_observed", rows + [{"drift": d} for d in drift]))
    print(json.dumps({k: v for k, v in res.items() if k not in ("disagreements", "servers")}, indent=1)[:2500])


if __name__ == "__main__":
    main()
