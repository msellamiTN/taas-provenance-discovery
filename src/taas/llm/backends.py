"""LLM roles (Section 6): analyst (decomposition) and assistant (repair proposals).

The roles only *propose*; every proposal passes through the engine's eligibility, typing, effect and
flow checks (Property 1). Three backends:

* ``ReplayAnalyst``     — recorded outputs (data/llm_records/analyst_*.jsonl). The experiments in this
                          repository replay outputs produced by Claude models in the build session,
                          so results are deterministic and auditable.
* ``AnthropicAnalyst``  — live calls through the Anthropic Messages API (needs ANTHROPIC_API_KEY),
                          recording every response to JSONL for later replay.
* ``HeuristicAnalyst``  — a rule-based stand-in used by unit tests (no LLM).
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Protocol

ROOT = Path(__file__).resolve().parents[3]


class Analyst(Protocol):
    name: str

    def decompose(self, pid: str, prompt: str, context: str = "") -> dict | None: ...


class ReplayAnalyst:
    def __init__(self, paths: list[str | Path], name: str = "replay") -> None:
        self.name = name
        self.records: dict[str, dict] = {}
        for p in paths:
            p = Path(p)
            if not p.is_absolute():
                p = ROOT / p
            if not p.exists():
                continue
            for line in open(p, encoding="utf-8"):
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                self.records[str(d.get("id"))] = d

    def decompose(self, pid: str, prompt: str, context: str = "") -> dict | None:
        return self.records.get(str(pid))

    def __len__(self) -> int:
        return len(self.records)


class AnthropicAnalyst:  # pragma: no cover - requires network and an API key
    def __init__(self, model: str = "claude-sonnet-4-5", record_to: str | Path | None = None,
                 api_key: str | None = None) -> None:
        import anthropic  # optional dependency
        self.client = anthropic.Anthropic(api_key=api_key or os.environ["ANTHROPIC_API_KEY"])
        self.model, self.name = model, f"anthropic:{model}"
        self.record_to = Path(record_to) if record_to else None
        self.guide = (ROOT / "docs" / "ANALYST_GUIDE.md").read_text()
        self.theta = (ROOT / "data" / "processed" / "theta.json").read_text()

    def decompose(self, pid: str, prompt: str, context: str = "") -> dict | None:
        msg = self.client.messages.create(
            model=self.model, max_tokens=2000,
            system=self.guide + "\n\nΘ:\n" + self.theta + "\nReturn only the JSON object.",
            messages=[{"role": "user", "content": json.dumps({"id": pid, "query": prompt, "context": context})}])
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        m = re.search(r"\{.*\}", text, re.S)
        d = json.loads(m.group(0)) if m else None
        if d is not None and self.record_to:
            with open(self.record_to, "a", encoding="utf-8") as f:
                f.write(json.dumps(d | {"id": pid}, ensure_ascii=False) + "\n")
        return d


_EXT = [
    (r"\b(search|find|look up|lookup|query)\b", "search", "record:search_result[]", ["egress(*)"]),
    (r"\b(price|stock|share)\b", "retrieve", "record:stock", ["egress(api)"]),
    (r"\b(weather|forecast)\b", "retrieve", "record:weather", ["egress(api)"]),
    (r"\b(read|open|load)\b.*\b(file|document)\b", "retrieve", "text", ["read(fs)"]),
]


class HeuristicAnalyst:
    """Rule-based decomposition for tests: one data goal per detected source, one write goal."""

    name = "heuristic"

    def decompose(self, pid: str, prompt: str, context: str = "") -> dict | None:
        p = prompt.lower()
        goals = []
        for pat, cls, out, eff in _EXT:
            if re.search(pat, p):
                goals.append({"id": f"g{len(goals) + 1}", "class": cls, "in": ["query"], "out": out, "eff": eff,
                              "sigma": "data", "n": 1, "desc": cls})
                break
        if re.search(r"\b(save|write|create|generate)\b.*\b(file|pdf|report|document)\b", p):
            goals.append({"id": f"g{len(goals) + 1}", "class": "create_document", "in": ["text"],
                          "out": "path:file", "eff": ["write(fs)"], "sigma": "effect", "n": 1,
                          "deps": [g["id"] for g in goals], "desc": "write file"})
        goals.append({"id": f"g{len(goals) + 1}", "class": "write", "in": ["text"], "out": "text", "eff": [],
                      "sigma": "native", "n": 1, "deps": [g["id"] for g in goals], "desc": "answer"})
        return {"id": pid, "prompt_inputs": ["text"], "goals": goals}


class HeuristicAssistant:
    """Assistant role stand-in: proposes relaxing an uncovered goal's output type to its kind."""

    name = "heuristic-assistant"

    def repair(self, chi, spec) -> dict | None:
        g = next((x for x in spec.goals if x.id == chi.goal), None)
        if g is None or g.out.domain is None:
            return None
        return {"goal_out": g.out.kind + ("[]" if g.out.collection else "")}
