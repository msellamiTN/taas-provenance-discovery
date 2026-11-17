# Statement of Work (SoW)
## Enterprise Agent Gateway, MCP Gateway and Automated Agent Exposure

| Document control | Value |
|---|---|
| Document ID | D2AI-CEVA-AGW-SOW-001 |
| Version | 0.1 — Draft for review |
| Date | 17 November 2026 |
| Status | Draft; scope and architecture decisions require client approval |
| Related documents | `02-LAD-MCP-Agent-Gateway.md`, `03-PAD-MCP-Agent-Gateway.md` |
| Client context | CMA / CEVA enterprise environment (legal entity and tenant ownership to be confirmed) |
| Architecture baseline | Apigee Hybrid + enterprise Agent Registry + Backstage/Camunda provisioning integration (proposed baseline) |

> **Document purpose.** This SoW defines the proposed scope, deliverables, responsibilities, acceptance conditions, assumptions and delivery approach for an enterprise gateway that governs how applications, users and other agents consume deployed agents, MCP tools and selected LLM endpoints. It is based on the supplied project brief and architecture screenshots. It is not a signed commercial commitment until the open decisions, estimates, service levels and acceptance authorities are approved.

---

## 1. Executive summary

The organisation is provisioning AI agents through an existing Release 1 (R1) workflow. The next release (R2) must close the lifecycle loop: every successfully provisioned agent is automatically registered in an enterprise Agent Registry and exposed through a governed gateway, with no separate manual publication step.

The gateway provides a controlled entry point for three consumer classes:

1. Business applications and machine-to-machine integrations (M2M).
2. End-user applications and frontends acting on behalf of authenticated users.
3. Other agents communicating with agents (A2A).

A related MCP consumption plane exposes approved enterprise APIs, non-API systems and external/SaaS MCP servers as governed tools. The scope also includes a model/LLM access path covering the identified Mistral and Vertex AI backends, subject to confirmation of the exact model-routing requirement.

The proposed implementation baseline is **Apigee Hybrid for runtime API exposure and enforcement, complemented by a custom enterprise Agent Registry and provisioning automation**. This fits the stated non-GCP/Mistral use case and avoids making Gemini Enterprise Agent Platform a mandatory dependency. Gemini Enterprise Agent Platform remains an option for a later, broader agent-mesh capability assessment.

The gateway is not assumed to provide a full agent orchestration mesh. Basic A2A exposure, authentication, policy enforcement, routing and audit are in scope; mesh-wide orchestration, advanced agent discovery, delegation planning and policy federation are separate capabilities unless explicitly approved.

## 2. Business outcomes and objectives

| ID | Objective | Expected outcome |
|---|---|---|
| OBJ-01 | Govern agent exposure | Every in-scope deployed agent has a controlled, documented and discoverable gateway endpoint. |
| OBJ-02 | Automate publication | R1 provisioning triggers registry registration and API/MCP/A2A exposure as part of the R2 lifecycle. |
| OBJ-03 | Decouple consumers from runtimes | Consumers use stable logical endpoints rather than direct Mistral or other runtime URLs. |
| OBJ-04 | Enforce access centrally | Authentication, authorisation, consumer-specific tool visibility, quotas and security controls are applied consistently. |
| OBJ-05 | Support multiple consumer types | M2M applications, end-user frontends and agent consumers can use the approved interfaces. |
| OBJ-06 | Govern tools and resources | Internal APIs, selected non-API systems and approved external MCP services are represented in a controlled catalogue. |
| OBJ-07 | Provide traceability | Calls, policy decisions, failures and administrative changes are auditable and correlated. |
| OBJ-08 | Support hybrid connectivity | Private connectivity is used for approved internal and model-runtime paths; external SaaS access follows controlled egress. |

## 3. Scope of services

### 3.1 In scope

**A. Discovery and design**

