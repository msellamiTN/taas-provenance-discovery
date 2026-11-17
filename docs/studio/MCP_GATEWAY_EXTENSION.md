# MCP Gateway Extension — TaaS feature extensions (v1alpha1 design seam)

| Document control | Value |
|---|---|
| Document ID | TAAS-EXT-MCPGW-001 |
| Status | **Design seam** — schema/entity extensions only; none of the fields or event kinds below are implemented or accepted by the current API |
| Related | `docs/enterprise/LAD.md` (D1–D8), `docs/enterprise/PAD.md` (§7), `AGENT_MANIFEST_V1ALPHA1.md`, `FEATURE_CATALOG.md` |

## Purpose

The enterprise gateway requirements (centralized MCP proxy, bearer-token broker, per-environment gateway realization, REST→MCP onboarding, private connectivity) are expressed here as **extensions of the existing TaaS feature model** — not as a separate platform. Every new concept binds to a delivered entity: MCP server registry entries, the agent manifest, policy profiles, lifecycle states, audit events and evidence bundles.

Boundary invariant preserved: `proposal ≠ evidence ≠ authorization ≠ execution`. None of these extensions enable `tools/call` — governed execution remains the Phase C PEP seam.

## E1. MCP server registry entry — `exposure` extension

Today an MCP server entry carries identity, transport (`stdio`), and inspection history. The extension adds a declarative `exposure` block describing *how the server may be reached through the governed layer*:

```yaml
# Extension of the existing MCP server registry record (design seam)
exposure:
  mode: direct | gateway | rest-adapter      # direct = current operator-configured inspection only
  gateway:
    route_ref: mcp-gw/servers/<server_id>    # logical route in the environment gateway (PAD §7)
    private_endpoint: true                   # inbound private endpoint required (PAD §5.3)
    dns_name: <server>.mcp.internal          # private FQDN, never raw IP
  adapter:                                   # rest-adapter mode only (FR-INT-8)
    source_api: jde|wso2|openapi-ref         # enterprise REST backend reference
    mapping_ref: rest-mappings/<id>          # REST operation → MCP tool mapping
  policy_profile_ref: profiles/<id>          # link to existing policy profile (UX-17)
  backends:
    - lb_ref: backends/<name>                # LB/service-attachment fronted backend (PAD PHY-05)
```

- `mode: direct` is the **current and only implemented** reality — Studio inspects operator-configured servers directly.
- `mode: gateway` and `mode: rest-adapter` are **not implemented**; when implemented, the registry remains authoritative for the exposure declaration while the gateway enforces it.
- `READY FOR CONSUMPTION` requires gateway config + health/auth/route smoke tests to pass (LAD §6.2) — configuration alone never suffices.

## E2. Agent manifest — `spec.exposure` + `spec.identity` (proposed v1alpha2 fields)

Extension of `AGENT_MANIFEST_V1ALPHA1.md` — same file format, same validation philosophy (unknown fields rejected, conservative defaults):

```yaml
spec:
  # ... existing v1alpha1 fields unchanged ...
  identity:                        # v1alpha2 proposal — not implemented
    workload_identity_ref: null    # agent runtime identity (LAD §9.1 domain 4); never a consumer token
  exposure:                        # v1alpha2 proposal — not implemented
    publish_via: gateway           # how the agent's own tool surface is published
    consumer_scopes: []            # scopes a consumer token must carry to see this agent
    policy_profile_ref: null       # exposure policy binding
```

Validation additions (when implemented): `exposure.consumer_scopes` entries are scope strings; `publish_via: gateway` requires `policy_profile_ref`; defaults remain closed (`consumer_scopes: []` = not exposed). `tools_authorized: false` and `execution_enabled: false` semantics unchanged.

## E3. Policy profile — gateway-exposure rules

The existing policy-designer surface (UX-17) governs tool selection policy. Extension adds **exposure policy** — which tools a consumer profile may see/call:

