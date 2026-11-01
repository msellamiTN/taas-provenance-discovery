"""Sanitised manifest (Section 6.3) and the experience repository R of task patterns.

The toolkit is exposed as a manifest whose names, descriptions and argument defaults are rewritten
from the contract rather than copied from the provider, which removes description-borne injection
and confusable neighbours.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from .certificate import Certificate
from .contracts import CapabilityContract
from .hypergraph import Hypergraph


def sanitise(c: CapabilityContract) -> dict:
    name = re.sub(r"[^a-zA-Z0-9_]", "_", f"{c.server}__{c.name}")[:64]
    args = {a.name: {"type": "string" if a.type.kind not in ("number", "boolean") else
                     ("number" if a.type.kind == "number" else "boolean"),
                     "description": f"{a.type}"} for a in c.args}
    effs = ", ".join(sorted(map(str, c.eff))) or "none"
    desc = (f"{c.tool_class.replace('_', ' ')}: takes "
            f"{', '.join(str(a.type) for a in c.args if a.required) or 'nothing'} and returns {c.head}. "
            f"Effects: {effs}.")
    return {"name": name, "description": desc,
            "inputSchema": {"type": "object", "properties": args,
                            "required": [a.name for a in c.args if a.required]}}


def manifest(H: Hypergraph, cert: Certificate, order: list[str] | None = None) -> dict:
    tools = [sanitise(H.contracts[t]) for t in cert.toolkit]
    return {"tools": tools, "suggested_order": order or cert.toolkit,
            "certificate": {k: v for k, v in cert.checks.items()}}


def manifest_tokens(tools: list[dict]) -> int:
    return len(json.dumps(tools)) // 4


def raw_tokens(H: Hypergraph, ids: list[str]) -> int:
    return sum(H.contracts[t].tokens for t in ids)


@dataclass
class Pattern:
    prompt: str
    goals: list[dict]
    classes: list[str]
    certificate: dict


@dataclass
class PatternRepository:
    """R: patterns abstracted from certified, executed and confirmed toolkits.

    Tools are replaced by their substitution classes; a pattern seeds decomposition but is
    always re-validated through the full pipeline (it can never bypass the checks)."""

    patterns: list[Pattern] = field(default_factory=list)
    threshold: float = 0.6

    def store(self, prompt: str, goals: list[dict], H: Hypergraph, cert: Certificate, confirmed_by: str) -> bool:
        if confirmed_by not in ("user", "postcondition", "verifier"):
            return False
        classes = sorted({Hypergraph.head_key(H.contracts[t].head) for t in cert.toolkit})
        self.patterns.append(Pattern(prompt, goals, classes, cert.to_dict()))
        return True

    def lookup(self, prompt: str) -> Pattern | None:
        def toks(s: str) -> set[str]:
            return set(re.findall(r"[a-z]+", s.lower()))
        q = toks(prompt)
        best, bs = None, 0.0
        for p in self.patterns:
            t = toks(p.prompt)
            s = len(q & t) / max(1, len(q | t))
            if s > bs:
                best, bs = p, s
        return best if bs >= self.threshold else None
