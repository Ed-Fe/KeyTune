# Project Guidelines

## Commands

- Install: `pip install -r requirements.txt` (virtualenv recommended).
- Run: `python src/main.py`.
- Quick validation after Python changes: `python -m compileall src`.
- Tests (backend/services/parsing changes): `python -m unittest discover -s tests`.
- UI changes: no automated coverage — manually walk the affected keyboard flows, dialogs, playlist behavior, and screen-reader announcements.
- Windows release build: `scripts/build_windows_release.ps1`; validate with `docs/update-testing.md`.
- MPV runtime must be available (system or bundled) for playback. Windows-only integrations (MPV discovery, file associations, SMTC) must degrade gracefully when unavailable.

## Boundaries

**Always**
- Keep user-facing text (labels, menus, status messages, screen-reader announcements) in Portuguese.
- Preserve existing keyboard shortcuts — this app is keyboard-first and accessibility-first; no mouse-only flows.
- Use the helpers in `src/player/accessibility.py` for screen-reader work; keep `accessible-output2` integration defensive.
- Keep Windows-only modules (`single_instance.py`, `file_associations.py`, `smtc/service.py`) isolated from cross-platform core logic.
- Keep `preferences/` (durable settings) and `session.py` (restorable session state) separated — do not mix them.

**Ask first**
- Before creating a Git commit for a large feature (use Conventional Commits style, e.g. `feat: ...`, and push after committing once confirmed).
- Before changing the MPV bootstrap order on Windows (env override → bundled/runtime-local `mpv/` → Chocolatey-style installs), unless the task is specifically about packaging.
- Before a broad refactor of `frames/*.py` — prefer small, targeted edits there.
- Before forcing a focus change in dialogs, tab switches, or auxiliary windows.

**Never**
- Cause noisy/unexpected focus on the native video output area.
- Mix UI flow, persistence, parsing, and external-service logic in one catch-all module — split into focused modules first.

## Architecture

Entry flow: `src/main.py` → `src/player/app.py` → `src/player/frames/base.py`. `main.py` also bootstraps the MPV runtime and forwards CLI-opened file paths to an already-running instance.

Module map (`src/player/`):
- `frames/` — `base.py` window shell + mixin composition; `ui.py` menus/layout/bindings; `commands.py` file dialogs & actions; `playback.py` MPV control; `library.py`/`library_tabs.py`/`library_loader.py`/`library_navigation.py` playlist tabs & folder browsing; `session.py` capture/restore; `recents.py`; `equalizer.py`; `update.py`; `smtc.py` SMTC bridge; `youtube_music.py` YT Music auth/menu flows & background tasks.
- `youtube_music/` — `service.py` facade over `client_provider.py` (client caching), `stream_cache.py` (TTL stream URLs), `library_manager.py` (playlists/search), `feedback_manager.py` (likes/history); `auth.py`, `dialog.py`, `panel.py`, `playlists.py`, `search.py`, `streams.py` (yt-dlp), `charts.py`, `browse.py` (moods/genres), `models.py`.
- `library/` — `open_dialog.py`, `browser.py` (browser UI/keyboard nav), `models.py`, `media_scan.py`, `playlist_io.py` (`.m3u`/`.m3u8`).
- `equalizer/` — `models.py`, `backend.py` (MPV filter generation), `dialog.py`, `panel.py`.
- `playlists/` — `models.py` (tab state/order), `titles.py`.
- `preferences/` — `dialog.py`, `models.py`, `storage.py` (`settings.json`).
- `update/` — `service.py` (GitHub release discovery, checksum, updater launch), `dialog.py`.
- Root: `mpv_runtime.py`, `single_instance.py`, `audio_output.py`, `file_associations.py`, `accessibility.py`, `session.py` (`session.json`).

When a feature crosses these boundaries (UI + service + parsing + playback), extract a focused module before extending an existing one. Follow existing patterns for style — dataclasses for persisted state, small explicit helpers — rather than introducing a new convention.

## Conventions

- The updater contract spans `constants.py`, `installer/keytune.iss`, `.github/workflows/release-windows.yml`, and the published release asset `KeyTune-Setup.exe` + `.sha256`. Updates are installer-driven: the app downloads the setup and runs it silently (`/VERYSILENT`); the Inno `[Run]` step relaunches. The installer also registers default-app `Capabilities`/`RegisteredApplications` (HKA). Keep them in sync.
- The update dialog shows the GitHub release body as the changelog; keep `CHANGELOG.md` and the published release notes consistent — the app doesn't read the file directly.
- Preserve `MEDIA_PLAYER_UPDATE_REPOSITORY_OWNER`/`_NAME` env overrides so updater testing can target a separate repo.
- Full feature list and shortcut inventory: `README.md` and `docs/manual.md`.

## Related Customizations

- `.github/instructions/player-architecture.instructions.md` — splitting modules, new integrations.
- `.github/instructions/player-ui-a11y.instructions.md` — wxPython UI, dialogs, menus, shortcuts, focus, screen reader.
- `.github/instructions/update-release.instructions.md` — updater, Windows packaging, release notes, CHANGELOG.
- `.github/instructions/git-workflow.instructions.md` — finalizing features, commits, pushes.
- `.github/prompts/accessibility-smoke-test.prompt.md` — post-change accessibility verification.
- `.github/prompts/release-readiness.prompt.md` — pre-release readiness review.
