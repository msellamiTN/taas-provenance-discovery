# Statement of Work (SOW)
## TaaS Studio — Provenance-Aware Agent & Tool Governance Platform
## Centralized MCP Gateway, Bearer-Token Broker and Automated Agent/Tool Exposure

| Document control | Value |
|---|---|
| Document ID | TAAS-ENT-SOW-001 |
| Version | 0.2 — Restructured to professional template |
| Date | November 2025 |
| Status | Draft — open for review; open questions and acceptance gates flagged per section |
| Related documents | `LAD.md`, `PAD.md`, `SAW.md`, `TAAS_PLATFORM_MEGAPLAN.md`, `REQUIREMENTS_GAP.md` |
| Template baseline | `docs/examples/01-SoW-MCP-Agent-Gateway.md` (professional SoW structure) |
| Physical reference | `docs/archi/apigeeArea.png` — real-project connectivity pattern |

> **Reading note.** This SOW describes the target capability and delivery intent for TaaS Studio. Where a capability is not yet implemented, the text marks it as a design commitment or open item — it is not a claim that the capability exists today. Current delivered scope is recorded in `REQUIREMENTS_GAP.md`.

## 1. Executive summary

TaaS Studio is a provenance-aware **control plane for governing AI agents and their tools**. The platform exists because agentic systems fail in ways that traditional API governance does not catch: a tool that can be listed can be invoked; a manifest that is published is not a runtime guarantee; a token that is valid at the consumer is not valid downstream. The platform's governing invariant is:

> **Proposal ≠ Evidence ≠ Authorization ≠ Execution.**

This statement of work covers the delivery of an enterprise-ready platform in which:

- All MCP server access is **centralized behind an API gateway + MCP proxy**; consumers never reach MCP servers directly.
- A **bearer-token broker** — Microsoft Entra ID or an equivalent identity provider (Keycloak, cloud-native IAM federation) — issues short-lived, scope-bound tokens and performs token exchange or workload-identity delegation downstream.
- The gateway is realized **per environment with the adapted technology**: Kubernetes Gateway API for private cloud/on-premises, and provider-native managed services on AWS, GCP and Azure.
- Agent and tool exposure follows a governed lifecycle — `REGISTERED → VALIDATED → READY FOR CONSUMPTION → PUBLISHED → REVOKED/DECOMMISSIONED` — with smoke tests required before `READY` and no silent publication.
- Provisioning is industrialized through automated workflows (Backstage/Camunda-style orchestration as a design seam) with idempotency, correlation, rollback and drift reconciliation.

The currently delivered build is a **single-operator inspection and assurance control plane**: provenance registry, read-only MCP discovery (`tools/list`, never `tools/call`), goal/goal-spec authoring with Pydantic validation, tamper-evident hash-chained audit, evidence bundles, token-scoped API with named key profiles, and a lifecycle UI (DEFINE → BUILD → DISCOVER → VERIFY → OPERATE → EVALUATE & MANAGE).

## 2. Business outcomes

| # | Outcome | How the platform delivers |
|---|---|---|
| O1 | Agents and tools are discoverable and governable as first-class assets | Central registry with lifecycle states, endpoint references, policy profiles and health status |
| O2 | No uncontrolled tool invocation | MCP access only through the gateway/proxy; the control plane itself never executes `tools/call`; future execution is PEP-gated with one-time approvals |
| O3 | Identity is correct end-to-end | Five identity domains kept distinct (consumer, end-user, gateway workload, agent runtime, backend); token exchange/delegation instead of token passthrough — no confused-deputy |
| O4 | Deployment is portable across environments | Same logical gateway contract realized via Kubernetes Gateway API on private cloud and provider-native gateways on AWS/GCP/Azure |
| O5 | Evidence is auditable, not asserted | Tamper-evident audit chain, signed evidence bundles, `UNAVAILABLE` over fabricated data; hash-chain proves tamper evidence, never truth |
| O6 | Onboarding is industrialized | Automated provisioning pipelines with idempotency keys, bounded retries, timeouts, compensation and drift reconciliation |
| O7 | Compliance is designed-in | NIST AI RMF, ISO/IEC 42001 and ISO 27001 mappings maintained from phase A (see `TAAS_PLATFORM_MEGAPLAN.md` §Compliance mapping) |

## 3. Scope

### 3.1 In scope

