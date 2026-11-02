# MCP-Bench TaaS runner integration

Target upstream repository: https://github.com/Accenture/mcp-bench
Pinned upstream revision: 7a8eaeae83a842a2949080acc5473f65e1569daf
Target file: benchmark/runner.py

IMPORTANT: runner.patch.template is illustrative and is NOT directly applicable.
It contains placeholder line/context hunks. Resolve exact context against the pinned
checkout, generate a real diff, then validate it with git apply --check. Do not apply
with fuzz or to a different upstream revision.

Intended behavior:
- Opt-in only; runner.taas_adapter defaults to None.
- Discovery runs after server connection and before TaskExecutor construction.
- TaskExecutor snapshots only the selected catalogue.
- The live server manager is restored before execute(), so call_tool can dispatch.
- Abstentions bypass execution and judge scoring, and are returned as status=abstained.
- The complete available_tools catalogue remains available to the evaluator.
- The TaaS trace is attached as a sidecar; task and gold data are not modified.

Configure runner.taas_adapter with a TaaSMCPBenchAdapter instance containing a
GoalSpec factory, model profile, and policy. No default analyst or policy is invented.