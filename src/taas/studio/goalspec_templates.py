"""Versioned GoalSpec template catalog.

Curated, immutable GoalSpec starting points. Each template's `spec_sha256` is a
deterministic content hash of its `goal_spec` payload — it identifies the exact
authored draft, nothing more. All semantic types use the declared Theta
vocabulary; every draft passes `POST /goals/validate`.

Boundary: templates are authored drafts. Loading one does not validate the spec,
does not produce evidence, and does not authorize anything. `POST /goals/validate`
remains the only validation path, and even a valid spec is a proposal — never
authorization or execution.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

_TEMPLATES: list[dict[str, Any]] = [
    {
        "id": "data-answer-simple",
        "version": "1.0.0",
        "title": "Simple data answer",
        "description": "Single-goal spec: answer a question over supplied records. "
                       "Smallest useful starting point for a retrieval-backed agent.",
        "tags": ["answer", "data", "single-goal"],
        "goal_spec": {
            "goals": [
                {
                    "id": "g1",
                    "class": "answer",
                    "desc": "Answer the operator's query from the supplied records",
                    "in": ["query", "record:news[]"],
                    "out": "text",
                    "sigma": "data",
                    "exactness": "tolerant",
                    "n": 1,
                }
            ],
            "prompt_inputs": ["query", "record:news[]"],
            "prompt": "Given the records, answer the query.",
        },
    },
    {
        "id": "extract-summarise",
        "version": "1.0.0",
        "title": "Extract then summarise",
        "description": "Two-goal chain: extract structured records from a document, "
                       "then summarise them. Demonstrates dependency (deps) and "
                       "generative output.",
        "tags": ["extract", "summarise", "chain", "generative"],
        "goal_spec": {
            "goals": [
                {
                    "id": "g1",
                    "class": "extract",
                    "desc": "Extract the requested records from the document",
                    "in": ["document"],
                    "out": "record[]",
                    "sigma": "data",
                    "exactness": "exact",
                    "n": 1,
                },
                {
                    "id": "g2",
                    "class": "summarise",
                    "desc": "Summarise the extracted records for the operator",
                    "in": ["record[]"],
                    "out": "text",
                    "sigma": "native",
                    "exactness": "tolerant",
                    "n": 1,
                    "deps": ["g1"],
                },
            ],
            "prompt_inputs": ["document"],
            "prompt": "Extract the records from the document, then summarise them.",
        },
    },
    {
        "id": "compare-aggregate",
        "version": "1.0.0",
        "title": "Compare and aggregate",
        "description": "Compare two datasets, then aggregate the differences into a "
                       "text report. Demonstrates multi-input goals and exact "
                       "exactness on computed outputs.",
        "tags": ["compare", "aggregate", "multi-goal"],
        "goal_spec": {
            "goals": [
                {
                    "id": "g1",
                    "class": "compare",
                    "desc": "Compare the two datasets and identify differences",
                    "in": ["record:dataset[]", "record:dataset[]"],
                    "out": "record:dataset[]",
                    "sigma": "data",
                    "exactness": "exact",
                    "n": 1,
                },
                {
                    "id": "g2",
                    "class": "aggregate",
                    "desc": "Aggregate the differences into a summary report",
                    "in": ["record:dataset[]"],
                    "out": "text",
                    "sigma": "data",
                    "exactness": "exact",
                    "n": 1,
                    "deps": ["g1"],
                },
            ],
            "prompt_inputs": ["record:dataset[]", "record:dataset[]"],
            "prompt": "Compare the two datasets and produce an aggregated report of the differences.",
        },
    },
    {
        "id": "plan-with-effects",
        "version": "1.0.0",
        "title": "Plan with declared effects",
        "description": "Planning goal that declares a side effect (eff+) it may "
                       "require. Demonstrates the effect vocabulary and why declared "
                       "effects are proposals — never granted capabilities.",
        "tags": ["plan", "effects", "generative"],
        "goal_spec": {
            "goals": [
                {
                    "id": "g1",
                    "class": "plan",
                    "desc": "Produce a step-by-step task plan to satisfy the request",
                    "in": ["query", "record:task[]"],
                    "out": "record:task[]",
                    "eff": ["write(draft)"],
                    "sigma": "native",
                    "exactness": "tolerant",
                    "n": 1,
                }
            ],
            "prompt_inputs": ["query", "record:task[]"],
            "prompt": "Produce a task plan for the request, respecting the constraints.",
        },
    },
]


def _spec_digest(goal_spec: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(goal_spec, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def list_templates() -> list[dict[str, Any]]:
    """Metadata-only view of every catalog entry, sorted by id for determinism."""
    out = []
    for t in sorted(_TEMPLATES, key=lambda x: x["id"]):
        out.append({
            "id": t["id"],
            "version": t["version"],
            "title": t["title"],
            "description": t["description"],
            "tags": list(t["tags"]),
            "spec_sha256": _spec_digest(t["goal_spec"]),
        })
    return out


def get_template(template_id: str) -> dict[str, Any] | None:
    """Full template including the GoalSpec draft payload, or None if unknown."""
    for t in _TEMPLATES:
        if t["id"] == template_id:
            return {
                "id": t["id"],
                "version": t["version"],
                "title": t["title"],
                "description": t["description"],
                "tags": list(t["tags"]),
                "spec_sha256": _spec_digest(t["goal_spec"]),
                "goal_spec": t["goal_spec"],
            }
    return None
