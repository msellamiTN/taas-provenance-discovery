# Scenario-Agnostic Objective Engineering

## Status

Architecture and acceptance contract for the TaaS Studio objective-to-capability pipeline. This document defines the platform contract; it does not claim that every capability or scenario is already implemented.

## Product invariant

TaaS accepts objectives from arbitrary domains. A scenario is input data for the general engine, never a production workflow definition. Production behavior must not branch on a scenario name, benchmark ID, customer, example prompt, domain-specific output filename, or showcase artifact.

The engine may use domain knowledge only through explicit, versioned, reviewable resources:
- the canonical GoalSpec class and field contract;
- Theta semantic kinds, domains and exact common types;
- registered capability and connector metadata;
- policy and authorization configuration;
- user-supplied schemas, context and constraints;
- evidence produced by discovery or a separately authorized execution runtime.

A scenario-specific adapter is permitted only when it is a genuine external integration boundary (for example, a connector protocol adapter). It must not bypass the shared objective, validation, assurance or governance pipeline.

## Shared lifecycle

1. **Intake** — preserve the immutable original objective and collect optional typed inputs, files, schemas, context and user constraints.
2. **Interpretation** — derive a versioned objective frame: requested outcomes, operations, scope, exactness, temporal constraints, output requirements, side effects, risk constraints, assumptions and unresolved questions. Deterministic lexical analysis is a constraint hint, not proof of meaning.
3. **Decomposition** — the analyst proposes the smallest useful dependency graph using only canonical GoalSpec classes, fields and Theta types. The analyst does not see the tool registry and cannot claim tool availability.
4. **Structural validation** — validate schema, identifiers, references, acyclicity, field types, effect syntax and exact Theta membership.
5. **Objective conformance** — check that every required outcome and constraint is represented, data dependencies are connected, exactness and scope are preserved, and no requested operation has been replaced by a superficially related one.
6. **Gap analysis** — ask TaaS Core whether the validated goals can be represented and supported by the current capability model. Preserve warnings, errors and unresolved ontology mappings; never silently invent synonyms or types.
7. **Human review** — present the original objective beside the proposed graph, diagnostics, assumptions, gaps and proposed effects. Discovery is blocked until the required review is confirmed.
8. **Capability discovery** — inspect eligible registered tools and their schemas/effects/provenance. Discovery is metadata analysis, not invocation.
9. **Assurance and decision** — report goal coverage, evidence witnesses, unsupported goals, capability gaps, policy conflicts, uncertainty and approval requirements.
10. **Governed execution (separate capability)** — only a separately implemented and authorized runtime may execute. It must enforce identity, least privilege, secrets isolation, network policy, budgets, cancellation, output validation, audit and provenance capture.

## Objective Contract v2 implementation status

The current branch now emits an additive `contract_version: "2.0"` frame from `derive_objective_contract`. It preserves the legacy `operation`, `required_goal_classes`, scope, exactness, temporal and source-data fields while adding:

- `outcomes[]`: ordered, independently identified required goal-class hypotheses;
- `constraints`: grouped input, scope, computation, temporal, unresolved-concept and ambiguity information;
- `review`: mandatory human review, explicit interpretation method and an always-false semantic verification flag.
- `objective_coverage` from the prepare API: each required outcome is mapped to matching proposed goal IDs, actual supplied input types, or an explicit `missing` state. Coverage is structural evidence only and never semantic proof.

The current outcome list is still derived from deterministic lexical rules. It is not yet an extensible semantic outcome graph, and the current parser can miss paraphrases, implicit operations, negation, conditional requirements and cross-lingual intent. The v2 shape is therefore a backward-compatible contract step—not a claim of universal objective understanding.

A focused test module, `tests/test_objective_contract_v2.py`, covers compound outcome preservation, legacy-field compatibility, user-supplied content handling, mandatory review and objective-context serialization. The Colab notebook pins the tested source revision and runs these focused tests. A notebook pin is not evidence that the notebook has been executed successfully; record actual Colab output before declaring acceptance.

## Objective frame: required properties

The frame must be extensible and versioned. It must not reduce a compound objective to one primary operation. At minimum, represent:

- immutable objective text and locale;
- zero or more requested outcomes;
- one or more required operations where identifiable;
- explicit inputs and whether data is user-supplied or must be acquired;
- output artefacts, formats, destinations and quality constraints;
- scope (all/every, filters, populations, time ranges and completeness);
- exactness and tolerance requirements;
- dependency and ordering constraints;
- side effects (write, delete, send, transact, execute, publish);
- privacy, security, policy and authorization constraints;
- temporal anchors and business timezone requirements;
- ambiguity, assumptions, unresolved concepts and required clarifications;
- evidence and provenance requirements;
- confidence and limitations of the interpretation method.

Unknown values remain unknown. The engine must not infer a source, schema, permission, timezone, destination, business definition or success state merely to complete a plan.

## Canonical vocabulary and effects

Goal classes, GoalSpec fields, semantic types and effect expressions must come from the repository's canonical contract and Theta data. Never construct types by combining individually valid kind/domain/cardinality fragments unless the exact type is declared. Never treat a business noun as a prompt input type.

