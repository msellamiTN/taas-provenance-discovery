# UX-5 — Alignment Review & Evidence Ledger

Status: implementation branch `codex/ux5-alignment-evidence-ledger`, stacked on UX-4 head `e28def63a29eda4a82b3c188e0b5b06325754572`.

## Objective

Capture an operator-reviewable evidence snapshot of the latest UX-4 exact-label comparison, with traceability to GoalSpec requirements and tool schema locations.

## Evidence contract

- Snapshot creation is explicit and requires a preceding metadata comparison refresh.
- Each finding records GoalSpec ID, direction (input/output), required label, result status, explanation, and exact matching tool/schema direction/path/label evidence.
- Source selection is recorded: current registry selection basket, or canonical discovery request toolset when the basket is empty.
- Separate deterministic fingerprints cover the relevant GoalSpec contract and selected tool identity/schema metadata.
- Fingerprints use FNV-1a 32-bit and are **non-cryptographic change detectors only**. They are not signatures, integrity proofs, or authenticity guarantees.
- A snapshot is marked stale when GoalSpec editing or a refreshed comparison detects changed fingerprints. Acknowledgement and export re-check current fingerprints before proceeding.
- Reviewer label is optional and operator-supplied. It is not authenticated identity; absent labels are recorded as `reviewer not recorded`.
- Review acknowledgement is a deliberate human action and records timestamp, label and narrow review scope.
- JSON export is user-triggered and contains comparison findings and schema paths, not API credentials or complete request payloads.

## Persistence and safety boundary

- Snapshot state exists only in the current page session. It is not persisted by TaaS Core and is not durable audit evidence.
- No new backend endpoint, API request, model call, discovery call, MCP invocation, approval mutation, authorization grant, or execution path is added.
- Exported records explicitly state `execution_performed=false`, `execution_record=false`, `authorization_granted=false`, `semantic_correctness_proven=false`, and `goal_fulfilment_proven=false`.
- Acknowledgement means only that an operator reviewed the metadata comparison. It does not establish semantic correctness, tool correctness, goal fulfillment, policy eligibility, authorization, or execution.
- UX-4 exact-label-only semantics and the fixed experimental protocol are unchanged.

## Regression coverage

`tests/test_studio_alignment_evidence_ledger.py` covers UI controls, explicit capture, fingerprint scope, schema-path traceability, acknowledgement, stale-state detection, export constraints, safety semantics, and absence of API/execution calls.

## Operator acceptance

1. Open Goal Design, create or load a GoalSpec, and refresh UX-4 metadata comparison.
2. Capture an evidence snapshot; confirm the reviewer label is optional and explicitly unauthenticated.
3. Inspect input and output findings separately, including tool identity and schema path for exact matches.
4. Acknowledge review explicitly; confirm timestamp and reviewer label are recorded.
5. Change a GoalSpec field, refresh, and confirm the old review is invalidated.
6. Change/remove a selected tool schema or basket entry, refresh, and confirm stale detection before acknowledgement/export.
7. Export JSON and verify the record contains only comparison evidence and fingerprints, with no bearer token or full discovery request.
8. Confirm page reload clears the in-memory snapshot; no durable Core persistence is claimed.
9. Confirm no API call, model call, MCP invocation, approval mutation, authorization grant, or execution occurred.
10. Test keyboard operation, narrow viewport, long labels, invalid JSON, and screen-reader announcements.

## Acceptance evidence classes

Source checks, JavaScript parsing, pytest, CI, authenticated Colab acceptance, and browser/keyboard review are separate. Do not mark UX-5 accepted until the exact-head automated and operator checks are complete.
