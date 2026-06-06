# Project Guidelines

## Code Style

- Use Python code consistent with the existing `src/player/*.py` modules: small helpers, explicit names, and dataclasses for persisted state.
- When a feature starts mixing UI flow, persistence, parsing, and external-service logic, split it into focused modules or mixins instead of extending a catch-all file.
- Keep user-facing labels, menu text, status messages, and screen reader announcements in Portuguese.
- Prefer small, targeted edits over broad refactors in the `src/player/frames/*.py` modules; `frames/base.py` coordinates the window and composes focused mixins.

## Architecture

- Entry flow is `src/main.py` -> `src/player/app.py` -> `src/player/frames/base.py`.
- `src/main.py` also bootstraps the MPV runtime and forwards command-line paths to the already-running instance before the wx app starts.
- Keep responsibilities separated:
  - `mpv_runtime.py` for locating and bootstrapping the Windows MPV/libmpv runtime
  - `single_instance.py` for named-pipe single-instance forwarding of external file launches
  - `audio_output.py` for audio-device normalization and menu-facing labels
  - `file_associations.py` for Windows file-association registration helpers
  - `frames/base.py` for the main window shell and mixin composition
  - `frames/smtc.py` for bridging Windows System Media Transport Controls into the frame
  - `frames/youtube_music.py` for YouTube Music auth/menu flows and background-task orchestration
  - `frames/ui.py` for menus, layout, control setup, and UI bindings
  - `frames/commands.py` for file dialogs, open/save actions, and command handlers
  - `frames/playback.py` for MPV backend setup, playback control, and progress updates
  - `frames/library.py` for composing library-related mixins and shared library-facing behavior
  - `frames/library_tabs.py` for playlist tabs, screen tabs, close/select logic, and playlist ordering behavior
  - `frames/library_loader.py` for background loading of folders and playlists
  - `frames/library_navigation.py` for folder navigation, browser refresh, and open flows
  - `frames/update.py` for startup/manual update checks and update-install flow orchestration
  - `frames/session.py` for session capture and restore
  - `frames/recents.py` for recent items and default path helpers
  - `frames/equalizer.py` for equalizer screen state, preset management, and tab integration
  - `library/open_dialog.py` for the open-source dialog and source-mode helpers
  - `library/browser.py` for playlist/folder browser UI and keyboard navigation
  - `library/models.py` for folder-browser entry models and related shared library data
  - `equalizer/models.py` for equalizer constants, dataclasses, and normalization helpers
  - `equalizer/backend.py` for equalizer preset catalog helpers and MPV filter generation
  - `equalizer/dialog.py` for the equalizer preset editing dialog
  - `equalizer/panel.py` for the equalizer tab UI
  - `playlists/models.py` for playlist/tab state and playback-order behavior
  - `playlists/titles.py` for playlist and folder tab naming helpers
  - `library/media_scan.py` for supported-media checks and folder scanning helpers
  - `library/playlist_io.py` for `.m3u` / `.m3u8` loading and saving
  - `preferences/dialog.py` for the preferences UI
  - `preferences/models.py` for durable user preference models
  - `preferences/storage.py` for reading and writing `settings.json`
  - `session.py` for restorable session state in `session.json`
  - `accessibility.py` for screen reader announcements and custom `wx.Accessible` helpers
  - `youtube_music/service.py` for the YouTube Music service facade used by frame mixins
  - `youtube_music/auth.py` for browser-auth parsing, normalization, and storage helpers
  - `youtube_music/dialog.py` for the browser-auth and cookie import dialog
  - `youtube_music/panel.py` for the dedicated YouTube Music tab UI and accessibility metadata
  - `youtube_music/playlists.py` for YouTube Music playlist and mix normalization plus source helpers
  - `youtube_music/search.py` for YouTube Music and YouTube search normalization helpers
  - `youtube_music/streams.py` for `yt-dlp` stream resolution
  - `youtube_music/models.py` for small shared YouTube Music data containers
  - `smtc/service.py` for the Windows System Media Transport Controls integration layer
  - `update/service.py` for GitHub release discovery, download, checksum validation, and updater launch
  - `update/dialog.py` for the update/changelog dialogs and download progress UI
