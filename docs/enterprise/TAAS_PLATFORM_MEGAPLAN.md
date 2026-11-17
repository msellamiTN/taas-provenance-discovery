# TaaS Platform Megaplan — Enterprise Layer

**Governing document** for the TaaS Intelligence Platform. Scope: platform-level
requirements, boundaries, compliance mapping, and phased roadmap. Implementation
detail lives in `docs/studio/LIFECYCLE_API_MEGAPLAN.md`; verified features in
`docs/studio/FEATURE_CATALOG.md`; requirement evidence in
`docs/enterprise/REQUIREMENTS_GAP.md`.

Status vocabulary: `delivered` · `design-seam` · `not implemented` · `out-of-scope`.

## 1. Vision & positioning

TaaS is a **provenance-aware control plane for governing AI agents and their
tools** — a Tools-as-a-Service Intelligence Platform for pioneers: platform
teams, AI governance offices, and regulated enterprises that must answer, with
evidence, *"which agent may use which tools, why, and who approved it"*.

The platform is organized around the agent/tool lifecycle
(DEFINE → BUILD → DISCOVER → VERIFY → OPERATE → EVALUATE & MANAGE) and a
four-state discipline: **intent → discovery → assurance → runtime outcome**.
The architectural spine is the invariant:

> **proposal ≠ evidence ≠ authorization ≠ execution**

No surface may imply a state it does not hold. A model proposal is not
evidence; inspection metadata is not a certificate; an approval is not
authorization; authorization is not execution; a valid audit chain is not
proof of truth. These refusals are *features* (§5).

Target deployments: public cloud (AWS/GCP/Azure), private cloud, and
air-gapped/on-premise environments, on CPU or GPU runtimes, integrated with
external AI platforms (Mistral AI La Plateforme, Azure AI Foundry, GCP Vertex
AI, AWS Bedrock) and local stacks (Ollama, vLLM).

## 2. Challenging issues → platform responses

| Pioneer challenge | Why it bites | Platform response | Status |
|---|---|---|---|
| **Shadow AI / ungoverned tool adoption** | Agents pick up MCP servers ad hoc; nobody knows the fleet | Operator-managed MCP registry; read-only `tools/list` inspection; retained snapshots + snapshot diffs | delivered |
| **Prompt injection / unsafe execution** | A tool call under injection is the incident | Control plane never executes: no `tools/call` surface; governed-execution gateway designed (one-time approval tokens bound to actor/tool/args/policy/evidence); isolated PEP seam | design-seam (execution) / delivered (refusal) |
| **Metadata forgery / trust decay** | MCP annotations are self-declared and forgeable | Attested assurance evidence (HMAC, content-addressed, immutable); skill/agent version signatures; revocation recorded, never deleted | delivered |
| **Audit & compliance burden** | Regulators ask "who authorized what, when" | Tamper-evident hash-chained audit ledger; actor-bound writes; request-id ↔ audit-seq correlation; subject-scoped queries | delivered |
| **Vendor lock-in / environment diversity** | CPU dev laptop ↔ GPU cluster ↔ air gap | Cloud-neutral packaging; single-process SQLite → Postgres adapter → K8s; pluggable model backends (Ollama shipped; Mistral/Foundry/Vertex/Bedrock adapters = Phase D) | partially delivered |
| **Scale-out & multi-tenancy** | Single token + SQLite cannot serve an org | Stateless API design; named API keys; keyset pagination; tenant isolation + OIDC/RBAC named as Phase B workstreams | partially delivered |

## 3. Functional requirements `FR-*`

Every requirement must preserve the boundary invariant. Full evidence: `REQUIREMENTS_GAP.md`.

### FR-LC — Lifecycle control plane

| ID | Requirement | Status |
|---|---|---|
| FR-LC-1 | GoalSpec authoring, validation, templates, vocabulary (DEFINE) | delivered |
| FR-LC-2 | Agent + Skill versioned registries: validate → publish → sign → revoke, diffs, events (BUILD) | delivered |
| FR-LC-3 | Tool discovery engine, certificate, persisted runs + diffs, MCP inspection (DISCOVER) | delivered |
| FR-LC-4 | Policy verdicts, release readiness, approvals, evidence freshness (VERIFY) | delivered |
| FR-LC-5 | Audit ledger + chain verify, runtime diagnostics, notifications, platform overview (OPERATE) | delivered |
| FR-LC-6 | Benchmark datasets, workspace drafts/revisions, overview KPIs (EVALUATE & MANAGE) | delivered |

