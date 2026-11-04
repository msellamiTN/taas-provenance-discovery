"""Inspect the frozen PaMCP experiment and baseline catalogues; no runs are executed."""
from __future__ import annotations

import argparse
import json

from taas.experiments.baseline_catalog import baseline_index, load_baseline_catalog
from taas.experiments.catalog import VARIANTS, load_catalog, validate_factorial


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect the PaMCP E1-E22 and baseline definitions.")
    parser.add_argument("command", choices=["list", "show", "variants", "validate", "baselines", "show-baseline"])
    parser.add_argument("--id", dest="item_id")
    args = parser.parse_args()
    data = load_catalog()
    validate_factorial(data)

    if args.command == "list":
        out = [{"id": e["id"], "title": e["title"], "status": e["status"],
                "baseline_ids": e.get("baseline_ids", [])} for e in data["experiments"]]
    elif args.command == "show":
        if not args.item_id:
            parser.error("--id is required for show")
        out = next((e for e in data["experiments"] if e["id"] == args.item_id.upper()), None)
        if out is None:
            raise SystemExit(f"Unknown experiment: {args.item_id}")
    elif args.command == "variants":
        out = {k: vars(v) for k, v in VARIANTS.items()}
    elif args.command == "baselines":
        catalog = load_baseline_catalog()
        out = {"schema_version": catalog["schema_version"], "baselines": catalog["baselines"]}
    elif args.command == "show-baseline":
        if not args.item_id:
            parser.error("--id is required for show-baseline")
        out = baseline_index().get(args.item_id)
        if out is None:
            raise SystemExit(f"Unknown baseline: {args.item_id}")
    else:
        baseline_catalog = load_baseline_catalog()
        baseline_ids = {x["id"] for x in baseline_catalog["baselines"]}
        missing = {b for e in data["experiments"] for b in e.get("baseline_ids", [])} - baseline_ids
        if missing:
            raise SystemExit(f"Unknown baseline IDs referenced by experiments: {sorted(missing)}")
        out = {
            "valid": True,
            "experiments": len(data["experiments"]),
            "baselines": len(baseline_ids),
            "factorial_cells": len(data["factorial_design"]["cells"]),
            "variants": list(VARIANTS),
            "all_planned_not_run": all(e["status"] == "planned_not_run" for e in data["experiments"]),
        }
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
