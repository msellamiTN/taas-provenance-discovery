# UX-F02 — Discovery History & Audit Integrity

## Purpose
Expose Core-owned persisted discovery observations and hash-chained audit records in Studio as read-only operational workspaces.

## Core contracts consumed
- `GET /api/v1/discovery/runs?limit=50`
- `GET /api/v1/discovery/runs/{run_id}`
- `GET /api/v1/audit/events?limit=100`
- `GET /api/v1/audit/verify`

## Behavior
- Lists Core-returned discovery run records and supports inspection by exact run ID.
- Lists audit events and exposes the full event record for inspection.
- Displays `chain_valid` and `first_divergence` exactly as reported by Core.
- Handles empty or missing collection fields without fabricating records.
- Uses text rendering for untrusted record fields.
- Uses the existing authenticated `apiGet` helper and does not store the bearer token.

## Safety semantics
Discovery history represents pre-execution analysis observations. Audit hash-chain validity is not proof that an event claim is true or that a tool was invoked. The UI does not call execution endpoints and does not change authorization or approval state.

## Acceptance
Run:
```bash
python -m pytest -q tests/test_studio_observability_workspace.py
```

The static tests verify navigation, endpoint wiring, response-field handling, safe rendering, and execution-boundary copy. Live endpoint and browser acceptance must still be performed against the authenticated Studio runtime.
