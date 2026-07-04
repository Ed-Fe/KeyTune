"""LRCLIB lyrics provider.

Queries the public LRCLIB search API over HTTPS (with normal certificate
verification) and returns the first result that carries plain lyrics.
"""

import json
import urllib.error
import urllib.parse
import urllib.request

from ..constants import APP_TITLE, APP_VERSION
from ..log import get_logger

_logger = get_logger(__name__)

LRCLIB_SEARCH_URL = "https://lrclib.net/api/search"
_REQUEST_TIMEOUT_SECONDS = 8


def fetch_lrclib_lyrics(query):
    """Return ``(raw_lyrics, track_name, artist_name)`` or ``None``.

    Never raises: any network or decoding failure is logged and reported as a
    miss so the caller can fall through to the next provider.
    """
    params = urllib.parse.urlencode({"q": query})
    url = f"{LRCLIB_SEARCH_URL}?{params}"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            # LRCLIB asks clients to identify themselves with a contactable UA.
            "User-Agent": f"{APP_TITLE}/{APP_VERSION} (https://github.com/Ed-Fe)",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=_REQUEST_TIMEOUT_SECONDS) as response:
            if response.getcode() != 200:
                return None
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, OSError, ValueError) as exc:
        _logger.debug("LRCLIB lyrics lookup failed: %s", exc)
        return None

    if not isinstance(data, list):
        return None

    for track in data:
        if not isinstance(track, dict):
            continue
        raw_lyrics = track.get("plainLyrics")
        if raw_lyrics:
            track_name = str(track.get("trackName") or "").strip()
            artist_name = str(track.get("artistName") or "").strip()
            return raw_lyrics, track_name, artist_name

    return None
