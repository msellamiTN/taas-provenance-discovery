# UX-7 — Isolated Runtime & Execution Observability Workspace

Status: implemented on `codex/ux7-isolated-runtime-observability`, stacked on UX-6 head `a61bad7c00254a151fda8b6acbaa92026554a38a`. The user explicitly approved the UX-7 visual baseline and all safety corrections before implementation.

## Objective

Provide a professional runtime and observability workspace for inspecting configured isolated runtimes and genuine execution records when such an integration is separately implemented and authorized. This UI increment does not implement a runtime.

## User journey

1. Open **Runtime & Observability (UX-7)** from the Studio navigation.
2. Review runtime, worker, session and resource availability.
3. Switch between Sessions, Timeline, Logs, Traces, Metrics and Diagnostics.
4. Inspect the isolation and governance boundary.
5. When no runtime adapter exists, receive explicit unconfigured/empty states rather than illustrative operational data.

## Current implementation state

- Runtime adapter: not configured.
- Worker pool: not configured.
- Session records: none available.
- Timeline, logs, traces, metrics and diagnostics: unavailable; empty states explain why.
- Sandbox/network/secrets posture: not verified or reported.
- Authorization: not granted.
- Execution: disabled. Run and export controls are disabled.

No runtime values, session IDs, timestamps, event records, trace IDs, resource utilization, health states or authorization are fabricated.

## Interaction and accessibility

- Six local tabs: Sessions, Timeline, Logs, Traces, Metrics and Diagnostics.
- Tabs support click, ArrowLeft/ArrowRight, Home and End keyboard navigation.
- `aria-selected`, `aria-pressed`, `tabIndex`, `aria-controls` and labelled tabpanels expose the active view.
- Responsive overview and two-column isolation layout.

## Governance and non-goals

This UI-only increment adds no runtime adapter, isolated worker, worker pool, scheduler, execution API, MCP invocation, model call, approval mutation, authorization grant, secrets handling, network policy enforcement, durable persistence or deployment integration.

Observability is not authorization. Logs, traces and metrics—if a future runtime integration supplies them—are observations, not proof of semantic correctness or goal fulfilment. Discovery metadata and assurance evidence are not execution records. Execution remains disabled until a separately reviewed and explicitly authorized capability exists.

The fixed experimental protocol and UX-2 through UX-6 behavior are unchanged.

## Regression coverage

`tests/test_studio_runtime_observability.py` checks navigation, empty/unconfigured states, disabled execution controls, absence of fabricated telemetry, governance wording, accessible tab semantics and absence of runtime/execution calls in the UX-7 script.

## Acceptance still required

1. Run the complete project pytest suite in the supported environment.
2. Run the repository CI workflows and inspect exact-head results.
3. Load the Studio in authenticated Colab and verify the section renders.
4. Verify responsive behavior at desktop, tablet and narrow mobile widths.
5. Test tab operation using keyboard only and a screen reader.
6. Confirm no runtime/API/network request is issued by UX-7.
7. Confirm execution remains unavailable and no runtime records appear unless genuine evidence is supplied by a separately authorized integration.

Source assertions are not a substitute for pytest, CI, Colab, or browser/assistive-technology acceptance. Do not mark UX-7 fully accepted until these evidence classes are recorded.
