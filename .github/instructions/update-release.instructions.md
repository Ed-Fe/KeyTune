---
description: "Use when editing the updater flow, Windows release packaging, GitHub release notes, update-testing docs, or CHANGELOG entries in the Media Player project."
name: "Update and Release Workflow"
applyTo:
  - "CHANGELOG.md"
  - "docs/changelog/**"
  - "src/player/changelog/**"
  - ".github/workflows/release-windows.yml"
  - "docs/update-testing.md"
  - "scripts/build_windows_release.ps1"
  - "installer/keytune.iss"
  - "src/player/install_info.py"
  - "src/player/constants.py"
  - "src/player/frames/update.py"
  - "src/player/update/dialog.py"
  - "src/player/update/service.py"
---
# Update and Release Workflow Guidelines

- Keep versioning and release metadata coherent across `src/player/constants.py` (`APP_VERSION`), `docs/changelog/<version>.md` (plus its `.en.md` and `.es.md` translations), and the GitHub release/tag being prepared.
- The changelog is one file per version in `docs/changelog/`: `X.Y.Z.md` (Portuguese, the source), `X.Y.Z.en.md`, `X.Y.Z.es.md`, plus `unreleased*.md` for what is not out yet. `CHANGELOG.md` at the root only points there. When cutting a release, rename `unreleased*.md` to the version and fix the `## [Não lançado]` / `[Unreleased]` / `[Sin publicar]` heading to `## [X.Y.Z] - YYYY-MM-DD`. `tests/test_changelog.py` fails when a released version lacks a translation or the translation has a different shape.
- The release workflow publishes the Portuguese file as the release body and the translations as assets `release-notes.en.md` / `release-notes.es.md` (it fails if one is missing). The update dialog shows the asset of the active language and falls back to the body (`update/service.py`, `_localized_release_notes`). Adding a language means adding it to that workflow step too.
- **Ajuda > Histórico de mudanças** (`src/player/changelog/`) reads the files bundled into `docs/changelog` of the installation, in the active language, falling back to Portuguese. The build copies them without `unreleased*`.
- Preserve the installer-driven update contract expected by `src/player/update/service.py`: publish `KeyTune-Setup.exe` and `KeyTune-Setup.exe.sha256`. The app downloads the setup and runs it silently (`/VERYSILENT`); the Inno `[Run]` section relaunches KeyTune. Per-machine installs are elevated via `runas` (scope read by `install_info.py`).
- Keep checksum validation intact; automatic installation is only supported for the frozen Windows build (`can_self_update`).
- The installer (`installer/keytune.iss`) owns file associations and default-app `Capabilities`/`RegisteredApplications` registration (HKA). Mirror the extension list with `SUPPORTED_MEDIA_EXTENSIONS` + `.m3u`/`.m3u8`.
- Preserve the environment variable overrides `MEDIA_PLAYER_UPDATE_REPOSITORY_OWNER` and `MEDIA_PLAYER_UPDATE_REPOSITORY_NAME` so updater tests can target a separate repository.
- When updating release/testing guidance, link to `docs/update-testing.md` for the full end-to-end checklist and to `docs/changelog/` for version history instead of duplicating long procedures.
- After touching the updater, release packaging, or changelog-related Python files, run `python -m compileall src`; for packaging changes, also confirm whether `README.md` or `docs/update-testing.md` needs a matching documentation update.
