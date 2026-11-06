# UX-3 — Tool Registry Workspace

Status: implementation branch `codex/ux3-tool-registry-workspace`, stacked on UX-2 head `0efdc00e2825b7345e8b6d5639b405bcddfe9a9c`.

## Objective

Make the existing Core-backed Tool Registry useful for engineering review while keeping Core authoritative for registry data and discovery.

## Delivered in this increment

- **Selection basket:** selected registry records remain in the page-session `Map` while the user changes pages or filters. The basket is visible, sorted for display, and supports per-tool removal and explicit clearing.
- **Detail inspector:** an Inspect action displays the selected Core-returned record's identity, source metadata when present, description, input schema, output schema, declared effects and annotations.
- **Deterministic request projection:** the selected basket is sorted by server, tool name and registry ID before projecting into the canonical discovery JSON. Projection replaces `body.tools`; it does not append to a previous toolset.
- **Explicit replacement:** the user must click **Replace discovery toolset with basket**. An empty basket is rejected. The operation invalidates human-review acknowledgements and explains that the previous request toolset was replaced.
- **Clear and remove:** basket mutations are visible immediately and invalidate review. When a benchmark task is active, the existing task workflow continues to synchronize its request toolset with the basket; otherwise the staged basket does not mutate the request until explicit replacement.

## Data and safety contract

- Reads only the existing `GET /api/v1/bench/tools` response; no new endpoint or upstream fetch is introduced.
- The inspector displays fields returned by Core. Missing values are labeled **Not reported**, not inferred.
- Schema, effects and annotations are declarations, not proof of runtime behavior, semantic correctness, trust, policy compliance, authorization or execution.
- Provenance fields are shown only when present in the returned record; they are not independently authenticated by the UI.
- All inspector and basket labels are inserted as DOM text. No `innerHTML` is used by the new inspector/basket logic.
- No MCP tool is invoked. No approval, authorization or execution action is added.
- The selection basket is page-session state, not durable server-side storage. It survives pagination/filter changes within the current page session; it is not promised to survive reload or browser restart.

## Automated regression

`tests/test_studio_tool_registry_workspace.py` covers inspector fields, safe rendering, selection persistence across pagination, deterministic replacement, review invalidation and basket removal/clearing.

## Operator acceptance

1. Check out the exact UX-3 PR head.
2. Load the benchmark workspace using an authenticated Studio session.
3. Select tools on page 1, navigate to page 2, then back; confirm the selection count and basket remain stable.
4. Change source and search filters; confirm selected tools remain selected in the basket.
5. Inspect tools with and without optional schema/effect/provenance fields; confirm absent values are labeled as not reported.
6. Remove one selected tool and clear the basket; verify counts and checkboxes update.
7. Build a non-empty basket and explicitly replace the discovery request toolset; inspect the canonical JSON and confirm deterministic server/name/ID ordering, with no append of the old toolset.
8. Confirm the review acknowledgement is invalidated after selection or replacement changes.
9. With an active benchmark task, confirm the existing task workflow synchronizes request tools to the basket; without an active task, confirm selection alone does not mutate the request.
10. Verify keyboard use, responsive layout, and that no MCP invocation or execution occurred.

## Evidence reporting

Source checks, JavaScript parsing, pytest, CI, authenticated Colab acceptance and browser review are separate evidence classes. Do not mark UX-3 accepted until the exact head has passed the relevant automated and operator checks.
