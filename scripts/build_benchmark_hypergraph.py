#!/usr/bin/env python3
"""Build a non-destructive TaaS capability hypergraph from benchmark registry data."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from taas.benchmark_hypergraph import build_from_processed_registry, write_bundle


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--outdir", required=True,
        help="new or empty output directory (existing non-empty directories are refused)",
    )
    args = parser.parse_args()
    _, graph, benchmark, report = build_from_processed_registry()
    write_bundle(Path(args.outdir), graph, benchmark, report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
