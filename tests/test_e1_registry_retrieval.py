from pathlib import Path
import sys

# The project installs the runtime package from src/, while experiments/ is a
# repository-level research directory and is intentionally not part of the wheel.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experiments.e1_registry_retrieval import group_ranks, metrics_at_k, resolved_gold_groups, task_metrics


def test_ambiguous_gold_mapping_is_one_any_of_group():
    class Task:
        gold_tools = ["server-a::search|server-b::search", "server-c::read"]
        gold_unresolved = ["missing::tool"]

    groups, unresolved = resolved_gold_groups(
        Task(), {"server-a::search", "server-b::search", "server-c::read"}
    )
    assert groups == [
        {"server-a::search", "server-b::search"},
        {"server-c::read"},
    ]
    assert unresolved == 1


def test_group_rank_uses_first_ranked_alternative_and_counts_group_once():
    ranking = ["s::alternative-a", "s::alternative-b", "s::other"]
    groups = [{"s::alternative-a", "s::alternative-b"}, {"s::other"}]
    assert group_ranks(ranking, groups) == [1, 3]


def test_group_metrics_do_not_double_count_ambiguous_alternatives():
    groups = [{"s::a", "s::b"}, {"s::c"}]
    result = task_metrics(["s::a", "s::b", "s::c"], groups, ks=(1, 2, 3))
    assert result["at_k"]["2"]["group_recall"] == 0.5
    assert result["at_k"]["2"]["group_precision"] == 0.5
    assert result["at_k"]["3"]["group_recall"] == 1.0


def test_unresolved_only_task_has_no_evaluable_groups():
    class Task:
        gold_tools = ["unknown::tool"]
        gold_unresolved = ["another::missing"]

    groups, unresolved = resolved_gold_groups(Task(), {"known::tool"})
    assert groups == []
    assert unresolved == 2
