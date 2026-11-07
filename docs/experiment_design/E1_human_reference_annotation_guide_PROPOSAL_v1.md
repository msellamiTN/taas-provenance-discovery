# E1 Human Reference Annotation Guide — Proposal v1.0

**Status:** PROPOSED — NOT APPROVED FOR ANNOTATION  
**Protocol:** PaMCP Definitive Experimental Specification v1.0  
**Scope:** E1 only. This proposal operationalizes the existing human reference-effect fields; it does not amend the frozen protocol.  
**Approval gate:** Do not use until the study owner approves this guide and records the approved version.

## 1. Purpose and boundary

E1 requires a human reference label for the share of tools that are non-read-only. The MCP `readOnlyHint` field is a declaration, not ground truth; it must not determine the human label.

The repository currently defines `STATE_MODIFYING` in `src/taas/effects.py` as exactly:

- `write`
- `delete`
- `exec`
- `money`

The proposed annotation construct must remain consistent with this implementation: **whether the documented operation can modify persistent, shared, or external state through at least one of these four effect classes**. This guide must not silently broaden the construct to every externally observable effect.

## 2. Unit and evidence

The annotation unit is one frozen tool definition, identified by `annotation_unit_id` and the exact definition hash in the owner-side mapping. A changed definition is a different unit.

Both annotators receive the same evidence packet, limited to:
1. Tool name and description.
2. Input schema and declared parameters.
3. Operation semantics explicitly present in the frozen definition.
4. Additional primary documentation only if the study owner includes the same versioned source for both annotators.

Do not use `readOnlyHint`, policy declarations, model/LLM guesses, embeddings, the other annotator's work, category-based assumptions, or undocumented server behavior as evidence.

## 3. Proposed binary decision rule

### `non_read_only=true`

Choose true when the documented operation can perform at least one of:

- **write:** create, modify, overwrite, append, upload, or persist data, resources, or configuration;
- **delete:** remove or destroy persistent/shared resources;
- **exec:** execute a command, job, workflow, deployment, or process that may change state;
- **money:** initiate or perform a payment, charge, refund, purchase, transfer, or comparable financial transaction.

A mixed read-and-modify operation is true. A supported parameter or mode that enables one of these effects is sufficient, even if another mode is observational.

### `non_read_only=false`

Choose false when the documented operation does not perform any of those four state-modifying classes.

The repository's other effect classes are `read`, `egress`, and `session`. These do **not** by themselves make `non_read_only=true` under the current `STATE_MODIFYING` definition. In particular, sending, publishing, fetching, browsing, or other network egress alone must not be labelled true unless the documented operation also entails `write`, `delete`, `exec`, or `money`.

### Ambiguous / insufficient evidence

The current annotation CSV and `experiments/e1/reconcile_reference_annotations.py` require a binary `non_read_only` value. They do not support an `UNRESOLVED` value. Therefore, annotators must **not guess or force a binary label** when the supplied evidence is insufficient. Stop that unit and escalate it to the study owner before freezing the sheets. The owner must resolve the evidence question under an approved written rule, or separately approve a schema/protocol change that supports unresolved labels. Any excluded or escalated units must be disclosed in coverage reporting.

## 4. Special cases

- **Mixed operations:** true if the same documented invocation can read and modify state.
- **Conditional effects:** true if a supported parameter or mode can invoke one of the four modifying classes.
- **Dry-run / preview:** false only when the definition clearly limits the assessed operation to non-mutating preview; true if the tool also supports applying/executing the change.
- **Validation / planning:** false if it only validates or plans; true if it applies the plan or executes it.
- **Notifications / messages / publishing:** egress alone is not true under the current construct; classify true only if a qualifying modifying effect is also documented.
- **Authentication:** reading identity/session information alone is not true; creating, rotating, revoking, or changing credentials is true when it constitutes a qualifying state modification.
- **Unknown implementation behavior:** do not infer hypothetical side effects. Escalate if the frozen definition cannot support a defensible binary decision.

## 5. Annotation sheet contract

The reconciliation utility currently requires the following columns: `annotation_unit_id`, `non_read_only`, `effect_classes`, `confidence_0_1`, and `rationale`; it also checks consistent tool-name context. This proposal does not add columns.

| Field | Instruction |
|---|---|
| `annotation_unit_id` | Preserve exactly as supplied. |
| `non_read_only` | Enter true/false only after applying the decision rule. |
| `effect_classes` | Record applicable classes from `read`, `write`, `delete`, `exec`, `egress`, `money`, `session`; do not treat all classes as state-modifying. |
| `confidence_0_1` | Numeric confidence in [0,1]. Low confidence is not a substitute for an unresolved label. |
| `rationale` | Concise evidence-based explanation. Quote or identify the relevant operation wording/parameter and explain why it maps to the selected class. |
| `tool_name` | Preserve the supplied context value unchanged. |

Do not introduce extra CSV columns unless the reconciliation utility and its tests are updated and separately reviewed. Rationales must not merely restate the decision.

## 6. Independent annotation and agreement

1. Provide both annotators the same evidence packet and approved guide version.
2. Keep annotators blind to each other's decisions and rationales.
3. Distribute only the minimum annotation sheet needed. Keep the restricted registry-to-identity mapping owner-side; never send it with annotator packets.
4. Each annotator completes the full assigned unit set independently.
5. Freeze both sheets before comparison.
6. Compute raw agreement and Cohen's κ over the paired binary labels; report the exact denominator and category counts.
7. If the data are degenerate (only one category) or κ is undefined/unstable, report that limitation and raw agreement. Do not claim reliability from κ alone.
8. Freeze agreement statistics before adjudication. Adjudicate disagreements through a qualified third reviewer or a documented consensus process. Preserve both original labels and the adjudicated label; never overwrite independent records.

## 7. E1 reporting

Report separately:
- total tools in the frozen registry;
- adjudicated true and false counts and percentages;
- count and percentage of units escalated/excluded before sheet freeze;
- count and percentage missing/not annotated;
- raw agreement and Cohen's κ, including denominator and category counts;
- disagreement count and adjudication procedure.

State the denominator for the non-read-only share. Report label coverage over the full frozen registry and do not present the labelled subset as if it covered every tool. Keep declared `readOnlyHint` prevalence separate. Any declaration/reference comparison must use only units with both values and must report that paired denominator.

## 8. Quality control

Before analysis:
- verify one row per `annotation_unit_id` per annotator;
- verify all IDs map to the expected frozen definition hash;
- verify both annotators cover the same assigned unit set;
- verify no duplicate IDs, invalid booleans, out-of-range confidence values, or missing rationales;
- verify independent completion and freeze timestamps precede agreement calculation;
- preserve original sheets, adjudication log, reconciliation script, environment, and output hashes;
- keep the restricted mapping separate from annotator materials.

## 9. Approval and change control

The study owner must explicitly approve:
1. the four-class construct and binary decision rule;
2. the permitted evidence packet;
3. the special-case handling;
4. the independent annotation, agreement, and adjudication procedure;
5. denominator and coverage reporting.

Adding an `UNRESOLVED` state would require coordinated changes to the annotation CSV schema, reconciliation script, tests, and statistical denominator rules. If it changes the target construct or E1 metric, it also requires a separately approved protocol amendment. Any substantive change after annotation begins requires a version bump, impact assessment, and a decision on re-annotation.

---

**Current disposition:** Proposed supplement only. E1 reference-effect annotation remains blocked pending approval and completion of independent annotation. This document is not evidence of an experimental result.
