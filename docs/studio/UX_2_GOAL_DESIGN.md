# UX-2 — Goal Design: Dependency Workspace and Examples

Status: implementation branch `codex/ux2-goal-design-dependency-workspace`.

## Scope delivered

- A Graph / Table switch for the current GoalSpec draft.
- A directed dependency view: each declared dependency is drawn from prerequisite to dependent goal.
- A text equivalent of the graph for screen-reader and non-visual inspection.
- A dependency table exposing goal ID, operation, output, inputs, dependencies and declared effects.
- Two explicitly loaded illustrative templates: web research → summary, and read data → aggregate → report.
- Template loading replaces the current draft only after the user selects a template and clicks **Replace draft with example**.
- Any template replacement invalidates the human-review checkbox and updates the canonical JSON request payload.

## Functional contract

The views are projections of `goalSpecState.goals`; the JSON request remains the canonical transport payload. The graph uses only declared `deps` references. It does not infer dependencies from matching semantic types, compute tool reachability, assess semantic compatibility, or establish assurance.

The graph uses a deterministic topological layering for acyclic dependency declarations. If a cycle exists, it falls back to editor order and displays a warning; structural validation remains authoritative for the validation result.

All API- or user-derived labels are written through DOM `textContent` / SVG text nodes. The feature introduces no `innerHTML`, new API endpoint, discovery call, approval action, tool invocation or execution capability.

## UX and safety boundaries

- Graph and table present the same declared GoalSpec dependencies.
- The text list remains available alongside the SVG.
- Templates are examples, not semantic recommendations or prevalidated contracts.
- Replacing a draft requires an explicit click and clears the human-review acknowledgement.
- Structural validation still uses the existing Core endpoint. This feature does not change Core validation semantics.
- A displayed dependency edge is not proof that one goal's output satisfies another goal's input.

## Acceptance

Automated regression: `tests/test_studio_goal_design_workspace.py`.

Colab/browser operator acceptance (required before marking UX-2 fully accepted):
1. Check out the exact PR head SHA.
2. Open Goal Design and verify Graph and Table views show identical IDs/dependencies.
3. Add, edit, and remove goals; verify both views refresh.
4. Load each example and verify the prior draft is replaced only after the explicit action.
5. Verify the human-review acknowledgement is cleared after edits/template replacement.
6. Create a cycle and an unknown dependency; verify the UI warns and existing Core structural validation remains authoritative.
7. Test keyboard operation, screen-reader text equivalent, narrow viewport and horizontal table scrolling.
8. Confirm no MCP invocation or execution occurred.

## Validation reporting

Unit/static tests, CI, Colab runtime acceptance and browser visual review are separate evidence classes. Do not report UX-2 as fully accepted until the exact commit has passed the required operator/browser checks.
