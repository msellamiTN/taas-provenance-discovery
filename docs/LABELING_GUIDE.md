# Silver labelling guide (LLM-produced ground truth J and typed contracts)

This guide is given verbatim to the LLM that labels each tool of the merged registry.
The labels play two roles in the experiments, kept strictly apart:

* `effects`, `modifies_state`, `private_source` — the **silver ground truth J** of the
  effect relation (what the tool really does to the world). The engine never sees these as
  evidence except through the *simulated verifier* of the experiments (H2), which reads J with
  a controlled false-accept rate.
* `in`, `out`, `class` — the **LLM-assisted typing τ** of the contract (Section 5, "Semantic
  typing"; Section 6.1, "typed inference over the description"). These *are* used by the engine.

Labels must describe what the tool **actually does when called**, judged from its name,
description and arguments. Ignore any claims of safety in the description; ignore annotations.

## Output format

One JSON object per line (JSONL), one line per tool, in the same order as the input:

```json
{"id": "server::name", "effects": ["read(web)", "egress(api.example)"], "modifies_state": false, "private_source": false, "in": {"symbol": "identifier:stock"}, "out": "record:stock", "class": "retrieve", "conf": 0.9}
```

## Fields

**effects** — list of scoped effect labels `class(scope)`; classes:

| class | meaning | scope examples |
|---|---|---|
| `read(src)` | reads data from a source | `read(fs)`, `read(db)`, `read(web)`, `read(api)`, `read(memory)`, `read(local)` |
| `write(r)` | creates or modifies persistent/shared state | `write(fs)`, `write(db)`, `write(github)`, `write(memory)`, `write(browser)`, `write(doc)` |
| `delete(r)` | deletes state | `delete(fs)`, `delete(github)` |
| `exec` | runs code, shell commands or processes | `exec` |
| `egress(dst)` | sends data to an external host / third party | `egress(*)` (arbitrary URL), `egress(api.openweathermap)`, `egress(slack)` |
| `money` | moves money or creates a payment/order/invoice | `money` |
| `session` | creates or mutates session-local state only (lost when the session ends) | `session` |

Rules: a call to any remote API counts as `egress(<host or service>)` in addition to `read(api)`;
a tool that takes an arbitrary URL is `egress(*)`. Pure local computation (calculator, random
number, time, text transform) is `read(local)` only. Browser automation that clicks/types/navigates
is `write(browser)` + `egress(*)`. Generating a file on disk is `write(fs)`.

**modifies_state** — `true` iff the tool modifies persistent, shared or external state
(any write/delete/exec/money; posting/sending a message; placing an order). Session-only state
(`session`) does not count. This is the "is NOT read-only" ground truth.

**private_source** — `true` iff the output can contain the principal's private data
(local files, databases, private accounts, memory stores, email, payment records).

**in** — map from each argument name to a semantic type; **out** — the semantic type of the result.
Semantic types are written `kind`, `kind:domain` or with `[]` for collections, e.g. `record:stock[]`.

Kinds (closed): `text, document, table, record, media, credential, identifier, location, number,
url, path, query, code, datetime, boolean, none` (`none` = no meaningful output).

Domains (prefer these; add a new lowercase singular term only when none fits):
`stock, crypto, currency, company, weather, route, place, map, review, repo, issue, package,
paper, article, news, web, search_result, message, email, channel, file, directory, word, slide,
sheet, pdf, chart, image, video, audio, transcript, entity, memory, task, calendar, event, product,
order, payment, invoice, person, game, champion, card, recipe, train, flight, hotel, listing, sql,
code, component, icon, whois, trend, metadata, book, music, artwork, medical, dataset, container,
process, commit, page, element, time, horoscope, chess, number`.

**class** — the operation class, one of:
`retrieve, search, fetch_web, compute_exact, aggregate, convert_format, render_media,
create_document, edit_document, store, send, transact, execute, navigate_browser, plan,
summarise, extract, classify, translate, generate_text, random, other`.

**conf** — your confidence in the effect labels, in [0, 1].
