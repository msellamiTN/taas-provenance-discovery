# Contracts — MCP governance extension seams

Machine-readable contracts for the E1–E9 design seams. These are the specs
Wave-1+ components are built against — write code to the contract, not to
improvisation. **Status** marks what's already shipped vs. still a seam.

| Contract | Seam | Status |
|---|---|---|
| `exposure.schema.json` | E1 + E8 — `exposure` block + `exposure_signature` on MCP server registry entries | **implemented** (`exposure_signing.py`) — minus `approvals[]`/`backend_identity` (seam) |
| `token-exchange.schema.json` | D2/D10 — broker exchange request/response | design seam (Phase B) |
| `filtered-tools-list.schema.json` | E3 — proxy filtered `tools/list` response | design seam (Phase B) |
| `pep-decision.schema.json` | Phase C PEP — decision request/response incl. args-bound approval | design seam (Phase C) |
| `audit-anchor.schema.json` | D12 — `audit.anchor` artifact record | **implemented** (`audit_anchor.py`) |

## Conventions

- Canonicalization for any signed payload: `json.dumps(sort_keys=True, separators=(",", ":"))` — must match `exposure_signing.canonical_exposure`.
- All schemas are `draft 2020-12`. `$id` uses the `taas.dev` URN space.
- "seam" fields are marked `x-seam: true` — reserved by contract, not yet enforced by code.
- Denials everywhere normalize to `403` with optional `step_up` challenge (RFC 6750) — never a distinct error shape per layer.
