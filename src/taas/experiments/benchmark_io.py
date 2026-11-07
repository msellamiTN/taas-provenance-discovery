"""Leakage-resistant ingestion and evaluation contracts for PaMCP benchmarks.

This module normalizes public benchmark exports without making discovery-time
records depend on evaluator labels. Dataset-specific loaders should map source
schemas into these canonical records; unknown source fields are retained only
in provenance metadata, never silently interpreted as ground truth.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


@dataclass(frozen=True)
class ToolRecord:
    dataset_id: str
    tool_id: str
    server_id: str | None
    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    annotations: dict[str, Any] = field(default_factory=dict)
    definition_hash: str | None = None
    source_record_id: str | None = None


@dataclass(frozen=True)
class TaskRecord:
    dataset_id: str
    task_id: str
    prompt: str
    split: str | None = None
    target_tool_ids: tuple[str, ...] = ()
    acceptable_tool_sets: tuple[tuple[str, ...], ...] = ()
    oracle_ref: str | None = None
    source_record_id: str | None = None


@dataclass(frozen=True)
class EffectReference:
    """Independent reference label; never populate from MCP hints automatically."""
    tool_id: str
    effects: tuple[str, ...]
    source: str
    adjudicated: bool
    confidence: float | None = None


_TOOL_ID_KEYS = ("tool_id", "id", "qualified_name", "name")
_TASK_ID_KEYS = ("task_id", "id", "example_id", "query_id")
_PROMPT_KEYS = ("prompt", "query", "task", "instruction", "user_request")


def _first(record: Mapping[str, Any], keys: Sequence[str], default: Any = None) -> Any:
    for key in keys:
        value = record.get(key)
        if value is not None and value != "":
            return value
    return default


def normalize_tool(record: Mapping[str, Any], dataset_id: str) -> ToolRecord:
    """Normalize one tool definition. Does not infer effects or safety labels."""
    tool_id = _first(record, _TOOL_ID_KEYS)
    if not tool_id:
        raise ValueError("Tool record has no stable tool identifier")
    server_id = _first(record, ("server_id", "server", "provider", "namespace"))
    schema = record.get("inputSchema", record.get("input_schema", {}))
    output = record.get("outputSchema", record.get("output_schema", {}))
    annotations = record.get("annotations", {})
    return ToolRecord(
        dataset_id=dataset_id,
        tool_id=str(tool_id),
        server_id=str(server_id) if server_id is not None else None,
        name=str(record.get("name", tool_id)),
        description=str(record.get("description", "")),
        input_schema=schema if isinstance(schema, dict) else {},
        output_schema=output if isinstance(output, dict) else {},
        annotations=annotations if isinstance(annotations, dict) else {},
        definition_hash=str(record["definition_hash"]) if record.get("definition_hash") else None,
        source_record_id=str(record.get("source_record_id", tool_id)),
    )


def normalize_task(record: Mapping[str, Any], dataset_id: str) -> TaskRecord:
    """Normalize task metadata while keeping oracle labels in a separate record."""
    task_id = _first(record, _TASK_ID_KEYS)
    prompt = _first(record, _PROMPT_KEYS)
    if not task_id or not prompt:
        raise ValueError("Task record requires a stable task ID and prompt")
    targets = record.get("target_tool_ids", record.get("target_tools", [])) or []
    acceptable = record.get("acceptable_tool_sets", []) or []
    return TaskRecord(
        dataset_id=dataset_id,
        task_id=str(task_id),
        prompt=str(prompt),
        split=str(record["split"]) if record.get("split") is not None else None,
        target_tool_ids=tuple(sorted({str(x) for x in targets})),
        acceptable_tool_sets=tuple(
            tuple(sorted({str(x) for x in group}))
            for group in acceptable if isinstance(group, (list, tuple))
        ),
        oracle_ref=str(record["oracle_ref"]) if record.get("oracle_ref") else None,
        source_record_id=str(record.get("source_record_id", task_id)),
    )


def load_json_records(path: str | Path, collection_keys: Sequence[str] = ()) -> list[dict[str, Any]]:
    """Read JSON or JSONL exports. No network access or implicit dataset download."""
    source = Path(path)
    text = source.read_text(encoding="utf-8")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        rows = []
        for line_no, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"JSONL line {line_no} must contain an object")
            rows.append(value)
        return rows
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = None
        for key in collection_keys:
            if isinstance(payload.get(key), list):
                rows = payload[key]
                break
        if rows is None:
            raise ValueError(f"No record list found; expected one of {tuple(collection_keys)}")
    else:
        raise ValueError("Dataset JSON must be an object or list")
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError("Every dataset record must be an object")
    return rows


def discovery_task_view(task: TaskRecord) -> dict[str, Any]:
    """Task fields visible to the discovery system; excludes all evaluator targets."""
    return {
        "dataset_id": task.dataset_id,
        "task_id": task.task_id,
        "prompt": task.prompt,
        "split": task.split,
        "source_record_id": task.source_record_id,
    }


def discovery_view(tool: ToolRecord) -> dict[str, Any]:
    """Fields allowed to discovery; intentionally excludes evaluator labels."""
    return {
        "tool_id": tool.tool_id,
        "server_id": tool.server_id,
        "name": tool.name,
        "description": tool.description,
        "input_schema": tool.input_schema,
        "output_schema": tool.output_schema,
        "annotations": tool.annotations,
        "definition_hash": tool.definition_hash,
    }


def assert_disjoint_ids(
    train: Iterable[str], test: Iterable[str], unit: str = "tool"
) -> None:
    train_ids, test_ids = set(train), set(test)
    overlap = sorted(train_ids & test_ids)
    if overlap:
        preview = ", ".join(overlap[:5])
        raise ValueError(f"{unit}-disjoint split violated: {len(overlap)} overlaps ({preview})")


def validate_tool_disjoint(
    train_tools: Sequence[ToolRecord], test_tools: Sequence[ToolRecord],
    by_server: bool = False,
) -> None:
    key = (lambda x: x.server_id) if by_server else (lambda x: x.tool_id)
    if by_server and any(key(x) is None for x in (*train_tools, *test_tools)):
        raise ValueError("Server-disjoint validation requires server_id for every tool")
    assert_disjoint_ids((key(x) for x in train_tools), (key(x) for x in test_tools),
                        "server" if by_server else "tool")


def unsafe_exposure_at_k(
    rankings: Mapping[str, Sequence[str]],
    unsafe_tool_ids: set[str] | None,
    k: int,
) -> float | None:
    """Query-level unsafe exposure. None means no independent reference exists."""
    if unsafe_tool_ids is None:
        return None
    if k < 1:
        raise ValueError("k must be >= 1")
    if not rankings:
        return None
    return sum(bool(set(list(items)[:k]) & unsafe_tool_ids)
               for items in rankings.values()) / len(rankings)


def unsafe_share_at_k(
    rankings: Mapping[str, Sequence[str]],
    unsafe_tool_ids: set[str] | None,
    k: int,
) -> float | None:
    """Unsafe retrieved-instance share; repeated retrievals count per query."""
    if unsafe_tool_ids is None:
        return None
    if k < 1:
        raise ValueError("k must be >= 1")
    retrieved = [tool for items in rankings.values() for tool in list(items)[:k]]
    if not retrieved:
        return None
    return sum(tool in unsafe_tool_ids for tool in retrieved) / len(retrieved)


def retrieval_coverage(
    rankings: Mapping[str, Sequence[str]], expected_task_ids: Sequence[str]
) -> float | None:
    """Fraction of the fixed evaluation request set receiving >=1 result."""
    if not expected_task_ids:
        return None
    return sum(bool(rankings.get(task_id)) for task_id in expected_task_ids) / len(expected_task_ids)


def complete_set_recall(
    predictions: Mapping[str, Sequence[str]],
    references: Mapping[str, Sequence[Sequence[str]]],
) -> float | None:
    """Accept any independently annotated valid tool set; no single-chain assumption."""
    evaluated = []
    for task_id, acceptable_sets in references.items():
        if not acceptable_sets:
            continue
        predicted = set(predictions.get(task_id, ()))
        evaluated.append(any(set(target).issubset(predicted) for target in acceptable_sets))
    if not evaluated:
        return None
    return sum(evaluated) / len(evaluated)


def serialize_tool(tool: ToolRecord) -> dict[str, Any]:
    return asdict(tool)
