# Analyst role: goal specification (Algorithm 1, line 2)

This is the instruction given to the LLM in the **analyst role**. The analyst sees the prompt and the
type vocabulary Θ only — never the tool registry. It writes goal contracts in a fixed JSON schema;
the engine then verifies every self-assessment against the executing model's measured profile.

## Task

Decompose the user prompt into the subtasks (goals) needed to fulfil it. For each goal give a
class, typed inputs and output, permitted effects, an input-size estimate, an exactness requirement,
dependencies, and your self-assessment of whether *you, the language model*, can do it natively
from text in your context.

## Output schema (one JSON object per prompt)

```json
{"id": "<prompt id>",
 "prompt_inputs": ["text", "identifier:repo", "path:file"],
 "goals": [
   {"id": "g1", "desc": "retrieve the reviews", "class": "retrieve", "in": ["query"],
    "out": "record:review[]", "eff": ["read(db)"], "sigma": "data", "n": 300,
    "exactness": "tolerant", "lang": "en", "deps": [], "optional": false}
 ]}
```

* **prompt_inputs** — types the prompt itself provides (always include `text`; add identifiers, paths,
  URLs, locations, dates or numbers that the prompt states explicitly).
* **class** — model-side classes: `classify, extract, summarise, translate, convert_format, write, plan,
  synthesise, aggregate, compute_exact, count, compare, answer`; boundary-crossing classes:
  `retrieve, search, fetch_web, store, send, transact, execute, navigate_browser, render_media,
  create_document, edit_document, random`.
* **in / out** — semantic types `kind`, `kind:domain` or `kind:domain[]` from Θ below. For a goal whose
  purpose is an effect (writing a file, sending a message) use the type of the artefact it creates if it
  has one (`document:pdf`, `document:slide`, `path:file`), otherwise `none`.
* **eff** — effects the goal legitimately requires: `read(src)`, `write(r)`, `delete(r)`, `exec`,
  `egress(dst)`, `money`, `session`. Leave empty for pure reasoning.
* **sigma** — your self-assessment: `native` (you can do it from text already in context, reliably),
  `data` (needs external data not in context), `effect` (needs an external effect),
  `unreliable` (you could attempt it but not reliably at this size/exactness).
* **n** — expected number of input items/records the goal processes (1 if not applicable).
* **exactness** — `exact` when an exact number/match is required, else `tolerant`.
* **deps** — ids of goals whose output this goal consumes.
* **optional** — true for nice-to-have goals not required by the prompt.

Keep goals at the granularity of one operation each (typically 1–6 goals). Do not name tools or
servers. Be honest in `sigma`: it will be checked.

## Θ — kinds (closed)

`text, document, table, record, media, credential, identifier, location, number, url, path, query,
code, datetime, boolean, none`

## Θ — domains used by the registry (prefer these)

See `data/processed/theta.json` (`domains`). Use a domain only when it adds meaning; a new lowercase
singular domain term is allowed when none fits.
