"""Independent set evaluator for E10 (joint feasibility). Written separately from src/taas/certificate.py and
using only the reference labels B (types and effects) and the analyst's goal record, so it does not share
the engine's typing, evidence or composition code.

Checks (named after the certificate's checks they mirror):
* S  every goal the analyst marks as needing the outside world (sigma != native) is served by a tool of K:
     data goals by a tool whose B output kind equals the goal's output kind (collections ignored); effect
     goals by a tool whose B classes contain the goal's effect class;
* C  every required input of every tool in K is obtainable: its B input kind is produced by the prompt,
     by another tool of K, or is a kind the model can write (text, query, number, boolean, datetime,
     identifier, url, location, path);
* E  every tool's B effect classes are allowed by the task's least-privilege policy;
* L  no private-output tool together with a caller-chosen egress tool (exfiltration pair);
* V  every tool carries verifier evidence at the policy level (provenance; from the evidence store);
* M  no tool can be removed while S still holds.
Joint feasibility = S and C and E and L.
"""
from __future__ import annotations

import fe

MODEL_KINDS = {"text", "query", "number", "boolean", "datetime", "identifier", "url", "location", "path"}
ALLOWED_BASE = {"read", "egress", "egress_any", "session"}


def _kind(s: str) -> str:
    s = (s or "").strip().lower().replace("[]", "")
    return s.split(":")[0] if s else "none"


def goal_needs(rec: dict) -> list[dict]:
    out = []
    for g in rec.get("goals", []):
        if g.get("optional") or g.get("sigma", "native") == "native":
            continue
        eff = [e.split("(")[0].strip().lower() for e in (g.get("eff") or [])]
        eff = [e for e in eff if e in ("write", "delete", "exec", "money")]
        out.append({"id": g["id"], "kind": _kind(g.get("out", "")), "effects": eff, "sigma": g.get("sigma")})
    return out


def serves(tool: dict, need: dict) -> bool:
    cls = set(tool.get("classes") or [])
    if need["effects"]:
        return all(e in cls for e in need["effects"])
    return _kind(tool.get("out", "")) == need["kind"] and need["kind"] != "none"


def evaluate(K: list[str], rec: dict, need_classes: set[str], prompt_kinds: set[str] | None = None,
             verified: set[str] | None = None) -> dict:
    Bd = fe.labels_B_raw()
    tools = {t: Bd.get(t, {}) for t in K}
    needs = goal_needs(rec)
    prompt_kinds = prompt_kinds or {_kind(x) for x in rec.get("prompt_inputs", [])}
    S_missing = [n["id"] for n in needs if not any(serves(tools[t], n) for t in K)]
    produced = {_kind(tools[t].get("out", "")) for t in K} | prompt_kinds | MODEL_KINDS
    mism = 0
    for t in K:
        for a, ty in (tools[t].get("in") or {}).items():
            k = _kind(ty)
            if k not in produced and k != "none":
                mism += 1
    allowed = ALLOWED_BASE | set(need_classes)
    forbidden = [t for t in K if set(tools[t].get("classes") or []) - allowed]
    priv = [t for t in K if tools[t].get("private")]
    egr = [t for t in K if "egress_any" in (tools[t].get("classes") or [])]
    flow_bad = bool(priv and egr and "egress_any" not in need_classes)
    unverified = [t for t in K if verified is not None and t not in verified]
    removable = [t for t in K if needs and not [n for n in needs if not any(serves(tools[u], n) for u in K if u != t)]]
    S, C, E, L = not S_missing, mism == 0, not forbidden, not flow_bad
    return {"S": S, "C": C, "E": E, "L": L, "V": not unverified if verified is not None else None,
            "M": not removable, "joint": S and C and E and L, "n_missing": len(S_missing), "interface_mismatch": mism,
            "forbidden_tools": len(forbidden), "flow_violation": flow_bad, "unverified": len(unverified),
            "n_needs": len(needs)}


# ------------------------------------------------------------------------------------------------ Revision 2
# A stricter variant of the evaluator (review Major 7). Differences from ``evaluate``:
# * S: the output must match the goal's kind AND domain (when both name one) AND collection (a goal that needs a
#   collection is not served by a single item);
# * C: only arguments the published schema marks as required must be obtainable, and only text, query, number,
#   boolean and datetime are taken as writable by the model (identifiers, URLs, paths and locations must come from
#   the prompt or another tool);
# * L: a private-output tool together with ANY egress tool (fixed or caller-chosen destination) is a violation
#   unless the task needs egress.
# Still not checked by either variant (no data for it in the labels): resource scope of effects, credentials and
# prerequisites, declassification conditions. Those cases are reported as limitations by the audit.
STRICT_MODEL_KINDS = {"text", "query", "number", "boolean", "datetime"}


def _parts(s: str) -> tuple[str, str, bool]:
    s = (s or "").strip().lower()
    coll = s.endswith("[]")
    s = s.replace("[]", "")
    k, _, d = s.partition(":")
    return (k or "none"), d, coll


def serves_strict(tool: dict, need: dict, goal_out: str) -> bool:
    cls = set(tool.get("classes") or [])
    if need["effects"]:
        return all(e in cls for e in need["effects"])
    gk, gd, gc = _parts(goal_out)
    tk, td, tc = _parts(tool.get("out", ""))
    if gk == "none" or tk != gk:
        return False
    if gd and td and gd != td:
        return False
    return tc or not gc


def evaluate_strict(K: list[str], rec: dict, need_classes: set[str], prompt_kinds: set[str] | None = None,
                    verified: set[str] | None = None, required: dict[str, set[str]] | None = None,
                    labels: dict | None = None) -> dict:
    Bd = labels if labels is not None else fe.labels_B_raw()
    tools = {t: Bd.get(t, {}) for t in K}
    goals = {g["id"]: g for g in rec.get("goals", [])}
    needs = goal_needs(rec)
    prompt_kinds = prompt_kinds or {_parts(x)[0] for x in rec.get("prompt_inputs", [])}

    def served(n, pool):
        return any(serves_strict(tools[t], n, goals[n["id"]].get("out", "")) for t in pool)
    S_missing = [n["id"] for n in needs if not served(n, K)]
    produced = {_parts(tools[t].get("out", ""))[0] for t in K} | prompt_kinds | STRICT_MODEL_KINDS
    mism = 0
    for t in K:
        req = (required or {}).get(t)
        for a, ty in (tools[t].get("in") or {}).items():
            if req is not None and a not in req:
                continue
            k = _parts(ty)[0]
            if k not in produced and k != "none":
                mism += 1
    allowed = ALLOWED_BASE | set(need_classes)
    forbidden = [t for t in K if set(tools[t].get("classes") or []) - allowed]
    priv = [t for t in K if tools[t].get("private")]
    egr = [t for t in K if {"egress", "egress_any"} & set(tools[t].get("classes") or [])]
    flow_bad = bool(priv and egr and not ({"egress", "egress_any"} & set(need_classes)))
    unverified = [t for t in K if verified is not None and t not in verified]
    removable = [t for t in K if needs and all(served(n, [u for u in K if u != t]) for n in needs)]
    S, C, E, L = not S_missing, mism == 0, not forbidden, not flow_bad
    return {"S": S, "C": C, "E": E, "L": L, "V": not unverified if verified is not None else None,
            "M": not removable, "joint": S and C and E and L, "n_missing": len(S_missing), "interface_mismatch": mism,
            "forbidden_tools": len(forbidden), "flow_violation": flow_bad}