### FR-GOV — Governance

| ID | Requirement | Status |
|---|---|---|
| FR-GOV-1 | Fail-closed authentication (503 unset, 401 mismatch) | delivered |
| FR-GOV-2 | Named API keys: hashed at rest, per-key actor binding, recorded revocation | delivered |
| FR-GOV-3 | OIDC/SSO interactive login | not implemented (Phase B) |
| FR-GOV-3b | Token broker — short-lived Bearer tokens for all MCP access, Entra ID or equivalent IdP, JWKS-validated at proxy edge | not implemented (Phase B) — SoW commitments C2/C6; extension seam `MCP_GATEWAY_EXTENSION.md` E6 |
| FR-GOV-4 | RBAC roles (viewer/operator/approver/admin) | not implemented (Phase B) |
| FR-GOV-5 | Org-scoped policies + multi-party approval workflows | not implemented (Phase B/E) |
| FR-GOV-6 | Tenant isolation | not implemented — separate security project |

### FR-EXEC — Governed execution

| ID | Requirement | Status |
|---|---|---|
| FR-EXEC-1 | PEP evaluating decisions fresh, never trusting caller state | design-seam (`ISOLATED_PEP.md`) |
| FR-EXEC-2 | Short-lived one-time approval tokens bound to actor, server, tool, exact args, GoalSpec, policy fingerprint, tool-def hash, evidence hash; replay/expiry fails closed | design-seam (`GOVERNED_EXECUTION_GATEWAY_PHASE1.md`) |
| FR-EXEC-3 | Isolated workers executing governed `tools/call` | not implemented — separate security project |
| FR-EXEC-4 | `tools/call` in the control plane | **refused by design** (boundary charter) |

### FR-INT — AI-platform & runtime integrations

| ID | Requirement | Status |
|---|---|---|
| FR-INT-1 | Model backends abstraction (HF/local, Ollama) | delivered |
| FR-INT-2 | Runtime GPU/CPU profiling (`/runtime/hardware`) with honest `unavailable` | delivered |
| FR-INT-3 | Mistral AI La Plateforme adapter | not implemented (Phase D) |
| FR-INT-4 | Azure AI Foundry adapter | not implemented (Phase D) |
| FR-INT-5 | GCP Vertex AI adapter | not implemented (Phase D) |
| FR-INT-6 | AWS Bedrock adapter | not implemented (Phase D) |
| FR-INT-7 | vLLM private inference adapter | not implemented (Phase D) |
| FR-INT-8 | REST→MCP onboarding — enterprise REST APIs (JDE/WSO2-class) surfaced as governed MCP tools via gateway adapter (LAD D6) | not implemented (Phase B) |

### FR-DEP — Deployment & provisioning

| ID | Requirement | Status |
|---|---|---|
| FR-DEP-1 | Container image, env-only config, no secrets in image | written, build unverified (Docker daemon) |
| FR-DEP-2 | Helm/K8s GPU chart | not implemented (Phase B) |
| FR-DEP-3 | Terraform modules: AWS/GCP/Azure/private | not implemented (Phase B) |
| FR-DEP-4 | API gateway route policy (auth, rate limit, size cap) | not implemented (Phase B) |
| FR-DEP-5 | Egress proxy policy for MCP servers + AI platforms | not implemented (Phase B) |
| FR-DEP-5b | Centralized MCP gateway/proxy — all MCP access transits the proxy (inspection today, governed execution Phase C) | not implemented (Phase B) — SoW commitment C2, LAD D1/D5 |
| FR-DEP-5c | Per-environment gateway realization — **private/on-prem via Kubernetes Gateway API** (GatewayClass + Gateway + HTTPRoute); GCP ApigeeX/Hybrid + PSC; AWS API GW/ALB + PrivateLink; Azure APIM/AppGW + Private Link. One logical contract (LAD D3, PAD §7) | not implemented (Phase B) |
| FR-DEP-5d | Private connectivity to backends & AI platforms — PSC / PrivateLink / Private Link endpoints + service attachments + private DNS; no raw-IP dialing (PAD §5.3) | not implemented (Phase B) |
| FR-DEP-6 | Air-gapped on-prem bundle (offline pip, seed registries) | not implemented (Phase D) |

