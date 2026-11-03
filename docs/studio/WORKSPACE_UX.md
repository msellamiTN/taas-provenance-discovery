# TaaS Studio — unified workspace UX

## Product intent

Studio is the user-facing control plane for TaaS. Its capabilities must be presented as one
guided workspace, not as disconnected API demos. The interface exposes the discovery and
governance model while preserving clear boundaries between declared metadata, verified
evidence, and runtime execution.

## Primary navigation

- **Workspace:** retained benchmark datasets, task prompts, registry search and tool selection.
- **Discovery:** visual GoalSpec authoring, policy/request configuration, discovery execution,
  selected toolkit, coverage explanation, certificate checks and counterexamples.
- **Model catalog:** model metadata, architecture/artifact inspection and conservative memory
  estimation. Metadata inspection does not download or execute model artifacts.
- **Runtime diagnostics:** host GPU/CUDA checks. Hardware detection is not model-load or
  inference readiness.

## Guided discovery journey

1. Browse a repository-retained benchmark dataset and search/filter task prompts.
2. Select a task. Only its prompt and non-gold metadata are shown to the authoring workflow.
3. Create or refine a GoalSpec using the visual editor:
   - natural-language objective and prompt context types;
   - goal ID and operation class;
   - semantic input/output types;
   - positive effects;
   - delegation class: native, data, effect or unreliable;
   - dependencies, cardinality, exactness, language and optionality.
4. Validate locally for immediate feedback, then validate against the authenticated API.
5. Search the retained tool registry and select candidate metadata records.
6. Review policy and request JSON, then run discovery.
7. Inspect selected tools, goal coverage, abstention reasons, certificate validity gates,
   diagnostic checks and counterexamples.
8. Send the discovery result to a separate evaluator that may access gold labels.

## Trust and safety boundaries

- Benchmark gold labels are not exposed by task browsing and must not be sent to an analyst
  or discovery request.
- Tool descriptions, schemas and annotations are declarations, not proof of runtime behavior.
- Local and server-side GoalSpec validation prove structural properties only; they do not
  prove that the specification faithfully captures user intent.
- Discovery selects metadata-compatible tools. It does not invoke MCP tools or verify their
  runtime behavior.
- A detected GPU does not imply a model is loaded or inference has run.
- The current UI is a single-user experimental workspace. Production multi-user roles,
  durable sessions, audit storage and isolated execution are separate milestones.

## Interaction and accessibility conventions

- Every form field has a visible label and a programmatic label association.
- Actions expose disabled/loading states and concise status messages.
- Search, filtering and pagination remain within their corresponding workspace panel.
- The visual GoalSpec editor is the primary authoring interface. Advanced JSON remains
  available for expert users; manual JSON edits require reloading the visual editor before
  validation or discovery to avoid stale state.
- Validation errors are actionable and identify the affected goal/field when possible.
- Status language distinguishes validated, selected, abstained, not verified and not executed.
  Do not present an unimplemented capability as available.

## Current implementation and next milestones

Implemented in this milestone: retained dataset/task browser, retained tool registry browser,
task/tool handoff to the discovery request, visual GoalSpec editor, local structural checks,
authenticated server-side GoalSpec validation, advanced JSON synchronization guard, and
structured certificate checks, goal coverage/binding and counterexample panels.

Next: richer provenance evidence drill-down, persistent discovery sessions and experiment
history, followed by the analyst provider interface and isolated MCP runtime. The analyst
provider and runtime must remain explicitly unavailable until their implementations and
tests are present.