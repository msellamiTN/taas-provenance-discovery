"""Fail-closed run ledger for the definitive PaMCP E1-E22 programme."""
from __future__ import annotations
import hashlib, json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping
from taas.experiments.catalog import load_catalog

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_LEDGER = ROOT / "results" / "pamcp_runs.jsonl"
DEFAULT_DEPENDENCIES = ROOT / "docs" / "experiment_design" / "pamcp_execution_dependencies_v1.json"
EXPERIMENT_IDS = {f"E{i}" for i in range(1, 23)}
LEDGER_STATUSES = {"running", "completed", "failed"}

class RunBlocked(RuntimeError):
    """Execution cannot be proven protocol-compliant."""

def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def _assert_acyclic(dependencies: Mapping[str, list[str]]) -> None:
    visiting, visited = set(), set()
    def visit(node: str) -> None:
        if node in visiting: raise RunBlocked(f"Cycle in dependency graph at {node}")
        if node in visited: return
        visiting.add(node)
        for parent in dependencies[node]: visit(parent)
        visiting.remove(node); visited.add(node)
    for node in dependencies: visit(node)

def validate_dependency_manifest(data: Mapping[str, Any]) -> dict[str, Any]:
    """Validate both file-loaded and injected manifests identically."""
    deps = data.get("depends_on")
    if data.get("schema_version") != "1.0.0" or data.get("programme") != "PaMCP":
        raise RunBlocked("Unsupported dependency manifest")
    if not isinstance(deps, dict) or set(deps) != EXPERIMENT_IDS:
        raise RunBlocked("Dependency manifest must define E1-E22 exactly once")
    external = data.get("external_prerequisites")
    if not isinstance(external, dict) or set(external) != EXPERIMENT_IDS:
        raise RunBlocked("External prerequisites must define E1-E22 exactly once")
    for exp, parents in deps.items():
        if not isinstance(parents, list) or any(not isinstance(p, str) for p in parents):
            raise RunBlocked(f"Invalid prerequisite list for {exp}")
        if len(parents) != len(set(parents)):
            raise RunBlocked(f"Duplicate prerequisite for {exp}")
        if any(p not in EXPERIMENT_IDS or p == exp for p in parents):
            raise RunBlocked(f"Invalid prerequisite reference for {exp}")
    for exp, gates in external.items():
        if not isinstance(gates, list) or any(not isinstance(g, str) or not g.strip() for g in gates):
            raise RunBlocked(f"Invalid external prerequisite list for {exp}")
        if len(gates) != len(set(gates)):
            raise RunBlocked(f"Duplicate external prerequisite for {exp}")
    _assert_acyclic(deps)
    return dict(data)

def load_dependency_manifest(path: Path = DEFAULT_DEPENDENCIES) -> dict[str, Any]:
    if not path.is_file():
        raise RunBlocked("Missing approved execution dependency manifest; do not infer DAG edges.")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RunBlocked("Dependency manifest is not valid UTF-8 JSON") from exc
    if not isinstance(data, dict):
        raise RunBlocked("Dependency manifest root must be an object")
    return validate_dependency_manifest(data)

def read_ledger(path: Path = DEFAULT_LEDGER) -> list[dict[str, Any]]:
    if not path.exists(): return []
    records = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip(): continue
        try: item = json.loads(line)
        except json.JSONDecodeError as exc: raise RunBlocked(f"Corrupt ledger at line {n}") from exc
        if (not isinstance(item, dict) or item.get("experiment_id") not in EXPERIMENT_IDS
                or item.get("status") not in LEDGER_STATUSES):
            raise RunBlocked(f"Invalid ledger record at line {n}")
        records.append(item)
    return records

def latest_successes(records: list[dict[str, Any]]) -> set[str]:
    latest = {}
    for item in records:
        if (not isinstance(item, dict) or item.get("experiment_id") not in EXPERIMENT_IDS
                or item.get("status") not in LEDGER_STATUSES):
            raise RunBlocked("Malformed run-ledger record")
        latest[item["experiment_id"]] = item["status"]
    return {key for key, status in latest.items() if status == "completed"}

