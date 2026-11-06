# Agent Engineering Workspace v1

## Purpose

The Agent Engineering workspace provides a focused, authenticated Studio surface for preparing an Objective and inspecting the TaaS Core response that connects objective clauses, required outcomes, GoalSpec coverage, and Agent Skill-trigger associations.

## User journey

1. The operator connects Studio using the existing bearer-token control.
2. The operator enters an Objective and optional context, chooses the already-supported inference provider, and explicitly selects **Prepare Objective**.
3. Studio sends `POST /api/v1/objectives/prepare` with the `AgentDecomposeRequest` fields (`provider`, `prompt`, and `context`).
4. Studio renders the returned `objective_skill_traceability`, `objective_coverage`, and raw Core response.
5. The operator reviews exact clause references, outcome coverage, GoalSpec goal links, Skill IDs/versions, trigger phrases, occurrence spans, and registry manifest digests when present.

## Contract and ownership

- TaaS Core remains authoritative for Objective interpretation, GoalSpec generation, coverage, Skill selection and provenance composition.
- The browser does not derive clauses, outcomes, goals, trigger matches, or Skill selection.
- The UI renders returned records using DOM `textContent`; it does not inject API data as HTML.
- The workspace is an explicit user-triggered request. It does not automatically prepare an Objective on page load.
- No Agent is published, no discovery is started, no policy is evaluated, no authorization is granted, and no tool is executed.

## Interpretation limits

- Skill-to-clause relationships are lexical trigger phrase occurrences within exact clause spans.
- Outcome-to-goal relationships are structural coverage records returned by Core.
- These relationships are provenance associations, not semantic proof, capability proof, causal attribution, trust certification, policy approval, or authorization.
- `semantic_correctness_verified`, `tools_authorized`, and `execution_enabled` remain Core-reported false values in this workflow.
- Human review remains mandatory before any downstream discovery workflow.

## UI states

The workspace distinguishes the initial empty state, missing token, missing Objective, loading, successful Core response, request failure, and explicit local clear. A failed request does not leave stale trace data presented as a current result.

## Validation

Static regression tests in `tests/test_agent_engineering_workspace.py` cover navigation/accessibility, authenticated endpoint usage, safe text rendering, trust-boundary wording, and empty/error/clear states. CI and operator Colab/browser acceptance are separate validation gates; this document does not claim they have run.
