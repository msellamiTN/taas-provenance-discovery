"""Tool-metadata linting for MCP inspection (FR-SEC-7).

Tool descriptions and schemas are untrusted input: a poisoned ``description``
is prompt injection delivered through a trusted channel into the agent's
context. This module lints metadata at inspection time and flags
instruction-like patterns. It is advisory today — findings are reported,
not blocked — because legitimate tools may trip a pattern.
"""
from __future__ import annotations

import re
from typing import Any

# Lowercase substring patterns that indicate instruction-like content aimed
# at the model rather than a human reader. Deliberately conservative: these
# are phrases, not verbs, to keep false positives low.
_INJECTION_PHRASES = (
    "ignore previous", "ignore all", "ignore the above", "disregard previous",
    "system prompt", "you are now", "you must", "you will", "do not tell",
    "do not reveal", "send to", "exfiltrat", "as an ai", "act as",
    "new instructions", "override", "jailbreak", "developer mode",
)

# Structural red flags: URIs in descriptions (data exfil channel),
# HTML/script-ish markup, and excessive length.
_URI = re.compile(r"https?://[^\s)>\"']+", re.IGNORECASE)
_MARKUP = re.compile(r"<\s*(script|iframe|img|form|a\s+href)", re.IGNORECASE)
_MAX_DESCRIPTION_LEN = 2000


def lint_description(description: str | None) -> list[dict[str, str]]:
    """Return findings for a single tool description."""
    desc = description or ""
    low = desc.lower()
    findings: list[dict[str, str]] = []
    for phrase in _INJECTION_PHRASES:
        if phrase in low:
            findings.append({"kind": "instruction-like-phrase", "match": phrase})
    for url in _URI.findall(desc):
        findings.append({"kind": "embedded-uri", "match": url[:120]})
    markup = _MARKUP.search(desc)
    if markup:
        findings.append({"kind": "embedded-markup", "match": markup.group(0)[:80]})
    if len(desc) > _MAX_DESCRIPTION_LEN:
        findings.append({"kind": "oversized", "match": f"{len(desc)} chars"})
    return findings


def lint_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Annotate each tool dict with ``metadata_findings``; returns the tools.

    Tools are mutated in place for a compact wire shape: only tools with
    findings carry the field.
    """
    flagged = 0
    for tool in tools:
        findings = lint_description(tool.get("description"))
        if findings:
            tool["metadata_findings"] = findings
            flagged += 1
    return tools


def summarize(tools: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the inspection-level lint summary."""
    total_findings = sum(len(t.get("metadata_findings", [])) for t in tools)
    return {
        "tools_flagged": sum(1 for t in tools if t.get("metadata_findings")),
        "finding_count": total_findings,
        "enforcement": "advisory",  # flag, not block — see module docstring
    }
