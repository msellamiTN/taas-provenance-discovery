# E1 Human Reference Annotation Guide — Proposal v1.0

**Status:** PROPOSED — NOT APPROVED FOR ANNOTATION  
**Protocol:** PaMCP Definitive Experimental Specification v1.0  
**Scope:** E1 only; operationalization of the existing human reference-effect annotation fields.  
**Change control:** This document does not amend the frozen experimental protocol. No annotator should use it until the study owner approves it and records the approval/version.

## 1. Purpose and boundary

E1 includes human reference-effect labels used to estimate the share of tools whose operation is non-read-only. The existing registry field `readOnlyHint` is a provider/server declaration. It is not ground truth and must never be used as the human reference label.

This guide proposes a reproducible coding procedure for the existing E1 annotation task. It does not add an experiment, alter E1 metrics, change the registry snapshot, or authorize relabeling historical results.

## 2. Unit of annotation

The unit is one frozen tool definition identified by the supplied `annotation_unit_id` and its associated tool identifier and definition hash.

Annotators must assess the exact tool definition represented by that hash. If the tool definition changes, it is a new annotation unit and must not silently inherit the old label.

## 3. Evidence permitted

For each unit, use only the evidence package explicitly supplied for E1:

1. Tool name and description.
2. Input schema and declared parameters.
3. Any operation semantics included in the frozen tool definition.
4. Additional primary documentation only if the study owner explicitly includes it in the common annotation packet and records its version/source for both annotators.

Do not use:
- `readOnlyHint` or other trust/policy declarations as evidence of actual effect;
- model-generated guesses, embeddings, similarity scores, or LLM labels;
- the other annotator's decisions;
- assumptions based only on a tool name;
- undocumented behavior inferred from a server category.

If evidence is insufficient, record an unresolved label rather than guessing.

## 4. Proposed decision rule

The repository currently defines the E1 state-modifying effect classes in `src/taas/effects.py`: `write`, `delete`, `exec`, and `money` (`STATE_MODIFYING`). The proposed human reference decision must be consistent with that operational construct: **whether the documented operation can modify persistent, shared, or external state through one or more of those four classes**. Do not silently broaden this to every externally observable effect.

### NON_READ_ONLY = YES

Choose YES when the documented operation can do at least one of the following:

- create, modify, overwrite, or delete data, files, records, resources, or configuration;
- submit, send, publish, transmit, or trigger an external action;
- execute a command, job, workflow, transaction, deployment, or other operation that may change system state;
- grant, revoke, or alter permissions, credentials, access, subscriptions, or account state;
- initiate a payment, purchase, booking, cancellation, or other consequential transaction.

A tool remains YES if it also returns information or a status after performing the action.

### NON_READ_ONLY = NO

Choose NO only when the documented operation is limited to observation, retrieval, search, listing, filtering, or description and there is no documented state-changing or externally side-effecting behavior.

Examples include reading a record, listing resources, searching documents, or retrieving a status, provided the operation does not also trigger a state change.

### UNRESOLVED

Choose UNRESOLVED when the definition does not provide enough evidence to decide, when the wording is materially ambiguous, or when the operation's effect depends on undocumented implementation behavior.

Do not force UNRESOLVED into YES or NO for the sake of completing a row. Report the number and proportion of unresolved units.

## 5. Special cases

- **Mixed operations:** If one documented invocation can both read and change state, label YES.
- **Conditional effects:** If the documented operation can change state under a supported parameter or mode, label YES even if a default invocation may only read.
- **Dry-run / preview:** Label NO only if the definition clearly guarantees that the operation is non-mutating in the assessed mode. If the same tool also supports execution, label YES.
- **Validation / planning:** Label NO when it only validates or plans and does not apply changes. Label YES if it applies the plan or triggers execution.
- **Messages and notifications:** Sending or publishing is YES, even if the underlying stored content is unchanged.
- **Authentication:** Obtaining or reading identity/session information is not by itself a side effect. Creating, rotating, revoking, or changing credentials is YES.
- **Unknown server behavior:** Do not infer side effects merely because a server could theoretically implement them. Use the documented tool semantics; otherwise UNRESOLVED.