- Provenance registry for agents, skills/tools, MCP servers, workspaces and runs — with lifecycle states and endpoint references.
- Centralized **MCP gateway + proxy** as the sole ingress for applications, frontends, agents and M2M consumers.
- **Bearer-token broker** integrating Entra ID or an equivalent IdP; token validation, scope/role checks, token exchange and workload-identity delegation.
- Policy-driven tool exposure: only approved tools per consumer/policy profile are listed and (in the governed phase) callable.
- **REST→MCP onboarding**: enterprise REST APIs (e.g. JDE/WSO2-style backends) surfaced as MCP tools through a controlled gateway adapter.
- Private connectivity patterns: inbound/outbound private endpoints, service attachments / PrivateLink / Private Link equivalents, private DNS zones, LB-fronted backends.
- Controlled public egress for SaaS MCP providers (Snowflake-, Atlassian-, ServiceNow-class) via corporate egress such as Zscaler.
- On-premises backend reachability via SD-WAN/firewall routes through the same governed path.
- Gateway policy set: TLS termination/re-encryption, OIDC/JWT validation, rate limits/quotas, threat protection, request-size limits (parity with the delivered 2 MiB API cap), request-ID/correlation propagation, audit/SIEM export, secret-free logging.
- Observability: structured logs, metrics, traces, gateway decision logs, backend latency/error categories, request-ID ↔ audit-sequence correlation.
- Environment strategy: DEV / TEST / PREPROD / PROD / private-on-prem, with environment differences as configuration overlays.
- IaC-first provisioning (Terraform module layout in `PAD.md`), CI/CD promotion, drift reconciliation.

### 3.2 Out of scope (current and stated non-goals)

- **MCP `tools/call` execution by the control plane** — deferred to the Phase C governed-execution design (`docs/studio/GOVERNED_EXECUTION_GATEWAY_PHASE1.md`, `docs/studio/ISOLATED_PEP.md`). Discovery remains `tools/list` inspection only.
- General-purpose API management replacing an existing enterprise gateway estate — TaaS integrates with the gateway layer, it does not displace it.
- LLM quality/safety evaluation of tool outputs — the platform is a control plane, not an evaluator.
- Multi-tenant SaaS operation — single-operator provenance model today; tenant isolation is a Phase B requirement.
- Building client business applications that consume the tools.

## 4. Target capability and delivery principles

### 4.1 Target capability (TO-BE)

```text
Consumers / agents / applications / M2M
                  |
                  v
   IdP / Entra ID / equivalent  --->  Bearer-token broker
                  |                    (validate, exchange, delegate)
                  v
      API Gateway + MCP proxy  ----->  TaaS registry (catalogue, lifecycle,
         (per-environment              policy profiles, health)
          implementation)
        |             |              |
        v             v              v
   Private MCP   REST→MCP       Public SaaS MCP
   services      adapters       (controlled egress)
        |
        v
Private endpoints / LB / PSC-PrivateLink / SD-WAN / firewall
```

### 4.2 Delivery principles and commitments

| ID | Commitment |
|---|---|
| C1 | **Boundary-first** — every feature ships with its provenance class declared; nothing silently crosses proposal→evidence→authorization→execution |
| C2 | **Centralization** — all MCP access flows through the gateway/proxy; direct consumer→MCP connections are a defect, not a shortcut |
| C3 | **Honest status** — `delivered`, `design-seam`, `not implemented`, `out-of-scope` labels are auditable against repository evidence (`REQUIREMENTS_GAP.md`) |
| C4 | **Adapted, not identical** — each environment gets its native gateway realization behind one logical contract; private cloud uses Kubernetes Gateway API |
| C5 | **Fail closed** — absent token → 401; absent signing key → 503; unvalidated → not READY; unreachable backend → UNAVAILABLE, never fabricated |
| C6 | **No token passthrough** — the consumer Bearer token is never assumed valid downstream; token exchange or workload identity is mandatory |
| C7 | **Provenance in audit** — caller context, correlation IDs and request-IDs are captured in audit metadata for every governed action |

## 5. Functional work packages and lifecycle states

### 5.1 Lifecycle state model

```text
REGISTERED → VALIDATED → READY FOR CONSUMPTION → PUBLISHED → REVOKED / DECOMMISSIONED
```

- `REGISTERED`: metadata present in the registry; no claim of reachability.
- `VALIDATED`: schema/manifest validation passed (`/goals/validate` pattern); still not consumable.
- `READY FOR CONSUMPTION`: gateway configuration applied **and** health/auth/route smoke tests passed — an agent or MCP exposure must never reach this state on config alone.
- `PUBLISHED`: visible in the approved catalogue view for authorized consumers.
- `REVOKED`/`DECOMMISSIONED`: removed from exposure; revocation is recorded, not deleted.

These are configuration/catalogue states — they are never presented as runtime states.

### 5.2 Work packages

