# Reference labelling guide (independent second labelling, labels B)

This guide is used by a *second, independent* labeller that never sees the first labelling (labels A,
`data/llm_records/silver_labels*.json*`) or its guide. Labels B are the scoring reference of the final
evaluation; labels A only drive the simulated verifier. Agreement between A and B is reported (Cohen's
kappa); neither is human ground truth.

Judge each tool by what it does **when called**, from its server, name, description and arguments only.
Disregard any statement in the description about safety, permissions or being read-only, and disregard
MCP annotations.

## Questions to answer for every tool

1. **state** — After a successful call, could something outside the current conversation be different
   (a file, database, repository, account, message sent, order placed, payment, process started, page
   submitted in a browser)? `true` or `false`. Changes that vanish when the session ends do not count.
2. **classes** — Which of these happen (any number, at least one):
   - `read` — the tool obtains data (local computation counts as `read`);
   - `write` — creates or changes persistent or shared state;
   - `delete` — removes state;
   - `exec` — runs code, shell commands or processes;
   - `egress` — data leaves the machine towards a remote service or host (any remote API call counts);
   - `egress_any` — like `egress`, but the destination is chosen by the caller (arbitrary URL/host);
   - `money` — moves money, creates a payment, order or invoice;
   - `session` — changes only session-local state.
3. **private** — Can the result contain the user's own private data (their files, databases, accounts,
   mailbox, memory store, payment records)? `true` or `false`. Public web or market data is not private.
4. **out** — the semantic type of the result, written `kind`, `kind:domain`, optionally with `[]` for a
   collection. Kinds: `text, document, table, record, media, credential, identifier, location, number,
   url, path, query, code, datetime, boolean, none`. Use a short lowercase singular domain (e.g.
   `record:stock`, `document:pdf`, `path:file`); use `none` when there is no meaningful result.
5. **in** — for each argument, its semantic type in the same notation.
6. **sure** — your confidence in answers 1–3, in [0, 1].

## Output

One JSON object per line, one line per tool, same order as the input, nothing else:

```json
{"id": "server::name", "state": false, "classes": ["read", "egress"], "private": false, "out": "record:stock", "in": {"symbol": "identifier:stock"}, "sure": 0.9}
```