```yaml
# Extension of policy profile record (design seam)
exposure_rules:
  consumer_scopes: [mcp.read, mcp.call]   # what consumer tokens may present
  tools_visible: [<server>/<tool>, ...]   # filtered tools/list per profile
  tools_callable: []                       # Phase C only — requires PEP gate; empty until then
  egress_class: private|saas-allowlisted   # which egress path the proxy may use
  quota: { calls_per_minute: 0 }           # enforced at gateway data plane
```

`tools_callable` is non-empty **only** under the Phase C governed-execution design; a policy that lists callable tools without a deployed PEP is invalid.

## E4. Lifecycle states — mapping, not replacement

The enterprise publication lifecycle is the **same state machine** the Studio already uses for agents (draft→published), renamed for catalogue semantics:

| Enterprise state (SOW §5.1) | Existing TaaS equivalent | Gate added by extension |
|---|---|---|
| REGISTERED | registry record created | — |
| VALIDATED | manifest/schema validation (`/agents/validate`, `/goals/validate` pattern) | — |
| READY FOR CONSUMPTION | — | **new gate:** gateway config + health/auth/route smoke tests |
| PUBLISHED | agent `published` state | catalogue-visible scope added |
| REVOKED / DECOMMISSIONED | agent `revoked` / archived | gateway route teardown recorded |

## E5. Audit & evidence — new event kinds

Extension of the existing tamper-evident audit chain (`/audit/verify`, UX-19). New event `kind` values, same hash-chain, same semantics (tamper evidence only):

| Event kind | Payload highlights | Boundary note |
|---|---|---|
| `exposure.registered` | server_id, exposure.mode, request_id | declaration, not reachability |
| `exposure.ready` | smoke-test results ref, gateway route ref | records gate evidence |
| `exposure.published` | policy_profile_ref, consumer scopes | catalogue decision |
| `exposure.revoked` | reason, actor | revocation record |
| `gateway.decision` | request_id, decision allow/deny, policy_profile | recorded at proxy; control plane stores the record, not the payload |
| `token.exchange` | subject ref, target audience ref, request_id | never stores tokens |

`payload.request_id` already exists on audit events (S5 work) — the extension reuses it for gateway↔audit correlation.

## E6. Token broker — evolution of the existing auth model

Current delivered model: `TAAS_STUDIO_API_TOKEN` + named `ak_*` API keys with scopes (`tests/test_api_keys.py`). The broker is the **enterprise evolution of that seam**, not a replacement:

| Current (delivered) | Extension (design) |
|---|---|
| Static bearer token / named keys | IdP-issued OIDC tokens (Entra ID or equivalent) |
| Key scopes on API routes | Consumer scopes drive tool-exposure filtering (E3) |
| No downstream calls | Token exchange / workload identity for downstream (LAD D5) |
| Actor attribution via `TAAS_STUDIO_ACTOR` | Caller context in `gateway.decision`/`token.exchange` audit events |

The `ak_*` key model remains valid for single-operator deployments; the IdP broker is the multi-consumer enterprise path (Phase B).

## E7. Environment realization — same entities, adapted backends

Per PAD §7, the `exposure.gateway.route_ref` (E1) resolves to a different substrate per environment — the registry schema is identical everywhere:

| Environment | `route_ref` realizes as | Private connectivity |
|---|---|---|
| Private/on-prem | Kubernetes Gateway API `HTTPRoute` on `Gateway`/`GatewayClass` | Cluster-internal LB / service |
| GCP | ApigeeX/Hybrid proxy route | PSC endpoint + service attachment |
| AWS | API GW / ALB route | PrivateLink endpoint service |
| Azure | APIM operation / AppGW rule | Private Link private endpoint |

## Explicitly not delivered

- All `exposure`, `identity`, `exposure_rules` fields above — validation, persistence, and gateway realization.
- `tools/call` under any mode; the `tools_callable` list is structurally gated on the Phase C PEP.
- IdP/token-broker integration; remains Phase B.

These are schema-level seams so the enterprise architecture (SOW/LAD/PAD) lands on **existing TaaS entities** — registry, manifest, policy, lifecycle, audit — rather than introducing a parallel model.
