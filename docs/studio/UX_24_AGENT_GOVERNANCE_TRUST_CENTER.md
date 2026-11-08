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
- [ ] Focused tests, full regression suite, browser acceptance and Colab validation pass on the exact implementation head.

## Validation record

Implementation commit: `99d060633de7de249c98f19e792c9e77c9589034`.

The commit records frontend implementation only. Automated CI, full regression, browser interaction and live Colab acceptance are not yet claimed.
