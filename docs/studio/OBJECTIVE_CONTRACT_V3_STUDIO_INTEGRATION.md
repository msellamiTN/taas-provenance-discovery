# Objective Contract v3 — Studio integration

## Purpose

Expose the conservative Objective Contract v3 projection in the existing Objective Intelligence workflow. This increment does not replace GoalSpec, change the TaaS Core discovery algorithm, or establish semantic correctness.

## Workflow

1. The user enters the original objective in Goal-oriented Agent Design.
2. The API derives the existing v2 objective frame and the v3 typed projection from the same original text.
3. Model inference proposes a GoalSpec independently of the MCP registry.
4. Existing structural validation, objective alignment diagnostics and Core gap analysis remain authoritative for their respective checks.
5. Studio displays the v3 outcomes with exact source spans and any blocking clarification signals.
6. When v3 reports blocking clarifications, Studio disables Apply. The user must clarify or rewrite the objective and prepare it again.
7. Discovery remains a separate, explicitly confirmed operation. Tool execution remains disabled.

## V3 response fields

- `objective_contract_v3`: original objective text, locale, outcomes, source evidence, constraints and clarification records.
- `objective_intelligence_v3.status`: `clarification_required` or `ready_for_human_review`.
- `structurally_valid`: result of the v3 invariant validator.
- `blocking_clarification_count`: number of blocking clarification records.
- `semantic_correctness_verified`: always false in this increment.
- `discovery_authorized`: always false in this increment.

## Evidence and limitations

Source offsets are Unicode code-point offsets into the unchanged original string. Evidence is checked against the exact source slice. Modality detection is deliberately conservative and punctuation-delimited; it is not a complete natural-language scope parser. The v3 projection is a clarification aid, not a semantic theorem prover.

A zero-clarification result means only that this parser found no supported blocking marker. It does not prove that the interpretation is complete or correct. Human review remains mandatory.

## Safety boundary

This feature does not invoke MCP tools, grant authorization, execute an Agent, or bypass the existing discovery confirmation. A v3 contract never authorizes discovery or execution.

## Validation

The canonical Colab notebook includes the Objective Contract v3 test module and Studio API regression suite. CI additionally validates notebook JSON/Python cells and runs the repository test workflow. A live Colab execution must be recorded separately; notebook inclusion alone is not runtime evidence.
