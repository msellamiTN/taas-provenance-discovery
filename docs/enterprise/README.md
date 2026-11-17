# TaaS — Enterprise Architecture Layer

Platform-level architecture and requirements documents. These sit **above**
`docs/studio/` (lifecycle control-plane implementation docs) and `docs/`
(paper/experiment docs): they state what the TaaS Intelligence Platform must
be, and honestly record what is delivered, designed, or not yet implemented.

| Doc | Role |
|---|---|
| `TAAS_PLATFORM_MEGAPLAN.md` | Governing plan: vision, threat model, functional requirements `FR-*`, non-functional requirements `NFR-*`, boundary charter, NIST AI RMF / ISO 42001 / ISO 27001 mapping, phased roadmap |
| `SAW.md` | Software Architecture Whitepaper: trust zones, components, design principles |
| `LAD.md` | Logical Architecture Design: component and data-flow views, interface inventory, trust-boundary analysis |
| `PAD.md` | Physical/Deployment Architecture Design: topologies, Terraform provisioning layout, API gateway + egress policy, secrets/KMS, multi-cloud/on-prem matrix |
| `REQUIREMENTS_GAP.md` | Requirement → repo evidence → status table (the audit trail for every `delivered` claim) |

## Vocabulary (binding across all enterprise docs)

- **Boundary invariant** — `proposal ≠ evidence ≠ authorization ≠ execution`.
  No surface may imply a state it does not hold.
- **Status vocabulary** — `delivered` (code + tests exist),
  `design-seam` (documented seam, deliberately no code),
  `not implemented`, `out-of-scope`.
- **Boundary charter** — refusals that are *features*: `tools/call`
  unavailable, evaluator absent, no tenant isolation, no production auth.
  Each names the security project that would unblock it.
- **Requirement IDs** — `FR-<pillar>-<n>` functional, `NFR-<pillar>-<n>`
  non-functional; pillars: `LC GOV EXEC INT DEP OBS SEC DR`.

Lower-level docs: `docs/studio/LIFECYCLE_API_MEGAPLAN.md` (A1–A6 lifecycle),
`docs/studio/FEATURE_CATALOG.md` (verified feature audit),
`docs/deployment/STUDIO_OPERATIONS.md` (operations runbook).
