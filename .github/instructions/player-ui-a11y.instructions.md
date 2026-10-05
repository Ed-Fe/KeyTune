---
description: "Use when editing wxPython UI, dialogs, menus, keyboard shortcuts, focus handling, playlist browser, or screen reader accessibility in the Media Player project."
name: "Player UI Accessibility"
applyTo:
  - "src/player/frames/*.py"
  - "src/player/youtube_music/dialog.py"
  - "src/player/preferences/*.py"
  - "src/player/equalizer/dialog.py"
  - "src/player/equalizer/panel.py"
  - "src/player/library/*.py"
  - "src/player/accessibility.py"
---
# Player UI and Accessibility Guidelines

- Keep all user-facing text in Portuguese, including menu items, dialog labels, status messages, and screen reader announcements.
- Preserve the keyboard-first design. Do not introduce mouse-only flows, and keep existing shortcuts stable unless the task explicitly changes them.
- Do not force focus changes in dialogs, tab switches, playlist views, or auxiliary windows unless the request explicitly asks for it.
- Reuse the helpers and patterns in `src/player/accessibility.py` before introducing new accessibility abstractions.
- Keep screen reader integration defensive: `accessible-output2` is optional, so new code must continue to behave safely when it is unavailable.
- Preserve the behavior that avoids noisy focus on the native video output area.
- Before creating or changing a dialog, panel, tab or group of controls, follow [ui-screens.instructions](ui-screens.instructions.md) and finish with `uv run python scripts/audit_ui_accessibility.py`.
- For shortcut inventories and feature behavior, link to `README.md` instead of duplicating long documentation inside code comments or instructions.
- After UI or accessibility changes, do a focused manual check of the affected keyboard navigation, announcements, and dialog behavior, then run `python -m compileall src` as a quick validation step.
