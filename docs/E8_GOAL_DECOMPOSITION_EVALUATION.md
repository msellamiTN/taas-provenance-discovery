# E8 — Agent LLM prompt decomposition and semantic validity

## Purpose

Evaluate the analyst/Agent LLM that transforms a user request into a GoalSpec. This is
separate from MCP tool retrieval, TaaS discovery certificates, and runtime task success.

## Current implementation boundary

The Studio API currently validates GoalSpec structure and dependency-DAG consistency.
Its response explicitly reports `semantic_correctness_verified: false`. The existing
`AnthropicAnalyst` backend can make live decomposition calls, but the existing E3
experiment primarily replays previously recorded Claude outputs. E8 adds a live,
repeatable acceptance evaluation; it does not claim a live model was run by CI.

## Protocol

1. Send only the natural-language prompt and the analyst instructions/type vocabulary.
2. Do not send the tool registry, benchmark gold tool chains, rubric, expected goals, or evaluator annotations.
3. Capture the raw GoalSpec response and model identifier for reproducibility.
4. Validate JSON shape, unique goal IDs, dependency references, and acyclic dependencies.
5. Score one-to-one semantic matches against evaluator-only requirements: operation class,
   output kind, required effects, and goal description intent.
6. Report goal precision/recall/F1, DAG validity, and forbidden side effects separately.

The one-to-one matcher prevents one broad goal from satisfying multiple required subtasks.
Forbidden effects are evaluated independently of the matching score.

## Acceptance cases

The initial five cases cover:
- external research + synthesis + Markdown file creation at an exact path;
- repository issue retrieval + summarisation + Slack posting;
- exact aggregation from a local CSV + file output;
- current weather retrieval + concise answer;
- pure reasoning with no external effects.

The rubric is expert-authored and intentionally small. It is a regression/acceptance set,
not a statistically representative gold benchmark. A larger evaluation requires independent
double annotation, adjudication, inter-annotator agreement, and a held-out test split.

## Run

```bash
pip install -e '.[test,llm,studio]'
export ANTHROPIC_API_KEY=...
python experiments/e8_goal_decomposition.py --model claude-sonnet-4-5
```

Outputs are written to `results/e8_goal_decomposition.json`. Optionally persist raw model
responses with `--record-to results/e8_raw.jsonl`. Do not commit API keys or raw prompts
containing private data.

## Interpretation and limits

- High structural validity does not imply semantic validity.
- High goal recall with low precision indicates over-decomposition or hallucinated subtasks.
- Missing effects can hide required boundary crossings; extra effects can violate least privilege.
- Dependency validity checks graph structure, not whether the dependency relation is semantically correct.
- Goal-level matching does not prove output quality or task completion.
- The current rubric does not yet independently score every field (input types, cardinality,
  exactness, language, optionality, sigma calibration, and dependency semantics). These are
  explicit next additions before using E8 as a paper-grade benchmark.
- The evaluator must remain offline from discovery and execution. Never expose its rubric to the analyst.