Effects describe the authority a goal would require; they are not decorative labels. A boundary-crossing goal with a missing or malformed required effect must fail conformance with an actionable diagnostic. The effect contract must be maintained in one canonical source and reused by analyst instructions, server validation, UI reference material and tests. Do not maintain separate hand-written mappings in each layer.

Effect requirements can be resource-dependent. For example, creating a local file and creating a remote document through a service may both produce a document but have different concrete resource scopes and connector semantics. The analyst must propose the minimal effect supported by the canonical contract; discovery must later verify the actual tool's declared effects. A goal's requested effect is not proof that a tool can safely provide it.

## Scenario independence requirements

- No scenario-specific branches in the production objective parser, decomposition endpoint, Core validator, discovery engine or assurance pipeline.
- No hardcoded prompt, entity, file name, output directory, business domain or expected goal count for an acceptance fixture.
- No fixture may inject gold tool IDs, expected tool bindings or benchmark labels into the analyst prompt.
- A scenario may declare expected semantic properties in test code; those expectations must not be imported by production code.
- New domains should be supported by declared Theta/capability metadata or an explicit clarification, not by silently expanding lexical synonyms.
- Unknown or unsupported objectives must fail safely with useful diagnostics, not be forced into the nearest known workflow.
- The same review, provenance and policy boundaries apply regardless of domain or output type.

## Acceptance matrix

The suite must contain unrelated objective families and both single-operation and compound requests. These are test categories, not hardcoded production templates.

| Family | Representative objective shape | Properties to verify |
|---|---|---|
| Research | Find recent papers, compare evidence and explain findings | acquisition, dates, source provenance, synthesis, uncertainty |
| Analytics | Calculate exact totals or counts over filtered records | source/schema gap, numeric output, exactness, scope completeness, dataflow |
| Data engineering | Design or run an ingestion/transformation workflow | planning vs execution distinction, schemas, dependencies, side effects |
| Software engineering | Inspect a repository, diagnose a defect and propose a patch | repository input, inspect/analyse/write separation, no unapproved mutation |
| Document production | Create a specified document from supplied or acquired material | content vs file creation, format, destination, write effect, artifact verification |
| Media production | Generate or transform an image/audio/video asset | input provenance, media output type, generation capability, file/effect boundary |
| Communication | Draft and send a notification | draft vs send separation, recipient ambiguity, egress effect, approval |
| Transactional | Book, purchase, transfer or otherwise change external state | exact target, amount/terms, authorization, money/state effects, confirmation |
| Scheduling | Create or modify an event with date/time constraints | timezone, temporal resolution, participant/availability ambiguity, write effect |
| Knowledge work | Extract, classify, translate, compare or summarise supplied content | user-supplied data distinction, operation preservation, output contract |
| Unknown domain | Objective containing undeclared business concepts or unfamiliar tools | explicit unresolved concepts, generic types only where valid, clarification/gap rather than invented mapping |

For each fixture, test at least:
1. original objective is preserved;
2. all required operations/outcomes are represented;
3. no unrelated operation is invented;
4. input and output types are members of the exact Theta vocabulary;
5. effects are syntactically and semantically adequate for the declared goal class;
6. dependency edges connect produced inputs to consuming goals;
7. scope, temporal constraints and exactness survive decomposition;
8. source-data requirements are not confused with user-supplied content;
9. Core diagnostics are surfaced without suppression;
10. discovery remains blocked until review;
11. no tool is invoked by decomposition or discovery;
12. no output is marked complete without independently verified evidence.

## Quality gates and reporting

Report separate statuses; do not collapse them into a single green check:
- interpretation status;
- structural validity;
- objective conformance;
- Core gap-analysis status;
- human-review status;
- discovery status;
- assurance status;
- execution authorization status;
- execution result and artifact verification status.

A proposal can be structurally valid but objectively incomplete. A conformant GoalSpec can still have a capability gap. A selected tool is not an execution result. A generated text response is not a verified file. An execution result is not successful until its declared outputs have been independently checked.

## Implementation sequence

1. Make the objective frame an explicit, versioned data contract and preserve compound outcomes.
2. Establish one canonical class/effect/type reference source consumed by analyst prompt, API, UI and tests.
3. Expand objective conformance from a single operation heuristic to outcome/constraint coverage with abstention on ambiguity.
4. Add scenario-independent decomposition and negative-test fixtures across the matrix above.
5. Integrate Core gap analysis and render diagnostics in a goal graph workbench.
6. Add capability discovery with provenance and effect compatibility evidence.
7. Add assurance reporting and decision gates.
8. Treat governed execution and artifact verification as a separate release track.

## Current limitations to retain explicitly

The objective analyser uses heuristics and does not prove semantic equivalence. The model proposes GoalSpecs and does not prove correctness. Core validation can establish only the properties implemented by its checks. Discovery does not invoke MCP tools. If governed execution, isolation, durable run history or artifact verification is unavailable in a build, the UI must say so and must not imply completion.
