#!/usr/bin/env python3
"""Reproduce the conservative E1 lexical pre-annotation pilot v0.1.

This creates triage candidates only. It does NOT create ground-truth labels.
"""
import argparse
import csv
import hashlib
import re
from collections import Counter
from pathlib import Path

PATTERNS = {
    "money": re.compile(r"\\b(refund|purchase|pay(?:ment)?|transfer funds|charge (?:a|the)|place an order|buy)\\b", re.I),
    "delete": re.compile(r"\\b(delete|remove|drop|erase|purge|clear (?:the|a|all)|cancel (?:the|a))\\b", re.I),
    "exec": re.compile(r"\\b(execute|run)\\s+(?:a |the |an )?(?:command|script|code|query|process|program|shell)", re.I),
    "write": re.compile(r"\\b(create|write|update|edit|modify|insert|add|save|upload|send|submit|publish|commit|append|set|assign|move|copy|rename|replace|install|deploy|provision|grant|revoke|subscribe|unsubscribe)\\b", re.I),
}
READ = re.compile(r"\\b(read|get|fetch|list|search|find|query|retrieve|lookup|describe|show|view|inspect|analy[sz]e|calculate|compute|convert|validate|check|summari[sz]e|load|extract|parse|rank|recommend|forecast|predict|compare|count|statistics|details|information|weather|price|times|standings|results)\\b", re.I)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("input_csv")
    p.add_argument("output_csv")
    a = p.parse_args()
    with open(a.input_csv, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    counts = Counter()
    for row in rows:
        evidence = ((row.get("tool_name") or "") + " " + (row.get("description") or "")).strip()
        hits = [name for name, pattern in PATTERNS.items() if pattern.search(evidence)]
        if hits:
            row["non_read_only"] = "true"
            row["effect_classes"] = "|".join(hits)
            row["confidence_0_1"] = "0.65"
            row["rationale"] = (
                "AI-assisted candidate based on explicit operation verb(s) in the documented "
                "tool name/description: " + ", ".join(hits) +
                ". Lexical triage only; not verified runtime behavior."
            )
            counts["true"] += 1
        elif (row.get("description") or "").strip() and READ.search(evidence):
            row["non_read_only"] = "false"
            row["effect_classes"] = "read"
            row["confidence_0_1"] = "0.45"
            row["rationale"] = (
                "Provisional retrieval/analysis candidate based on documented wording. "
                "Not proof of read-only behavior; indirect writes and external/session effects remain unverified."
            )
            counts["false"] += 1
        else:
            row["non_read_only"] = ""
            row["effect_classes"] = ""
            row["confidence_0_1"] = "0.00"
            row["rationale"] = (
                "UNRESOLVED: supplied name/description does not support a defensible classification. "
                "Requires richer documentation or runtime evidence; do not infer from readOnlyHint or category."
            )
            counts["unresolved"] += 1
    out = Path(a.output_csv)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    print({"rows": len(rows), "counts": dict(counts), "sha256": digest})

if __name__ == "__main__":
    main()
