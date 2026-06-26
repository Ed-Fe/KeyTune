---
description: "Run a focused pre-release readiness review for Media Player Windows packaging, updater compatibility, and release-note alignment."
name: "Release Readiness"
argument-hint: "Which version, tag, branch, or release candidate should be reviewed?"
agent: "agent"
---
Review the requested Media Player release candidate and decide whether it is ready to publish.

Use the workspace guidance in [AGENTS](../../AGENTS.md) and the release-specific rules in [update-release.instructions](../instructions/update-release.instructions.md).

When needed, reference:
- [update-testing guide](../../docs/update-testing.md)
- [release workflow](../../.github/workflows/release-windows.yml)
- [changelog](../../CHANGELOG.md)

Scope the review to the user-provided target (for example: a tag like `v0.2.0`, a branch, or a set of changed files).

Check these risks when relevant:
- Version coherence across `src/player/constants.py` (`APP_VERSION`), `CHANGELOG.md`, and the intended GitHub release tag/body.
- Release asset contract expected by `src/player/update/service.py`: `KeyTune-Setup.exe` and `KeyTune-Setup.exe.sha256` (installer-driven updates, run silently via `/VERYSILENT`).
- Release-body and changelog consistency (the app shows the GitHub release body in the update dialog).
- Preservation of `MEDIA_PLAYER_UPDATE_REPOSITORY_OWNER` and `MEDIA_PLAYER_UPDATE_REPOSITORY_NAME` for updater testing overrides.
- Whether `README.md` and/or `docs/update-testing.md` need matching updates for packaging or updater behavior changes.
- Whether updater/release Python changes require `python -m compileall src` as quick validation.

Then produce a concise report with:
1. Readiness verdict: `Ready`, `Ready com pendências`, or `Bloqueado`
2. Issues found, ordered by severity (blockers first)
3. Exact file-level fix list (path + one-line change intent)
4. Minimal pre-release checklist (5 to 10 items) for this candidate
5. Recommended next action (publish now, patch first, or re-run checks)
