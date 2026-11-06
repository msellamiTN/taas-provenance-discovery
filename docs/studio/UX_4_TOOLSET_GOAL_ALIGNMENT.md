# UX-4 — Toolset-to-Goal Alignment Workspace

Status: implementation branch `codex/ux4-toolset-goal-alignment`, stacked on UX-3 head `a9f3ed05e5751877e212a8b95b0f431dda20691e`.

## Objective

Provide a conservative, read-only comparison between GoalSpec semantic type declarations and semantic labels explicitly supplied by selected tool JSON Schemas.

## Comparison contract

- Goal requirements are read from the current visual GoalSpec state.
- Tool metadata comes from the current non-empty registry selection basket; when that basket is empty, the inspector uses the canonical discovery request's `tools` array.
- Input and output labels are collected separately from each tool's `input_schema` and `output_schema`.
- Only exact labels declared through `x-taas-semantic-type` or `x-taas-semantic-types` are considered.
- The extension is recognized at the schema root, under `properties`, `items`, `prefixItems` and schema-valued `additionalProperties`, with bounded traversal (depth 8, at most 200 visited schema nodes per schema).
- Labels must follow the GoalSpec semantic type token syntax. Labels are not normalized or guessed.
- A row reports exact input-label and output-label matches, unmatched labels, or a non-comparable state when metadata is absent.

## Explicit non-goals and safety

- No inference from JSON Schema primitive types, property names, descriptions, tool names, MCP annotations or effect declarations.
- No comparison of operation class, dependency satisfiability, effect policy, trust, provenance authenticity, reachability or authorization.
- No natural-language semantic similarity, model call, embedding, external API call or Core API call.
- A label match is only metadata-level equality; it is not proof that a tool can perform a goal, that its output satisfies downstream requirements, or that execution will succeed.
- No tool is invoked. No discovery, approval, authorization or execution state is changed.
- This is an advisory display; structural GoalSpec validation remains the existing Core contract.

## UI behavior

- The operator explicitly clicks **Refresh metadata comparison**.
- The inspector reads the current GoalSpec, current basket or canonical request and renders a per-goal table.
- Empty toolsets, invalid JSON, missing schema extensions and empty GoalSpecs are shown as unavailable/non-comparable rather than treated as passes.
- Values are rendered with DOM text nodes.

## Automated regression

`tests/test_studio_toolset_goal_alignment.py` covers the panel, explicit extension-only extraction, strict input/output separation, no inferred metadata, source selection, non-comparable states, safety disclaimers and absence of API/execution calls.

## Operator acceptance

1. Check out the exact UX-4 PR head.
2. Open Goal Design and load an illustrative GoalSpec.
3. With no selected tool metadata, refresh and confirm the result is non-comparable, not a pass.
4. Inspect schemas without `x-taas-semantic-type(s)`; confirm ordinary `type`, property names and descriptions do not produce semantic matches.
5. Add explicit matching labels to input and output schemas and confirm exact matches are shown in the corresponding columns only.
6. Change one label, remove a schema, and clear the basket; confirm rows update after refresh and become unmatched/non-comparable as appropriate.
7. Confirm a non-empty registry basket is preferred; when empty, the canonical request toolset is used.
8. Confirm no API request, model call, MCP tool invocation, approval mutation or execution occurred.
9. Test keyboard operation, narrow viewport, long labels, invalid JSON and screen-reader status announcements.

## Evidence reporting

Repository-content checks, JavaScript parsing, pytest, CI, authenticated Colab acceptance and browser review are separate evidence classes. Do not mark UX-4 accepted until exact-head automated and operator checks are complete.
