# UX-6 — Evidence Diff & Change Impact Workspace

Status: implemented on branch `codex/ux6-evidence-diff-change-impact`; stacked on the approved UX-5 head `557574299be63ea5538c5af6fddaabaa77c73c58`. The visual mockup was explicitly approved before implementation.

## Objective

Compare two user-selected UX-5 alignment evidence JSON exports, explain finding-level changes, and summarize the possible impact on metadata alignment.

## User journey

1. Export two UX-5 snapshots using the existing user-triggered JSON export.
2. Load snapshot A as the baseline and snapshot B as the compared state.
3. Select **Compare snapshots**.
4. Filter added, removed, and modified findings.
5. Inspect each finding's GoalSpec ID, direction, required label, status, explanation, and schema evidence paths.
6. Review aggregate alignment indicators and optionally export the local diff JSON.
7. Reset the workspace to clear selected files and in-memory comparison state.

## Input contract

- Accepts only `taas.alignment-evidence.v1` JSON with a findings array, GoalSpec and toolset fingerprints, and explicit `execution_performed=false` / `execution_record=false` semantics.
- Each file is limited to 2 MiB.
- Finding identity is the tuple `goal_id + direction + required_label`.
- Added: identity appears only in B.
- Removed: identity appears only in A.
- Modified: identity exists in both, but status, explanation, or evidence differs.
- Unchanged findings are omitted from the change list; still-matched count is reported separately.
- GoalSpec and toolset fingerprints are compared and shown as change indicators. The UX-5 FNV-1a fingerprints remain non-cryptographic drift indicators, not integrity proofs.

## Impact interpretation

- `still_matched`: a B finding is matched and the same finding identity was matched in A.
- `now_unmatched`: a changed/added B finding has status `unmatched`.
- `now_incompatible`: a changed/added B finding explicitly reports `incompatible`.
- `needs_review`: a changed/added B finding is `not_comparable` or has no reported status.
- Removed findings are reported as removals, not misclassified as current B-state gaps.
- These are metadata status counts, not semantic compatibility or goal-satisfaction claims.

## Safety and persistence boundary

- Both files are parsed and compared locally in the browser tab. No backend/API request, model call, discovery call, MCP invocation, approval mutation, authorization grant, or execution is added.
- Snapshot inputs are not rewritten or mutated.
- The diff export is explicit and contains comparison metadata and finding evidence only.
- Export semantics explicitly state `execution_performed=false`, `execution_record=false`, `authorization_granted=false`, `semantic_correctness_proven=false`, and `goal_fulfilment_proven=false`.
- No durable storage or Core audit record is claimed. Reset clears the current workspace; reload clears in-memory state.
- UX-4 exact-label comparison, UX-5 evidence capture, and the fixed experimental protocol are unchanged.

## Regression coverage

`tests/test_studio_evidence_diff_impact.py` checks navigation and controls, input schema validation, identity and change classification, impact semantics, local export boundaries, safe text rendering, and non-mutation of UX-5.

## Operator acceptance still required

1. Export two genuine UX-5 snapshots from the running Studio.
2. Compare identical snapshots; confirm zero changes and unchanged matched findings.
3. Compare snapshots with a changed GoalSpec fingerprint only.
4. Compare snapshots with a changed toolset fingerprint only.
5. Verify added, removed, and modified finding cases, including input/output directions.
6. Verify unmatched, incompatible, and not-comparable statuses; confirm removed findings are not counted as current gaps.
7. Test malformed JSON, wrong schema version, missing fingerprints, missing non-execution semantics, and files over 2 MiB.
8. Test keyboard navigation, screen-reader announcements, long labels/schema paths, and narrow viewport.
9. Export the diff and inspect the explicit non-execution/non-authorization semantics.
10. Confirm no network/API call or execution occurs.

Source checks, JavaScript parsing, pytest, CI, authenticated Colab acceptance, and browser/keyboard acceptance are separate evidence classes. Do not mark UX-6 accepted until exact-head automated and operator checks are complete.
