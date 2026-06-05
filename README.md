# KeyTune

An accessible media player called **KeyTune**, built with **Python**, **wxPython**, and **MPV**.

The project is keyboard-first and screen-reader-friendly, with support for playlists, folder browsing, session restore, and persistent user preferences.

## Status

KeyTune is ready for the `1.0.0` Windows release candidate, with the main playback, library, accessibility, update, and YouTube Music flows already integrated.

## Highlights

- Embedded MPV playback inside a wxPython window
- Multiple playlists in tabs
- Folder browser with preview support
- Tab-specific equalizer with built-in presets and custom presets
- Aba dedicada do YouTube Music com filtro, atualização da biblioteca e abertura por link ou ID
- `.m3u` / `.m3u8` playlist loading and saving
- Session restore for tabs, current item, position, and volume
- Persistent preferences in `settings.json`
- Recent files, folders, and playlists
- Keyboard-first navigation
- Accessibility announcements through screen readers when available

## Requirements

- Python 3.10 or newer
- `python-mpv` installed in the active Python environment
- A libmpv runtime available in a local `mpv/` folder, via `MPV_HOME` or `MPV_DLL_DIR`, or in a common Chocolatey install path

## Manual do usuário

O manual inicial do projeto fica em `docs/manual.md`.

Você pode lê-lo de três maneiras:

1. direto no repositório, como arquivo Markdown;
2. no VS Code, usando a pré-visualização de Markdown;
3. na release do Windows, abrindo `docs/manual.html` dentro do ZIP gerado no momento do empacotamento.

## Installation

### 1. Clone the repository
```bash
git clone https://github.com/Ed-Fe/KeyTune.git
```

Optional if you already have the files locally.

### 2. Create a virtual environment

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

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Download the MPV runtime for development

```powershell
python scripts/download_mpv_runtime.py
```

Esse helper baixa a release mais recente do `mpv-winbuild`, extrai a pasta que contém `libmpv-2.dll` e a grava em `./mpv/` por padrão. Ele depende do `7z`/7-Zip para desempacotar o arquivo `.7z`.

Se você já tiver um runtime compatível em outro caminho, pode pular essa etapa e deixar o `MPV_HOME`, `MPV_DLL_DIR` ou o cache do Chocolatey apontarem para ele.

### 5. Run the application

```bash
.venv\Scripts\python.exe src/main.py
```

## Windows release with bundled MPV

This repository includes a GitHub Actions workflow at `.github/workflows/release-windows.yml`.

When triggered (manually or by pushing a tag like `v1.2.3`), it will:

1. Build the app with PyInstaller
2. Build the external updater with PyInstaller
3. Download the MPV runtime with `scripts/download_mpv_runtime.py`
4. Copy the updater to the release folder
5. Copy the MPV runtime to `dist/KeyTune/mpv`
6. Create `KeyTune-windows.zip`
7. Generate `KeyTune-windows.zip.sha256`
8. Upload the files as workflow artifacts
9. Attach the files to the GitHub Release when running on a tag

The app startup now looks for a local `mpv/` folder before creating the playback backend, and both the Windows build script and the GitHub workflow use the shared MPV download helper to populate that folder.
The Windows package also includes `KeyTuneUpdater.exe`, used by the app to apply downloaded updates after the user confirms the installation.

For a repeatable end-to-end updater test flow before publishing a release, see `docs/update-testing.md`.

## Main keyboard shortcuts

- `Space`: play / pause
- `Left` / `Right`: seek backward / forward
- `Up` / `Down`: volume down / up
- `Home` / `End`: jump to start / end of the current media
- `Ctrl+T`: new playlist tab
- `Ctrl+W`: close current media or close an empty tab
- `Ctrl+Shift+W`: close the current tab or playlist directly
- `Ctrl+PageUp` / `Ctrl+PageDown`: previous / next track
- `Ctrl+Shift+E`: open the equalizer tab for the active media tab
- `Ctrl+Tab` / `Ctrl+Shift+Tab`: next / previous tab
- `Ctrl+O`: open media files directly or a local `.m3u` / `.m3u8` playlist
- `Ctrl+Shift+O`: open a folder directly in the folder browser
- `Ctrl+Alt+O`: open media, playlist, or folder in the unified dialog
- `Ctrl+C`: copy the path or link of the selected item to the clipboard
- `Ctrl+V`: paste a path or link and add it to the current playlist when possible
- `Ctrl+Shift+V`: paste a path, playlist, or link and open it in a new playlist
- `Ctrl+Shift+S`: save current playlist
- `Ctrl+,`: open preferences
- `F1`: open quick keyboard help
- `Tab`: switch focus between the item list and the player
- `F6`: open the YouTube Music tab
- In the item browser, type letters or numbers to jump quickly to matching items
- `T`: announce playback time
- `V`: announce volume
- `S`: announce player status
- `E`: toggle shuffle
- `R`: cycle repeat mode

## Project structure

- `src/main.py` — application entry point
- `src/player/app.py` — wx application bootstrap
- `src/player/frames/base.py` — main window coordinator and mixin composition
- `src/player/frames/ui.py` — menus, layout, and UI bindings
- `src/player/frames/commands.py` — event handlers, dialogs, and shortcuts
- `src/player/frames/playback.py` — lógica de reprodução com MPV
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
- `src/player/preferences/dialog.py` — preferences UI
- `src/player/preferences/models.py` — persistent user settings model
- `src/player/preferences/storage.py` — persistent user settings storage
- `src/player/session.py` — session persistence
- `src/player/accessibility.py` — screen reader helpers

## Accessibility notes

- UI labels, status messages, and announcements are currently in **Portuguese**.
- The app is designed to avoid noisy focus on the native video output area.
- `accessible-output2` is optional; the app should continue to work without it.

## Contributing

Contributions are welcome.

If you want to help:

1. Fork the repository
2. Create a feature branch
3. Make focused changes
4. Run the quick validation step
5. Open a pull request with a clear description

### Development notes

- Prefer small, targeted changes over broad refactors
- Keep user-facing text in Portuguese unless the project direction changes
- Preserve keyboard-first behavior and accessibility flows
- Try not to introduce mouse-only interactions
- Use `scripts/download_mpv_runtime.py` to populate `mpv/` during local development instead of manual MPV extraction

### Quick validation

```bash
python -m compileall src
```

### Local Windows release build

To generate a local packaged build for updater testing, use:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows_release.ps1
```

## Roadmap

- Multi-selection in the playlist browser
- Batch reordering support
- More playback and library management features

## Changelog

- See `CHANGELOG.md` for version history and notable changes.
