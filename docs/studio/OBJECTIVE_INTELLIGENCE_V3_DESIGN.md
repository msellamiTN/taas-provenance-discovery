# Objective Intelligence v3 — Design and Acceptance Contract

## Purpose

Extend Objective Contract v2 from a flat list of lexical outcome hypotheses into a traceable, typed objective-intent structure. The engine must remain scenario-independent: no production behavior may depend on a named customer, benchmark, example prompt, domain, or expected number of goals.

This document is a design contract. It does not claim that v3 is implemented.

## Non-negotiable invariants

1. Preserve the exact original objective and its source locale.
2. Every proposed interpretation must be traceable to a source span or explicitly marked as an inferred/derived requirement.
3. Never treat a lexical cue as proof of user intent.
4. Negation must not be converted into a positive action.
5. Conditional, optional, and alternative requirements must not be silently promoted to unconditional mandatory outcomes.
6. Preserve operation order only when the request expresses ordering or a dependency is logically required by the requested result.
7. Do not infer data availability, schemas, connectors, recipients, destinations, permissions, timezones, or external state.
8. Use only canonical GoalSpec classes, fields, effect syntax, and exact Theta common types.
9. Keep the existing mandatory human-review gate. No interpretation status can authorize discovery or execution.
10. Keep v2 fields backward-compatible until all consumers have migrated under a versioned API contract.

## Proposed v3 frame

The v3 frame is additive and versioned. Suggested top-level shape:

```json
{
  "contract_version": "3.0",
  "objective": {
    "text": "original user text, unchanged",
    "locale": "detected-or-user-supplied",
    "normalization": "none"
  },
  "outcomes": [
    {
      "id": "outcome_1",
      "goal_class": "search",
      "requirement": "required",
      "modality": "asserted",
      "source_evidence": [
        {
          "start": 0,
          "end": 6,
          "text": "Search",
          "cue": "operation_lexeme"
        }
      ],
      "condition_ref": null,
      "alternative_group": null,
      "depends_on": [],
      "interpretation": {
        "method": "deterministic_rule",
        "confidence": null,
        "semantic_correctness_verified": false
      }
    }
  ],
  "conditions": [],
  "alternatives": [],
  "dependencies": [],
  "inputs": [],
  "outputs": [],
  "constraints": {},
  "clarifications": [],
  "review": {
    "required": true,
    "semantic_correctness_verified": false
  }
}
```

The example is illustrative, not a mandatory schema until canonical GoalSpec and Theta compatibility is confirmed.

## Requirement semantics

Use a closed vocabulary:

- `required`: directly requested or strictly necessary for a requested outcome.
- `conditional`: required only when a named condition is satisfied.
- `optional`: explicitly offered as optional or requested as a non-blocking enhancement.
- `alternative`: one member of an explicitly expressed choice; do not require all alternatives.
- `negated`: explicitly prohibited or explicitly not requested; it must not become an executable outcome.

Do not infer `optional` from politeness, uncertainty, or an analyst's preference. Do not infer `conditional` without an identifiable condition expression. If scope or modality cannot be resolved conservatively, create a clarification and leave the outcome unresolved rather than guessing.

## Source traceability

- Use offsets into the exact, unnormalized original text.
- Define offsets consistently (Unicode code points) and test accented and non-Latin text.
- Every lexical outcome must carry at least one evidence span.
- Derived prerequisites must identify the outcome they support and use evidence kind `derived_dependency`, not fabricated source text.
- If text normalization is later introduced, retain an explicit reversible offset map.
- Evidence spans are provenance, not semantic proof.

## Negation and modality handling

Detect negation locally and structurally, not by searching the entire prompt for a negation word. Examples to cover include:
- “Do not send the report; only draft it.”
- “Do not execute the migration.”
- “If validation fails, notify the owner.”
- “You may optionally create a chart.”
- “Create either a PDF or a presentation, not both.”

A rule-based parser must abstain when negation scope is unclear (for example, nested clauses, contrastive conjunctions, or double negation). It must never silently reinterpret a prohibited side effect as requested.

## Alternatives and conditions

Represent an alternative as a group with an explicit selection policy only when the user expresses a choice. Do not decide the preferred alternative unless the objective does so.

Represent a condition as a separately identified predicate with:
- original source span;
- unresolved variables, if any;
- the outcome(s) it governs;
- evaluation status `unresolved` until an authorized, evidenced evaluator exists.

