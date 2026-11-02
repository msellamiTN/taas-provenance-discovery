"""MCP-Bench-compatible GoalSpec analyst for TaaS.

The analyst sees only the task text. It must not see MCP tool catalogues, benchmark gold
mappings, task dependency annotations, fuzzy/concrete paired descriptions, or evaluator
materials. Its output is a hypothesis about the task contract, not ground truth.
"""
from __future__ import annotations
from typing import Any, Protocol


SYSTEM_PROMPT = """You are the TaaS goal-contract analyst.
Convert the user's task into a structured GoalSpec for capability-gap analysis.
You are NOT a tool selector. Do not name, guess, recommend, or invent MCP servers or tools.
Use only the task text supplied by the user. Do not assume access to external data or APIs.
Return one JSON object and no Markdown.

Each goal has:
- id: unique short identifier
- class: one of retrieve, search, fetch_web, store, send, transact, execute,
  navigate_browser, render_media, create_document, edit_document, classify, extract,
  summarise, translate, convert_format, write, plan, synthesise, aggregate, compute_exact,
  count, compare, answer, random
- in: array of semantic input type strings
- out: semantic output type string
- eff: array of scoped effects, using forms such as read(*), write(document), delete(*),
  egress(*), execute(*), transact(*), or session
- sigma: native, data, effect, or unreliable
- n: estimated number of records/items, default 1
- exactness: tolerant or exact
- lang: language code, default en
- deps: IDs of prerequisite goals
- optional: boolean
- desc: concise goal description

Goal decomposition rules:
1. Split multi-step tasks into atomic goals and encode genuine dependencies.
2. Use data for goals requiring retrieval from an external source, service, database,
   filesystem, or remote API; use effect for requested state changes or external actions.
3. Use native only for transformations that can be completed from information already
   present in the task context; never assume tools or hidden data.
4. Use unreliable only when the task explicitly requires a model capability beyond
   ordinary reliable generation (for example exact large-scale computation).
5. Describe required data types with domain qualifiers where supported, e.g. repository[],
   openapi_spec, weather_observation[], document, structured_report, json.
6. Add effects only when explicitly required by the task. Do not infer hidden side effects.
7. Do not create dependencies merely because goals are listed in sequence.
8. prompt_inputs should normally contain text plus any explicitly supplied input types.
9. If the task is underspecified, represent the uncertainty in a goal description rather
   than inventing missing facts.

JSON shape:
{"prompt_inputs":["text"],"goals":[{"id":"g1","class":"search","in":["query"],"out":"repository[]","eff":["read(*)"],"sigma":"data","n":1,"exactness":"tolerant","lang":"en","deps":[],"optional":false,"desc":"..."}]}
"""


class CompletionProvider(Protocol):
    def get_completion(self, system_prompt: str, user_prompt: str, max_tokens: int, **kwargs) -> Any: ...
    def clean_and_parse_json(self, raw_json: str) -> Any: ...


class MCPBenchGoalAnalyst:
    """Callable GoalSpec factory using an MCP-Bench LLM provider.

    Usage: analyst = MCPBenchGoalAnalyst(llm_provider); goal_spec = analyst(task)
    The last_response and last_usage fields should be persisted in the per-task sidecar.
    """

    def __init__(self, llm_provider: CompletionProvider, max_tokens: int = 4000) -> None:
        self.llm = llm_provider
        self.max_tokens = max_tokens
        self.last_response: str | None = None
        self.last_usage: dict[str, Any] = {}
        self.prompt_version = "taas-goal-spec-analyst/1.0"

    def __call__(self, task: str) -> dict[str, Any]:
        prompt = "TASK (the only information source):\n" + task + (
            "\n\nReturn the GoalSpec JSON object. Do not include tool names or tool IDs."
        )
        try:
            response = self.llm.get_completion(SYSTEM_PROMPT, prompt, self.max_tokens, return_usage=True)
        except TypeError:
            response = self.llm.get_completion(SYSTEM_PROMPT, prompt, self.max_tokens)
        if isinstance(response, tuple):
            self.last_response = response[0]
            self.last_usage = response[1] or {}
        else:
            self.last_response = response
            self.last_usage = {}
        parsed = self.llm.clean_and_parse_json(self.last_response or "")
        self._validate(parsed)
        return parsed

    @staticmethod
    def _validate(value: Any) -> None:
        if not isinstance(value, dict) or not isinstance(value.get("goals"), list):
            raise ValueError("Goal analyst output must be an object containing a goals array")
        ids = []
        for goal in value["goals"]:
            if not isinstance(goal, dict):
                raise ValueError("Each goal must be a JSON object")
            for field in ("id", "class", "in", "out", "sigma", "deps", "desc"):
                if field not in goal:
                    raise ValueError(f"Goal is missing required field: {field}")
            if not isinstance(goal["in"], list) or not isinstance(goal["deps"], list):
                raise ValueError("Goal fields 'in' and 'deps' must be arrays")
            if goal["sigma"] not in {"native", "data", "effect", "unreliable"}:
                raise ValueError("Invalid sigma value")
            ids.append(str(goal["id"]))
        if len(ids) != len(set(ids)):
            raise ValueError("Goal IDs must be unique")
        known = set(ids)
        for goal in value["goals"]:
            unknown = set(map(str, goal["deps"])) - known
            if unknown:
                raise ValueError(f"Unknown goal dependencies: {sorted(unknown)}")
        if not isinstance(value.get("prompt_inputs", ["text"]), list):
            raise ValueError("prompt_inputs must be an array")