### FR-OBS — Observability

| ID | Requirement | Status |
|---|---|---|
| FR-OBS-1 | Structured JSON request logs; no headers/bodies | delivered |
| FR-OBS-2 | Request-id ↔ audit-seq correlation | delivered |
| FR-OBS-3 | `/health` + `/ready` | delivered |
| FR-OBS-4 | OpenTelemetry traces + metrics endpoint | not implemented (Phase B) |
| FR-OBS-5 | Audit → SIEM export | not implemented (Phase B) |

### FR-SEC — Security

| ID | Requirement | Status |
|---|---|---|
| FR-SEC-1 | Security headers (`nosniff`, frame `DENY`, `no-referrer`), 2 MiB body cap | delivered |
| FR-SEC-2 | Parameterized stores; bounded fields; constrained IDs | delivered |
| FR-SEC-3 | Secrets from platform secret store (KMS/Vault/Key Vault) | not implemented (Phase B) |
| FR-SEC-4 | mTLS service mesh | not implemented (Phase C) |
| FR-SEC-5 | SBOM + signed images (SLSA attestation) | not implemented (Phase B) |

### FR-DR — Resilience

| ID | Requirement | Status |
|---|---|---|
| FR-DR-1 | Online backup + restore rehearsal (7 stores, integrity verified) | delivered |
| FR-DR-2 | Documented RPO/RTO + rollback | delivered (runbook) |
| FR-DR-3 | HA topology (replicas + shared store) | design only (Phase B) |

## 4. Non-functional requirements `NFR-*`

Targets, not achieved metrics. Verification lives in `REQUIREMENTS_GAP.md`.

| ID | Requirement | Target / boundary |
|---|---|---|
| NFR-SEC-1 | Authentication fail-closed | no credential → 503; mismatch → 401; revoked → 401 (verified) |
| NFR-SEC-2 | Transport security | TLS terminated at gateway; same-origin-only API (no CORS by design) |
| NFR-SEC-3 | Secrets hygiene | secrets via env/secret store only; never logged, never in audit payloads, never committed |
| NFR-SEC-4 | At-rest protection | attestation key + API-key hashes (SHA-256) delivered; store encryption delegated to platform volume encryption |
| NFR-SCL-1 | Stateless API | all state in stores; replicas share nothing in-process (gateway-ready) |
| NFR-SCL-2 | Bounded reads | keyset pagination (`after_seq`), capped limits, bounded Pydantic fields |
| NFR-SCL-3 | Store-backend portability | SQLite contract-compatible with a Postgres adapter; swap must not change API contracts |
| NFR-PRT-1 | Deployment neutrality | identical `taas.*/v1` contracts across Colab, VM, K8s, air-gap |
| NFR-PRT-2 | Runtime parity | CPU/GPU — GPU profile informational, never a claimed capability |
| NFR-AUD-1 | Ledger integrity | append-only hash chain; verify scans full ledger; tamper evidence ≠ truth evidence |
| NFR-AUD-2 | Correlation | every mutation carries actor + `payload.request_id` |
| NFR-CMP-1 | Compliance mapping | NIST AI RMF GOVERN/MAP/MEASURE/MANAGE → TaaS artifacts (§6) |
| NFR-PERF-1 | Bounded latency | inspection timeouts enforced; p95 read < 2 s on preprod stores (target) |
| NFR-PERF-2 | Bounded payloads | 2 MiB request cap → 413 |
| NFR-OPS-1 | Operability | `/health`,`/ready`; runbook; backup/rollback procedures; structured logs |

## 5. Boundary charter — refusals as features

