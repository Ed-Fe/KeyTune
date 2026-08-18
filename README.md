# KeyTune

KeyTune is a media player built with Python, wxPython, and MPV.

It focuses on playlist management, folder browsing, session restore, and persistent user preferences.

## Features

- Embedded MPV playback inside a wxPython window
- Tabbed playlists and folder browsing
- `.m3u` and `.m3u8` playlist loading and saving
- Session restore for tabs, playback position, volume, and the current item
- Persistent preferences stored in `settings.json`
- Recent files, folders, and playlists
- Item search inside the active playlist or folder (`Ctrl+F`, `F3`, `Shift+F3`)
- Smart library: FTS5-backed global search across indexed playlists and folders (`Ctrl+G`)
- Favorites (`Ctrl+D`) and star ratings (`Ctrl+0`–`Ctrl+5`) for local media, shown inline in the item list
- Local playback history with all-plays, grouped, and most-played views (`Ctrl+Shift+H`)
- Per-file resume for podcasts, audiobooks, and other long-form media, plus a "continue listening" list (`Ctrl+Shift+R`)
- Smart playlists: saved rules (favorites, rating, folder, staleness, play count) rebuilt on every open
- Reusable metadata and audio-analysis cache shared by future features
- Sleep timer with preset durations, a custom duration, or an end-of-track stop (`Ctrl+Shift+D`)
- Built-in equalizer presets plus custom presets
- YouTube Music integration for search, link-based open flows, and library refresh
- Optional YouTube Music related-content autoplay (radio) when a playlist ends

## Requirements

- Python 3.10 or newer
- `python-mpv` installed in the active Python environment
- A compatible libmpv runtime available in one of these locations:
	- a local `mpv/` folder
	- the path pointed to by `MPV_HOME`
	- the path pointed to by `MPV_DLL_DIR`
	- a supported Chocolatey installation path

## Installation

1. Clone the repository.

   ```bash
   git clone https://github.com/Ed-Fe/KeyTune.git
   cd KeyTune
   ```

2. Create and activate a virtual environment.

   On Windows:

   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   ```

   On Linux or macOS:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

3. Install dependencies.

   ```bash
   pip install -r requirements.txt
   ```

4. Download the MPV runtime for local development.

   ```powershell
   python scripts/download_mpv_runtime.py
   ```

   This helper downloads the latest `mpv-winbuild` release, extracts the folder containing `libmpv-2.dll`, and writes it to `./mpv/` by default. It depends on `7z` or 7-Zip to unpack the `.7z` archive.

   If you already have a compatible runtime in another location, you can skip this step and point `MPV_HOME`, `MPV_DLL_DIR`, or a Chocolatey installation to it.

5. Run the application.

   ```powershell
   .venv\Scripts\python.exe src/main.py
   ```

## Usage

Useful project links:

- [User manual](docs/manual.md)
- [Roadmap](ROADMAP.md)
- [Releases](https://github.com/Ed-Fe/KeyTune/releases)
- [Issues](https://github.com/Ed-Fe/KeyTune/issues)
- [Discussions](https://github.com/Ed-Fe/KeyTune/discussions)
- [Pull requests](https://github.com/Ed-Fe/KeyTune/pulls)

## Windows Release

The Windows release workflow is defined in `.github/workflows/release-windows.yml`. It builds the app, bundles the MPV runtime, compiles the Inno Setup installer (`installer/keytune.iss`), and publishes `KeyTune-Setup.exe` plus the matching SHA256 file.

The installer supports both per-user (no admin) and per-machine installs, registers KeyTune for Windows "Default apps", and drives updates: the app downloads `KeyTune-Setup.exe` and runs it silently to upgrade in place, then relaunches.

For a repeatable end-to-end updater test flow, see `docs/update-testing.md`.

## Project Structure

- `src/main.py` — application entry point
- `src/player/app.py` — wx application bootstrap
- `src/player/frames/base.py` — main window coordinator and mixin composition
- `src/player/frames/ui.py` — menus, layout, and UI bindings
- `src/player/frames/commands.py` — event handlers, dialogs, and shortcuts
- `src/player/frames/playback.py` — playback control and MPV integration
- `src/player/frames/library.py` — library mixin composition
- `src/player/frames/library_tabs.py` — tab state, selection, and ordering behavior
- `src/player/frames/library_loader.py` — background loading for folders and playlists
- `src/player/frames/library_navigation.py` — folder navigation and browser refresh flows
- `src/player/frames/session.py` — session capture and restore
- `src/player/frames/recents.py` — recent items and path helpers
- `src/player/playlists/models.py` — playlist state and playback order helpers
- `src/player/playlists/titles.py` — playlist and folder tab naming helpers
- `src/player/library/media_scan.py` — supported media checks and folder scanning helpers
- `src/player/library/playlist_io.py` — `.m3u` / `.m3u8` load and save helpers
- `src/player/library/browser.py` — side panel for playlist and folder navigation
- `src/player/library/search_dialog.py` — item search dialog (`Ctrl+F`)
- `src/player/frames/item_search.py` — item search coordination and result navigation
- `src/player/smart_library/` — smart library storage (SQLite index, favorites, ratings, history, resume, metadata cache)
- `src/player/smart_library/search_dialog.py` — global library search dialog (`Ctrl+G`)
- `src/player/smart_library/history_dialog.py` — playback history dialog (`Ctrl+Shift+H`)
- `src/player/smart_library/smart_playlists.py` — smart playlist rules and their query builder
- `src/player/smart_library/smart_playlist_dialog.py` — smart playlist manager and rule editor
- `src/player/frames/smart_library/` — window behavior for the smart library
- `src/player/frames/sleep_timer.py` — sleep timer scheduling and countdown handling
- `src/player/sleep_timer/dialog.py` — sleep timer configuration dialog
- `src/player/preferences/dialog.py` — preferences UI
- `src/player/preferences/models.py` — persistent user settings model
- `src/player/preferences/storage.py` — persistent user settings storage
- `src/player/session.py` — session persistence
- `src/player/accessibility.py` — shared UI helpers

## Contributing

Contributions are welcome. Start with [CONTRIBUTING.md](CONTRIBUTING.md) for the recommended workflow, local setup, and validation steps.

In short:

1. Fork the repository and create a feature branch.
2. Make focused changes that match the existing architecture.
3. Run the relevant validation before opening a pull request.
4. Describe the behavior change clearly in the PR description.