- Do not mix durable preferences with session restoration logic; preserve the separation between `preferences/` and `session.py`.

## Build and Test

- Install dependencies from `requirements.txt` in a virtual environment.
- Run the app with `python src/main.py`.
- Use `python -m compileall src` as the quick validation step after Python changes.
- Run `python -m unittest discover -s tests` for automated regression checks when touching backend/services or parsing logic.
- For UI changes, do a focused manual check of the affected keyboard flows, dialogs, playlist behavior, and announcements.
- The app depends on an MPV runtime being available on the system or bundled locally.
- On Windows, integrations such as MPV runtime discovery, file associations, and SMTC should degrade gracefully when the host environment or optional dependencies are unavailable.
- For packaged Windows updater work, use `scripts/build_windows_release.ps1` for a local build and `docs/update-testing.md` for the end-to-end validation checklist.

## Conventions

- This project is keyboard-first and accessibility-first. Preserve existing shortcuts and avoid introducing mouse-only flows.
- Do not force focus changes in dialogs, tab switches, or auxiliary windows unless explicitly requested.
- When touching accessibility, prefer the existing helpers in `src/player/accessibility.py` and keep optional `accessible-output2` integration defensive.
- Preserve behavior that avoids noisy focus on the native video output area.
- Preserve the runtime bootstrap path order for MPV on Windows unless the task explicitly changes packaging behavior: environment overrides first, then bundled/runtime-local `mpv/`, then Chocolatey-style installs.
- Before adding a large behavior block to an existing player module, check whether it crosses UI, service, parsing, or playback boundaries; if it does, extract a focused module first.
- Windows-specific helpers such as `single_instance.py`, `file_associations.py`, and `smtc/service.py` should stay isolated from cross-platform core logic and fail safely when unavailable.
- Keep the updater contract aligned across `src/player/constants.py`, `.github/workflows/release-windows.yml`, and release assets: the packaged updater expects `KeyTune-windows.zip`, the matching `.sha256`, and `KeyTuneUpdater.exe`.
- The update dialog shows the GitHub release body as the user-facing changelog for a new version; when working on releases or docs, keep `CHANGELOG.md` and the published release notes consistent instead of assuming the app reads the changelog file directly.
- Preserve the test override environment variables `MEDIA_PLAYER_UPDATE_REPOSITORY_OWNER` and `MEDIA_PLAYER_UPDATE_REPOSITORY_NAME` so updater testing can target a separate repository.
- For large new features, after implementation and validation, ask the user whether they want you to create a Git commit before committing anything.
- When the user wants a commit for a large new feature, use a semantic commit message in Conventional Commits style (for example `feat: ...`) and perform the push after the commit.
- For the full feature list and shortcut inventory, see `README.md` and docs/manual.md when needed.
## Related Customizations

- Use `.github/instructions/player-architecture.instructions.md` when editing `src/player/*.py`, splitting large modules, or adding new integrations so responsibilities stay separated.
- Use `.github/instructions/player-ui-a11y.instructions.md` when editing wxPython UI, dialogs, menus, keyboard shortcuts, focus handling, playlist browser, or screen reader accessibility.
- Use `.github/instructions/update-release.instructions.md` when editing the updater, Windows release packaging, GitHub release notes, or `CHANGELOG.md`.
- Use `.github/instructions/git-workflow.instructions.md` when finalizing a large feature, preparing a commit, or pushing repository changes.
- Use `.github/prompts/accessibility-smoke-test.prompt.md` for a focused post-change accessibility verification pass after UI or accessibility work.
- Use `.github/prompts/release-readiness.prompt.md` for a focused pre-release readiness review of version sync, release assets, updater compatibility, and docs alignment.
