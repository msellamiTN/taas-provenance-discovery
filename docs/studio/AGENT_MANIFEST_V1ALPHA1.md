# Agent Studio — declarative Agent contract (v1alpha1)

## Purpose

This increment introduces a strict, versioned manifest for describing an Agent resource. It is the configuration contract for the next Agent Studio workstream; it is not an agent executor.

The authenticated endpoint `POST /api/v1/agents/validate` validates and normalizes a manifest. It does not save it, publish it, load its model, authorize tools, call MCP, or run the agent.

## Manifest

```yaml
apiVersion: taas.ai/v1alpha1
kind: Agent
metadata:
  id: support-assistant
  name: Support Assistant
  version: 1.0.0
  description: Draft support workflow agent
spec:
  model:
    provider: huggingface
    model_id: Qwen/Qwen2.5-0.5B-Instruct
    # revision: immutable Hub commit SHA (optional in this increment)
  instructions: |
    Help the operator summarize support requests.
  goal_spec_template: null
  tool_allowlist: []
  resources:
    max_new_tokens: 512
    timeout_seconds: 90
    max_tool_calls: 0
  approval:
    require_human_approval: true
    require_assurance: true
    allow_side_effects: false
```

## Contract rules

- `apiVersion` and `kind` are fixed and required.
- Agent IDs are lowercase DNS-style identifiers; versions use SemVer syntax.
- Model references are Hugging Face `namespace/repository` IDs. They are configuration references, not proof that the model exists, is accessible, or is compatible with the runtime.
- Unknown fields are rejected at every typed object boundary.
- Tool grants are exact `server_id/tool_name` pairs. Duplicate grants are rejected.
- A non-empty allowlist requires `max_tool_calls > 0`; a positive tool-call budget requires a non-empty allowlist.
- Side-effect capability cannot be declared without human approval.
- Defaults are conservative: empty tool allowlist, zero tool calls, human approval required, assurance required, and side effects disabled.

## Validation response semantics

A successful response reports:

- `valid: true`: the manifest satisfies the structural schema and cross-field invariants.
- `lifecycle_state: draft`: it remains an unpersisted draft.
- `semantic_correctness_verified: false`: schema validation does not prove that instructions or the GoalSpec template faithfully encode user intent.
- `tools_authorized: false` and `execution_enabled: false`: a manifest grant is not an authorization decision and does not enable invocation.

## Explicitly not delivered

- Durable agent registry, immutable version history, publication, rollback, or audit events.
- Runtime model binding or admission control.
- Tool authorization against a live registry snapshot.
- Policy evaluation, human approval workflow, or MCP invocation.
- Isolated workers, secrets brokering, quotas, cancellation, or durable run traces.

These capabilities must be delivered as separate, testable increments. In particular, a future executor must resolve the manifest's tool grants against a versioned registry snapshot and re-authorize each call at the execution boundary; it must not treat this manifest as a bearer capability.
