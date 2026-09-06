# Contributing to KeyTune

Thank you for taking the time to contribute.

KeyTune is a media player. Contributions should preserve the existing structure: avoid mouse-only flows, prefer small and focused changes over broad refactors, and keep changes aligned with the existing architecture.

## Before You Start

- Fork the repository
- Create a feature branch
- Read the README to understand the current scope and project layout
- Use the issue templates for bugs and feature requests, and open Discussions for ideas, questions, and broader feedback

## Local Setup

1. Create and activate a virtual environment.
2. Install the main dependencies with `pip install -r requirements.txt`. To
   develop or test YouTube Music and AutoDJ from the source tree, also run
   `pip install -r requirements-youtube.txt -r requirements-autodj.txt`.
3. Download the MPV runtime with `python scripts/download_mpv_runtime.py` if you do not already have a compatible libmpv installation.
4. Run the app with `python src/main.py`.

## What to Check

- Keep changes aligned with the existing module boundaries in `src/player/`.
- Avoid introducing unrelated refactors.
- Keep the Windows release flow compatible with the existing build scripts and workflow.

## Validation

Use the narrowest validation that fits the change:

- `python -m compileall src` for a quick syntax check
- `python -m unittest discover -s tests` when changing backend, parsing, or service logic
- A focused manual check for UI and behavior changes

## Pull Requests

Please include:

- A short summary of what changed
- Any validation you ran
- Notes about behavior changes, especially if they affect playback, playlists, or the update flow

## Need More Context?

If you are unsure where a change belongs, start from the existing module structure described in the README and keep the edit as small as possible.