- Confirm current R1 provisioning architecture, Backstage/Camunda workflow, agent runtime patterns and ownership boundaries.
- Review Apigee organisation, environment, Hybrid cluster, networking, DNS, Private Service Connect (PSC), firewall, SD-WAN and Zscaler constraints.
- Confirm the Mistral agent deployment and endpoint contract, along with the planned Vertex AI model endpoint.
- Inventory the first-wave enterprise APIs, non-API systems, SaaS MCP servers and consumer applications.
- Validate licensing, contract entitlements, Apigee Hybrid version, supported policies and product capabilities.
- Produce the Logical Architecture Document (LAD), Physical Architecture Document (PAD), decision log and detailed interface requirements.

**B. Enterprise Agent Registry**

- Define a canonical agent metadata model and lifecycle states.
- Implement or configure the agreed enterprise registry service/API.
- Store endpoint references, protocol declarations, ownership, version, environment, policy profile, health state and publication state.
- Store references to secrets and identity configuration; do not store plaintext credentials in the registry.
- Provide controlled search/discovery for authorised consumers and administrators.

**C. Gateway and exposure automation**

- Configure Apigee Hybrid as the governed exposure and policy-enforcement layer, subject to the approved version and feature compatibility assessment.
- Establish reusable proxy/provisioning templates for in-scope agent endpoints.
- Extend the R1 Backstage/Camunda provisioning workflow so that a successful agent deployment triggers registry registration, proxy configuration, publication and verification.
- Make the process idempotent and support retry, compensation, rollback and de-registration.
- Provide consumer-specific access policies for approved M2M, frontend and agent identities.
- Expose agent endpoints through approved REST/API and, where supported and required, A2A protocol bindings.

**D. MCP capabilities**

- Establish the governed MCP endpoint pattern for approved internal APIs and existing MCP servers.
- Expose the agreed first-wave API operations as MCP tools, using API specifications or an approved MCP backend.
- Configure authentication, per-tool authorisation, tool filtering and per-tool quotas where supported by the selected Apigee design.
- Integrate the first-wave Snowflake MCP endpoint/proxy and the JDE API path through the existing WSO2 integration layer, subject to endpoint and protocol validation.
- Provide a controlled outbound pattern for selected SaaS MCP endpoints (the brief names ServiceNow and Jira as examples; the architecture image also shows Snowflake and Atlassian).
- Validate end-user identity delegation and downstream credential handling for each integration; do not forward an inbound bearer token to a downstream service unless it is explicitly valid for that resource and approved by the identity/security design.

**E. LLM/model access path**

- Configure the approved model access façade/proxy pattern for the two identified backend families: Mistral and Vertex AI / Model Garden.
- Route requests only to approved backends based on the agreed routing rules.
- Apply agreed authentication, quota, usage measurement, logging and redaction controls.
- Confirm whether this is a common LLM API endpoint, separate backend-specific endpoints, or an agent-runtime dependency. This distinction is an architecture decision and must be closed before implementation.

**F. Security, operations and handover**

- Configure identity integration, policy baselines, TLS, network restrictions, secret references, logging and monitoring for the delivered components.
- Execute integration, security, functional, performance-baseline and failure/recovery tests.
- Deliver operational runbooks, deployment instructions, configuration inventory, test evidence and knowledge-transfer sessions.

### 3.2 Out of scope unless added by change request

- Building or retraining AI models, agent reasoning logic, prompts, business workflows or domain-specific skills.
- Rewriting the Mistral runtime or replacing WSO2, Snowflake, Jira, ServiceNow or other source platforms.
- Full enterprise agent orchestration, autonomous delegation planning, mesh scheduling, cross-domain agent negotiation or a complete zero-trust agent-mesh control plane.
- A full Gemini Enterprise Agent Platform implementation or migration. It may be evaluated as an option, but it is not a required dependency in the proposed baseline.
- General-purpose integration of every internal system or every public SaaS MCP server. Only the agreed first-wave endpoints are included.
- Remediation of source-system defects, API quality issues, data quality, entitlement gaps or third-party service limitations.
- Procurement of Google Cloud, Apigee, Mistral, Vertex AI, SaaS or third-party licences and consumption charges.
- Enterprise-wide IAM redesign, corporate PKI redesign, WAN redesign or security operations transformation.
- A contractual 24x7 managed service, production SLA or formal penetration test unless separately contracted.

## 4. Target capability and delivery principles

The delivered platform must provide a **governed layer to expose, protect, discover and route calls to agents and tools for approved consumers**.

