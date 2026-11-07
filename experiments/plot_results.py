#!/usr/bin/env python3
"""Validate, template, and render the PaMCP E1-E22 publication figures."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from taas.experiments.plotting import (  # noqa: E402
    PLOT_PLAN_PATH,
    create_csv_templates,
    iter_figures,
    load_plot_plan,
    plan_summary,
    render_experiments,
    validate_figure_data,
    validate_plot_plan,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("validate", help="validate all E1-E22 plot contracts against frozen catalogues")

    init = sub.add_parser("init-templates", help="create header-only CSV templates; inserts no observations")
    init.add_argument("--input-dir", type=Path, default=ROOT / "results/visualization/data")
    init.add_argument("--overwrite", action="store_true")

    check = sub.add_parser("validate-data", help="validate available CSV inputs without rendering")
    check.add_argument("--experiment", help="E1 ... E22; default validates all")
    check.add_argument("--input-dir", type=Path, default=ROOT / "results/visualization/data")
    check.add_argument("--strict", action="store_true", help="fail if any expected CSV is missing")

    render = sub.add_parser("render", help="render available experiment CSVs to PDF, SVG and PNG")
    render.add_argument("--experiment", help="E1 ... E22; default attempts all")
    render.add_argument("--input-dir", type=Path, default=ROOT / "results/visualization/data")
    render.add_argument("--output-dir", type=Path, default=ROOT / "results/visualization/figures")
    render.add_argument("--formats", nargs="+", choices=["pdf", "svg", "png"], default=["pdf", "svg", "png"])
    render.add_argument("--dpi", type=int, default=300)
    render.add_argument("--strict", action="store_true", help="fail if any expected CSV is missing or invalid")
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.command == "validate":
            print(json.dumps(plan_summary(), indent=2))
            return 0

        plan = load_plot_plan()
        if args.command == "init-templates":
            paths = create_csv_templates(args.input_dir, plan=plan, overwrite=args.overwrite)
            print(json.dumps({"created": len(paths), "directory": str(args.input_dir),
                              "note": "Header-only files; no experimental observations were generated."}, indent=2))
            return 0

        selected = list(iter_figures(plan, args.experiment))
        if args.command == "validate-data":
            checked, missing, errors = [], [], []
            for figure in selected:
                path = args.input_dir / f'{figure["id"]}.csv'
                if not path.exists():
                    missing.append(figure["id"])
                    continue
                try:
                    import pandas as pd
                    result = validate_figure_data(figure, pd.read_csv(path))
                    checked.append({"figure_id": figure["id"], **result})
                except Exception as exc:
                    errors.append(f'{figure["id"]}: {type(exc).__name__}: {exc}')
            report = {"checked": len(checked), "missing": missing, "errors": errors}
            print(json.dumps(report, indent=2))
            if errors or (args.strict and missing):
                return 2
            return 0

        result = render_experiments(
            experiment_id=args.experiment,
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            formats=tuple(args.formats),
            dpi=args.dpi,
            strict=args.strict,
        )
        print(json.dumps(result, indent=2))
        return 2 if result["errors"] else 0
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
