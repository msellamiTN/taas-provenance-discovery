# Model Studio and Agent Studio workspace refinement

## UX objective

Make Model Runtime, Agent Chat, and Agent Design behave as separate work destinations inside the existing application shell. Previously, their navigation links resolved to the same enclosing Agent Studio section, so choosing one destination did not isolate the requested task.

## Changes

- Navigation now resolves the selected nested panel and hides sibling panels along the ancestor path.
- The global environment overview remains visible across workspace changes.
- Model Runtime, Agent Chat, and Agent Design use a consistent full-width task layout with aligned card treatment.
- Long model and agent outputs have bounded viewport height and remain scrollable.
- Chat and GoalSpec authoring text areas use the product interface font rather than a code-oriented font.

## Product truth

- Model loading still calls the real authenticated model-load endpoint.
- Chat still calls real inference; no conversation history is fabricated or persisted.
- Agent decomposition still returns a proposal; structural validity does not prove semantic correctness.
- Applying a proposal still requires human review before discovery.
- No tool execution or remote Colab control is added.

## Validation

Static regression tests assert distinct navigation destinations, nested workspace isolation, consistent layouts, and preservation of the global runtime snapshot. Tests and browser-level interaction checks must still be run before release.