The following principles are mandatory:

1. **One logical entry point:** consumers use published gateway endpoints, not runtime-specific URLs.
2. **Registry is authoritative for agent metadata:** the registry records what exists, who owns it, its lifecycle state and how it may be consumed.
3. **Provisioning-to-publication continuity:** an agent is not marked `READY_FOR_CONSUMPTION` until its registry entry, proxy, policy and smoke test are complete.
4. **Least privilege:** each consumer receives only its approved agent endpoints and tool set.
5. **Identity separation:** distinguish calling application/agent identity, authenticated end-user identity and gateway/runtime service identity.
6. **No credential leakage:** secrets are retrieved from an approved secret manager; they are never embedded in registry metadata, source code, logs or proxy bundles.
7. **Protocol clarity:** MCP is used for agent-to-tool/resource access; A2A is used for agent-to-agent interaction. Do not treat these protocols as interchangeable.
8. **Vendor/runtime decoupling:** the registry and consumer contract must not expose Mistral-specific deployment details unnecessarily.
9. **Policy as code:** reusable, version-controlled templates and configuration are preferred over ad hoc per-agent setup.
10. **Fail closed:** an agent with incomplete registration, invalid policy or failed exposure validation is not published as consumable.

## 5. Functional work packages and requirements

| ID | Requirement | Work package | Acceptance evidence |
|---|---|---|---|
| FR-01 | Register agent metadata on successful R1 provisioning | WP-03 | Registry record created from provisioning event. |
| FR-02 | Generate/configure a governed API proxy for each supported agent | WP-03 | Stable gateway URL resolves to the correct runtime. |
| FR-03 | Publish the agent only after policy and health checks pass | WP-03 | Negative test proves incomplete agents remain unpublished. |
| FR-04 | Support M2M consumers | WP-04 | Authenticated service client invokes authorised agent. |
| FR-05 | Support authenticated end-user frontend calls | WP-04 | User identity is validated and delegated/mapped according to approved design. |
| FR-06 | Support agent-to-agent consumption | WP-04 | Approved agent client invokes a published agent through the governed endpoint. |
| FR-07 | Provide an authorised agent catalogue/discovery API | WP-02 | Consumers see only entries permitted by their policy. |
| FR-08 | Expose approved enterprise API operations as MCP tools | WP-05 | MCP client can list and invoke approved tools. |
| FR-09 | Apply consumer-specific tool filtering and quotas | WP-05 | Different clients receive different tool lists and quota treatment. |
| FR-10 | Integrate first-wave external/SaaS MCP endpoint(s) | WP-05 | Connectivity, authentication and tool invocation tests pass. |
| FR-11 | Integrate the JDE API path through WSO2 | WP-05 | Agreed JDE operation is invokable via the approved MCP/API path. |
| FR-12 | Provide the approved Mistral/Vertex AI model access pattern | WP-06 | Requests route to the selected backend and are observable. |
| FR-13 | Correlate calls across gateway, runtime and integration layer | WP-07 | Correlation ID is present across agreed telemetry points. |
| FR-14 | De-register, suspend and revoke an agent | WP-03 | Revoked agent cannot be newly invoked; existing sessions follow agreed revocation semantics. |
| FR-15 | Support versioned agent endpoint publication | WP-02/03 | New version can be staged, tested and promoted/rolled back. |

### 5.1 Lifecycle states

Minimum proposed state machine:

`REQUESTED → PROVISIONING → DEPLOYED → REGISTERING → EXPOSING → VALIDATING → READY_FOR_CONSUMPTION`

Failure and control states:

`REGISTRATION_FAILED`, `EXPOSURE_FAILED`, `VALIDATION_FAILED`, `SUSPENDED`, `DEPRECATED`, `REVOKED`, `DECOMMISSIONED`.

State transitions must be auditable. Retries must be safe and idempotent. A partial failure must not leave an externally consumable endpoint without a valid registry record and policy.

## 6. Delivery approach and work packages

