# ToolScope merger: semantic-equivalence judgements

ToolScope (ACL 2026) merges tools that are semantically equivalent, using an LLM as a binary classifier on
candidate pairs found by embedding similarity. Two tools are **equivalent** when either could serve every
request the other serves: same operation on the same kind of object, compatible arguments and the same
kind of result (server and naming may differ). Tools that are related but differ in operation (get vs
list, read vs write), scope (one file vs a directory) or target platform-specific data are **not**
equivalent.

For each input pair output one JSON line: {"pair": "<pair id>", "equivalent": true|false}
