"""PaMCP experiment-catalog CLI. Does not execute experiments."""
from __future__ import annotations
import argparse
import json
from taas.experiments.catalog import load_catalog, VARIANTS, validate_factorial

def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect the frozen PaMCP E1-E22 design.")
    parser.add_argument("command", choices=["list", "show", "variants", "validate"])
    parser.add_argument("--id", dest="experiment_id")
    args = parser.parse_args()
    data = load_catalog()
    validate_factorial(data)
    if args.command == "list":
        out = [{"id": e["id"], "title": e["title"], "status": e["status"]} for e in data["experiments"]]
    elif args.command == "show":
        if not args.experiment_id:
            parser.error("--id is required for show")
        out = next((e for e in data["experiments"] if e["id"] == args.experiment_id.upper()), None)
        if out is None:
            raise SystemExit(f"Unknown experiment: {args.experiment_id}")
    elif args.command == "variants":
        out = {k: vars(v) for k,v in VARIANTS.items()}
    else:
        out = {"valid": True, "experiments": len(data["experiments"]),
               "factorial_cells": len(data["factorial_design"]["cells"]),
               "variants": list(VARIANTS), "all_planned_not_run": all(
                   e["status"] == "planned_not_run" for e in data["experiments"])}
    print(json.dumps(out, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
