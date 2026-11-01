"""Run every experiment in dependency order and produce the figures (python experiments/run_all.py)."""
from __future__ import annotations

import json
import time

from common import RESULTS, banner

import e0_registry
import e2_eligibility
import e3_gap
import e3_tune
import e4_injection
import e5_synthetic
import e6_ablations
import e7_scalability
import plot


def main() -> None:
    t0 = time.time()
    log = {}
    for name, fn in [("e0", e0_registry.main), ("e2", e2_eligibility.main), ("e3_tune", e3_tune.main),
                     ("e3", lambda: e3_gap.run(analyst_model="sonnet")), ("e4", e4_injection.main),
                     ("e5", e5_synthetic.main), ("e6", e6_ablations.main), ("e7", e7_scalability.main)]:
        t = time.time()
        fn()
        log[name] = round(time.time() - t, 1)
    plot.main()
    log["total_s"] = round(time.time() - t0, 1)
    json.dump(log, open(RESULTS / "run_log.json", "w"), indent=1)
    banner(f"all experiments finished in {log['total_s']} s")


if __name__ == "__main__":
    main()