| WP | Phase | Main activities | Outputs / exit gate |
|---|---|---|---|
| WP-01 | Mobilisation & discovery | Kick-off, stakeholder mapping, R1 review, endpoint inventory, access and network workshops, licensing/version checks | Approved scope baseline, issue log, validated inventories |
| WP-02 | Architecture & detailed design | Complete LAD/PAD, security model, protocol choices, registry schema, network flows, decision records | Architecture review and sign-off |
| WP-03 | Registry & lifecycle automation | Registry API/data model, Backstage/Camunda integration, proxy/provisioning templates, lifecycle compensation | End-to-end R1-to-R2 automated publication demo |
| WP-04 | Agent exposure & access | Configure Apigee, endpoint routing, authentication, client classes, agent discovery and versioning | M2M, frontend and A2A tests pass |
| WP-05 | MCP integration | API-to-tool exposure, Snowflake MCP, WSO2/JDE path, selected SaaS MCP connection, tool policy | Tool discovery, filtering, invocation and quota tests pass |
| WP-06 | LLM/model access | Mistral and Vertex AI connectivity/routing pattern, security and usage controls | Agreed model route tests pass |
| WP-07 | Security, observability & operations | Hardening, audit, dashboards, alerting, runbooks, failure tests | Security/operations acceptance |
| WP-08 | UAT, handover & closeout | UAT, defect resolution, knowledge transfer, as-built package, closure | Signed acceptance and handover |

The delivery schedule and staffing will be estimated after WP-01 confirms system access, integration complexity, traffic profiles, non-production environments and third-party dependencies. No calendar duration is committed in this draft.

## 7. Deliverables

| Deliverable | Format | Minimum content |
|---|---|---|
| D-01 Discovery and readiness report | Markdown/PDF | Current state, dependencies, endpoint inventory, gaps and risks |
| D-02 Statement of Work | Markdown/PDF | Scope, responsibilities, work packages, acceptance, assumptions |
| D-03 Logical Architecture Document | Markdown + diagrams | Logical components, interfaces, flows, identity, lifecycle and decisions |
| D-04 Physical Architecture Document | Markdown + diagrams | Projects, clusters, VPCs, PSC, endpoints, DNS, firewall and deployment plan |
| D-05 Agent Registry schema and API contract | OpenAPI/JSON Schema/Markdown | Entity model, API operations, state machine and example manifests |
| D-06 Provisioning automation | Source/configuration | Backstage/Camunda integration, idempotency, retry and rollback mechanisms |
| D-07 Gateway configuration | Version-controlled artefacts | Proxies, policies, API products, routes and environment overlays |
| D-08 Integration test pack | Markdown/scripts | Test cases, expected results and execution evidence |
| D-09 Security and operations pack | Markdown | Threat considerations, logging, runbooks, monitoring and support model |
| D-10 As-built and handover package | Markdown/source | Final configuration inventory, diagrams, decisions and knowledge-transfer record |

## 8. Roles and responsibilities

R = Responsible; A = Accountable; C = Consulted; I = Informed. Named individuals are to be assigned at mobilisation.

| Activity | Client product owner | Client platform/network | Client IAM/security | Agent/runtime team | Delivery partner |
|---|---:|---:|---:|---:|---:|
| Scope and priority approval | A | C | C | C | R |
| Apigee org/Hybrid access and operations | I | A/R | C | I | C |
| Network, PSC, DNS and firewall changes | I | A/R | C | C | C |
| Identity model and delegated access | C | C | A/R | C | R |
| Agent runtime contract and health checks | I | C | C | A/R | R |
| Registry design and implementation | A | C | C | C | R |
| Backstage/Camunda workflow changes | A | C | C | R | R |
| MCP/API backend readiness | A | C | C | R | R |
| Security approval | I | C | A/R | C | C |
| UAT and acceptance | A/R | C | C | R | C |
| Handover and operational ownership | A | R | C | R | R |

## 9. Assumptions and dependencies

