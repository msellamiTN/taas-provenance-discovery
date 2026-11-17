# Requirements → Evidence Gap Analysis

Every `delivered` claim maps to verifiable repo evidence. Statuses:
`delivered` · `design-seam` · `not implemented` · `out-of-scope`.
Audit baseline: `main` @ `e108345` (752 tests; 89 API routes).

## FR-LC — Lifecycle control plane

| Req | Evidence | Status |
|---|---|---|
| FR-LC-1 GoalSpec define | `POST /goals/validate`, `GET /goalspec/templates(+/{id})`, `GET /reference/vocabulary` in `src/taas/studio/api.py`; `tests/test_studio_api.py` | delivered |
| FR-LC-2 Agent/Skill lifecycle | `/agents` + `/skills` validate/publish/sign/revoke/diff/events routes; `tests/test_lifecycle_scenario_e2e.py` A2 | delivered |
| FR-LC-3 Discovery | `POST /discover`, `GET /discovery/runs(+diff)`, `GET /tools(+facets,+intelligence)`, `GET /mcp/servers(+inspect)`, `GET /mcp/registry/snapshots(+diff)`, `GET /hypergraph/projections` | delivered |
| FR-LC-4 Verify | `POST /policy/evaluate`, `…/policy-verdict(+history)`, `…/release-readiness`, `GET/POST …/approvals`, `POST /assurance/evidence/freshness`, assurance router | delivered |
| FR-LC-5 Operate | `GET /audit/events(+after_seq/subject)`, `GET /audit/verify` (full ledger), `GET /runtime/*`, `GET /notifications`, `GET /platform/overview` | delivered |
| FR-LC-6 Evaluate & manage | `GET /bench/*`, `GET/POST/PUT/DELETE /workspaces`, `GET /workspaces/{id}/revisions(+kind/actor/cursor)` | delivered |

## FR-GOV — Governance

| Req | Evidence | Status |
|---|---|---|
| FR-GOV-1 Fail-closed auth | `require_api_token` in `api.py`; 503/401 asserted in `tests/test_api_keys.py`, acceptance notebook fail-closed battery | delivered |
| FR-GOV-2 Named API keys | `src/taas/studio/api_keys.py`; `GET/POST /admin/api-keys`, `POST …/revoke`; `api_key` audit events; per-key `StudioPrincipal` actor | delivered |
| FR-GOV-3 OIDC/SSO | none | not implemented (Phase B) |
| FR-GOV-3b Token broker (Entra ID / equivalent IdP) — short-lived Bearer tokens for all MCP access, JWKS-validated at proxy edge; **edge replacement** for data-path auth | `MCP_GATEWAY_EXTENSION.md` E6 — `ak_*` keys remain control-plane/dev only; `token.exchange` audit kind (design seam) | design seam — not implemented (Phase B) |
| FR-GOV-3c Sender-constrained tokens (DPoP / mTLS-bound) on MCP data path | none (LAD D13, OD-2) | not implemented (Phase B) |
| FR-GOV-4 RBAC | none | not implemented (Phase B) |
| FR-GOV-5 Org policies, multi-party approvals | `POST /policy/evaluate` (diagnostic) + `GET/POST …/approvals` exist; org-scoped/multi-party absent | partially delivered |
| FR-GOV-6 Tenant isolation | single-tenant by design; megaplan §7.1 | not implemented — separate security project |

## FR-EXEC — Governed execution

| Req | Evidence | Status |
|---|---|---|
| FR-EXEC-1 PEP | `docs/studio/ISOLATED_PEP.md` — seam only | design-seam |
| FR-EXEC-2 Approval tokens | `docs/studio/GOVERNED_EXECUTION_GATEWAY_PHASE1.md`; `POST …/authorization/preflight` exists (preflight, not execution) | design-seam |
| FR-EXEC-3 Isolated workers | none | not implemented — separate security project |
| FR-EXEC-4 `tools/call` in control plane | MCP inspect asserts `inspection_only`, `tool_execution_performed:false` (`tests/test_studio_api.py`); browser suite asserts no mutation requests | **refused by design** |

## FR-INT — AI-platform & runtime integrations

| Req | Evidence | Status |
|---|---|---|
| FR-INT-1 Backend abstraction | `docs/deployment/MODEL_RUNTIME_BACKENDS.md`; HF + Ollama runtime paths; `POST /models/load`, `/models/chat` | delivered |
| FR-INT-2 GPU/CPU profiling | `GET /runtime/hardware`, `GET /models/runtime`; honest unavailable states | delivered |
| FR-INT-3/4/5/6/7 Mistral/Foundry/Vertex/Bedrock/vLLM adapters | none | not implemented (Phase D) |

## FR-DEP — Deployment & provisioning