The parser must not evaluate business conditions using invented data.

## Dependency and data contracts

Represent dependencies as directed edges between outcomes, with:
- edge kind: `explicit_order`, `data_dependency`, or `derived_prerequisite`;
- evidence span or derivation rationale;
- validation status.

A dependency graph must be acyclic for a sequential GoalSpec proposal. If the request expresses a loop/recurrence, preserve it as a workflow-level requirement and request a supported orchestration model rather than forcing it into a DAG.

Inputs and outputs must distinguish:
- user-supplied data;
- requested external acquisition;
- intermediate artefacts;
- final deliverables;
- side effects (persist, publish, send, transact, execute).

Each type must be an exact canonical Theta common type. Keep undeclared business concepts in descriptions and clarification records.

## Clarification policy

Create explicit clarification items for material unknowns that change the plan, safety, or expected result, including:
- ambiguous source or population;
- missing business date field or timezone;
- ambiguous unit/currency or aggregation definition;
- unspecified recipient or destination for a side effect;
- alternatives with no selection rule;
- conflicting constraints;
- unsupported goal class or semantic type.

A clarification must state the unresolved question, why it matters, affected outcomes, and whether discovery must be blocked. Do not ask for details that are not necessary to proceed safely.

## API and Studio integration

- Keep `/api/v1/objectives/prepare` as the Core-first preparation entry point.
- Return v3 interpretation alongside legacy v2 projection during migration.
- Render a side-by-side evidence view: original text, source spans, requirement modality, dependencies, conditions, alternatives, unresolved concepts, and clarifications.
- Allow users to correct classifications and spans; retain both machine proposal and human edits with provenance.
- Any edit invalidates previous review confirmation and requires reconfirmation.
- Apply must be blocked for negated-as-required conflicts, unresolved mandatory outcomes, invalid dependency graphs, unsupported canonical types, or blocking clarifications.
- Discovery remains metadata-only and requires explicit human confirmation.
- No execution action is introduced by this milestone.

## Acceptance matrix

Tests must be scenario-independent and include unrelated domains, languages, and output forms.

| Case | Example shape | Required assertion |
|---|---|---|
| Negated side effect | “Draft the email; do not send it.” | Draft/write intent retained; send is negated, never required |
| Conditional side effect | “If the check fails, notify the owner.” | Notify is conditional and linked to the condition |
| Optional enhancement | “Optionally include a chart.” | Chart is optional, not mandatory |
| Explicit alternatives | “Export as PDF or DOCX.” | One alternative group; neither forced as both |
| Explicit order | “Validate, then publish.” | Ordered dependency with source evidence |
| Data dependency | “Calculate the average from the supplied table.” | Input provenance and computation dependency retained |
| Conflicting requirements | “Do not store it, but save a copy.” | Blocking clarification; no silent resolution |
| Multilingual | Equivalent English, French, Arabic prompts | Locale-aware evidence spans; no fabricated translation |
| Unknown domain | Unfamiliar domain vocabulary | Unknown concepts preserved; no invented Theta types |
| Unicode offsets | Accented and non-Latin text | Evidence offsets point to exact original substrings |
| Nested modality | Nested “unless/except/only if” clauses | Conservative abstention when scope is uncertain |
| No operation verb | Declarative or underspecified request | No fabricated operation; clarification when material |

For every case assert: exact original text retained; evidence offsets are valid; no unsupported type is created; no tool is invoked; human review remains mandatory; semantic correctness remains false; discovery is blocked until review.

## Release gates

1. Schema and migration design reviewed against all current consumers.
2. Parser unit tests pass for English, French, and Arabic Unicode examples.
3. Property-based tests verify every evidence span slices the exact original text.
4. Negative tests prove negated actions never appear as required outcomes.
5. Alternative/conditional tests prove the parser does not flatten modality.
6. Core conformance consumes the v3 projection without weakening canonical validation.
7. Studio renders evidence and clarification states accessibly.
8. Colab acceptance notebook runs from a clean runtime and records actual output.
9. GitHub Actions passes on the exact notebook-pinned source revision.
10. Human review and no-execution boundaries remain intact.

## Known limitations

Rule-based parsing cannot guarantee general natural-language understanding. A language model may propose a richer interpretation, but its output must be checked against source evidence, canonical vocabularies, structural invariants, and human review. No confidence score should be presented as calibrated unless measured and validated on a representative held-out dataset.