def append_record(record: dict[str, Any], path: Path = DEFAULT_LEDGER) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")

def execute_experiment(experiment_id: str, *, handler: Callable[[dict[str, Any]], Mapping[str, Any]] | None,
                       input_manifest: Mapping[str, Any], dependency_manifest: Mapping[str, Any] | None = None,
                       ledger_path: Path = DEFAULT_LEDGER, catalog_path: Path | None = None) -> dict[str, Any]:
    if handler is None: raise RunBlocked(f"No validated implementation registered for {experiment_id}")
    if experiment_id not in EXPERIMENT_IDS: raise RunBlocked(f"Unknown experiment: {experiment_id}")
    catalog = load_catalog() if catalog_path is None else load_catalog(catalog_path)
    experiment = next((e for e in catalog["experiments"] if e["id"] == experiment_id), None)
    if experiment is None: raise RunBlocked(f"Unknown experiment: {experiment_id}")
    if experiment["status"] != "planned_not_run": raise RunBlocked("Frozen catalogue status changed")
    if dependency_manifest is None: dependency_manifest = load_dependency_manifest()
    else: dependency_manifest = validate_dependency_manifest(dependency_manifest)
    deps = dependency_manifest["depends_on"][experiment_id]
    missing = sorted(set(deps) - latest_successes(read_ledger(ledger_path)))
    if missing: raise RunBlocked(f"{experiment_id} blocked by incomplete prerequisites: {missing}")
    required_gates = dependency_manifest["external_prerequisites"][experiment_id]
    gate_evidence = input_manifest.get("external_gate_evidence", {})
    if not isinstance(gate_evidence, Mapping):
        raise RunBlocked("external_gate_evidence must be an object")
    missing_gates = []
    for gate in required_gates:
        evidence = gate_evidence.get(gate)
        digest = evidence.get("sha256", "") if isinstance(evidence, Mapping) else ""
        refs = evidence.get("artifact_refs", []) if isinstance(evidence, Mapping) else []
        valid_digest = (isinstance(digest, str) and len(digest) == 64
                        and all(ch in "0123456789abcdef" for ch in digest.lower()))
        if (not isinstance(evidence, Mapping) or evidence.get("status") != "satisfied"
                or not isinstance(refs, list) or not refs
                or any(not isinstance(ref, str) or not ref.strip() for ref in refs)
                or not valid_digest):
            missing_gates.append(gate)
    if missing_gates:
        raise RunBlocked(f"{experiment_id} blocked by unsatisfied or unproven external prerequisites: {missing_gates}")
    required = ("dataset_snapshot_hash", "code_revision")
    if any(not input_manifest.get(k) for k in required): raise RunBlocked("Dataset hash and code revision are required")
    if "seed" not in input_manifest: raise RunBlocked("An explicit seed is required, including zero")
    if input_manifest.get("protocol_version") != "1.0.0": raise RunBlocked("Only protocol 1.0.0 is accepted")
    record = {"experiment_id": experiment_id, "status": "running", "protocol_version": "1.0.0",
              "catalog_hash": canonical_hash(catalog), "definition_hash": canonical_hash(experiment),
              "input_manifest": dict(input_manifest), "input_hash": canonical_hash(input_manifest),
              "dependencies": deps, "external_prerequisites": required_gates,
              "external_gate_evidence": {g: dict(gate_evidence[g]) for g in required_gates},
              "started_at": datetime.now(timezone.utc).isoformat()}
    append_record(record, ledger_path)
    try:
        result = dict(handler(dict(input_manifest)))
        if result.get("status") != "completed" or not result.get("artifacts"):
            raise RunBlocked("Handler must return completed plus at least one artifact reference")
        record.update(status="completed", result=result, result_hash=canonical_hash(result),
                      finished_at=datetime.now(timezone.utc).isoformat())
    except Exception as exc:
        record.update(status="failed", error_type=type(exc).__name__, error=str(exc),
                      finished_at=datetime.now(timezone.utc).isoformat())
        append_record(record, ledger_path)
        raise
    append_record(record, ledger_path)
    return record
