# COLT training queries (ToolLens-style)

COLT (Qu et al., 2024) is trained on queries labelled with the *set* of tools that solve them together
("scenes"). The MCP registries have no such training set, so one is generated as ToolLens was: each input
scene is a group of 2-3 tools; write ONE natural, realistic user request that needs every tool of the scene
to be solved, without naming the tools, servers or function names. Vary style and length (10-40 words),
mention concrete values (file names, places, symbols) where natural. Do not reuse wording from the tool
descriptions verbatim.

Output, one JSON object per line per scene: {"scene": "<scene id>", "query": "...", "tools": ["id", ...]}
(`tools` copied unchanged from the input).
