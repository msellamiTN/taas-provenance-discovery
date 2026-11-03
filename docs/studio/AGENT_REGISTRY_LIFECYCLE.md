# Agent Registry and lifecycle

## Scope

The Agent Registry persists immutable versions of structurally valid `taas.ai/v1alpha1` manifests. It provides a small SQLite-backed persistence primitive for a single Studio service. It is not a multi-tenant production registry.

## API

All routes require the Studio bearer token.

| Method | Route | Behavior |
|---|---|---|
| POST | `/api/v1/agents` | Validate the manifest and create a new immutable version in `draft` |
| GET | `/api/v1/agents` | List versions; optional `agent_id`, bounded `limit` |
| GET | `/api/v1/agents/{agent_id}/versions/{version}` | Read exact immutable version |
| POST | `/api/v1/agents/{agent_id}/versions/{version}/validate` | Revalidate stored manifest and transition draft → validated |
| POST | `/api/v1/agents/{agent_id}/versions/{version}/publish` | Transition validated → published |
| GET | `/api/v1/agents/events` | Read append-only lifecycle event history; optional `agent_id` |

Set `TAAS_AGENT_REGISTRY_PATH` to choose the SQLite database location. If unset, the service uses `~/.taas/studio/agents.sqlite3`. On POSIX systems the implementation attempts owner-only directory and file permissions (0700/0600). SQLite WAL mode and a write transaction serialize lifecycle updates. Database triggers reject updates/deletes to version content, deletion of version rows, and updates/deletes to lifecycle event rows. Lifecycle-state and updated-at columns are the only mutable version fields.

## Lifecycle

```text
create manifest
     |
     v
   DRAFT -- structural validation --> VALIDATED
                                        |
                                        | explicit publish
                                        v
                                    PUBLISHED
```

Only the transitions `draft → validated` and `validated → published` are accepted. Published versions are immutable. A changed configuration must be created as a new SemVer version; an existing `agent_id + version` pair cannot be overwritten.

Every successful transition appends an event with event type, prior/new state, actor label, timestamp, and manifest SHA-256. The hash is calculated over canonical JSON (UTF-8, sorted keys, compact separators). It is a content-integrity identifier, not a digital signature or external timestamp proof. Database triggers protect against accidental/application-level mutation; a filesystem/database administrator can still alter the database or drop triggers.

## Trust boundaries

- `validated` means only that the stored manifest satisfies the Pydantic schema and cross-field constraints. It does not establish semantic correctness or goal fidelity.
- `published` means the immutable configuration version was published in this registry. It does not mean the model exists, can be loaded, or was evaluated.
- Tool grants remain declarations. The registry does not resolve them against a live/versioned MCP registry, authorize calls, or invoke MCP tools.
- All API responses continue to state `tools_authorized: false` and `execution_enabled: false`.
- The current actor is the service label `studio-api`, not an authenticated human identity. The bearer-token layer does not provide user attribution.
- SQLite persistence is local to the configured service filesystem. Tenant isolation, encrypted-at-rest storage, backup/restore, distributed coordination, retention, signed audit records, and external identity integration are not implemented.
- Manifest JSON is stored as supplied after normalization. Do not put credentials, API keys, or other secrets in instructions or manifests. A dedicated secret broker and secret-reference contract are future work.

## Operator smoke test

1. Set `TAAS_STUDIO_API_TOKEN` and `TAAS_AGENT_REGISTRY_PATH`.
2. Submit a manifest to `POST /api/v1/agents`; expect HTTP 201 and `draft`.
3. Submit the exact version to the `/validate` route; expect `validated`.
4. Submit the exact version to `/publish`; expect `published` with execution still disabled.
5. Read `/api/v1/agents/events`; expect created, validated and published events in reverse chronological order.
6. Attempt duplicate creation or a backwards lifecycle transition; expect HTTP 409.

The tests use a temporary SQLite database and do not mutate a user's real registry.
