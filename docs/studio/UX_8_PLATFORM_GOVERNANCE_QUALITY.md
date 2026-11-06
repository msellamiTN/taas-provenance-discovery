# UX-8 — Platform Governance, Security, Performance & Validation

Status: implemented as a UI-only increment on `codex/ux8-governance-quality-validation`, stacked on UX-7 PR #83 head `90c448f5fd250845c62a2ea26c02c42431a6f04f`. The user explicitly approved the UX-8 visual structure before implementation.

## Objective

Provide a unified workspace for inspecting platform quality and recording evidence-backed accessibility, security, performance and validation outcomes. The workspace must not imply that an assessment was run or that a control is effective without verifiable evidence.

## User journey

1. Open **Platform Governance & Quality (UX-8)** from Studio navigation.
2. Review the evidence posture and acceptance boundary.
3. Inspect Accessibility, Security & Policies, Performance, Validation & Quality, and Reports.
4. Treat NOT_RUN and UNKNOWN as unresolved states; do not interpret them as success.
5. Attach future test evidence to an exact commit and environment through a separately reviewed integration.

## Implemented views

- Overview: evidence posture, acceptance boundary and execution governance.
- Accessibility: WCAG 2.2 AA target, keyboard, screen-reader, contrast, zoom and reflow evidence requirements.
- Security & Policies: secret handling, authentication/RBAC, input validation, isolation and network-policy evidence requirements.
- Performance: LCP, INP, CLS, load/bundle and resource profile fields, explicitly NOT_RUN.
- Validation & Quality: build, unit/regression, browser, security and Colab validation matrix.
- Reports: explicit empty state until a traceable report exists.
- Six local tabs with click, ArrowLeft/ArrowRight, Home and End keyboard navigation, ARIA tab semantics and responsive layouts.

## Evidence-state semantics

- `NOT_RUN`: the check has not been executed or no execution result has been supplied.
- `UNKNOWN`: the control's state is not established by available evidence.
- `PASS` / `FAIL`: reserved for an actual, reviewable result tied to exact commit, environment, timestamp, procedure and output.
- `NEEDS_REVIEW`: evidence exists but is incomplete, ambiguous, stale or requires human assessment.

WCAG 2.2 AA is an intended target, not a certification or conformance claim. No accessibility score, security compliance percentage, performance metric, validation run ID, test pass count or deployment status is fabricated.

## Governance and non-goals

This increment is a local UI surface. It adds no validation runner, browser automation, security scanner, telemetry collector, runtime adapter, isolated worker, execution API, MCP invocation, model call, authorization grant, policy enforcement, secret access, persistence, or deployment automation.

Discovery metadata, assurance observations and policy descriptions are not proof of enforcement, authorization, semantic correctness or goal fulfilment. Governed MCP execution and isolated workers remain disabled. The fixed experimental protocol and UX-2 through UX-7 behavior are unchanged.

## Regression coverage

`tests/test_studio_governance_quality.py` checks navigation, the six panels, evidence-state semantics, WCAG target wording, non-fabrication, absence of execution/validation claims, accessible tabs, keyboard behavior and documentation.

## Acceptance still required

1. Run the complete project pytest suite in the supported environment.
2. Run repository CI against the exact UX-8 head and inspect all workflow results.
3. Load the Studio in authenticated Colab and verify the section renders.
4. Verify desktop, tablet and narrow mobile layouts.
5. Test keyboard-only navigation and screen-reader behavior.
6. Run actual accessibility, security and performance assessments before recording outcomes.
7. Confirm no UX-8 action makes runtime, execution, authorization or policy-enforcement requests.

Source assertions are not substitutes for pytest, CI, browser, Colab or assistive-technology acceptance. Do not mark UX-8 accepted until those evidence classes are recorded.
