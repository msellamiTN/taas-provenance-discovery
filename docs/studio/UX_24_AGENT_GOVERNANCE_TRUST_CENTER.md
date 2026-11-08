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

The audit verifier recomputes the hash chain over the entire recorded ledger in bounded batches (`audit_ledger.verify_chain`, `scan_scope: full_ledger`). UX-24 therefore labels a successful result `FULL_CHAIN_VALID`. Audit-event listing remains keyset-paginated at 1,000 events per page via `after_seq`; verification itself is a whole-ledger guarantee. This is tamper evidence over recorded events — never proof of execution.

On each assessment, UX-24 clears prior subject data before requesting the newly selected immutable version and temporarily locks the selectors to prevent late responses from being attributed to a different selection. An empty evidence summary is rendered as `NO_VERIFIED_RECORDS`, not as evidence present.


## Browser and Colab acceptance harness

A real-browser acceptance harness is now included:

- Test file: `tests/test_studio_browser_e2e.py`.
- Existing Hypergraph Explorer browser journey remains covered.
- UX-24 browser journey covers navigation, all five tabs, ArrowRight/Home/End keyboard operation, authenticated Agent/version retrieval, read-only assessment when an immutable version exists, and the no-Agent empty state.
- UX-24 browser assertions reject non-GET API requests and MCP requests from the UX-24 workflow.
- Desktop (1440px) and mobile (390px) screenshots are exported under `TAAS_E2E_ARTIFACT_DIR`.
- The Colab launcher pins code/test revision `c799e657b5620f1a3fa3fd35c94cff928bb01dc5`; the browser notebook reuses that running process, token and proxy.

GitHub Actions run [#42457100242](https://github.com/msellamiTN/taas-provenance-discovery/actions/runs/42457100242) on the follow-up branch head completed successfully: **666 passed, 4 skipped, 1 existing warning**. The four browser cases are skipped in ordinary CI because no live Colab URL/token is configured; the notebook runs them against the real Colab process.

**Still pending:** execute the updated Colab launcher and browser notebook, inspect the four desktop/mobile screenshots, and record the exact runtime commit and test output. Automated CI success is not Colab acceptance.

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
