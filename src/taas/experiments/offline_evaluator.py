"""Single offline dispatch surface for E1-E22 evaluator payloads.

Payloads must contain frozen, protocol-approved records. This dispatcher performs
analysis only; it never retrieves tools, executes MCP calls, generates labels, or
mutates experiment status.
"""
from __future__ import annotations

from typing import Mapping

from .evaluation_metrics import (
    certificate_check_metrics, multi_tool_set_metrics, retrieval_metrics,
)
from .provenance_policy_evaluators import (
    effect_discrepancy, malicious_provider_exposure_curve, policy_encoding_metrics,
    policy_threshold_pareto, probe_coverage, trust_threshold_sweep,
    verifier_threshold_sweep,
)
from .registry_typing_evaluators import (
    registry_characterization, semantic_typing_metrics, typing_threshold_curve,
)
from .gap_execution_factorial_evaluators import (
    capability_gap_metrics, end_to_end_metrics, factorial_effects, prompt_injection_metrics,
)
from .calibration_refinement_roles_experience import (
    experience_reuse_metrics, model_profile_calibration, refinement_metrics,
    role_configuration_metrics,
)
from .scalability_sensitivity_statistics import (
    adjust_pvalues, exact_greedy_gap, evolution_replay_metrics, paired_sign_flip,
    percentile_bootstrap, rank_stability, scalability_summary, weight_sensitivity,
)


def _need(payload: Mapping, *keys):
    missing = [key for key in keys if key not in payload]
    if missing:
        raise ValueError(f"Payload missing required fields: {missing}")


def evaluate_payload(experiment_id: str, payload: Mapping) -> dict:
    """Dispatch one frozen payload to its protocol experiment evaluator."""
    eid = experiment_id.upper()
    if eid == "E1":
        _need(payload, "registry_rows")
        return registry_characterization(payload["registry_rows"])
    if eid == "E2":
        _need(payload, "reference", "predictions")
        result = semantic_typing_metrics(payload["reference"], payload["predictions"],
                                         confidence_threshold=payload.get("confidence_threshold", 0.0))
        if "thresholds" in payload:
            result["threshold_curve"] = typing_threshold_curve(
                payload["reference"], payload["predictions"], payload["thresholds"])
        return result
    if eid == "E3":
        _need(payload, "declared", "observed", "definition_hashes", "observed_hashes", "probeable_tool_ids")
        return {
            "discrepancy": effect_discrepancy(payload["declared"], payload["observed"],
                                              payload["definition_hashes"], payload["observed_hashes"]),
            "coverage": probe_coverage(payload["declared"], payload["observed"],
                                       payload["definition_hashes"], payload["observed_hashes"],
                                       payload["probeable_tool_ids"]),
        }
    if eid == "E4":
        _need(payload, "rankings", "unsafe_reference", "read_only_target_qrels", "encodings")
        return {name: policy_encoding_metrics(
            payload["rankings"], payload["unsafe_reference"], payload["read_only_target_qrels"],
            config["eligible_tools"], int(payload.get("k", 5)))
            for name, config in payload["encodings"].items()}
    if eid == "E5":
        _need(payload, "rankings", "provider_by_tool", "malicious_provider_sets")
        return {"exposure_curve": malicious_provider_exposure_curve(
            payload["rankings"], payload["provider_by_tool"], payload["malicious_provider_sets"],
            int(payload.get("k", 5)))}
    if eid == "E6":
        _need(payload, "reference_unsafe", "risk_scores", "thresholds")
        return {"verifier_operating_curve": verifier_threshold_sweep(
            payload["reference_unsafe"], payload["risk_scores"], payload["thresholds"])}
    if eid == "E7":
        _need(payload, "property_strengths", "required_properties", "thresholds",
              "exposure_by_threshold", "utility_by_threshold")
        sweep = trust_threshold_sweep(payload["property_strengths"], payload["required_properties"],
                                      payload["thresholds"])
        return {"threshold_sweep": sweep, "pareto": policy_threshold_pareto(
            sweep, payload["exposure_by_threshold"], payload["utility_by_threshold"])}
    if eid == "E8":
        _need(payload, "rankings", "relevant")
        return retrieval_metrics(payload["rankings"], payload["relevant"], ks=(1, 5, 10))
    if eid == "E9":
        _need(payload, "selected", "required_groups")
        return multi_tool_set_metrics(payload["selected"], payload["required_groups"])
    if eid == "E10":
        _need(payload, "independent_audits")
        return certificate_check_metrics(payload["independent_audits"])
    if eid == "E11":
        _need(payload, "records")
        return capability_gap_metrics(payload["records"])
    if eid == "E12":
        _need(payload, "records")
        return model_profile_calibration(payload["records"], tau=float(payload.get("tau", .9)),
                                         replicates=int(payload.get("replicates", 10000)),
                                         seed=int(payload.get("seed", 0)))
    if eid == "E13":
        _need(payload, "records")
        return end_to_end_metrics(payload["records"])
    if eid == "E14":
        _need(payload, "records")
        return prompt_injection_metrics(payload["records"])
    if eid == "E15":
        _need(payload, "timing_records", "exact_greedy_pairs")
        return {
            "scalability": scalability_summary(payload["timing_records"]),
            "exact_greedy_gaps": [exact_greedy_gap(**row) for row in payload["exact_greedy_pairs"]],
        }
    if eid == "E16":
        _need(payload, "events")
        return evolution_replay_metrics(payload["events"])
    if eid == "E17":
        _need(payload, "records")
        return refinement_metrics(payload["records"])
    if eid == "E18":
        _need(payload, "factorial_cells", "outcome")
        return factorial_effects(payload["factorial_cells"], str(payload["outcome"]))
    if eid == "E19":
        _need(payload, "records")
        return role_configuration_metrics(payload["records"])
    if eid == "E20":
        _need(payload, "toolkits_by_weight")
        return weight_sensitivity(payload["toolkits_by_weight"], payload.get("outcomes_by_weight"))
    if eid == "E21":
        _need(payload, "records")
        return experience_reuse_metrics(payload["records"])
    if eid == "E22":
        _need(payload, "paired_differences", "confirmatory_p_values", "exploratory_p_values",
              "rankings", "bootstrap_values")
        return {
            "paired_tests": {name: paired_sign_flip(values, seed=int(payload.get("seed", 0)))
                             for name, values in payload["paired_differences"].items()},
            "holm_confirmatory": adjust_pvalues(payload["confirmatory_p_values"], "holm"),
            "bh_exploratory": adjust_pvalues(payload["exploratory_p_values"], "bh"),
            "rank_stability": rank_stability(payload["rankings"]),
            "bootstrap": {name: percentile_bootstrap(values, seed=int(payload.get("seed", 0)))
                          for name, values in payload["bootstrap_values"].items()},
        }
    raise KeyError(f"Unknown protocol experiment: {experiment_id}")
