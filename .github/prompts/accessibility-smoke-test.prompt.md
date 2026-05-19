---
description: "Run a focused accessibility and keyboard smoke test for Media Player UI changes such as dialogs, menus, playlist views, focus handling, and screen reader announcements."
name: "Accessibility Smoke Test"
argument-hint: "What screen, dialog, file, or change should be reviewed?"
agent: "agent"
---
Review the requested Media Player UI or accessibility change and perform a focused smoke test.

Use the workspace instructions in [AGENTS](../../AGENTS.md) and the UI-specific rules in [player-ui-a11y.instructions](../instructions/player-ui-a11y.instructions.md).

Scope the review to the user-provided target, such as a dialog, menu flow, playlist view, shortcut change, or accessibility helper.

Check for these risks when relevant:
- Forced focus changes or unexpected focus jumps
- Missing, duplicated, or unclear labels for assistive technologies
- Regressions in keyboard-first navigation and existing shortcuts
- Screen reader announcements that are noisy, missing, or not in Portuguese
- Behavior that depends unsafely on optional `accessible-output2`
- Changes that may reintroduce focus on the native video output area
- Preference or session changes that break backward compatibility

Then produce a concise report with:
1. A short summary of what was reviewed
2. Issues found, ordered by severity
3. Suggested fixes or follow-up edits
4. A compact manual test checklist for the affected flow
5. Whether `python -m compileall src` should be run or was already enough for this review
