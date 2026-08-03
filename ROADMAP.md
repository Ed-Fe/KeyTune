# Roadmap

This roadmap outlines the planned direction for KeyTune. Priorities may change
as features are tested and feedback is collected.

## Version 1.3.0 — Playback Experience

- Connect to YouTube Music directly through a supported browser session
- Search within the active playlist or folder, with accessible result navigation
- Add a sleep timer with preset durations and an end-of-track option
- Refresh the user manuals and release documentation

## Version 1.4.0 — Smart Library

- Add global search across local playlists and folders
- Support favorites and ratings for local media
- Keep a local playback history
- Remember playback positions per file for podcasts, audiobooks, and other long-form media
- Introduce a reusable metadata and audio-analysis cache

## Version 1.5.0 — AutoDJ Beta

- Analyze BPM and beat positions for local audio in the background
- Cache analysis results to avoid repeating expensive work
- Align transitions to beats while preserving the original pitch
- Offer 8-, 16-, and 32-beat transitions
- Limit tempo adjustment and fall back to the regular crossfade when confidence is low
- Allow AutoDJ to be enabled independently for each playlist
- Keep all controls and transition status accessible to screen-reader users

## Version 1.6.0 — Advanced AutoDJ

- Improve transition selection using musical phrases, energy, and key compatibility
- Add editable entry and exit points
- Provide transition profiles such as Smooth, Party, and Electronic
- Add rules to avoid repeating artists or recently played tracks
- Evaluate AutoDJ support for YouTube Music and other remote streams

## Version 1.7.0 — Plugin System Beta

- Discover local plugins through manifests
- Introduce a versioned plugin API with compatibility requirements
- Expose controlled playback, metadata, menu-action, and lifecycle events
- Provide an accessible plugin manager for enabling and disabling plugins
- Isolate plugin failures and keep separate diagnostic logs
- Clearly communicate that in-process Python plugins have the same system access as KeyTune
- Use first-party plugins to validate the API before declaring it stable

## Version 2.0.0 — Extensible Platform

- Stabilize the public plugin API
- Add process isolation for plugins that require stronger safety boundaries
- Provide a supported plugin distribution and update workflow
- Complete the stable AutoDJ experience based on beta feedback
- Document compatibility and migration guarantees for plugin developers

## Additional Ideas

- Loudness normalization between tracks
- Display BPM and musical key in media information
- Analyze an entire playlist before playback starts
- Synchronized, line-by-line lyrics
- Last.fm, Discord, radio, and other integrations delivered as plugins
- Transition history with an option to retry or replace the upcoming track

## Development Principles

- Preserve keyboard-first and screen-reader-friendly workflows
- Run expensive analysis and network work outside the UI thread
- Keep ordinary playback reliable when optional features are unavailable
- Introduce experimental capabilities behind explicit user controls
- Avoid freezing a public API until its real integration needs are understood
