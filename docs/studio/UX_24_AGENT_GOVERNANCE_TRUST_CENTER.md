# UX-24 — Agent Governance & Trust Center

## Status

- Mockup: approved by the product owner.
- Implementation: first frontend increment committed on `feature/ux-24-agent-governance-trust-center`.
- Scope: read-only governance workspace for an exact immutable Agent version.
- Backend: reuses existing TaaS Core APIs; no new policy engine or endpoint introduced.

## User workflow

1. Connect to TaaS Studio using the existing application-header authentication.
2. Load Agent versions from `GET /api/v1/agents?limit=500`.
3. Select an Agent ID and immutable version.
4. Refresh the assessment. The Studio independently requests:
   - `GET /api/v1/agents/{agent_id}/versions/{version}`
   - `GET /api/v1/agents/{agent_id}/versions/{version}/release-readiness`
   - `GET /api/v1/agents/{agent_id}/versions/{version}/policy-verdict`
   - `GET /api/v1/agents/{agent_id}/versions/{version}/approvals`
   - `GET /api/v1/agents/events?agent_id={agent_id}&limit=100`
   - `GET /api/v1/audit/verify`

All calls use the existing bearer-token helper. Requests are read-only.

## Workspace views

| View | Data source | Display |
|---|---|---|
| Trust overview | Agent version, release readiness, policy verdict | Exact subject binding, decision and readiness summary |
| Policy registry & verdict | Per-Agent policy verdict | Core-returned fired rules and raw verdict; no client-authored rules |
| Consistency & conflicts | Policy verdict and readiness | Conflicts, unavailable facts, checks, blockers and warnings |
| Permissions & access | Exact Agent manifest | Declared tool/resource grants and explicit authorization boundary |
| Governance evidence | Approval records, Agent events, audit verification | Human approval records, lifecycle events and audit-chain state |

## Decision and evidence semantics

- The policy verdict is diagnostic. `allow` is not authorization.
- Release readiness is not an execution permission.
- Declared tool grants are not effective authorization.
- HMAC evidence integrity does not establish assessor-claim truth.
- Missing evidence remains UNKNOWN / NEEDS_REVIEW; it is never rendered as PASS.
- Audit-chain validity proves tamper-evidence of recorded events, not that an action occurred.
- Human approval records are evidence records; the workspace does not create or renew them.
- No write, publish, revoke, policy mutation, authorization preflight, MCP invocation or execution control is added.

## Known API boundary

The current policy engine exposes default rules through the per-Agent verdict's `fired_rules`; there is no separate policy CRUD/registry endpoint in the inspected Core API. UX-24 therefore labels this view “Policy registry & verdict” but displays only rules returned by Core, without implying editable policy administration.

The current per-Agent verdict response does not expose the complete internal fact bundle. The UI does not reconstruct or infer missing facts; evidence summaries not present in the response remain UNKNOWN.

The current audit verifier scans the entire recorded ledger in bounded batches of at most 1,000 events per page (`audit_ledger.verify_chain` via `list_events_page`). UX-24 therefore labels a successful result `FULL_CHAIN_VALID` and a failed or unavailable result `FULL_CHAIN_INVALID_OR_UNKNOWN`. The response reports `scan_scope: full_ledger`. This establishes tamper-evidence for all recorded events at verification time; it does not prove that the recorded claims are true, that an action occurred, or that any tool was authorized or executed.

On each assessment, UX-24 clears prior subject data before requesting the newly selected immutable version and temporarily locks the selectors to prevent late responses from being attributed to a different selection. An empty evidence summary is rendered as `NO_VERIFIED_RECORDS`, not as evidence present.

## Acceptance criteria

- [ ] Navigation link opens UX-24 through the existing workspace router.
- [ ] Agent list and immutable version selection use Core data only.
- [ ] Assessment requests are bound to the selected Agent ID and version.
- [ ] Each panel distinguishes returned data from unavailable data.
- [ ] Policy rules/conflicts are rendered only from Core responses.
- [ ] Tool grants are explicitly labelled as declarations, not authorization.
- [ ] Approval and audit data are read-only.
- [ ] Keyboard-operable tabs and responsive layouts work.
- [ ] No MCP endpoint is called and no execution path is introduced.
- [ ] Focused tests, inline JavaScript syntax check, full regression suite, browser acceptance and Colab validation pass on the exact implementation head.

## Validation record

Initial frontend implementation commit: `99d060633de7de249c98f19e792c9e77c9589034`. Current implementation and validation state are tracked by the head commit and checks on [PR #88](https://github.com/msellamiTN/taas-provenance-discovery/pull/88).

Current automated validation was run on commit `1e69553aff3614d1aa934ca1f67927caf68c8170`: GitHub Actions run `42455120612` completed successfully with 666 tests passed and one existing Starlette/httpx deprecation warning. The inline Studio JavaScript syntax gate, benchmark hypergraph build and artifact upload also passed. Browser/keyboard acceptance and live Colab validation remain pending; this draft PR has not been merged or deployed.
