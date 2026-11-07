"""Dependency and artifact gate for the canonical PaMCP E1-E22 programme.

This module never runs experiments or changes protocol status. It tells the workbench
whether the frozen inputs and prerequisite experiment artifacts are present.
"""
from __future__ import annotations

from typing import Iterable, Mapping


DEPENDENCIES = {
    "E1": (), "E2": ("E1",), "E3": ("E1",), "E4": ("E1","E2","E3"),
    "E5": ("E1","E2","E3"), "E6": ("E1","E2","E3"), "E7": ("E1","E2","E3"),
    "E8": ("E1","E2","E3"), "E9": ("E1","E2","E3","E12"),
    "E10": ("E2","E3","E9"), "E11": ("E12",),
    "E12": (), "E13": ("E2","E3","E12","E8","E9","E10"),
    "E14": ("E3","E10","E13"), "E15": ("E1",), "E16": ("E1",),
    "E17": ("E10","E13"), "E18": ("E8","E9","E10","E11","E13","E14"),
    "E19": ("E12","E13"), "E20": ("E13",), "E21": ("E13",),
    "E22": ("E8","E9","E10"),
}

REQUIRED_ARTIFACTS = {
    "E1": ("frozen_registry_snapshot", "independent_non_read_only_reference_labels"),
    "E2": ("independent_semantic_typing_labels",),
    "E3": ("hash_bound_observed_effect_records",),
    "E4": ("rankings", "unsafe_reference", "read_only_target_qrels"),
    "E5": ("rankings", "malicious_provider_assignments", "provider_mapping"),
    "E6": ("independent_unsafe_reference", "verifier_risk_scores"),
    "E7": ("property_strength_records"),
    "E8": ("single_tool_rankings", "single_tool_qrels"),
    "E9": ("multi_tool_rankings", "acceptable_goal_groups"),
    "E10": ("frozen_graph_and_goal_inputs", "submitted_certificates"),
    "E11": ("review_type_records", "calibrated_model_profile"),
    "E12": ("purpose_built_calibration_records",),
    "E13": ("confirmed_agent_trajectories", "external_task_oracle"),
    "E14": ("prompt_injection_trajectories", "independent_policy_oracle"),
    "E15": ("stage_timing_and_memory_records", "exact_and_greedy_objectives"),
    "E16": ("registry_event_replay_records", "full_recomputation_states"),
    "E17": ("counterexample_refinement_records",),
    "E18": ("complete_factorial_cell_records",),
    "E19": ("role_configuration_records",),
    "E20": ("weight_sensitivity_records",),
    "E21": ("confirmed_execution_trajectory_repository",),
    "E22": ("paired_e8_e9_e10_outcomes", "tool_disjoint_split_manifest"),
}

EXTERNAL_GATES = {
    "E11": ("E11 harness definition freeze",),
    "E12": ("calibration-set freeze",),
    "E15": ("implementation and benchmark freeze",),
    "E16": ("implementation and event-log freeze",),
    "E21": ("confirmed trajectory repository",),
}


def assess_experiment_readiness(
    experiment_id: str,
    *,
    available_artifacts: Iterable[str],
    completed_experiments: Iterable[str] = (),
    satisfied_external_gates: Iterable[str] = (),
) -> dict:
    """Return a conservative readiness assessment; no status is changed or inferred."""
    if experiment_id not in DEPENDENCIES:
        raise KeyError(f"Unknown protocol experiment {experiment_id}")
    artifacts = set(available_artifacts)
    completed = set(completed_experiments)
    gates = set(satisfied_external_gates)
    missing_artifacts = sorted(set(REQUIRED_ARTIFACTS[experiment_id]) - artifacts)
    missing_dependencies = sorted(set(DEPENDENCIES[experiment_id]) - completed)
    missing_gates = sorted(set(EXTERNAL_GATES.get(experiment_id, ())) - gates)
    ready = not (missing_artifacts or missing_dependencies or missing_gates)
    return {
        "experiment_id": experiment_id,
        "status": "ready_for_offline_evaluation" if ready else "blocked_missing_inputs_or_gates",
        "missing_artifacts": missing_artifacts,
        "missing_dependencies": missing_dependencies,
        "missing_external_gates": missing_gates,
        "protocol_status_mutated": False,
    }


def assess_programme_readiness(
    *, available_artifacts: Iterable[str],
    completed_experiments: Iterable[str] = (),
    satisfied_external_gates: Iterable[str] = (),
) -> list[dict]:
    """Assess all 22 experiments in protocol order."""
    return [
        assess_experiment_readiness(
            experiment_id, available_artifacts=available_artifacts,
            completed_experiments=completed_experiments,
            satisfied_external_gates=satisfied_external_gates,
        )
        for experiment_id in (f"E{i}" for i in range(1, 23))
    ]
