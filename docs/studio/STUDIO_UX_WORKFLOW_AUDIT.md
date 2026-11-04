# TaaS Studio UX and workflow audit

## Scope and evidence

This review is based on the Studio HTML/JavaScript, existing navigation and discovery integration, the maintained Colab notebook, and the existing regression tests. It is an implementation audit, not a live Chrome/Colab visual acceptance report.

## Findings addressed in this change

### 1. Nested workspace visibility was not reversible

The previous router set `hidden=true` on sibling panels but did not record which visibility flags belonged to navigation. Selecting a nested destination and then returning to its parent could leave sibling panels hidden. The new router marks only elements it hides and restores only those marks before resolving the next route. Application-controlled hidden states are not reset globally.

### 2. Browser history did not represent Studio navigation

The previous router used `history.replaceState`, which overwrote the current entry and did not respond to Back/Forward navigation. The router now pushes a history entry for user-initiated workspace changes and handles both `popstate` and `hashchange`. Initial deep links are still resolved without creating an extra history entry.

### 3. Runtime overview was intended to be global but had no matching ID

The router already contained a special case for an element with ID `runtime-overview`, but the runtime overview section did not have that ID. It could therefore be hidden along with the selected workspace. The section now has the expected ID and remains visible as a global runtime utility.

### 4. Benchmark task handoff navigated to the wrong destination

The “Use prompt in GoalSpec” action copied the task prompt and then attempted to scroll to the Discovery panel. That was both semantically out of order and could target a panel hidden by single-workspace navigation. It now opens the GoalSpec designer after copying the prompt, preserving the intended sequence: task intent → GoalSpec review → tool selection → discovery.

## Navigation contract

- Every sidebar and lifecycle destination must resolve to a real element ID.
- A navigation action selects one top-level workspace and, where applicable, one nested destination.
- Only visibility changes made by the navigation router may be undone by the router.
- The runtime overview remains available across workspace changes.
- Back/Forward and direct hash links must resolve to the same workspace as sidebar navigation.
- The active sidebar destination is reflected through `aria-current="page"`.
- Reduced-motion preferences are respected for scrolling.

## Workflow contract

1. Select a retained benchmark task or author an objective in the Agent workspace.
2. Draft and review the GoalSpec; structural validity is not semantic task alignment.
3. Inspect MCP declarations or retained registry contracts; inspection is not tool execution.
4. Select/synchronize tool metadata with the discovery request.
5. Run Core discovery and inspect selection/abstention, counterexamples, and certificate gates.
6. Explore a hypergraph only when the API reports an available, supported Core projection.
7. Inspect assurance evidence separately; evidence integrity is not authorization or execution.
8. Execution remains explicitly unavailable in this build.

The “Use prompt in GoalSpec” action now routes to step 2. The Explorer continues to call the existing Discovery action rather than creating a second discovery workflow.

## Trust and state rules retained

- The browser does not compute semantic reachability, effects, composition, or certification.
- No graph is synthesized from GoalSpec, selected tools, certificate bindings, or browser state.
- A restored Discovery result is a tab-scoped display snapshot; it does not rerun Discovery.
- A retained projection may be stale after a failed subsequent request; the UI status must continue to identify that condition.
- MCP inspection uses declared metadata only; no `tools/call` is introduced.
- No authorization grant, governed invocation, or durable execution history is implied.

## Validation plan

Automated checks cover destination integrity, unique IDs, reversible navigation-owned visibility, history events, global runtime overview, and the benchmark-to-GoalSpec handoff. GitHub Actions is the code-validation gate. The maintained Colab notebook is the operator integration gate; a passing CI run does not claim live browser validation.
