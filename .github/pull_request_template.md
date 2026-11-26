## What changed

<!-- A short summary of the change. Pode escrever em português. -->

## Why

<!-- The problem it solves or the issue it closes, for example "Closes #123". -->

## How it was tested

- [ ] `python -m compileall src`
- [ ] `python -m unittest discover -s tests`
- [ ] `uv run python scripts/audit_ui_accessibility.py` (any dialog, panel, tab or preferences change)
- [ ] Manual pass with a screen reader over the keyboard flows I touched

<!-- Say which screen reader and version you used, and anything you could not test. -->

## Checklist

- [ ] Everything new works from the keyboard, and existing shortcuts still work
- [ ] New user-facing text is in Portuguese, wrapped in `_()`, with the English and Spanish translations
- [ ] `docs/changelog/unreleased*.md` updated in the three languages, if users will notice the change
- [ ] The manual updated in the three languages, if a feature or shortcut changed

## Notes for the reviewer

<!-- Anything that affects playback, playlists, the update flow or Windows-only code. -->
