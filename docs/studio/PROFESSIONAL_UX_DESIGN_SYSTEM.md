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
