# Objective Contract v2/v3: outcome and temporal conformance

## Purpose

The Objective Contract is a deterministic, provenance-preserving interpretation frame. It is a review aid, not a semantic proof system. The original user objective remains immutable, human review is mandatory, and Objective Contract v3 blocks discovery until the separate Core review gates are satisfied.

## Outcome preservation

Objective Contract v2 records independently detected required operation classes. The oncology regression fixture covers three distinct operations:

1. **Search** — identify the study matching the title and publication-period criteria and retrieve its abstract.
2. **Translate** — translate only the study title while preserving the abstract's source language.
3. **Extract** — identify the cancer type and the requested historical publication attribution/year.

The v2 coverage projection maps each required operation to GoalSpec goal IDs. Coverage is structural (goal_class_only); it does not establish that the model interpreted the business meaning correctly. Missing operation classes remain uncovered.

Objective Contract v3 attaches each outcome to exact source-clause evidence and orders outcomes by the position of that evidence in the original text. This avoids assigning IDs in an internal operation-detection order that differs from the user's request order.

## Absolute month/year constraints

An explicit month/year expression such as November 2024 is represented as a resolved half-open calendar interval:

- start_inclusive: 2024-11-01
- end_exclusive: 2024-12-01
- business_timezone_required: false

This is a calendar constraint, not a claim that the source has a publication-date field. The actual source field and its semantics remain unresolved until schema discovery.

## Latest/last selection

When recency wording (last, latest, newest, etc.) appears with publication wording, the contract preserves a selection rule:

- mode: top_k
- limit: 1
- order: descending
- order_by_concept: publication_date
- source_field_unresolved: true

The concept is grounded in the user's wording; no concrete source column is invented. Core discovery must establish the source mapping before the constraint can be operationalized.

## Cross-clause article references

A later clause that explicitly refers to the study, the article, or the paper may receive a dependency on one uniquely identified earlier acquisition outcome. The relation includes exact source-span evidence and is marked as a deterministic hypothesis with semantic_correctness_verified: false.

No dependency is inferred when there are multiple possible prior acquisition outcomes or multiple outcomes in the referring clause. Explicit sequencing dependencies continue to use their existing relation rule.

## Θ and GoalSpec validation

The GoalSpec analyst must use exact semantic type strings from the repository's Θ vocabulary. A malformed list, undeclared type, or invented domain is rejected. This change does not weaken the validator and does not silently coerce malformed model output.

## Acceptance

The Colab notebook runs the oncology regression tests from:

- tests/test_objective_contract_v2.py
- tests/test_objective_contract_v3.py

The regression checks three operations, November 2024 calendar bounds, top-one descending publication-date selection, source-clause provenance, and dependencies from the retrieved study to translation/extraction.

Passing these tests establishes deterministic contract behavior only. It does not certify natural-language semantic correctness, source availability, tool suitability, authorization, or execution.