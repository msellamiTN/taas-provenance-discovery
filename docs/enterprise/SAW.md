# SAW — Software Architecture Whitepaper

TaaS: a provenance-aware control plane that lets an enterprise govern the full
lifecycle of AI agents and their tools. This paper states the problem frame,
trust zones, component responsibilities, and the design principles every
component obeys.

## 1. Problem frame

An enterprise deploying LLM agents over MCP tool fleets faces a governance
vacuum: tools are adopted ad hoc, metadata is self-declared, invocations are
invisible, and compliance asks arrive after the fact. A control plane must
answer four questions with evidence:

1. **Intent** — what was asked (GoalSpec, authored or model-proposed)?
2. **Discovery** — which tools/skills compose a conformant solution?
3. **Assurance** — what verified evidence supports that choice?
4. **Runtime outcome** — what actually happened?

The dangerous failure mode is collapsing these states: treating a proposal as
evidence, inspection as authorization, or an approval as execution. TaaS
therefore makes the separation architectural, not cosmetic:

> **proposal ≠ evidence ≠ authorization ≠ execution**

Critically, the control plane **observes and records; it does not invoke**.
Execution is a separate, opt-in security project with its own enforcement
point — never a side effect of browsing or approving.

## 2. Trust zones

| Zone | Contents | Trust posture |
|---|---|---|
| **T1 — Operator plane** | Studio UI, notebooks, admin consoles | Interactive user; credential entry; no client-supplied authority is ever trusted |
| **T2 — Control-plane API** | FastAPI service: 89 versioned routes, auth middleware, deterministic stores | Authenticated boundary; fails closed; the only writer into T3 |
| **T3 — Persistence** | 7 stores: audit, agents, skills, workspaces, runs, evidence, api_keys | Append-mostly; audit + evidence immutable; only reachable via T2 |
| **T4 — External untrusted** | MCP servers (stdio/HTTP), AI platforms (HF/Ollama today; Mistral/Foundry/Vertex/Bedrock planned), public registries | All metadata **unverified by design**; inspections are observations, never certificates |
| **T5 — Execution (future)** | PEP + isolated workers per `GOVERNED_EXECUTION_GATEWAY_PHASE1.md` / `ISOLATED_PEP.md` | Separate trust domain; re-checks every binding fresh; absent from this build |

Zone crossings are the audit surface: every T1→T2 request is authenticated and
correlated; T2→T4 inspections are read-only and recorded; T5 does not exist
until Phase C.

## 3. Components

| Component | Responsibility | Key property |
|---|---|---|
| **Discovery engine** (`taas.engine`) | Gap analysis → minimal toolkit + certificate | Deterministic; replayed LLM records make runs reproducible |
| **Registry stores** | Versioned agent/skill/tool manifests; lifecycle transitions | Immutable versions; transitions validated; revocation recorded not deleted |
| **Assurance evidence store** | Content-addressed, attested evidence records | HMAC attestation; SQL UPDATE/DELETE-blocked append-only |
| **Policy engine** | Typed verdicts `allow/deny/needs_review` | Diagnostic only — never grants authorization |
| **Approval service** | Human approval records bound to subjects | `authorization_granted: false` markers preserved |
| **Audit ledger** | Tamper-evident event chain | Hash-chained; full-ledger verify; `request_id` correlation |
| **MCP inspector** | `tools/list` against configured servers | Inspection only; snapshots + diffs; `tools/call` absent |
| **Model backends** | Model catalog + runtime sandbox (HF/Ollama) | Metadata unverified; sandbox-scoped chat; no model claims |
| **API-key service** | Named credentials with actor binding | SHA-256 at rest; plaintext shown once; revoke recorded |
| **Execution gateway (design)** | One-time approval tokens, PEP, workers | Seam documented; deliberately no code |

## 4. Design principles

1. **Fail closed.** No credential source → 503; mismatch → 401; missing
   attestation key → 503; unknown effects → rejected, not assumed safe.
2. **Deterministic contracts.** Every response is a versioned `taas.*/v1`
   schema with explicit `record_semantics` and `execution_record` markers.
3. **Semantic markers over claims.** Responses name what a record *is*
   (observation, diagnostic, proposal) rather than implying what it proves.
4. **Immutable records.** Versions, evidence, approvals, audit events are
   append-only; revocation is a recorded state, never deletion.
5. **Inspection ≠ invocation.** Reading a registry or listing tools changes
   nothing and grants nothing.
6. **Everything auditable.** Every mutation emits a ledger event carrying
   actor and request-id; verification is full-ledger, not sampled.
7. **Honest absence.** Unsupported data renders `UNAVAILABLE` with a reason —
   never synthesized, never hidden.