| WP | Package | Contents | Status |
|---|---|---|---|
| WP1 | Registry & provenance core | Agents, skills, MCP servers, workspaces, runs; audit chain; evidence bundles | Delivered (control-plane scope) |
| WP2 | Inspection & discovery | `tools/list` inspection, registry snapshot diffs, recorded activity, `UNAVAILABLE` semantics | Delivered |
| WP3 | Governance surface | Goal/GoalSpec authoring + validation, assurance evidence, agent lifecycle (draft→published) | Delivered |
| WP4 | Centralized MCP gateway + proxy | Sole MCP ingress; filtered `tools/list`; gated `tools/call` (Phase C); REST→MCP adapter | Design — not implemented |
| WP5 | Bearer-token broker | IdP integration (Entra ID / equivalent), token exchange, workload-identity delegation, JWKS validation | Design — not implemented |
| WP6 | Per-environment gateway realization | K8s Gateway API (private/on-prem); ApigeeX/Hybrid+PSC (GCP); API GW/ALB+PrivateLink (AWS); APIM/AppGW+Private Link (Azure) | Design — not implemented |
| WP7 | Provisioning industrialization | Backstage/Camunda-style orchestration, idempotency, compensation, drift reconciliation | Design seam |
| WP8 | Enterprise identity & tenancy | OIDC/SSO, RBAC, tenant isolation | Design seam — not implemented |
| WP9 | Governed execution (Phase C) | PEP, isolated workers, one-time approvals, fresh evidence checks | Design — not implemented |

## 6. Delivery approach

1. **Phase A (delivered)** — single-operator inspection/assurance control plane; boundary semantics proven; SQLite stores; token + named-key auth.
2. **Phase B — enterprise platform** — IdP token broker, OIDC/RBAC, tenant isolation, gateway realization per environment, Terraform modules, K8s (GPU-aware) deployment, PostgreSQL-class store.
3. **Phase C — governed execution** — PEP + isolated workers; `tools/call` only through the governed path; one-time approvals bound to fresh evidence.
4. **Phase D — platform integrations** — AI-platform adapters (Mistral, Foundry, Vertex AI/Model Garden, Bedrock, Ollama/vLLM), private connectivity to SaaS providers, air-gap variant.
5. **Phase E — certification readiness** — NIST AI RMF / ISO 42001 / ISO 27001 evidence packages.

Each phase ships only what its evidence supports; phases do not borrow capability claims from later phases.

## 7. Deliverables

| # | Deliverable | Acceptance evidence |
|---|---|---|
| DL-01 | Enterprise document set (this SOW, LAD, PAD, SAW, megaplan, gap analysis) | Documents committed under `docs/enterprise/`; cross-references resolve |
| DL-02 | Control-plane implementation (delivered) | `src/taas/studio/` + test suite green |
| DL-03 | Reviewer package | Colab notebook, walkthrough video, reviewer guide |
| DL-04 | LAD/PAD alignment to template | Section structure parity with `docs/examples/`; no unvalidated claims |
| DL-05 | Gateway strategy decision record | D3 in `LAD.md`; per-environment baseline in `PAD.md` |
| DL-06 | Requirements/gap register | `REQUIREMENTS_GAP.md` — every requirement traced to evidence or labelled |

## 8. Roles and responsibilities

| Role | Responsibility |
|---|---|
| Platform architect | Owns SAW/LAD/PAD coherence; decision records; boundary charter |
| Control-plane engineering | Registry, API, UI, assurance features, tests |
| Gateway/network engineering | Per-environment gateway realization, private connectivity, DNS, firewall |
| Identity engineering | IdP integration, token broker, exchange/delegation flows |
| Security & compliance | Threat model, policy profiles, NIST/ISO mapping, audit review |
| Operations | Observability, runbooks, DR rehearsal, drift reconciliation |
| Product owner | Lifecycle scope, publication gates, acceptance sign-off |

## 9. Assumptions and dependencies

- An enterprise IdP exists (Entra ID or equivalent); its availability, licensing and federation model are dependencies, not deliverables.
- Network teams own the physical connectivity matrix; `PAD.md` records the connectivity contract, not their firewall syntax.
- The ApigeeX diagram is a **reference pattern** — provider-specific projects/VPCs/PSC constructs map to equivalents, not copies.
- Backstage/Camunda-style orchestration is a design intent; the registry contract does not depend on a specific orchestrator.
- AI platform availability (Mistral/Vertex/Bedrock/Foundry/local) varies per environment and is handled via adapter profiles.

## 10. Acceptance criteria

