# UX-3 — Studio Command Palette

## Purpose

Add a keyboard-accessible quick switcher to the existing TaaS Studio shell. This is an incremental navigation enhancement; it does not introduce a parallel router, duplicate workspace registry, or backend endpoint.

## Interaction

- Open with the visible **Quick switcher** control or `Ctrl+K` / `⌘+K`.
- Search destinations by workspace label, navigation group, or anchor.
- Navigate with Arrow Up / Arrow Down and Enter.
- Close with Escape or by clicking the dialog backdrop.
- Return focus to the trigger after closing.
- Respect the user's reduced-motion preference.

## Source of truth

Destinations are derived from the existing `.studio-nav` anchor elements at open time. New workspaces automatically appear in the palette when added to the primary navigation. No route list is maintained separately.

## Safety and accessibility

- Uses the native HTML `dialog` element and a labelled search field.
- API values are not rendered; labels are read from existing static navigation.
- DOM output is built with `createElement` and `textContent`, not HTML string interpolation.
- The palette only navigates. It does not invoke Core APIs, mutate state, authorize actions, or execute tools.

## Validation

```bash
python -m pytest -q tests/test_studio_command_palette.py
```

Full CI and Colab acceptance remain separate release gates.