| Refused surface | Why | Unblocked by |
|---|---|---|
| `tools/call` / governed execution in control plane | Execution under injection is the #1 incident; control plane observes, it does not act | FR-EXEC security project (PEP + isolated workers) |
| Evaluator (`/api/v1/eval/*`) | Gold labels must stay isolated from discovery/analyst paths | Evaluator security project |
| Tenant isolation / production multi-user auth | Single-tenant preprod; tenancy changes every trust boundary | Phase B (OIDC/RBAC/tenancy workstream) |
| Fabricated live data | `UNAVAILABLE` is a truthful state; synthesis destroys audit value | — (never unblocked) |
| Browser-supplied MCP commands / policies | Client-supplied authority is unverifiable | — (never unblocked) |

## 6. Compliance mapping

| NIST AI RMF function | ISO/IEC 42001 (AIMS) | ISO 27001 Annex-A (ref) | TaaS artifact | Maturity |
|---|---|---|---|---|
| GOVERN (accountability, roles) | A.2/A.3 roles & responsibilities | 5.2, 5.3 | Lane charter (megaplan §0), actor-bound writes, approvals | delivered (process) / planned (org) |
| GOVERN (policies) | A.4 AI policy | 5.1 | Policy engine verdicts, org policies | partial (verdicts delivered, org policy = Phase B) |
| MAP (context, risk identification) | A.5 impact assessment | 5.7, 8.2 | GoalSpec + objective traceability; threat table §2 | delivered |
| MEASURE (analysis, tracking) | A.6 lifecycle mgmt | 8.15, 8.16 | Discovery runs, evidence freshness, release-readiness, audit metrics | delivered |
| MEASURE (evidence) | A.7 verification & validation | 8.29, 8.32 | Attested assurance evidence (HMAC, content-addressed) | delivered |
| MANAGE (risk response) | A.8 risk treatment | 5.24, 5.28 | Approvals, revocation, verdict history | delivered |
| MANAGE (incident & continuity) | A.9 incident mgmt | 5.26, 5.30 | Audit ledger, backup/restore rehearsal, runbook | delivered (single-instance) |
| GOVERN (supply chain) | A.10 third-party | 5.19–5.22 | Skill/agent signatures, revocation, MCP snapshot diffs | delivered |
| MANAGE (secure dev) | — | 8.25–8.31 | Versioned contracts `taas.*/v1`, semantic markers, regression suite | delivered |
| — (identity) | — | 5.16–5.18 | Named API keys (hashed, actor-bound); OIDC/RBAC | partial (Phase B) |

## 7. Phased roadmap

| Phase | Scope | Exit criteria |
|---|---|---|
| **A — Control plane (done)** | Lifecycle API, Studio UI, preprod hardening (S1–S5/O1), E1–E3, reviewer package | All §7.4 gates green except S2 build-verify |
| **B — Enterprise platform** | OIDC/SSO + RBAC, Postgres adapter, Terraform modules, K8s (incl. GPU nodes) + Helm, API gateway policy, **centralized MCP proxy + token broker (Entra ID/equiv.)**, egress proxy, secret-store integration, OTel + SIEM export, SBOM/SLSA pipeline | Deploy from Terraform to ≥2 clouds; SSO + roles enforced; MCP traffic proxied + brokered; metrics/traces flow; image signed |
| **C — Governed execution pilot** | PEP + isolated workers per `GOVERNED_EXECUTION_GATEWAY_PHASE1.md` + `ISOLATED_PEP.md`; opt-in only; mTLS; still no `tools/call` outside the gated path | One governed invocation end-to-end in staging, all bindings re-checked, audit-complete |
| **D — AI-platform & air-gap** | Provider adapters (Mistral, Foundry, Vertex, Bedrock, vLLM); offline install bundle; seed-registry import | Adapter contract tests per provider; air-gap install from bundle |
| **E — Certification readiness** | NIST AI RMF profile, ISO 42001 AIMS evidence pack, tenancy, org policies, multi-party approvals | External audit walk-through; compliance matrix §6 all `delivered` |

Each phase keeps the boundary charter intact: execution enters only via Phase
C's gated, opt-in path; tenancy only via Phase B/E security workstreams;
`UNAVAILABLE` is never replaced by synthesized data.