| Req | Evidence | Status |
|---|---|---|
| FR-DEP-1 Container | root `Dockerfile` + `.dockerignore` + `deploy/hf-studio/Dockerfile` | written — build unverified (Docker daemon unavailable) |
| FR-DEP-2 Helm/K8s | none | not implemented (Phase B) |
| FR-DEP-3 Terraform | none | not implemented (Phase B) |
| FR-DEP-4 API gateway | same-origin design documented; no gateway artifact | not implemented (Phase B) |
| FR-DEP-5 Egress proxy | none | not implemented (Phase B) |
| FR-DEP-5b Centralized MCP gateway/proxy — all MCP access (inspection today, governed execution Phase C) transits the proxy; direct client→MCP unsanctioned (SoW C2, LAD D1/D5, PAD §2/§5) | `docs/studio/MCP_GATEWAY_EXTENSION.md` E1 `exposure` block on MCP server registry entries (design seam); today inspection reaches operator-configured stdio servers directly | design seam — not implemented (Phase B) |
| FR-DEP-5c Per-environment gateway realization — **Kubernetes Gateway API** (GatewayClass/Gateway/HTTPRoute) for private/on-prem; GCP ApigeeX+PSC; AWS API GW/ALB+PrivateLink; Azure APIM/AppGW+Private Link — one logical contract (LAD D3, PAD §7) | `MCP_GATEWAY_EXTENSION.md` E7 `route_ref` per-environment mapping (design seam); no K8s manifests or gateway resources in repo | design seam — not implemented (Phase B) |
| FR-DEP-5d Private connectivity — PSC/PrivateLink/Private Link endpoints + service attachments + private DNS to backends & AI platforms (PAD §5.3, ref `docs/archi/apigeeArea.png`) | `MCP_GATEWAY_EXTENSION.md` E1 `private_endpoint`/`dns_name`/`lb_ref` fields (design seam) | design seam — not implemented (Phase B) |
| FR-INT-8 REST→MCP onboarding — enterprise REST APIs exposed as governed MCP tools via gateway adapter (LAD D6) | `MCP_GATEWAY_EXTENSION.md` E1 `mode: rest-adapter` + `adapter.mapping_ref` (design seam) | design seam — not implemented (Phase B) |
| FR-INT-9 MCP session & notification policy — session↔identity binding, `notifications/*` allow-listing, elicitation/sampling interception, streaming limits (LAD D11) | none — proxy is a REST mental model today; bidirectional JSON-RPC semantics undesigned (OD-5) | not implemented (Phase B) |
| FR-DEP-5e Per-env capability matrix + conformance tests — `route_ref` schema-identical but enforcement strength divergent (PAD §7.6) | PAD §7.6 matrix (design) | design seam — not implemented (Phase B) |
| FR-DEP-6 Air-gap bundle | Colab notebooks prove offline-capable checkout; no bundle | not implemented (Phase D) |

## FR-OBS — Observability

| Req | Evidence | Status |
|---|---|---|
| FR-OBS-1 Structured logs | request-logging middleware in `api.py` (JSON, no headers/bodies); megaplan S5 | delivered |
| FR-OBS-2 Correlation | `payload.request_id` in audit events; `X-Request-ID` middleware | delivered |
| FR-OBS-3 Health/readiness | `GET /health`, `GET /ready` (`calibration` state) | delivered |
| FR-OBS-4 OTel/metrics | none | not implemented (Phase B) |
| FR-OBS-5 SIEM export | none (stdout JSON is SIEM-ingestible) | not implemented (Phase B) |
| FR-OBS-6 External audit anchoring — signed ledger digests to WORM/witness store; producer never sole anchor (LAD D12, NFR-AUD-3, OD-3) | `audit_ledger.py` hash chain is self-anchored today — tamper-evident but self-attested | not implemented (Phase B) |
| FR-OBS-7 Anomaly detection — tool-use bursts, new egress FQDN, token-exchange anomalies → metrics/SIEM | none | not implemented (Phase B) |

## FR-SEC — Security

| Req | Evidence | Status |
|---|---|---|
| FR-SEC-1 Headers + body cap | `nosniff`/`DENY`/`no-referrer` headers + 413 @2MiB middleware; megaplan S4 | delivered |
| FR-SEC-2 Injection safety | parameterized SQLite; regex-constrained IDs; bounded Pydantic fields | delivered |
| FR-SEC-3 Secret store | env-only today; `STUDIO_OPERATIONS.md` rotation procedure | not implemented (Phase B) |
| FR-SEC-4 mTLS | none | not implemented (Phase C) |
| FR-SEC-5 SBOM/SLSA | none | not implemented (Phase B) |
| FR-SEC-6 Signed exposure records — signature + four-eyes publication + backend identity pinning on `exposure` block (E8) | registry entries are unsigned JSON today — the configuration plane is the confused-deputy surface | design seam — not implemented (Phase B) |
| FR-SEC-7 Tool metadata sanitization — lint tool descriptions for injection patterns at inspection; schema-required fields only | `mcp_registry.py` inspection stores metadata as-observed | not implemented (Phase B) |
| FR-SEC-8 MCP server artifact provenance — image digest + SBOM + SLSA attestation on server record (E9) | snapshots attest observations, not artifact origins | not implemented (Phase C/D) |

## FR-DR — Resilience

| Req | Evidence | Status |
|---|---|---|
| FR-DR-1 Backup/restore | online SQLite backup rehearsal — integrity + row counts verified; megaplan S3 | delivered |
| FR-DR-2 RPO/RTO + rollback | `docs/deployment/STUDIO_OPERATIONS.md` | delivered (single-instance) |
| FR-DR-3 HA | `PAD.md` T-C only | design — Phase B |
| FR-DR-4 Token-broker/IdP resilience — HA, JWKS cache/rotation, IdP-outage behavior (PAD §7.7, NFR-AVL-1) | PAD §7.7 (design) | design seam — not implemented (Phase B) |

## NFR spot verification

| Claim | Verification |
|---|---|
| No `tools/call` anywhere | no such route in `api.py`; browser suite asserts zero invocation requests |
| No fabricated KPIs | `platform/overview` `unsupported_kpis` explicit; `state: unavailable` blocks |
| Semantic markers present | `record_semantics`, `execution_record`, `authorization_granted:false` asserted in acceptance notebook (29/29) |
| Audit = full ledger | `audit/verify` `scan_scope: full_ledger` |
| Boundary invariant | FEATURE_CATALOG §1 four-state boundary; tests pin refusal semantics |
