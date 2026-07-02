"""Lyrics lookup service.

Network access and response parsing for song lyrics live here, isolated from
the wxPython UI (``frames/lyrics_panel.py``). Two providers are queried in
order: LRCLIB first (fast, HTTP) and YouTube Music as a fallback (broader
catalogue, reuses the managed ``ytmusicapi`` dependency).
"""

from .service import fetch_lyrics

__all__ = ["fetch_lyrics"]
