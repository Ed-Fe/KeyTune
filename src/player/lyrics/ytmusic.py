"""YouTube Music lyrics provider.

Fallback provider that reuses the project's managed ``ytmusicapi`` dependency
(imported through :func:`import_ytmusicapi_module`) instead of importing the
package directly. A single public (anonymous) client is created lazily and
cached so repeated lookups do not rebuild it. Lyrics never require
authentication, so the shared public client is enough.
"""

import threading

from ..log import get_logger
from ..youtube_music.dependencies import (
    import_ytmusicapi_module,
    youtube_dependencies_available,
)

_logger = get_logger(__name__)

_public_client = None
_public_client_lock = threading.Lock()


def _get_public_client():
    global _public_client
    with _public_client_lock:
        if _public_client is None:
            module = import_ytmusicapi_module()
            _public_client = module.YTMusic()
        return _public_client


def fetch_ytmusic_lyrics(query):
    """Return ``(raw_lyrics, title, artist)`` or ``None``.

    Skips the lookup entirely when the optional YouTube dependencies are not
    installed, so a lyrics search never triggers a heavy managed install on its
    own. Never raises: failures are logged and reported as a miss.
    """
    if not youtube_dependencies_available():
        return None

    try:
        client = _get_public_client()
    except Exception as exc:  # pragma: no cover - defensive: optional dependency
        _logger.debug("YTMusic client unavailable for lyrics: %s", exc)
        return None

    try:
        results = client.search(query, filter="songs")
        if not results:
            return None

        top_result = results[0]
        video_id = top_result.get("videoId")
        if not video_id:
            return None

        title = str(top_result.get("title") or "").strip()
        artists_list = top_result.get("artists") or []
        artist = ", ".join(
            entry["name"]
            for entry in artists_list
            if isinstance(entry, dict) and entry.get("name")
        )

        watch_playlist = client.get_watch_playlist(videoId=video_id)
        lyrics_id = watch_playlist.get("lyrics") if isinstance(watch_playlist, dict) else None
        if not lyrics_id:
            return None

        lyrics_data = client.get_lyrics(lyrics_id)
        raw_lyrics = lyrics_data.get("lyrics") if isinstance(lyrics_data, dict) else None
        if not raw_lyrics:
            return None

        return raw_lyrics, title, artist
    except Exception as exc:
        _logger.debug("YTMusic lyrics lookup failed: %s", exc)
        return None
