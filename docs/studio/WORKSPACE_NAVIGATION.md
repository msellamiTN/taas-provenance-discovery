# Studio workspace navigation

Status: implemented in the workspace-navigation branch. The browser shell remains framework-agnostic HTML/CSS/JavaScript.

## Behavior

- A persistent left navigation remains available while switching workspaces.
- Selecting a navigation item reveals the containing workspace panel and hides sibling panels.
- Nested destinations (for example Goal Design inside the discovery workspace) reveal their containing workspace and scroll to the requested control.
- The host runtime snapshot remains visible as global context; it is explicitly host diagnostics, not model runtime state.
- Agent Studio is inside the same shell as discovery, MCP, model catalog and host diagnostics.
- The selected navigation link receives `aria-current="page"`.
- The initial view is Overview unless the URL hash identifies a valid navigation destination.
- The URL hash is updated without adding browser-history entries.

## Capability boundaries

Navigation does not create new backend capabilities. Model load/chat and agent decomposition continue to call their existing authenticated APIs. MCP remains inspection-only. Discovery remains separate from execution. Runs & Traces are not presented as implemented.

## Verification

Static regression tests verify that every navigation destination exists, Agent Studio remains inside the shell, and the workspace visibility logic preserves the global host snapshot. These checks do not replace browser automation, keyboard testing, or viewport screenshot review. Those remain release gates.
