# TaaS Studio UX design system

Status: implementation foundation for PR #16. This document describes the product direction and capability boundaries; it does not claim every workspace is complete.

## Product principles
1. Workspace first: task-oriented workspaces, not an undifferentiated dashboard.
2. One source of truth per status: host diagnostics, model runtime, MCP inspection, discovery, assurance and execution are separate state domains.
3. Progressive disclosure: primary action and result first; configuration, schemas, raw JSON and diagnostics are secondary.
4. Visible provenance: show source, model/runtime, timestamp and freshness where applicable.
5. No simulated capability: planned or unavailable functions must be labelled; never fabricate runs, traces, execution or metrics.
6. Review before side effects: proposals and discovery remain distinct from execution.
7. Responsive and accessible: keyboard focus, semantic landmarks, labels, status announcements, contrast and layouts that collapse without horizontal scrolling.

## Information architecture
- Overview: API readiness and host diagnostics. Host state does not imply a model is loaded.
- Model Studio: model selection, process-local load state, inference chat and measured latency/token metadata.
- Agent Studio: objective/context, selected loaded model, GoalSpec proposal, parse/structural validation, raw output and human review.
- Tools & MCP: operator-configured server list and initialize/tools/list inspection. Inspection is not invocation.
- Goal Design: visual editing and API validation of canonical GoalSpec.
- Discovery: candidate toolsets for a GoalSpec. Discovery is not execution.
- Assurance: pre-execution evidence and counterexamples, not runtime proof.
- Runs & Traces: reserved for actual governed invocations; do not render fake history.

## Navigation and layout
Use persistent workspace navigation and a compact context header. Desktop uses a narrow navigation rail and flexible main canvas; tablet/mobile collapses navigation above the active workspace. Each module needs a clear heading, purpose statement, primary action, result area and secondary details. Avoid one enormous form.

## Interaction standards
- Buttons name the operation and show pending state.
- Errors are plain-language summaries with structured details when useful.
- Empty states explain how to configure the real capability.
- Status labels include scope (for example, API host versus loaded model in this process).
- Inference metadata belongs to the exact response, not host GPU detection.
- MCP schemas are untrusted declarations, not behavioral evidence.
- Agent proposals remain unapplied until structural validation succeeds and the user chooses Apply.
- Preserve raw model output; never auto-correct malformed JSON into an apparently valid plan.

## Visual system
Use restrained neutral surfaces, consistent spacing, one primary action color, semantic status colors, clear type hierarchy and predictable control dimensions. Reserve monospace for code, schemas and raw payloads. Avoid decorative gradients, excessive cards and dense monospaced blocks as the default presentation.

## Release gates
No dead navigation links or inert primary controls; no contradictory global runtime status; no [object Object] errors; every async action has pending/success/empty/failure states; no secrets in browser storage, URLs or rendered diagnostics; keyboard navigation and narrow viewport behavior verified.
