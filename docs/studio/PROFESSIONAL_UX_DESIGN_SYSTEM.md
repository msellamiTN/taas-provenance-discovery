# TaaS Studio — Professional UX Design System

## Purpose

This increment establishes a coherent visual foundation for the existing server-rendered Studio. It is a visual and responsive-design change; it does not introduce a frontend framework migration or change API semantics.

## Design direction

- **Product character:** precise, calm, technical, enterprise-oriented.
- **Information hierarchy:** persistent navigation, clear workspace title, contextual status, task content, then diagnostics and raw detail.
- **Palette:** deep navy application chrome, restrained blue action color, neutral surfaces, muted secondary text, and semantic amber/green/red states.
- **Surfaces:** white cards on a quiet neutral canvas, consistent borders, modest elevation, and a small radius scale.
- **Typography:** compact interface typography with stronger page titles and readable supporting copy.
- **Controls:** consistent input height, explicit focus rings, predictable primary/secondary button hierarchy, and disabled states that do not imply progress.
- **Responsive behavior:** sidebar and workspace adapt at tablet/mobile widths; dense grids collapse without horizontal overflow.
- **Accessibility:** visible keyboard focus, semantic color not used as the only status signal, and reduced-motion support.

## Interaction and trust constraints

- Visual status must reflect API responses, not optimistic assumptions.
- Host hardware diagnostics and process-local model runtime remain separate concepts.
- Model metadata inspection is not model loading; model loading is not inference.
- Agent decomposition is a proposal requiring structural validation and human review.
- Discovery does not execute tools. MCP inspection does not call tools.
- No fake run history, execution metrics, compatibility guarantees, or task-success indicators are introduced.

## Scope

Updated the existing HTML/CSS presentation layer only. Existing endpoint calls, authentication flow, model lifecycle, discovery semantics, MCP inspection boundaries, and execution gateway boundaries are unchanged.

## Validation status

Static regression tests cover design tokens, keyboard focus, responsive breakpoints, reduced-motion support, and preservation of the execution-disabled trust message. Browser screenshot review, keyboard walkthrough, contrast audit, and automated browser tests remain required before production release.


## UX-2 — Persistent workspace context

The application content area now exposes a compact breadcrumb/context strip. Its title is driven by the same navigation link that controls workspace visibility, so direct navigation, browser history and sidebar navigation share one source of truth.

- The current workspace label is announced through an accessible polite live region.
- The context strip is responsive and collapses its secondary hint on narrow screens.
- Reduced-motion preferences disable smooth document scrolling.
- No workspace health, authorization, execution or readiness status is inferred or displayed by this component.

Validation adds static regression checks for the context element, navigation-driven title update, responsive behavior and reduced-motion handling. Browser-level visual and keyboard acceptance remains a separate gate.


## UX-3 — API-backed platform overview

The Overview workspace now provides a read-only summary using existing authenticated Core endpoints:

- Agent versions: `GET /api/v1/agents?limit=100`
- Skill versions: `GET /api/v1/skills?limit=100`
- Tool registry total: `GET /api/v1/bench/tools?source=all&limit=1&offset=0`
- Configured MCP servers: `GET /api/v1/mcp/servers`

The dashboard shows recent Agent and Skill version records returned by the registries, preserving their lifecycle state and revocation flag. It labels Agent/Skill figures as returned records (maximum 100), and labels the tool count as the Core-reported registry total. It does not invent a model inventory: the current model API is search-driven rather than a platform-owned model registry list.

Each resource request is handled independently. Loading, empty, partial-data and unavailable states are distinct. Values are rendered with DOM text nodes; API values are not injected as HTML. The overview contains navigation shortcuts only and does not initiate discovery, authorization, model loading or execution.

Validation adds static checks for the four endpoint contracts, partial/unavailable behavior, lifecycle labels and responsive layouts. Browser-level interaction and live API verification remain pending.