1. R1 provisioning already deploys an agent and exposes a machine-readable deployment result or event that R2 can consume.
2. Backstage and/or Camunda APIs, workflow definitions and non-production access will be made available.
3. The client provides Apigee Hybrid administrative access, the required Google Cloud project access, network diagrams and security standards.
4. The exact Apigee product, plan, add-ons, feature entitlements and contractual usage are confirmed in writing by the client and Google.
5. The target Apigee Hybrid runtime version and supported Kubernetes platform are approved before build. Current public documentation lists Apigee Hybrid 1.17.3 as the current patch on 17 November 2026; MCP support in Hybrid begins at 1.17.0. This must be rechecked against the client's support channel and release cadence before implementation.
6. Mistral and Vertex AI endpoints, network access, quotas, model identifiers and service identities are supplied by the responsible platform teams.
7. WSO2 remains the existing API integration layer for the identified JDE path unless a change is approved.
8. Snowflake and other SaaS MCP services provide supported endpoints, credentials, scopes and tenant permissions.
9. Client IAM/security teams define whether end-user identity must be propagated as a delegated user token, represented by claims, or mapped to a service identity for each backend.
10. Required firewall, SD-WAN, Zscaler, DNS and PSC changes are performed by authorised client teams within the agreed change windows.
11. Test data and non-production backend accounts are available.
12. Third-party service behaviour, rate limits and service availability are outside the delivery partner's control.

## 10. Acceptance criteria

The project is eligible for acceptance when all the following are met:

- **AC-01 — Automated lifecycle:** one in-scope agent can be provisioned by R1 and becomes registered and exposed by R2 without manual publication.
- **AC-02 — Atomic publication:** when registration, policy deployment or health validation fails, the endpoint is not published as ready; a retry or rollback path is demonstrated.
- **AC-03 — Consumer separation:** M2M, frontend and agent consumer identities are independently authenticated and authorised.
- **AC-04 — Least privilege:** unauthorised callers are rejected; authorised callers see only the allowed agent/tool set.
- **AC-05 — MCP:** at least one internal/API-backed tool and each agreed first-wave MCP integration can be discovered and invoked successfully.
- **AC-06 — Model routing:** the agreed Mistral and Vertex AI routes pass connectivity, authentication and functional tests.
- **AC-07 — Traceability:** request correlation and audit records are available for successful and denied calls, without recording secrets or prohibited payload data.
- **AC-08 — Operations:** health checks, alerts, deployment/rollback instructions and support ownership are documented and demonstrated.
- **AC-09 — Documentation:** SoW, LAD, PAD, interface contracts, test evidence and as-built configuration are delivered.
- **AC-10 — UAT:** client product owner and designated technical/security approvers sign the agreed test report or document remaining accepted deviations.

Numerical availability, latency, throughput, recovery time, retention and support targets are **TBD** and must be agreed before performance and production acceptance. This SoW does not imply a specific SLA.

## 11. Risks and mitigations

| ID | Risk | Impact | Mitigation / action |
|---|---|---|---|
| R-01 | Apigee feature or licence entitlement differs from the assumptions in the brief | Scope or cost change | Obtain written feature/entitlement matrix from Google and procurement before design freeze. |
| R-02 | Existing Hybrid version is below the required native MCP baseline | MCP delivery blocked | Validate and plan upgrade to a supported release; include maintenance window and rollback plan. |
| R-03 | Hybrid upgrade causes traffic interruption | Production availability impact | Use a multi-cluster/traffic-diversion strategy where feasible; rehearse in non-production and agree downtime. |
| R-04 | Proxy generation for agents is not fully native/automatic | Extra engineering effort | Prove the API automation path in a technical spike; use a versioned proxy template and controlled provisioning service. |
| R-05 | End-user identity cannot be propagated to a downstream SaaS/API | Authorisation mismatch | Define per-backend token exchange, delegation or service-identity mapping; reject unsafe token passthrough. |
| R-06 | External MCP server auth or network egress is restricted | Integration delay | Early connectivity/authentication tests; coordinate allowlists, Zscaler and third-party administrators. |
| R-07 | A2A mesh governance is mistaken for basic gateway exposure | Scope and cost expansion | Keep A2A endpoint security in baseline; make full mesh orchestration a separate decision. |
| R-08 | Registry and gateway deployment become inconsistent | Unpublished or orphaned endpoints | Idempotent state machine, reconciliation job, compensating action and drift detection. |
| R-09 | Audit logging captures sensitive prompts/tool payloads | Privacy/compliance exposure | Log metadata by default; apply field-level redaction and approved retention. |
| R-10 | Traffic sizing and usage are unknown | Capacity/cost risk | Establish workload profile and jointly size with Google/client before production. |

