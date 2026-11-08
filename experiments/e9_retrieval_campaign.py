#!/usr/bin/env python3
"""Protocol-gated E9 LiveMCPBench retrieval campaign.

The runner creates discovery rankings without loading evaluator references. It reads
the evaluator reference file only after rankings.jsonl and its checksum are frozen.
No GoalSpecs, semantic contracts, effects, calibration profiles, training scenes or
equivalence labels are inferred from evaluation references.

The E1/E2/E3/E12 and comparator-approval gate is mandatory. Unit-test fixtures and
unaccepted proposal artifacts cannot be used as empirical experiment inputs.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from collections import defaultdict
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from taas.composer import ComposerConfig
from taas.contracts import Arg, CapabilityContract, QoS
from taas.effects import FlowTransformer, parse_effects
from taas.engine import DiscoveryEngine, EngineConfig
from taas.experiments.baseline_catalog import baselines_for_experiment
from taas.experiments.baseline_runner import BaselineResult, run_baseline
from taas.goals import GoalSpec, parse_goal_spec
from taas.model_profile import ModelProfile
from taas.policy import Declassification, Policy
from taas.provenance import ProvenanceRecord
from taas.retrieval import HybridRetriever
from taas.types import TypeAssignment, parse_type

DECOMPOSITIONS = ("none", "clause_splitter", "llm_analyst")
RANKING_CUTOFFS = (1, 3, 5, 10, 20)
PRIMARY_CONFIGURATION_ID = "Full_PaMCP"
REQUIRED_PREREQUISITES = ("E1", "E2", "E3", "E12")
FORBIDDEN_EVALUATOR_KEYS = {
    "acceptable_tool_sets", "target_tool_ids", "qrels", "labels", "gtfa_claims",
    "trajectory_reference", "reference_trace_tool_ids", "answer", "reference_answer",
    "relevance_judgments",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_sha256(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return sha256_text(raw)


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as stream:
        for line_no, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSONL: {exc}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_no}: expected a JSON object")
            rows.append(row)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def git_value(*args: str) -> str | None:
    try:
        return subprocess.check_output(
            ["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def load_discovery_package(prepared_dir: Path):
    """Load only discovery-side material; evaluator references are deliberately untouched."""
    manifest_path = prepared_dir / "PREPARATION_MANIFEST.json"
    tools_path = prepared_dir / "discovery" / "tools.json"
    tasks_path = prepared_dir / "discovery" / "tasks.jsonl"
    visibility_path = prepared_dir / "discovery" / "task_visibility.jsonl"
    for path in (manifest_path, tools_path, tasks_path, visibility_path):
        if not path.is_file():
            raise FileNotFoundError(f"Missing E9 discovery input: {path}")

    manifest = read_json(manifest_path)
    if manifest.get("experiment_id") != "E9" or manifest.get("status") != "prepared_not_run":
        raise ValueError("Dataset package must identify E9 and prepared_not_run")
    tools = json.loads(tools_path.read_text(encoding="utf-8"))
    tasks = read_jsonl(tasks_path)
    visibility = read_jsonl(visibility_path)
    if not isinstance(tools, list) or not tools:
        raise ValueError("E9 candidate registry must be a non-empty JSON array")

    tool_ids = [str(row.get("tool_id") or "") for row in tools]
    if any(not value for value in tool_ids) or len(tool_ids) != len(set(tool_ids)):
        raise ValueError("E9 tool IDs must be non-empty and unique")
    task_by_id = {str(row.get("task_id") or ""): row for row in tasks}
    vis_by_id = {str(row.get("task_id") or ""): row for row in visibility}
    if "" in task_by_id or len(task_by_id) != len(tasks):
        raise ValueError("E9 task IDs must be non-empty and unique")
    if set(task_by_id) != set(vis_by_id) or len(vis_by_id) != len(visibility):
        raise ValueError("E9 task visibility must match the discovery task IDs exactly")
    candidate_set = set(tool_ids)
    for task_id, row in vis_by_id.items():
        visible = row.get("visible_tool_ids")
        if not isinstance(visible, list) or not visible or len(visible) != len(set(visible)):
            raise ValueError(f"{task_id}: visible_tool_ids must be a non-empty unique list")
        if not set(visible).issubset(candidate_set):
            raise ValueError(f"{task_id}: visible tools fall outside the candidate registry")
    for row in tasks:
        if not str(row.get("prompt") or "").strip():
            raise ValueError(f"{row.get('task_id')}: empty task prompt")
        leaked = FORBIDDEN_EVALUATOR_KEYS.intersection(row)
        if leaked:
            raise ValueError(f"{row.get('task_id')}: evaluator-only keys in discovery task: {sorted(leaked)}")
    return tools, tasks, visibility, manifest


def load_goal_specs(path: Path, tasks: list[dict[str, Any]]) -> dict[tuple[str, str], GoalSpec]:
    rows = read_jsonl(path)
    task_by_id = {str(row["task_id"]): row for row in tasks}
    found: dict[tuple[str, str], GoalSpec] = {}
    for row in rows:
        task_id = str(row.get("task_id") or "")
        decomposition = str(row.get("decomposition") or "")
        if task_id not in task_by_id or decomposition not in DECOMPOSITIONS:
            raise ValueError(f"GoalSpec has unknown task/decomposition: {task_id!r}/{decomposition!r}")
        key = (task_id, decomposition)
        if key in found:
            raise ValueError(f"Duplicate frozen GoalSpec: {key}")
        prompt = str(task_by_id[task_id].get("prompt") or "")
        metadata = row.get("freeze_metadata")
        if row.get("prompt") != prompt or row.get("prompt_sha256") != sha256_text(prompt):
            raise ValueError(f"{task_id}/{decomposition}: frozen prompt/hash mismatch")
        if row.get("evaluator_reference_accessed") is not False:
            raise ValueError(f"{task_id}/{decomposition}: evaluator access must be explicitly false")
        if not isinstance(metadata, dict) or metadata.get("status") != "frozen":
            raise ValueError(f"{task_id}/{decomposition}: freeze metadata is not accepted/frozen")
        if decomposition == "none":
            if metadata.get("transform") != "unsegmented_single_goal":
                raise ValueError(f"{task_id}: none condition must represent the unsegmented request")
        elif decomposition == "clause_splitter":
            for field in ("splitter_version", "splitter_path", "splitter_sha256"):
                if not metadata.get(field):
                    raise ValueError(f"{task_id}: clause-splitter metadata missing {field}")
            splitter_path = Path(metadata["splitter_path"])
            if not splitter_path.is_absolute():
                splitter_path = (path.parent / splitter_path).resolve()
            if not splitter_path.is_file() or sha256_file(splitter_path) != metadata["splitter_sha256"]:
                raise ValueError(f"{task_id}: clause-splitter artifact is missing or hash-mismatched")
        else:
            for field in ("model_id", "model_revision", "prompt_sha256", "raw_response_sha256", "prompt_path", "raw_response_path"):
                if not metadata.get(field):
                    raise ValueError(f"{task_id}: llm_analyst metadata missing {field}")
            for path_key, hash_key in (("prompt_path", "prompt_sha256"), ("raw_response_path", "raw_response_sha256")):
                artifact_path = Path(metadata[path_key])
                if not artifact_path.is_absolute():
                    artifact_path = (path.parent / artifact_path).resolve()
                if not artifact_path.is_file() or sha256_file(artifact_path) != metadata[hash_key]:
                    raise ValueError(f"{task_id}: llm_analyst {path_key} is missing or hash-mismatched")
        spec_data = row.get("goal_spec")
        if not isinstance(spec_data, dict) or not spec_data.get("goals"):
            raise ValueError(f"{task_id}/{decomposition}: non-empty GoalSpec is required")
        spec = parse_goal_spec(spec_data, prompt=prompt)
        if spec.order() is None:
            raise ValueError(f"{task_id}/{decomposition}: cyclic goal dependency graph")
        if decomposition == "none" and len(spec.goals) != 1:
            raise ValueError(f"{task_id}: none condition must have exactly one unsegmented goal")
        found[key] = spec

    expected = {(task_id, mode) for task_id in task_by_id for mode in DECOMPOSITIONS}
    missing = sorted(expected - set(found))
    extra = sorted(set(found) - expected)
    if missing or extra:
        raise ValueError(
            f"Frozen GoalSpec matrix incomplete: missing={missing[:5]} ({len(missing)}), "
            f"extra={extra[:5]} ({len(extra)})"
        )
    return found


def _provenance(value: Any) -> ProvenanceRecord:
    if not isinstance(value, dict):
        raise ValueError("Each provenance record must be a JSON object")
    return ProvenanceRecord(
        ptype=str(value.get("ptype") or ""),
        signer=value.get("signer"),
        kappa=float(value.get("kappa", 1.0)),
        method=str(value.get("method") or ""),
    )


def contract_from_json(row: dict[str, Any]) -> CapabilityContract:
    required = ("tool", "name", "server", "out", "eff", "eff_record", "flow", "h")
    missing = [key for key in required if key not in row]
    if missing:
        raise ValueError(f"Contract missing required fields: {missing}")
    args = tuple(
        Arg(
            name=str(item["name"]),
            type=parse_type(str(item["type"])),
            required=bool(item.get("required", True)),
            confidence=float(item.get("confidence", 1.0)),
            domain=item.get("domain"),
        )
        for item in row.get("args", [])
    )
    output = row["out"]
    flow = row["flow"]
    if not isinstance(output, dict) or "type" not in output or not isinstance(flow, dict):
        raise ValueError(f"{row['tool']}: invalid output/flow contract")
    props = {
        str(prop): [_provenance(record) for record in records]
        for prop, records in (row.get("props") or {}).items()
    }
    return CapabilityContract(
        tool=str(row["tool"]),
        name=str(row["name"]),
        server=str(row["server"]),
        description=str(row.get("description") or ""),
        args=args,
        out=TypeAssignment(
            parse_type(str(output["type"])),
            float(output.get("confidence", 1.0)),
            str(output.get("source") or "accepted_contract"),
        ),
        eff=parse_effects(row["eff"]),
        eff_record=_provenance(row["eff_record"]),
        flow=FlowTransformer(
            source_label=str(flow.get("source_label") or "public"),
            narrowed_args=frozenset(str(value) for value in flow.get("narrowed_args", [])),
        ),
        req=tuple(str(value) for value in row.get("req", [])),
        qos=QoS(**(row.get("qos") or {})),
        srv=dict(row.get("srv") or {}),
        props=props,
        h=str(row["h"]),
        tool_class=str(row.get("tool_class") or "other"),
        tokens=int(row.get("tokens", 0)),
        annotations=row.get("annotations"),
    )


def load_contracts(path: Path, tools: list[dict[str, Any]]) -> tuple[list[CapabilityContract], dict]:
    bundle = read_json(path)
    if bundle.get("schema_version") != "1.0.0" or bundle.get("status") != "accepted":
        raise ValueError("Contract bundle must have schema_version=1.0.0 and status=accepted")
    if bundle.get("evaluator_labels_used_for_contract_generation") is not False:
        raise ValueError("Accepted contract bundle must certify no evaluator-label use")
    rows = bundle.get("contracts")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Contract bundle contains no contracts")
    sources = bundle.get("source_artifacts") or {}
    for experiment in ("E2", "E3"):
        source = sources.get(experiment) or {}
        if source.get("status") != "accepted" or not source.get("sha256"):
            raise ValueError(f"Contract bundle must cite accepted, hash-bound {experiment} inputs")
    tool_by_id = {str(row["tool_id"]): row for row in tools}
    contracts: list[CapabilityContract] = []
    seen: set[str] = set()
    for row in rows:
        contract = contract_from_json(row)
        if contract.tool not in tool_by_id:
            raise ValueError(f"Contract refers to tool outside candidate registry: {contract.tool}")
        expected_hash = str(tool_by_id[contract.tool].get("definition_hash") or "")
        if contract.h != expected_hash or row.get("definition_hash") != expected_hash:
            raise ValueError(f"{contract.tool}: contract is not hash-bound to the prepared definition")
        if contract.tool in seen:
            raise ValueError(f"Duplicate contract for {contract.tool}")
        seen.add(contract.tool)
        contracts.append(contract)
    coverage = len(seen) / max(1, len(tool_by_id))
    return contracts, {
        "contract_count": len(contracts),
        "candidate_tool_count": len(tool_by_id),
        "coverage": coverage,
        "uncontracted_tool_ids": sorted(set(tool_by_id) - seen),
        "bundle_sha256": sha256_file(path),
        "bundle_id": bundle.get("bundle_id"),
        "source_artifacts": bundle.get("source_artifacts", {}),
    }


def make_no_backward_closure_config(base: ComposerConfig) -> ComposerConfig:
    """Return the same frozen PaMCP config with only backward-closure depth set to zero."""
    if base.depth < 1:
        raise ValueError("Full_PaMCP must use positive backward-closure depth")
    ablated = replace(base, depth=0)
    base_values = asdict(base)
    ablated_values = asdict(ablated)
    base_values.pop("depth")
    ablated_values.pop("depth")
    if base_values != ablated_values:
        raise RuntimeError("NoBackwardClosure config changed parameters beyond closure depth")
    return ablated


def load_composer_config(path: Path) -> tuple[ComposerConfig, int, dict]:
    bundle = read_json(path)
    if bundle.get("schema_version") != "1.0.0" or bundle.get("status") != "accepted":
        raise ValueError("E9 composer configuration must be accepted, schema_version=1.0.0")
    if bundle.get("experiment_id") != "E9" or not bundle.get("approval_record"):
        raise ValueError("Composer configuration must be E9-specific and approved")
    values = bundle.get("composer")
    if not isinstance(values, dict):
        raise ValueError("Composer configuration must contain a composer object")
    config = ComposerConfig(**values)
    if config.K != 20:
        raise ValueError("Accepted E9 base composer config must freeze K=20; the campaign applies each protocol K separately")
    if config.depth < 1:
        raise ValueError("Full_PaMCP config must enable backward closure (depth >= 1)")
    refine_k = int(bundle.get("refine_k", -1))
    if not 0 <= refine_k <= 10:
        raise ValueError("Accepted E9 composer config must freeze refine_k in [0,10]")
    return config, refine_k, {
        "bundle_sha256": sha256_file(path),
        "composer": asdict(config),
        "refine_k": refine_k,
        "approval_record": bundle["approval_record"],
    }


def load_policy(path: Path) -> tuple[Policy, str]:
    bundle = read_json(path)
    if bundle.get("schema_version") != "1.0.0" or bundle.get("status") != "accepted":
        raise ValueError("E9 policy bundle must be accepted, schema_version=1.0.0")
    data = bundle.get("policy")
    if not isinstance(data, dict):
        raise ValueError("E9 policy bundle has no policy object")
    declass = tuple(
        Declassification(
            label_from=str(row["label_from"]),
            label_to=str(row["label_to"]),
            tool_classes=frozenset(row.get("tool_classes", ["aggregate"])),
            tools=frozenset(row.get("tools", [])),
            min_evidence=str(row.get("min_evidence", "obs")),
            min_records=int(row.get("min_records", 10)),
        )
        for row in data.get("declass", [])
    )
    policy = Policy(
        name=str(data.get("name") or "E9-policy"),
        required=frozenset(data.get("required", [])),
        forbidden=frozenset(data.get("forbidden", [])),
        encoding=str(data.get("encoding") or "positive"),
        lmin=float(data.get("lmin", 0.65)),
        visible=None if data.get("visible") is None else frozenset(data["visible"]),
        allowed=parse_effects(data.get("allowed", ["read(*)", "egress(*)", "session"])),
        declass=declass,
        egress_threshold=str(data.get("egress_threshold") or "internal"),
        forbidden_pairs=tuple(tuple(pair) for pair in data.get("forbidden_pairs", [["private_read", "egress_any"]])),
        prompt_label=str(data.get("prompt_label") or "public"),
        credentials=None if data.get("credentials") is None else frozenset(data["credentials"]),
    )
    return policy, sha256_file(path)


def load_accepted_profile(path: Path) -> tuple[ModelProfile, dict]:
    bundle = read_json(path)
    if bundle.get("schema_version") != "1.0.0" or bundle.get("status") != "accepted":
        raise ValueError("E12 profile bundle must be accepted and schema_version=1.0.0")
    if bundle.get("calibration_experiment") != "E12":
        raise ValueError("Profile bundle must originate from accepted E12")
    profile_data = bundle.get("model_profile")
    if not isinstance(profile_data, dict):
        raise ValueError("E12 profile bundle does not contain model_profile")
    if not bundle.get("model_id") or not bundle.get("model_revision"):
        raise ValueError("E12 profile bundle must identify the calibrated model and immutable revision")
    profile = ModelProfile.from_json(profile_data)
    if profile.model_id != bundle.get("model_id"):
        raise ValueError("E12 profile model_id does not match the bundle metadata")
    if not profile.classes:
        raise ValueError("E12 model profile has no measured class curves")
    return profile, {
        "bundle_sha256": sha256_file(path),
        "model_id": profile.model_id,
        "tau": profile.tau,
        "profile_sha256": canonical_sha256(profile.to_json()),
    }


class LocalSentenceTransformerEncoder:
    """Local-only pinned sentence-transformer encoder; no implicit model downloads."""

    def __init__(self, model_path: Path, device: str):
        self.model_path = model_path.resolve()
        self.device = device
        self.model = None

    def fit(self, documents: Sequence[str]):
        if self.model is not None:
            return self
        try:
            from importlib.metadata import version
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError("Install the pinned sentence-transformers runtime to execute E9") from exc
        expected_version = getattr(self, "expected_package_version", None)
        if expected_version and version("sentence-transformers") != expected_version:
            raise RuntimeError("sentence-transformers package version differs from the encoder bundle")
        if not self.model_path.exists():
            raise FileNotFoundError(self.model_path)
        # model_path must be a verified local snapshot; this call cannot fall back to Hub.
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        self.model = SentenceTransformer(str(self.model_path), device=self.device)
        return self

    def encode(self, texts: Sequence[str]):
        if self.model is None:
            raise RuntimeError("Encoder must be fitted before encode")
        import numpy as np
        return np.asarray(self.model.encode(
            list(texts), normalize_embeddings=True, convert_to_numpy=True,
            show_progress_bar=False,
        ))


def load_encoder(path: Path, device: str):
    bundle = read_json(path)
    if bundle.get("schema_version") != "1.0.0" or bundle.get("status") != "accepted":
        raise ValueError("Encoder bundle must be accepted and schema_version=1.0.0")
    if bundle.get("provider") != "sentence-transformers-local":
        raise ValueError("Only a verified local sentence-transformers encoder is supported")
    if not bundle.get("model_id") or not bundle.get("model_revision") or not bundle.get("package_version"):
        raise ValueError("Encoder bundle must pin model ID, model revision and package version")
    model_path = Path(bundle.get("model_path") or "")
    if not model_path.is_absolute():
        model_path = (path.parent / model_path).resolve()
    if model_path.is_symlink() or not model_path.is_dir():
        raise FileNotFoundError(f"Pinned encoder snapshot directory missing or unsafe: {model_path}")
    expected_files = bundle.get("files")
    if not isinstance(expected_files, dict) or not expected_files:
        raise ValueError("Encoder bundle must record per-file SHA-256 values")

    # A partial manifest is insufficient: tokenizer/config/weights or nested module
    # files could otherwise change the loaded model without changing the bundle hash.
    expected_names: set[str] = set()
    actual_files = {}
    for relative, expected_hash in expected_files.items():
        if not isinstance(relative, str) or not relative.strip():
            raise ValueError("Encoder manifest file paths must be non-empty relative paths")
        normalized = relative.replace("\\", "/")
        relative_path = Path(normalized)
        if relative_path.is_absolute() or any(part in {"", ".", ".."} for part in relative_path.parts):
            raise ValueError(f"Unsafe encoder manifest path: {relative}")
        canonical_name = relative_path.as_posix()
        if canonical_name in expected_names:
            raise ValueError(f"Duplicate encoder manifest path: {canonical_name}")
        expected_names.add(canonical_name)
        if not isinstance(expected_hash, str) or len(expected_hash) != 64 or any(
            char not in "0123456789abcdef" for char in expected_hash.lower()
        ):
            raise ValueError(f"Invalid SHA-256 in encoder manifest: {canonical_name}")
        file_path = model_path / relative_path
        if file_path.is_symlink() or not file_path.is_file():
            raise FileNotFoundError(f"Missing or unsafe pinned encoder file: {file_path}")
        actual_hash = sha256_file(file_path)
        if actual_hash != expected_hash.lower():
            raise ValueError(f"Encoder file hash mismatch: {canonical_name}")
        actual_files[canonical_name] = actual_hash

    actual_names: set[str] = set()
    for file_path in model_path.rglob("*"):
        if file_path.is_symlink():
            raise ValueError(f"Encoder snapshot must be materialized without symlinks: {file_path}")
        if file_path.is_file():
            actual_names.add(file_path.relative_to(model_path).as_posix())
        elif not file_path.is_dir():
            raise ValueError(f"Unsupported non-regular entry in encoder snapshot: {file_path}")
    if actual_names != expected_names:
        missing = sorted(actual_names - expected_names)
        absent = sorted(expected_names - actual_names)
        raise ValueError(
            "Encoder snapshot inventory differs from its SHA-256 manifest: "
            f"unhashed_files={missing[:5]} ({len(missing)}), "
            f"missing_files={absent[:5]} ({len(absent)})"
        )
    encoder = LocalSentenceTransformerEncoder(model_path, device)
    encoder.expected_package_version = str(bundle["package_version"])
    return encoder, {
        "bundle_sha256": sha256_file(path),
        "model_path": str(model_path),
        "model_id": bundle.get("model_id"),
        "model_revision": bundle.get("model_revision"),
        "package_version": bundle.get("package_version"),
        "files_verified": len(actual_files),
        "file_hashes": actual_files,
    }


def validate_release_gate(gate_path: Path, comparator_path: Path) -> dict:
    gate = read_json(gate_path)
    if gate.get("schema_version") != "1.0.0" or gate.get("status") != "accepted":
        raise ValueError("E9 release gate must be accepted, schema_version=1.0.0")
    prereqs = gate.get("prerequisites") or {}
    for experiment in REQUIRED_PREREQUISITES:
        item = prereqs.get(experiment) or {}
        if item.get("status") != "accepted":
            raise ValueError(f"Confirmatory E9 execution blocked: {experiment} prerequisite is not accepted")
    prerequisite_proofs = {}
    for experiment in REQUIRED_PREREQUISITES:
        item = prereqs[experiment]
        acceptance_id = item.get("acceptance_id")
        if not isinstance(acceptance_id, str) or not acceptance_id.strip():
            raise ValueError(f"{experiment} accepted prerequisite must carry a non-empty acceptance_id")
        artifact = Path(item.get("artifact_path") or "")
        if not artifact.is_absolute():
            artifact = (gate_path.parent / artifact).resolve()
        if not artifact.is_file():
            raise FileNotFoundError(f"{experiment} accepted prerequisite artifact missing: {artifact}")
        actual_hash = sha256_file(artifact)
        if actual_hash != item.get("sha256"):
            raise ValueError(f"{experiment} prerequisite artifact SHA-256 mismatch")
        prerequisite_proofs[experiment] = {
            "artifact_path": str(artifact),
            "sha256": actual_hash,
            "acceptance_id": item.get("acceptance_id"),
        }

    comparator = read_json(comparator_path)
    if comparator.get("schema_version") != "1.0.0" or comparator.get("status") != "accepted":
        raise ValueError("E9 comparator map must be accepted, schema_version=1.0.0")
    comparator_ids = comparator.get("baseline_ids")
    frozen_ids = [item["id"] for item in baselines_for_experiment("E9")]
    if comparator_ids != frozen_ids:
        raise ValueError(
            "Accepted comparator map must preserve the frozen E9 baseline IDs/order; "
            f"expected={frozen_ids}, got={comparator_ids}"
        )
    if comparator.get("primary_configuration_id") != PRIMARY_CONFIGURATION_ID:
        raise ValueError("Comparator map must separately approve Full_PaMCP")
    if not comparator.get("protocol_document_sha256") or not comparator.get("approval_record"):
        raise ValueError("Comparator map must cite protocol-document hash and approval record")
    return {
        "release_gate_sha256": sha256_file(gate_path),
        "comparator_map_sha256": sha256_file(comparator_path),
        "comparator_map_version": comparator.get("map_version"),
        "baseline_ids": frozen_ids,
        "primary_configuration_id": PRIMARY_CONFIGURATION_ID,
        "prerequisite_proofs": prerequisite_proofs,
    }


def load_training_scenes(
    path: Path | None, candidate_ids: set[str], evaluation_task_ids: set[str]
) -> list[dict[str, Any]]:
    """Build COLT scene co-use only from MCPToolBench++ dev queries and server membership.

    The source-to-candidate tool crosswalk is explicit and hash-bound. Scene members
    are mapped LiveMCPTool candidate IDs; no LiveMCPBench evaluator labels are used.
    """
    if path is None:
        return []
    bundle = read_json(path)
    if bundle.get("schema_version") != "1.0.0" or bundle.get("status") != "accepted":
        raise ValueError("COLT scene bundle must be accepted, schema_version=1.0.0")
    if bundle.get("source_dataset") != "MCPToolBench++" or bundle.get("source_split") != "dev":
        raise ValueError("COLT scenes must originate from the MCPToolBench++ development split")
    if bundle.get("scene_source") != "server_membership":
        raise ValueError("COLT E9 scenes must be derived from server membership")
    if bundle.get("e9_evaluator_labels_used") is not False:
        raise ValueError("COLT scene preparation must explicitly certify no E9 evaluator-label use")
    crosswalk = bundle.get("tool_crosswalk")
    tool_servers = bundle.get("source_tool_servers")
    queries = bundle.get("dev_query_server_membership")
    if not isinstance(crosswalk, dict) or not crosswalk:
        raise ValueError("COLT bundle requires a source-tool to LiveMCPTool crosswalk")
    if bundle.get("crosswalk_sha256") != canonical_sha256(crosswalk):
        raise ValueError("COLT tool crosswalk SHA-256 mismatch")
    if not isinstance(tool_servers, dict) or not tool_servers:
        raise ValueError("COLT bundle requires MCPToolBench++ tool-to-server membership")
    if not isinstance(queries, list) or not queries:
        raise ValueError("COLT bundle requires development query-to-server memberships")
    if not set(crosswalk).issubset(set(tool_servers)):
        raise ValueError("COLT crosswalk contains tool IDs without source server membership")
    for source_tool, target_tool in crosswalk.items():
        if str(target_tool) not in candidate_ids:
            raise ValueError(f"COLT crosswalk target falls outside LiveMCPTool registry: {target_tool}")
    source_by_server: dict[str, list[str]] = defaultdict(list)
    for source_tool, server_id in tool_servers.items():
        if not str(server_id).strip():
            raise ValueError(f"{source_tool}: blank MCPToolBench++ server ID")
        if source_tool in crosswalk:
            source_by_server[str(server_id)].append(str(crosswalk[source_tool]))

    scenes = []
    seen_task_ids = set()
    for query in queries:
        task_id = str(query.get("task_id") or "")
        split = str(query.get("split") or "").lower()
        server_ids = query.get("server_ids")
        if not task_id or split != "dev" or not isinstance(server_ids, list) or not server_ids:
            raise ValueError("Each COLT dev query requires task_id, split=dev and server_ids")
        if task_id in seen_task_ids:
            raise ValueError(f"Duplicate COLT development query: {task_id}")
        seen_task_ids.add(task_id)
        if task_id in evaluation_task_ids:
            raise ValueError("COLT development query overlaps the E9 LiveMCPBench evaluation set")
        members = sorted({
            target_tool
            for server_id in map(str, server_ids)
            for target_tool in source_by_server.get(server_id, [])
        })
        if not members:
            raise ValueError(f"{task_id}: no dev-server members resolve through the frozen tool crosswalk")
        scenes.append({
            "task_id": f"MCPToolBench++:dev:{task_id}",
            "source_task_id": task_id,
            "split": "train",
            "source_dataset": "MCPToolBench++",
            "scene_source": "server_membership",
            "server_ids": sorted(set(map(str, server_ids))),
            "tools": members,
        })
    return scenes

def load_equivalence_oracle(path: Path | None, candidate_ids: set[str]) -> dict | None:
    if path is None:
        return None
    bundle = read_json(path)
    if bundle.get("schema_version") != "1.0.0" or bundle.get("status") != "accepted":
        raise ValueError("ToolScope equivalence oracle must be accepted")
    if bundle.get("evaluator_labels_used_for_oracle") is not False:
        raise ValueError("ToolScope oracle must be independently authored, not inferred from E9 labels")
    pairs = []
    for label, key in (("equivalent_pairs", "positive"), ("non_equivalent_pairs", "negative")):
        for pair in bundle.get(label, []):
            if len(pair) != 2 or pair[0] == pair[1] or not set(pair).issubset(candidate_ids):
                raise ValueError(f"Invalid ToolScope oracle pair: {pair}")
            pairs.append((str(pair[0]), str(pair[1]), key))
    if not pairs:
        raise ValueError("ToolScope equivalence oracle contains no adjudicated pairs")
    return {
        "sha256": sha256_file(path),
        "positive_pairs": [x[:2] for x in pairs if x[2] == "positive"],
        "negative_pairs": [x[:2] for x in pairs if x[2] == "negative"],
    }


def evaluate_equivalence_groups(groups: list[list[str]], oracle: dict | None) -> dict:
    if oracle is None:
        return {"status": "blocked_missing_independent_equivalence_oracle"}
    predicted = {
        tuple(sorted((left, right)))
        for group in groups
        for i, left in enumerate(group)
        for right in group[i + 1:]
    }
    positive = {tuple(sorted(pair)) for pair in oracle["positive_pairs"]}
    negative = {tuple(sorted(pair)) for pair in oracle["negative_pairs"]}
    observed = positive | negative
    tp = len(predicted & positive)
    fp = len(predicted & negative)
    fn = len(positive - predicted)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "status": "scored",
        "oracle_sha256": oracle["sha256"],
        "adjudicated_pair_count": len(observed),
        "predicted_merge_pair_count": len(predicted),
        "true_positive_merges": tp,
        "false_equivalence_merges": fp,
        "missed_equivalent_pairs": fn,
        "merge_precision": precision,
        "merge_recall": recall,
        "false_equivalence_rate": fp / max(1, len(negative)),
        "oracle_coverage_of_predicted_pairs": len(predicted & observed) / max(1, len(predicted)),
    }


def _result_ranking(result: BaselineResult, cutoff: int) -> list[str]:
    if result.status != "completed":
        return []
    if result.ranking:
        ordered = [str(row["tool_id"]) for row in result.ranking if row.get("tool_id")]
    else:
        ordered = list(result.selected_tools)
    if len(ordered) != len(set(ordered)):
        raise ValueError(f"{result.baseline_id}: baseline produced duplicate tool IDs")
    return ordered[:cutoff]


def run_campaign(args: argparse.Namespace) -> dict:
    prepared_dir = args.prepared_dir.resolve()
    output_dir = args.output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite E9 result directory: {output_dir}")
    gate_info = validate_release_gate(args.release_gate, args.comparator_map)
    tools, tasks, visibility, prep_manifest = load_discovery_package(prepared_dir)
    contracts, contract_info = load_contracts(args.contract_bundle, tools)
    if contract_info["coverage"] < 1.0:
        raise ValueError(
            "Full_PaMCP confirmatory comparison requires accepted hash-bound contracts "
            f"for every candidate tool; current coverage={contract_info['coverage']:.3f}"
        )
    profile, profile_info = load_accepted_profile(args.model_profile)
    policy, policy_sha = load_policy(args.policy_bundle)
    composer_config, refine_k, composer_info = load_composer_config(args.composer_config)
    encoder, encoder_info = load_encoder(args.encoder_bundle, args.device)
    goal_specs = load_goal_specs(args.goal_specs, tasks)
    candidate_ids = {str(row["tool_id"]) for row in tools}
    evaluation_task_ids = {str(row["task_id"]) for row in tasks}
    train_scenes = load_training_scenes(args.training_scenes, candidate_ids, evaluation_task_ids)
    equivalence_oracle = load_equivalence_oracle(args.equivalence_oracle, candidate_ids)

    # Fit one pinned model to the full tool-definition collection; no evaluator files
    # have been read at this point.
    documents = [
        " ".join([
            str(row.get("name") or ""),
            str(row.get("description") or ""),
            json.dumps(row.get("input_schema") or {}, sort_keys=True, ensure_ascii=False),
            json.dumps(row.get("output_schema") or {}, sort_keys=True, ensure_ascii=False),
        ]).strip()
        for row in tools
    ]
    started_fit = time.perf_counter()
    retriever = HybridRetriever(encoder=encoder).fit(contracts)
    encoder_fit_seconds = time.perf_counter() - started_fit
    if len(documents) != len(tools):
        raise RuntimeError("Candidate document count drift")
    # The encoder is fitted on the accepted contract renderings by HybridRetriever;
    # candidate coverage was checked above.

    baseline_specs = baselines_for_experiment("E9")
    baseline_ids = [item["id"] for item in baseline_specs]
    baseline_fidelity = {
        item["id"]: {
            "implementation": item.get("implementation"),
            "name": item.get("name"),
            "method": item.get("method"),
            "params": item.get("params", {}),
        }
        for item in baseline_specs
    }

    ranking_rows: list[dict[str, Any]] = []
    primary_rows = 0
    no_backward_rows = 0
    start_time = time.perf_counter()

    # Paired engines differ in exactly one factor: backward-closure depth.
    full_config = replace(composer_config, K=20)
    no_backward_config = make_no_backward_closure_config(replace(composer_config, K=20))
    full_engine = DiscoveryEngine(
        contracts,
        profile,
        cfg=EngineConfig(composer=full_config, refine_k=refine_k),
        encoder=encoder,
    )
    no_backward_engine = DiscoveryEngine(
        contracts,
        profile,
        cfg=EngineConfig(composer=no_backward_config, refine_k=refine_k),
        encoder=encoder,
    )

    method_counts: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"completed_task_runs": 0, "blocked_task_runs": 0, "status_counts": defaultdict(int)}
    )
    expected_runs = len(tasks) * len(DECOMPOSITIONS) * len(RANKING_CUTOFFS)
    mcp_zero_block_reason = "blocked_official_active_request_loop_not_implemented"
    colt_block_reason = "blocked_missing_MCPToolBench_dev_server_membership_scenes_and_crosswalk"
    toolscope_block_reason = "blocked_missing_independent_equivalence_oracle"

    for decomposition in DECOMPOSITIONS:
        for task in tasks:
            task_id = str(task["task_id"])
            prompt = str(task["prompt"])
            visible_row = next(row for row in visibility if str(row["task_id"]) == task_id)
            visible = [str(tool_id) for tool_id in visible_row["visible_tool_ids"]]
            base_spec = goal_specs[(task_id, decomposition)]

            for k in RANKING_CUTOFFS:
                # Apply the candidate budget to both PaMCP variants while keeping every
                # other accepted composer parameter identical. The selected toolkit is
                # the actual set prediction; do not truncate it to k after composition.
                full_engine.cfg.composer.K = k
                result = full_engine.discover(copy.deepcopy(base_spec), policy)
                selected = list(result.toolkit or [])
                if result.toolkit is not None and (result.certificate is None or not result.certificate.valid):
                    raise RuntimeError(f"{task_id}/{decomposition}/Full_PaMCP/k={k}: invalid certificate selected")
                if len(selected) != len(set(selected)) or not set(selected).issubset(set(visible)):
                    raise RuntimeError(f"{task_id}/{decomposition}/Full_PaMCP/k={k}: invalid selected toolkit")
                ranking_rows.append({
                    "task_id": task_id,
                    "benchmark": "live_mcpbench",
                    "baseline": PRIMARY_CONFIGURATION_ID,
                    "decomposition": decomposition,
                    "ranking_k": k,
                    "prediction_kind": "selected_toolkit",
                    "task_group": str(task.get("task_group") or "unspecified"),
                    "ranked_tool_ids": selected,
                    "visible_tool_ids": visible,
                    "method_status": "completed" if result.toolkit is not None else "abstained",
                    "certificate_valid": bool(result.certificate and result.certificate.valid),
                    "discovery_time_seconds": result.time_s,
                    "gap_goal_ids": [goal.id for goal in result.gap.gap],
                    "model_profile_id": profile.model_id,
                    "model_profile_sha256": profile_info["profile_sha256"],
                    "closure_depth": composer_config.depth,
                })
                primary_rows += 1
                method_counts[PRIMARY_CONFIGURATION_ID]["completed_task_runs"] += 1
                method_counts[PRIMARY_CONFIGURATION_ID]["status_counts"][
                    "abstained" if result.toolkit is None else "completed"
                ] += 1

                no_backward_engine.cfg.composer.K = k
                no_backward_result = no_backward_engine.discover(copy.deepcopy(base_spec), policy)
                no_backward_selected = list(no_backward_result.toolkit or [])
                if no_backward_result.toolkit is not None and (
                    no_backward_result.certificate is None or not no_backward_result.certificate.valid
                ):
                    raise RuntimeError(
                        f"{task_id}/{decomposition}/PaMCP_NoBackwardClosure/k={k}: invalid certificate selected"
                    )
                if (len(no_backward_selected) != len(set(no_backward_selected))
                        or not set(no_backward_selected).issubset(set(visible))):
                    raise RuntimeError(
                        f"{task_id}/{decomposition}/PaMCP_NoBackwardClosure/k={k}: invalid toolkit"
                    )
                ranking_rows.append({
                    "task_id": task_id,
                    "benchmark": "live_mcpbench",
                    "baseline": "pamcp_no_backward_closure",
                    "decomposition": decomposition,
                    "ranking_k": k,
                    "prediction_kind": "selected_toolkit",
                    "task_group": str(task.get("task_group") or "unspecified"),
                    "ranked_tool_ids": no_backward_selected,
                    "visible_tool_ids": visible,
                    "method_status": "completed" if no_backward_result.toolkit is not None else "abstained",
                    "certificate_valid": bool(
                        no_backward_result.certificate and no_backward_result.certificate.valid
                    ),
                    "discovery_time_seconds": no_backward_result.time_s,
                    "gap_goal_ids": [goal.id for goal in no_backward_result.gap.gap],
                    "model_profile_id": profile.model_id,
                    "model_profile_sha256": profile_info["profile_sha256"],
                    "closure_depth": 0,
                })
                no_backward_rows += 1
                method_counts["pamcp_no_backward_closure"]["completed_task_runs"] += 1
                method_counts["pamcp_no_backward_closure"]["status_counts"][
                    "abstained" if no_backward_result.toolkit is None else "completed"
                ] += 1

                for baseline_id in baseline_ids:
                    # Do not report a partial MCP-Zero implementation as the official
                    # iterative active-request baseline. Missing prerequisite data also
                    # keeps COLT and ToolScope blocked rather than substituting controls.
                    if baseline_id == "mcp_zero":
                        method_counts[baseline_id]["blocked_task_runs"] += 1
                        method_counts[baseline_id]["status_counts"][mcp_zero_block_reason] += 1
                        continue
                    if baseline_id == "colt_adapted" and not train_scenes:
                        method_counts[baseline_id]["blocked_task_runs"] += 1
                        method_counts[baseline_id]["status_counts"][colt_block_reason] += 1
                        continue
                    if baseline_id == "toolscope_adapted" and equivalence_oracle is None:
                        method_counts[baseline_id]["blocked_task_runs"] += 1
                        method_counts[baseline_id]["status_counts"][toolscope_block_reason] += 1
                        continue
                    if baseline_id == "pamcp_no_backward_closure":
                        continue

                    baseline_result = run_baseline(
                        baseline_id=baseline_id,
                        retriever=retriever,
                        spec=copy.deepcopy(base_spec),
                        prompt=prompt,
                        pool=visible,
                        top_k=k,
                        policy=policy,
                        training_scenes=train_scenes,
                        parameters={"top_k": k},
                    )
                    if baseline_result.status != "completed":
                        method_counts[baseline_id]["blocked_task_runs"] += 1
                        method_counts[baseline_id]["status_counts"][baseline_result.status] += 1
                        continue
                    method_counts[baseline_id]["completed_task_runs"] += 1
                    method_counts[baseline_id]["status_counts"]["completed"] += 1
                    ranked = _result_ranking(baseline_result, k)
                    if not set(ranked).issubset(set(visible)):
                        raise RuntimeError(
                            f"{task_id}/{decomposition}/{baseline_id}/k={k}: out-of-visibility output"
                        )
                    row = {
                        "task_id": task_id,
                        "benchmark": "live_mcpbench",
                        "baseline": baseline_id,
                        "decomposition": decomposition,
                        "ranking_k": k,
                        "prediction_kind": "top_k_retrieved_tools",
                        "task_group": str(task.get("task_group") or "unspecified"),
                        "ranked_tool_ids": ranked,
                        "visible_tool_ids": visible,
                        "method_status": "completed",
                        "discovery_time_seconds": None,
                        "fidelity_label": baseline_fidelity[baseline_id]["implementation"],
                    }
                    if baseline_id == "toolscope_adapted":
                        row["merge_quality"] = evaluate_equivalence_groups(
                            baseline_result.merged_groups, equivalence_oracle
                        )
                    ranking_rows.append(row)

    # Freeze discovery evidence before reading any evaluator references.
    output_dir.mkdir(parents=True)
    discovery_dir = output_dir / "discovery"
    rankings_path = discovery_dir / "rankings.jsonl"
    write_jsonl(rankings_path, ranking_rows)
    rankings_sha256 = sha256_file(rankings_path)

    # Only now open evaluator references from the prepared dataset.
    evaluator_source = prepared_dir / "evaluator" / "task_references.jsonl"
    evaluator_rows = read_jsonl(evaluator_source)
    expected_task_ids = {str(row["task_id"]) for row in tasks}
    actual_ref_ids = {str(row.get("task_id") or "") for row in evaluator_rows}
    if actual_ref_ids != expected_task_ids:
        raise ValueError("Evaluator reference task IDs do not match the prepared discovery task set")
    evaluator_dir = output_dir / "evaluator"
    write_jsonl(evaluator_dir / "task_references.jsonl", evaluator_rows)

    elapsed = time.perf_counter() - start_time
    executed = sorted({
        row["baseline"] for row in ranking_rows
        if row["baseline"] in baseline_ids
    })
    statuses = {}
    for method in baseline_ids:
        counts = method_counts[method]
        if counts["completed_task_runs"] == expected_runs:
            status = "completed"
        elif counts["completed_task_runs"] > 0:
            status = "partial"
        elif counts["blocked_task_runs"] > 0:
            status = "blocked"
        else:
            status = "not_executed"
        statuses[method] = {
            "status": status,
            "completed_task_runs": counts["completed_task_runs"],
            "blocked_task_runs": counts["blocked_task_runs"],
            "status_counts": dict(counts["status_counts"]),
            **baseline_fidelity[method],
        }
    statuses["pamcp_no_backward_closure"] = {
        "status": "completed" if no_backward_rows == expected_runs else "partial",
        "rows": no_backward_rows,
        "expected_rows": expected_runs,
        "variant": "PaMCP with backward-closure depth fixed to zero; all other composer settings identical",
        "status_counts": dict(method_counts["pamcp_no_backward_closure"]["status_counts"]),
    }
    statuses[PRIMARY_CONFIGURATION_ID] = {
        "status": "completed" if primary_rows == expected_runs else "partial",
        "rows": primary_rows,
        "expected_rows": expected_runs,
        "variant": "Full PaMCP with backward closure and certification",
        "status_counts": dict(method_counts[PRIMARY_CONFIGURATION_ID]["status_counts"]),
    }
    expected_methods = set(baseline_ids) | {PRIMARY_CONFIGURATION_ID}
    complete = all(statuses.get(method, {}).get("status") == "completed" for method in expected_methods)
    manifest = {
        "schema_version": "1.0.0",
        "experiment_id": "E9",
        "run_id": args.run_id,
        "status": "complete" if complete else "partial",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "code_commit": git_value("rev-parse", "HEAD"),
        "code_branch": git_value("branch", "--show-current"),
        "dataset": {
            "benchmark": "live_mcpbench",
            "preparation_manifest_sha256": sha256_file(prepared_dir / "PREPARATION_MANIFEST.json"),
            "source_revision": prep_manifest.get("source_revision"),
            "candidate_tool_count": len(tools),
            "task_count": len(tasks),
            "discovery_rankings_sha256": rankings_sha256,
            "evaluator_references_sha256": sha256_file(evaluator_dir / "task_references.jsonl"),
        },
        "baseline_ids_registered": baseline_ids,
        "baseline_ids_executed": executed,
        "ranking_cutoffs": list(RANKING_CUTOFFS),
        "decomposition_conditions": list(DECOMPOSITIONS),
        "primary_configuration_id": PRIMARY_CONFIGURATION_ID,
        "primary_configuration_executed": True,
        "primary_configuration_rows": primary_rows,
        "no_backward_configuration_rows": no_backward_rows,
        "expected_task_decomposition_k_runs_per_method": expected_runs,
        "method_status": statuses,
        "fidelity": baseline_fidelity,
        "inputs": {
            "release_gate": gate_info,
            "contract_bundle": contract_info,
            "model_profile": profile_info,
            "policy_sha256": policy_sha,
            "composer_config": composer_info,
            "no_backward_composer_config": {
                "composer": asdict(no_backward_config),
                "changed_factor": "depth",
                "base_composer_sha256": composer_info["bundle_sha256"],
            },
            "encoder": encoder_info,
            "goal_specs_sha256": sha256_file(args.goal_specs),
            "training_scenes_sha256": sha256_file(args.training_scenes) if args.training_scenes else None,
            "tool_equivalence_oracle": equivalence_oracle,
        },
        "runtime": {
            "python": sys.version,
            "platform": platform.platform(),
            "device": args.device,
            "encoder_fit_seconds": encoder_fit_seconds,
            "elapsed_seconds": elapsed,
            "seed": args.seed,
            "refine_k": refine_k,
        },
        "separation": {
            "discovery_rankings_frozen_before_evaluator_read": True,
            "discovery_rankings_sha256": rankings_sha256,
            "evaluator_labels_used_for_discovery": False,
        },
        "primary_rows_written": primary_rows,
        "ranking_rows_written": len(ranking_rows),
        "interpretation": (
            "Set-retrieval evaluation only. It is not a tool-execution success, effect "
            "correctness, policy-safety or composition-runtime experiment."
        ),
    }
    write_json(output_dir / "MANIFEST.json", manifest)
    write_json(output_dir / "SHA256SUMS.json", {
        "discovery/rankings.jsonl": rankings_sha256,
        "evaluator/task_references.jsonl": sha256_file(evaluator_dir / "task_references.jsonl"),
        "MANIFEST.json": sha256_file(output_dir / "MANIFEST.json"),
    })
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared-dir", type=Path, required=True)
    parser.add_argument("--release-gate", type=Path, required=True)
    parser.add_argument("--comparator-map", type=Path, required=True)
    parser.add_argument("--goal-specs", type=Path, required=True)
    parser.add_argument("--contract-bundle", type=Path, required=True)
    parser.add_argument("--model-profile", type=Path, required=True)
    parser.add_argument("--policy-bundle", type=Path, required=True)
    parser.add_argument("--composer-config", type=Path, required=True)
    parser.add_argument("--encoder-bundle", type=Path, required=True)
    parser.add_argument("--training-scenes", type=Path)
    parser.add_argument("--equivalence-oracle", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--seed", type=int, default=20261108)
    args = parser.parse_args()
    result = run_campaign(args)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
