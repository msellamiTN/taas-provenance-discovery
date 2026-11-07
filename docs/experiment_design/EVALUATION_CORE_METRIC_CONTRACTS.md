# PaMCP Evaluation Core — Metric and Evidence Contracts

**Status:** implementation slice; not an experiment result and not a protocol amendment.  
**Protocol authority:** `docs/experiment_design/pamcp_experiments_v1.json` and
`docs/experiment_design/pamcp_baselines_v1.json`.

## Boundary

This package evaluates frozen registry snapshots, discovery rankings, reference labels,
certificates and provenance/QoS evidence records. It does not start MCP servers, call MCP
tools, execute agent trajectories, or infer effects from tool responses. It is an evaluator
support layer, not a replacement for the independent runtime evaluators required by E3,
E10, E13 or E14.

## Implemented metric functions

| Function | Contract | Protocol alignment |
|---|---|---|
| `binary_classification_metrics` | TP/FP/TN/FN; unknown reference labels and prediction abstentions are separate; precision/recall/F1 and coverage denominators are explicit | E2 semantic typing; reusable for reference-labelled binary properties |
| `retrieval_metrics` | Hit@k, MRR, macro Hit@1; exact request-ID match; empty qrels excluded and counted through requests_total/scored | E8 |
| `exposure_at_k` | Exp@k = request fraction whose top-k includes at least one independently reference-labelled unsafe tool | E4–E7 |
| `multi_tool_set_metrics` | group recall, macro set precision, complete-set share; acceptable alternatives represented as groups | E9 |
| `qos_evidence_record` | retains declared/observed/attested/unknown provenance; observed/attested records require a definition hash | Evidence/QoS data integrity supporting E1, E3–E7, E15 |

## Evidence semantics

- `declared` means a provider or registry claim. It is not a measurement.
- `observed` means a measurement record. It must be bound to the exact tool definition hash.
- `attested` means a signed/attributed assertion. It is not silently relabelled as observed.
- `unknown` remains unknown.
- The helper records evidence status; it does not verify signatures, probe systems, establish publisher identity, or certify measurement validity.

The contract schema in `src/taas/contracts.py` currently has default QoS values
(`price=0.0`, `latency=1.0`, `fail=0.05`, `source="default"`). These defaults must
not be interpreted as empirical QoS. Evaluation pipelines must preserve the source and
evidence kind and exclude unsupported defaults from measured-QoS claims.

## Interpretation limits

- Retrieval coverage is not task success.
- Group recall and complete-set share are not independent joint-feasibility.
- Exp@k requires an independently established unsafe reference set; discovery predictions
  cannot serve as their own gold labels.
- Precision/recall computed over incomplete labels must expose unknowns and abstentions.
- A hash binding establishes record-to-definition association, not the truth of the record.
- No result produced by these functions alone establishes the paper's propositions or hypotheses.

## Validation

Focused unit tests are in `tests/test_evaluation_metrics.py`. The metric module was exercised
against six focused checks during implementation. A full repository test suite and CI run
have not yet been verified for this commit.