| AC | Criterion |
|---|---|
| AC-01 | All MCP traffic demonstrably flows through the gateway/proxy; a direct consumer→MCP attempt is denied and logged |
| AC-02 | A consumer token cannot be replayed downstream unchanged — exchange or delegation is enforced (design-gated Phase B test) |
| AC-03 | An agent/tool cannot reach `READY FOR CONSUMPTION` until gateway config + health + auth + route tests pass |
| AC-04 | Private-cloud deployment passes with Kubernetes Gateway API resources only (GatewayClass/Gateway/HTTPRoute); no cloud-specific CRDs required |
| AC-05 | Each cloud deployment uses the provider-adapted gateway; the logical contract (identity, policy, audit, correlation) is identical across all four environments |
| AC-06 | Audit correlation: a governed action's request-ID is traceable end-to-end in audit metadata |
| AC-07 | `tools/call` remains absent from the control-plane API until Phase C evidence exists |
| AC-08 | Documentation honesty: every `delivered` claim in `REQUIREMENTS_GAP.md` resolves to repository evidence |

## 11. Risks

| Risk | Mitigation |
|---|---|
| Confused-deputy via token passthrough | Mandatory exchange/delegation (C6); threat row in LAD §security |
| Over-exposed tools | Per-profile filtered `tools/list`; only approved tools callable in governed phase |
| SSRF via arbitrary MCP targets | FQDN allow-lists, private endpoints, no raw-IP dialing, egress policy |
| Registry outage | Published proxies continue only with valid cached policy; new publications fail closed |
| Version/compatibility drift on managed gateways (e.g. Hybrid MCP enablement) | Version baseline section in PAD; per-cluster consistency checks |
| Scope creep: gateway work conflated with control plane | Separate component boundaries; this SOW keeps them distinct |

## 12. Security and compliance requirements

- TLS for all gateway, registry, management and backend paths; re-encryption where trust domains change.
- OIDC/JWT validation at the gateway: issuer, audience, signature, expiry, scope/role/claim checks.
- Token exchange or dedicated workload identity downstream — never passthrough. Token mechanics: OAuth 2.1, RFC 8693 downscoping per hop, opaque tokens outward, RFC 6750 step-up consent for sensitive operations.
- Fine-grained authorization behind a standardized AuthZEN facade → ABAC/ReBAC engine (OpenFGA/Permit-class), with normalized `403` denials — aligned with the Google Apigee MCP-authorization pattern (see LAD D9/D10 references).
- Rate limits, quotas, threat protection, request-body limit parity (2 MiB), request-ID propagation.
- Audit: tamper-evident chain; SIEM export; no payload logging by default; no secrets in logs/audit.
- Secrets: environment-only bootstrap today; platform secret stores in target deployments (Vault/Key Vault/Secrets Manager/Secret Manager); evidence-signing key persisted and rotatable.
- Egress: explicit MCP/backend allow-lists; SSRF protection; private DNS; corporate egress for public endpoints.
- Compliance mapping maintained in `TAAS_PLATFORM_MEGAPLAN.md` (NIST AI RMF GOVERN/MAP/MEASURE/MANAGE; ISO/IEC 42001; ISO 27001 controls).

## 13. Change control

Changes to the target architecture are recorded as decision updates in `LAD.md` §options/decisions and the ADR table; material scope changes update this SOW's version row. The boundary charter may not be weakened by change control without an explicit, reviewed decision.

## 14. Commercial and contractual placeholders

This document describes technical scope for an internal/pioneer delivery. Commercial terms, SLAs and procurement artefacts are out of scope here and belong to the sponsoring programme.

## 15. Approval

| Role | Name | Status |
|---|---|---|
| Platform architect | — | Drafted |
| Product owner | — | Pending review |
| Security lead | — | Pending review |

## 16. References

- `docs/examples/01-SoW-MCP-Agent-Gateway.md`, `02-LAD-…`, `03-PAD-…` — professional template baseline.
- `docs/archi/apigeeArea.png` — physical connectivity reference pattern.
- Kubernetes Gateway API — https://kubernetes.io/docs/concepts/services-networking/gateway/
- `docs/enterprise/TAAS_PLATFORM_MEGAPLAN.md`, `SAW.md`, `LAD.md`, `PAD.md`, `REQUIREMENTS_GAP.md`
- `docs/studio/LIFECYCLE_API_MEGAPLAN.md` — delivered product/API contract.
- `docs/studio/GOVERNED_EXECUTION_GATEWAY_PHASE1.md`, `ISOLATED_PEP.md`, `POLICY_ENGINE_V1.md` — Phase C design seams.

---

**End of document — TAAS-ENT-SOW-001**