## 12. Security and compliance requirements

- Authentication and authorisation must be enforced at the gateway before request forwarding.
- Use OAuth 2.0/OIDC or the client-approved enterprise identity mechanism. For MCP HTTP transports, align with the applicable MCP authorisation specification and resource/audience boundaries.
- Use token exchange or explicit credential brokering for downstream calls where delegated identity is required. Do not relay an inbound token to an unrelated downstream resource.
- Separate runtime service identity from consumer identity and end-user identity.
- Enforce per-agent and per-tool allowlists, scope restrictions, quotas and payload-size limits.
- Restrict direct access to internal MCP data-plane services to the intended gateway runtime components.
- Store credentials in the approved secret manager; rotate and audit them.
- Apply TLS in transit and client-approved encryption at rest.
- Redact access tokens, API keys, passwords, secrets, sensitive prompt content and protected personal data from logs.
- Maintain auditability for administrative changes, proxy publication, policy changes, registry state changes and tool invocations.
- Conduct threat modelling for prompt injection, tool misuse, confused-deputy/token-passthrough, SSRF, excessive privileges, MCP tool poisoning and agent impersonation.

## 13. Change control and governance

Any change to the number of agents, backends, SaaS MCP providers, protocols, environments, identity flows, network zones, availability targets or support model must be assessed for schedule, cost, security and architectural impact. Changes are approved by the client product owner and the relevant platform/security authority before implementation.

Architecture decisions must be recorded with options, rationale, impact and approval status. The following are mandatory design gates:

- ADR-01: Apigee Hybrid + custom registry versus Gemini Enterprise Agent Platform.
- ADR-02: Apigee Hybrid version and MCP protocol compatibility.
- ADR-03: Agent proxy generation and registration mechanism.
- ADR-04: Identity propagation and downstream token exchange per backend.
- ADR-05: LLM routing abstraction and Mistral/Vertex AI endpoint model.
- ADR-06: A2A protocol support level and boundary of mesh governance.
- ADR-07: Network topology, PSC roles, egress controls and DNS ownership.
- ADR-08: Production HA, upgrade strategy and service objectives.

## 14. Commercial and approval placeholders

| Item | To be completed by the parties |
|---|---|
| Delivery start / end dates | TBD |
| Estimated effort and team composition | TBD after discovery |
| Fees and payment milestones | TBD |
| Licence and consumption charges | Client / vendor confirmation required |
| Environments and support hours | TBD |
| Warranty / hypercare period | TBD |
| Authorised client approver | TBD |
| Authorised delivery approver | TBD |

## 15. Approval

Approval confirms agreement with the scope and delivery controls described in this draft, subject to completion of the placeholders and open decisions above.

| Role | Name | Signature | Date |
|---|---|---|---|
| Client sponsor / product owner |  |  |  |
| Client platform owner |  |  |  |
| Client security / IAM owner |  |  |  |
| Delivery lead |  |  |  |

## 16. References

- Google Cloud, [Model Context Protocol (MCP) in Apigee overview](https://docs.cloud.google.com/apigee/docs/api-platform/apigee-mcp/apigee-mcp-overview).
- Google Cloud, [Manage MCP tool access with API products](https://docs.cloud.google.com/apigee/docs/api-platform/apigee-mcp/manage-mcp-tool-access).
- Google Cloud, [Enable MCP in Apigee hybrid](https://docs.cloud.google.com/apigee/docs/api-platform/apigee-mcp/enable-mcp).
- Google Cloud, [Apigee hybrid supported platforms and versions](https://docs.cloud.google.com/apigee/docs/hybrid/supported-platforms).
- Google Cloud, [Upgrading Apigee hybrid to version 1.17](https://docs.cloud.google.com/apigee/docs/hybrid/v1.17/upgrade).
- MCP project, [Authorization specification](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization).
- A2A project, [A2A and MCP](https://a2a-protocol.org/latest/topics/a2a-and-mcp/).

---

**End of document — D2AI-CEVA-AGW-SOW-001**