## 6. Required annotation record

For every unit, each annotator independently records:

| Field | Requirement |
|---|---|
| annotation_unit_id | Copy exactly from the assigned sheet |
| decision | YES, NO, or UNRESOLVED |
| rationale | Concise evidence-based explanation; identify the action verb/parameter that supports the decision |
| evidence_excerpt | Short exact excerpt from the supplied tool definition |
| ambiguity_note | Required for UNRESOLVED; otherwise optional |
| annotator_id | Assigned opaque annotator code |
| guide_version | This guide version, if approved |
| definition_hash | Must match the frozen mapping |

Rationales must describe evidence, not merely restate the decision (e.g. avoid “non-read-only because it is not read-only”).

## 7. Independent annotation and agreement

1. Provide the same evidence packet and guide version to both annotators.
2. Keep the annotators blind to each other's decisions and rationales.
3. Do not expose the restricted registry-to-identity mapping unless it is strictly needed; distribute only the minimum per-annotator annotation sheet.
4. Freeze both completed sheets before comparison.
5. Compute raw agreement and Cohen's κ on units where both annotators made a binary YES/NO decision. Report the denominator and unresolved counts explicitly.
6. Also report each annotator's unresolved rate. Do not silently discard unresolved units from coverage reporting.
7. If the binary subset is degenerate (one category only) or κ is undefined/unstable, report that limitation and raw agreement; do not claim reliable agreement from κ alone.
8. Only after agreement statistics are frozen, adjudicate disagreements with a third qualified reviewer or a documented consensus process. Preserve both original labels and the adjudicated label; never overwrite the independent records.

## 8. E1 reporting rules

Report separately:

- total frozen tools;
- number and percentage with an adjudicated YES label;
- number and percentage with an adjudicated NO label;
- number and percentage unresolved;
- number and percentage not annotated / missing;
- each annotator's raw agreement and Cohen's κ, with the exact denominator and method;
- adjudication procedure and count of disagreements.

The non-read-only share must state its denominator. Under the current binary schema, the intended denominator is all tools with a final adjudicated human reference label. Report coverage over the full frozen registry and disclose any excluded/escalated units; do not present the labelled subset as if it covered all registry tools.

Declared `readOnlyHint` prevalence must remain a separate descriptive statistic. Any comparison between declarations and human reference labels must use only units with both fields available and must report that paired denominator.

## 9. Quality-control checks before analysis

- Verify one row per `annotation_unit_id` per annotator.
- Verify all annotation IDs map to the expected frozen definition hash.
- Verify the two annotators cover the same assigned unit set.
- Verify no duplicate IDs, missing rationales for resolved labels, or invalid decision values.
- Verify the two annotation sheets were independently completed and frozen before agreement computation.
- Preserve original sheets, adjudication log, script, environment, and output hashes.
- Do not release the restricted mapping with annotator packets.

## 10. Approval gate

Before this guide is used, the study owner must explicitly approve:

1. the YES/NO/UNRESOLVED construct and decision rule;
2. the permitted evidence packet;
3. the special-case handling;
4. the agreement and adjudication procedure;
5. the denominator/reporting rules.

Any substantive change after annotation starts requires a version bump, impact assessment, and a decision on whether affected rows must be re-annotated. In particular, adding `UNRESOLVED` requires coordinated changes to the CSV schema, reconciliation script, statistical denominator rules, and (if the target construct changes) a protocol amendment. The protocol itself remains frozen unless a separately approved protocol amendment is issued.

---

**Current disposition:** This is a proposed operational supplement only. E1 reference-effect annotation remains blocked pending approval and completion of independent annotation. No experimental result is asserted by this document.
