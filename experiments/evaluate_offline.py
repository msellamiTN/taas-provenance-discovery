#!/usr/bin/env python3
"""Run an offline PaMCP evaluator against a frozen JSON payload (no MCP execution)."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from taas.experiments.offline_evaluator import evaluate_payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", required=True, choices=[f"E{i}" for i in range(1, 23)])
    parser.add_argument("--input", required=True, type=Path, help="Frozen JSON payload")
    parser.add_argument("--output", required=True, type=Path, help="Result JSON destination")
    parser.add_argument("--run-id", required=True, help="Preassigned immutable run identifier")
    parser.add_argument("--code-commit", required=True, help="Full code commit SHA used for evaluation")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    raw = args.input.read_bytes()
    input_sha256 = hashlib.sha256(raw).hexdigest()
    document = json.loads(raw)
    if not isinstance(document, dict) or not isinstance(document.get("payload"), dict):
        raise ValueError("Input JSON must be an object containing a payload object")
    required_metadata = ("protocol_version", "dataset_snapshot_hash", "definition_hash_manifest")
    missing_metadata = [key for key in required_metadata if not document.get(key)]
    if missing_metadata:
        raise ValueError(f"Frozen input metadata missing: {missing_metadata}")
    payload = dict(document["payload"])
    payload.setdefault("seed", args.seed)
    result = evaluate_payload(args.experiment, payload)
    output = {
        "schema_version": "1.0.0",
        "experiment_id": args.experiment,
        "run_id": args.run_id,
        "code_commit": args.code_commit,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "seed": args.seed,
        "protocol_version": document["protocol_version"],
        "dataset_snapshot_hash": document.get("dataset_snapshot_hash"),
        "definition_hash_manifest": document.get("definition_hash_manifest"),
        "parameters": document.get("parameters", {}),
        "input_sha256": input_sha256,
        "evaluator": "taas.experiments.offline_evaluator.evaluate_payload",
        "execution_scope": "offline evaluation only; no MCP servers or tools invoked",
        "result_status": "evaluated_payload_not_experiment_completion",
        "result": result,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(output, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8") + b"\n"
    args.output.write_bytes(encoded)
    print(json.dumps({
        "experiment_id": args.experiment,
        "run_id": args.run_id,
        "input_sha256": input_sha256,
        "output_sha256": hashlib.sha256(encoded).hexdigest(),
        "output": str(args.output),
        "result_status": output["result_status"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
