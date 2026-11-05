"""E0 campaign runner: coverage-aware, immutable, silver-label agreement report.

This runner deliberately does not call experiments.common.save() and never overwrites
results/e0_registry.json. Metrics against silver_labels.json are agreement metrics,
not independently validated ground-truth accuracy.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from taas.data.registries import raw_tools_from_processed
from taas.effects import lexical_effects, modifies_state
from taas.realreg import truth


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run(root: Path, output: Path) -> dict:
    processed = root / "data/processed/registry_merged.json"
    labels = root / "data/llm_records/silver_labels.json"
    if not processed.is_file() or not labels.is_file():
        raise FileNotFoundError("Required processed registry or silver labels file is missing")
    d = json.loads(processed.read_text(encoding="utf-8"))
    raw = raw_tools_from_processed(d)
    J = truth()
    ids = {t.id for t in raw}
    matched = ids & set(J)
    missing = ids - set(J)
    labelled = [t for t in raw if t.id in J]
    ann = [t for t in raw if t.annotations]
    ann_not_ro = [t.id for t in ann if t.id in J and J[t.id].unsafe_read_only]
    silver_mod = {t.id for t in labelled if J[t.id].unsafe_read_only}
    lex_mod = {
        t.id for t in labelled
        if modifies_state(lexical_effects(
            t.name, t.description,
            list(((t.input_schema or {}).get("properties") or {}).keys())
        ))
    }
    tp = len(lex_mod & silver_mod)
    precision = tp / len(lex_mod) if lex_mod else None
    recall = tp / len(silver_mod) if silver_mod else None
    f1 = (2 * precision * recall / (precision + recall)
          if precision is not None and recall is not None and precision + recall else None)
    effect_classes = Counter(
        e.cls for t in labelled for e in J[t.id].effects
    )
    total = len(raw)
    ann_true = sum((t.annotations or {}).get("readOnlyHint") is True for t in ann)
    ann_false = sum((t.annotations or {}).get("readOnlyHint") is False for t in ann)
    ann_unknown = len(ann) - ann_true - ann_false
    result = {
        "experiment": "E0_registry_characterisation",
        "status": "EXECUTED",
        "interpretation": "Registry characterization; lexical-vs-silver agreement only, not independent ground-truth validation.",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": __import__("subprocess").run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True
        ).stdout.strip() or None,
        "inputs": {
            "registry_path": str(processed.relative_to(root)),
            "registry_sha256": sha256(processed),
            "silver_labels_path": str(labels.relative_to(root)),
            "silver_labels_sha256": sha256(labels),
        },
        "coverage": {
            "registry_tools": total,
            "silver_label_records": len(J),
            "matched_registry_tools": len(matched),
            "missing_registry_labels": len(missing),
            "coverage_fraction": len(matched) / total if total else None,
            "missing_sample": sorted(missing)[:30],
            "extra_silver_label_records": len(set(J) - ids),
        },
        "table1": {
            k: {x: v.get(x) for x in ("servers", "tools", "annotated")}
            for k, v in d["stats"].items() if k != "requests"
        },
        "requests": d["stats"].get("requests", {}),
        "published_annotations": {
            "annotated_tools": len(ann),
            "readOnlyHint_true": ann_true,
            "readOnlyHint_false": ann_false,
            "readOnlyHint_missing": ann_unknown,
            "annotated_but_unsafe_by_silver": ann_not_ro,
        },
        "silver_label_analysis": {
            "labelled_registry_tools": len(labelled),
            "silver_state_modifying_count": len(silver_mod),
            "silver_state_modifying_share_of_labelled": len(silver_mod) / len(labelled) if labelled else None,
            "lexical_state_modifying_count": len(lex_mod),
            "lexical_state_modifying_share_of_labelled": len(lex_mod) / len(labelled) if labelled else None,
            "lexical_vs_silver": {
                "precision": precision, "recall": recall, "f1": f1,
                "true_positive": tp,
                "false_positive": len(lex_mod - silver_mod),
                "false_negative": len(silver_mod - lex_mod),
            },
            "silver_effect_classes": dict(effect_classes),
        },
        "limitations": [
            "silver_labels.json is model-generated silver annotation, not an independent adjudicated oracle",
            "metrics are computed only on registry tools with matching silver labels",
            "published MCP annotations are metadata claims, not observed runtime effects",
            "no sandbox probes or external model calls are performed by this E0 runner",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive create: a previous campaign report is never overwritten.
    with output.open("x", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    return result


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, default=Path("."))
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    r = run(a.root.resolve(), a.output.resolve())
    print(json.dumps({
        "status": r["status"],
        "registry_tools": r["coverage"]["registry_tools"],
        "matched_labels": r["coverage"]["matched_registry_tools"],
        "missing_labels": r["coverage"]["missing_registry_labels"],
        "annotation_counts": r["published_annotations"],
        "lexical_vs_silver": r["silver_label_analysis"]["lexical_vs_silver"],
        "report_path": str(a.output),
        "interpretation": r["interpretation"],
    }, indent=2))


if __name__ == "__main__":
    main()
