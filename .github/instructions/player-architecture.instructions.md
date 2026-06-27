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
- Preserve public method names unless the refactor requires a coordinated call-site update.
- Prefer small helper functions and composition over adding another long conditional block to an already-large module.
- After structural Python refactors, run `python -m compileall src`.
