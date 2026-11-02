"""TaaS adapter for the Accenture MCP-Bench execution protocol.

The adapter transforms MCP-Bench's discovered tool catalogue into TaaS contracts,
obtains a GoalSpec from an injected analyst, runs discovery/certification, and returns
the selected subset in MCP-Bench's native tool-map shape. MCP-Bench remains responsible
for task execution and evaluation.
"""
from __future__ import annotations
from contextlib import contextmanager
from dataclasses import dataclass
import time
from typing import Any, Callable, Iterator, Mapping

from .contracts import extract_contract
from .data.registries import RawTool
from .engine import DiscoveryEngine, DiscoveryResult, EngineConfig
from .goals import vocabulary_report
from .model_profile import ModelProfile
from .policy import Policy
from .provenance import DEFAULT_TRUST, TrustPolicy

GoalSpecFactory = Callable[[str], dict[str, Any]]


@dataclass
class MCPBenchSelection:
    tools: dict[str, dict[str, Any]]
    discovery: DiscoveryResult
    trace: dict[str, Any]


def raw_tools_from_mcpbench(tool_map: Mapping[str, Mapping[str, Any]]) -> tuple[list[RawTool], dict[str, str]]:
    """Convert MCP-Bench's server:tool catalogue to TaaS RawTool records.

    Returns a mapping from TaaS's server::tool identity to the original MCP-Bench key.
    No benchmark task labels or gold mappings are consulted.
    """
    raw: list[RawTool] = []
    key_by_id: dict[str, str] = {}
    for key, info0 in tool_map.items():
        info = dict(info0)
        server = str(info.get("server") or key.split(":", 1)[0])
        name = str(info.get("original_name") or info.get("name") or key.split(":", 1)[-1])
        tool_id = f"{server}::{name}"
        if tool_id in key_by_id:
            raise ValueError(f"Duplicate MCP tool identity in MCP-Bench catalogue: {tool_id}")
        raw.append(RawTool(
            server=server,
            name=name,
            description=str(info.get("description") or ""),
            input_schema=info.get("input_schema") or info.get("inputSchema") or {},
            output_schema=info.get("output_schema") or info.get("outputSchema"),
            annotations=info.get("annotations"),
            source="MCP-Bench-live",
            category=str(info.get("category") or ""),
            extra={k: v for k, v in info.items()
                   if k not in {"server", "original_name", "name", "description", "input_schema",
                                "inputSchema", "output_schema", "outputSchema", "annotations", "category"}},
        ))
        key_by_id[tool_id] = key
    return raw, key_by_id


@contextmanager
def selected_task_executor_scope(
    server_manager: Any,
    selected_tools: Mapping[str, Mapping[str, Any]],
) -> Iterator[dict[str, Any]]:
    """Scope the executor's server catalogue while preserving evaluator visibility.

    MCP-Bench's TaskExecutor snapshots server_manager.all_tools in __init__.
    Construct it inside this scope. The connection manager's all_tools snapshot
    remains untouched, and the server manager is restored even on errors.
    """
    original = server_manager.all_tools
    unknown = set(selected_tools) - set(original)
    if unknown:
        raise ValueError(f"Selection contains tools absent from live catalogue: {sorted(unknown)}")
    filtered = {key: original[key] for key in selected_tools}
    server_manager.all_tools = filtered
    try:
        yield filtered
    finally:
        server_manager.all_tools = original

@contextmanager
def selected_tool_catalogue_scope(
    server_manager: Any,
    selected_tools: Mapping[str, Mapping[str, Any]],
) -> Iterator[None]:
    """Backward-compatible catalogue scope for existing MCP-Bench integrations."""
    with selected_task_executor_scope(server_manager, selected_tools):
        yield


class TaaSMCPBenchAdapter:
    """Pre-execution discovery stage for MCP-Bench.

    goal_spec_factory returns the paper's GoalSpec JSON shape. It is injected so the
    experiment can use its configured LLM provider and account for analyst overhead.
    """

    def __init__(
        self,
        profile: ModelProfile,
        goal_spec_factory: GoalSpecFactory,
        policy: Policy,
        trust: TrustPolicy = DEFAULT_TRUST,
        engine_config: EngineConfig | None = None,
        typing: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> None:
        """``typing`` is the LLM-assisted contract typing of Section 6.1 (``in``, ``out``, ``class``)
        keyed by TaaS tool id ``server::name``, produced offline for the discovered catalogue.
        An entry carrying ``hash`` is used only while it matches the live definition hash h(t);
        a changed definition falls back to lexical typing (the rug-pull rule of Algorithm 3B).
        Without ``typing`` every contract is typed lexically, which rarely matches analyst types."""
        self.profile = profile
        self.goal_spec_factory = goal_spec_factory
        self.policy = policy
        self.trust = trust
        self.engine_config = engine_config or EngineConfig()
        self.typing = dict(typing or {})

    def select(self, task: str, all_tools: Mapping[str, Mapping[str, Any]]) -> MCPBenchSelection:
        raw_tools, key_by_id = raw_tools_from_mcpbench(all_tools)
        if not raw_tools:
            raise ValueError("MCP-Bench supplied an empty tool catalogue")
        analyst_started = time.perf_counter()
        goal_spec = self.goal_spec_factory(task)
        analyst_time_s = time.perf_counter() - analyst_started
        if not isinstance(goal_spec, dict) or not isinstance(goal_spec.get("goals"), list):
            raise ValueError("goal_spec_factory must return a GoalSpec dictionary with a goals array")

        contracts, typed, stale = [], 0, []
        for t in raw_tools:
            ty = self.typing.get(t.id)
            if ty is not None and ty.get("hash") not in (None, t.definition_hash()):
                stale.append(t.id)
                ty = None
            typed += ty is not None
            contracts.append(extract_contract(t, dict(ty) if ty is not None else None))
        engine = DiscoveryEngine(contracts, self.profile, trust=self.trust, cfg=self.engine_config)
        result = engine.discover(goal_spec, self.policy)
        if result.abstained:
            selected: dict[str, dict[str, Any]] = {}
        else:
            selected_ids = set(result.toolkit or [])
            selected_keys = {key_by_id[x] for x in selected_ids if x in key_by_id}
            selected = {key: dict(value) for key, value in all_tools.items() if key in selected_keys}

        counterexample = result.counterexample
        trace = {
            "adapter": "taas-mcpbench/0.1",
            "registry_tool_count": len(all_tools),
            "selected_tool_count": len(selected),
            "selected_tool_keys": sorted(selected),
            "abstained": result.abstained,
            "analyst_time_s": analyst_time_s,
            "analyst_prompt_version": getattr(self.goal_spec_factory, "prompt_version", None),
            "analyst_usage": getattr(self.goal_spec_factory, "last_usage", {}),
            "analyst_raw_response": getattr(self.goal_spec_factory, "last_response", None),
            "discovery_time_s": result.time_s,
            "taas_pre_execution_time_s": analyst_time_s + result.time_s,
            "goal_spec": goal_spec,
            "goal_spec_vocabulary": vocabulary_report(goal_spec),
            "contract_typing": {"llm_typed": typed, "lexical": len(raw_tools) - typed, "stale_hash": stale},
            "gap": [g.id for g in result.gap.gap],
            "gap_shrink": [g.id for g in result.gap.shrink],
            "rho": result.gap.rho,
            "certificate": result.certificate.to_dict() if result.certificate is not None else None,
            "counterexample": (
                counterexample.to_dict()
                if counterexample is not None else None
            ),
            "manifest": result.manifest,
            "composition_stats": result.compose.stats,
        }
        return MCPBenchSelection(selected, result, trace)
