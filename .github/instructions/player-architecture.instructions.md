---
description: "Use when editing Media Player Python modules, splitting large modules, or adding integrations such as YouTube Music."
name: "Player Architecture Boundaries"
applyTo:
  - "src/player/*.py"
---
# Player Architecture Boundaries

- Keep each module focused on a single responsibility; if a change starts mixing UI flow, persistence, parsing, and backend integration, split it before adding more behavior.
- Prefer dedicated `frames/*.py` modules for feature-specific window behavior instead of growing a catch-all module inside the player package.
- Keep dialogs in `*dialog.py`, durable settings in `preferences/models.py` plus `preferences/storage.py`, session restore in `session.py`, and service or integration helpers in focused non-UI modules.
- For YouTube Music changes, keep responsibilities separated:
  - `frames/youtube_music/` for command handlers, background-task coordination, and menu state
  - `youtube_music/service.py` for the service facade used by the frame
  - `youtube_music/auth.py` for browser-auth parsing and normalization
  - `youtube_music/playlists.py` for playlist and mix normalization plus source helpers
  - `youtube_music/streams.py` for `yt-dlp` stream resolution
  - `youtube_music/models.py` for small shared data containers
- For smart-library changes (busca global, favoritos, avaliações, histórico, retomada, cache):
  - `frames/smart_library/` for window behavior, split by concern (lifecycle, indexing, search, ratings, history, resume, playback tracking)
  - `smart_library/service.py` for the facade the frame talks to — reads are synchronous, writes and folder scans go to its worker thread
  - `smart_library/database.py` for the SQLite connection and schema; one access module per table alongside it
  - `smart_library/*_dialog.py` for the wx dialogs; everything else in the package must stay free of wxPython so it can be tested headless
  - The service must degrade to a no-op when the database cannot be opened; playback never depends on it.
- Preserve public method names unless the refactor requires a coordinated call-site update.
- Prefer small helper functions and composition over adding another long conditional block to an already-large module.
- After structural Python refactors, run `python -m compileall src`.
