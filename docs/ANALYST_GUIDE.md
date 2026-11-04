# Analyst role: GoalSpec decomposition

The analyst receives the user's objective, optional user-provided context, and semantic type vocabulary Θ. It does not receive the tool registry. It proposes a declarative GoalSpec; it does not select tools, execute operations, or prove task fulfilment.

## Task

Decompose the objective into the smallest useful sequence of goals (typically 1–6). Each goal describes one operation. Express dependencies when a goal consumes another goal's output. Do not invent external facts, tools, servers, permissions, or successful outcomes.

## Canonical output contract

Return exactly one JSON object with only these top-level keys:
- prompt (optional string): preserve the user's objective faithfully.
- prompt_inputs (required array): types supplied by the objective; always include text.
- goals (required non-empty array): one operation per goal.

Example:

    {
      "prompt": "Summarise the latest reviews for product X",
      "prompt_inputs": ["text"],
      "goals": [
        {
          "id": "g1",
          "desc": "Retrieve recent reviews for product X",
          "class": "retrieve",
          "in": ["query"],
          "out": "record[]",
          "eff": ["read(db)"],
          "sigma": "data",
          "n": 100,
          "exactness": "tolerant",
          "deps": [],
          "lang": "en",
          "optional": false
        },
        {
          "id": "g2",
          "desc": "Summarise the retrieved reviews",
          "class": "summarise",
          "in": ["record[]"],
          "out": "text",
          "eff": [],
          "sigma": "native",
          "n": 100,
          "exactness": "tolerant",
          "deps": ["g1"],
          "lang": "en",
          "optional": false
        }
      ]
    }

Do not wrap the object in an id/query/context envelope. Do not add Markdown fences or explanatory prose. Do not emit tool or server names.

## Goal fields

- id: unique identifier matching [A-Za-z][A-Za-z0-9_-]{0,63}.
- desc: concise, non-empty description of the intended operation.
- class: model-side classes: classify, extract, summarise, translate, convert_format, write, plan, synthesise, aggregate, compute_exact, count, compare, answer; boundary-crossing classes: retrieve, search, fetch_web, store, send, transact, execute, navigate_browser, render_media, create_document, edit_document, random.
- in / out: exact semantic type strings listed in Θ.common_types. Do not synthesize kind:domain or array combinations. Use none when no artefact is produced.
- eff: required effects such as read(src), write(r), delete(r), exec, egress(dst), money, session. Use an empty array for pure reasoning.
- sigma: self-assessment native, data, effect, or unreliable. This is not trusted proof.
- n: positive integer estimate of processed items (1 when not applicable).
- exactness: exact or tolerant.
- deps: IDs of goals whose output this goal consumes.
- optional: boolean.
- lang: optional non-empty language label.

## Semantic vocabulary Θ

Kinds: text, document, table, record, media, credential, identifier, location, number, url, path, query, code, datetime, boolean, none.

Prefer domains from data/processed/theta.json. Use a lowercase singular domain only when the exact kind/domain/cardinality combination is present in Θ.common_types. Never construct a type merely because its kind and domain are individually declared. If the exact collection type is absent, use a declared generic type such as record[] and preserve the business concept in the goal description.

## Trust and validation boundaries

A generated object is only a proposal. The Studio API validates structure, field types, semantic types, effects, identifiers, dependency references and dependency cycles. Passing those checks does not establish semantic alignment, completeness, safety, policy authorization, tool availability, or task fulfilment. A human must review the objective-to-goal mapping before discovery. Unsupported output is rejected rather than silently repaired.


## Analytical intent preservation

The decomposition must preserve the requested operation, not merely the topic or data source.

- Distinguish **summarise** (produce a textual synopsis) from **aggregate** (compute a reduction such as sum, average, min, max, grouping, or count). Never substitute one for the other.
- For requests to calculate a total/sum of values, include an explicit `aggregate` or `compute_exact` goal. Its inputs must include the relevant numeric field or typed records that contain it, and its output must be `number` (or an explicitly typed numeric result).
- For financial amounts, preserve exact arithmetic intent with `exactness: "exact"` when the objective asks for a total. Do not silently round or estimate.
- If currency is unspecified and mixed currencies are possible, surface the ambiguity or ask for clarification; do not assume amounts in different currencies can be added.
- Do not invent a fixed collection size as a guarantee of completeness. `n` is an estimate, not proof that all matching records were retrieved.
- Preserve scope words such as "all", "every", and date/range constraints.
- A final answer goal may format a computed result, but must not replace the computation.

Examples:
- "Summarize transactions" → `summarise`, output `text`.
- "Calculate the total value of transactions" → retrieval (if required), then `aggregate`/`compute_exact`, output `number`.
- "Count transactions" → `count`, output `number`.

These rules guide generation. Runtime semantic diagnostics are deterministic heuristic warnings, not a semantic correctness proof. Human review remains mandatory.

## Scenario-independent decomposition

The analyst must handle the objective as an arbitrary user request, not as an instance of a known showcase, benchmark task, customer workflow or sample prompt.

- Never branch on a scenario name, benchmark ID, known entity, example filename, output directory or expected number of goals.
- Preserve every distinct requested outcome in a compound objective. Do not collapse the objective to one primary operation when it asks for acquisition, analysis, transformation, communication or artifact creation in combination.
- Decompose by the operations actually requested, not by a memorised sequence. A goal is included only when justified by the objective or necessary to produce a requested outcome.
- Distinguish user-supplied inputs from information that must be acquired. A noun in the objective is not proof that the corresponding data exists or was supplied.
- Distinguish producing content from persisting, publishing, sending or otherwise changing external state. Include the appropriate boundary-crossing goal and required effect when the objective requests that side effect.
- For every goal, choose input and output types only from the exact canonical Θ vocabulary. Preserve undeclared concepts in descriptions and diagnostics; do not invent a type or silently map to a neighbouring domain.
- Do not assume a source, connector, tool, destination, file system, execution environment, recipient, permission, business timezone or output location.
- Preserve explicit output requirements (format, destination, language, quality constraints and requested evidence). If a required detail is missing and cannot be safely left unresolved, surface a clarification rather than guessing.
- Do not add a verification or execution goal unless that class and its semantics are part of the canonical GoalSpec contract. Output verification belongs to a separately evidenced runtime boundary when such a capability exists.
- When the objective cannot be represented faithfully with the current canonical vocabulary, produce the best explicitly incomplete proposal only if the API contract permits it; otherwise abstain with a clear explanation. Never force the request into a nearby workflow.

The shared platform lifecycle, scenario-independence invariants and cross-domain acceptance matrix are specified in [Scenario-Agnostic Objective Engineering](studio/SCENARIO_AGNOSTIC_OBJECTIVE_ENGINEERING.md). This document is a design contract, not evidence that all listed capabilities are implemented.
