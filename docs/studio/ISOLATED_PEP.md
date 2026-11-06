# Isolated Policy Enforcement Point — design seam

Status: **design document only** — no enforcement code ships in this build.
Purpose: mark the boundary where a future governed-execution increment inserts
a policy enforcement point (PEP) between today's analysis surfaces and real
tool invocation.

## The seam

```
Analysis (today)                    Enforcement (future)
────────────────                    ────────────────────
Studio API            ──request──▶  Isolated worker / PEP
  discovery engine                     evaluates decision *fresh*,
  policy engine (decisions)            never trusting caller state
  eligibility explanations             │
  assurance evidence                   ├─ allow → invoke MCP tool
                                       └─ deny  → structured denial
```

## Principles

1. **Decision ≠ enforcement.** Policy Engine v1 produces typed verdicts
   (`/api/v1/policy/evaluate`, Agent `policy-verdict`). A PEP *consumes* a
   decision but re-verifies every input itself — request fingerprint, subject
   binding, evidence freshness, approval records — at enforcement time.
   A caller-supplied verdict is never trusted.
2. **Fail closed.** Any missing input (evidence store, approval record,
   registry snapshot, ledger) = deny. Errors are denials, not bypasses.
3. **Five-concept isolation at the boundary.** The PEP checks *authorization*
   only: relevance (retrieval), capability (contracts), evidence trust
   (assurance), eligibility (policy) each stay in their own record and may be
   *inputs* to a decision — never substitutes for it.
4. **Audit first.** Every enforcement decision — allow or deny — appends to
   the hash-chained audit ledger (`taas.studio.audit_ledger`) before the
   action proceeds. Denials are as auditable as allows.
5. **No ambient authority.** The worker receives exactly the approved tool
   set, the bound digests, and fresh credentials scope — not Studio process
   state, not registry write access, not the model runtime.

## What the PEP consumes (all exist today)

| Input | Source |
|---|---|
| Typed policy verdict | `taas.studio.policy_engine` / `POST /api/v1/policy/evaluate` |
| Verified approvals | `assurance_evidence.list_verified_evidence_for_subject` (freshness-checked) |
| Tool identity + hash | `tool_registry.resolve_registry_tool` (`definition_hash_verified`) |
| Eligibility detail | `tool_service.eligibility_explain` |
| Run provenance | `discovery_runs.get_discovery_run` (record of the analysis that produced the selection) |
| Event sink | `audit_ledger.append_event` |

## Explicitly out of scope here

MCP invocation, sandboxing mechanics, credential issuance, streaming
execution traces, multi-user isolation. This document only fixes where those
attach — so the future increment cannot smuggle enforcement semantics into
the analysis layer.
