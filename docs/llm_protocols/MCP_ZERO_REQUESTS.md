# MCP-Zero active tool requests (round 1)

Reproduces the request step of MCP-Zero (Fei et al., 2025): the agent itself decides which capabilities it
lacks and writes, for each, a structured request with two fields.

* `server` — the platform or permission domain the tool would belong to (e.g. "file system", "GitHub",
  "map service", "web search engine", "stock market data").
* `tool` — the operation type and its target (e.g. "read the content of a text file", "search route between
  two places", "get historical prices of a stock").

Rules: write one request per capability the task needs and that you cannot perform from your own knowledge
and reasoning (writing, summarising, simple arithmetic, translation and similar are done by you and get no
request). Order the requests in the order they would be used. Do not name concrete tools; describe the
capability. Use English. Between 0 and 6 requests per task.

Output, one JSON object per line per task, same order as the input:

    {"id": "<task id>", "requests": [{"server": "...", "tool": "..."}, ...]}
