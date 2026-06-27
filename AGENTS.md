# Project Guidelines

Runtime instructions for coding agents — every line is loaded into each session, so keep it lean. Detailed module rules live in `.github/instructions/` (listed at the end); point there instead of growing this file.

## Commands

- Install: `pip install -r requirements.txt` (virtualenv recommended).
- Run: `python src/main.py`.
- Syntax check after Python changes: `python -m compileall src`.
- Tests (backend/services/parsing changes): `python -m unittest discover -s tests`.
- Windows release build: `scripts/build_windows_release.ps1` (validate via `docs/update-testing.md`).
- UI has no automated coverage — manually walk the affected keyboard flows, dialogs, playlist behavior, and screen-reader announcements.
- Playback needs the MPV runtime (system or bundled). Windows-only integrations must degrade gracefully when unavailable.

## Boundaries

**Always**
- User-facing text (labels, menus, status, screen-reader announcements) in **Portuguese**.
- Keyboard-first and accessibility-first: preserve existing shortcuts; no mouse-only flows.
- Route screen-reader work through `src/player/accessibility.py`; keep `accessible-output2` defensive.
- Keep Windows-only modules (`single_instance.py`, `file_associations.py`, `smtc/service.py`) isolated from cross-platform core.
- Keep `preferences/` (durable settings) and `session.py` (restorable state) separate.

**Ask first**
- Committing a large feature (Conventional Commits, e.g. `feat: ...`; push after).
- A broad `frames/*.py` refactor, including splitting a mixin into a subpackage (see Modularity) — prefer small, targeted edits.
- Changing the Windows MPV bootstrap order (env override → bundled/runtime-local `mpv/` → Chocolatey installs), unless the task is packaging.
- Forcing a focus change in dialogs, tab switches, or auxiliary windows.

**Never**
- Cause unexpected focus on the native video output area.
- Mix UI, persistence, parsing, and external-service logic in one catch-all module.

## Architecture

Entry flow: `main.py` (bootstraps the MPV runtime; forwards CLI-opened paths to a running instance) → `player/app.py` → `player/frames/base.py` (window shell composed from mixins). Code under `src/player/` is split by responsibility into subpackages — `frames/` (window behavior), `youtube_music/`, `library/`, `equalizer/`, `playlists/`, `preferences/`, `update/`. For the per-module map, see `.github/instructions/player-architecture.instructions.md`.

**Modularity** — one module, one responsibility. When a module accumulates several concerns, split it into a subpackage of focused sub-mixins recomposed in `__init__.py` (the existing pattern: `frames/commands/`, `library_tabs/`, `playback/`, `youtube_music/`), keeping the public class name and `base.py` composition unchanged. Treat it as behavior-preserving: verify method-set parity against the pre-split class, then run `compileall`, the tests, and a `frames/base.py` import smoke test. For everyday edits, just leave each file at least as focused as you found it — don't widen a catch-all.

## Conventions

- The updater contract spans `constants.py`, `installer/keytune.iss`, `.github/workflows/release-windows.yml`, and the release assets `KeyTune-Setup.exe` + `.sha256` — keep them in sync. Updates are installer-driven: the app downloads the setup and runs it `/VERYSILENT`; the Inno `[Run]` step relaunches; the installer also registers default-app `Capabilities`/`RegisteredApplications` (HKA).
- The update dialog shows the GitHub release body as the changelog — keep `CHANGELOG.md` and the published release notes consistent (the app doesn't read the file).
- Preserve the `MEDIA_PLAYER_UPDATE_REPOSITORY_OWNER`/`_NAME` env overrides so updater testing can target a separate repo.
- Full feature list and shortcut inventory: `README.md`, `docs/manual.md`.

## Detailed rules (`.github/`)

- `instructions/player-architecture.instructions.md` — module map, splitting modules, new integrations.
- `instructions/player-ui-a11y.instructions.md` — wxPython UI, dialogs, menus, shortcuts, focus, screen reader.
- `instructions/update-release.instructions.md` — updater, Windows packaging, release notes, CHANGELOG.
- `instructions/git-workflow.instructions.md` — finalizing features, commits, pushes.
- `prompts/accessibility-smoke-test.prompt.md`, `prompts/release-readiness.prompt.md` — verification checklists.
