"""Dual-engine lyrics orchestration.

:func:`fetch_lyrics` runs synchronously and is meant to be called from a worker
thread. It queries LRCLIB first, then YouTube Music, and returns the formatted
lyrics text (with a source header) or ``None`` when neither provider has them.
"""

from ..i18n import _
from .lrclib import fetch_lrclib_lyrics
from .ytmusic import fetch_ytmusic_lyrics


def fetch_lyrics(artist, title, *, on_progress=None):
    """Return formatted lyrics text or ``None``.

    ``on_progress`` is an optional callable invoked with a status message before
    the slower YouTube Music engine is queried, so the UI can reflect the wait.
    """
    query = f"{str(artist or '').strip()} {str(title or '').strip()}".strip()
    if not query:
        return None

    lrclib_result = fetch_lrclib_lyrics(query)
    if lrclib_result:
        raw_lyrics, found_title, found_artist = lrclib_result
        return _format_lyrics(_("LRCLIB"), found_title, found_artist, raw_lyrics)

    if on_progress is not None:
        on_progress(_("Buscando letra no YouTube Music..."))

    ytmusic_result = fetch_ytmusic_lyrics(query)
    if ytmusic_result:
        raw_lyrics, found_title, found_artist = ytmusic_result
        return _format_lyrics(_("YT Music"), found_title, found_artist, raw_lyrics)

    return None


def _format_lyrics(source_label, title, artist, raw_lyrics):
    display_title = title or _("Desconhecido")
    display_artist = artist or _("Desconhecido")
    header = _("[{source}: {title} - {artist}]").format(
        source=source_label, title=display_title, artist=display_artist
    )
    return f"{header}\r\n\r\n{_normalize_line_endings(raw_lyrics)}"


def _normalize_line_endings(text):
    return text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\r\n")
