"""Reconhece links de vídeo do YouTube e do YouTube Music; sem wxPython.

Fica fora dos pacotes ``youtube_music`` e ``playlists`` porque o roteador de
links (``link_router``) decide o destino de um link antes de a interface
carregar, e aqueles pacotes puxam a interface junto.

Só os endereços que o KeyTune toca contam: vídeo (``watch``, ``youtu.be``,
``shorts``, ``live``, ``embed``) e playlist. Canais, buscas e a página inicial
continuam no navegador.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlencode, urlsplit

YOUTUBE_HOSTS = frozenset({"youtube.com", "www.youtube.com", "m.youtube.com"})
YOUTUBE_MUSIC_HOST = "music.youtube.com"
YOUTUBE_SHORT_HOST = "youtu.be"
_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_PLAYLIST_ID = re.compile(r"^[A-Za-z0-9_-]{2,}$")
_VIDEO_PATH_PREFIXES = ("shorts", "live", "embed", "v")


def _parts(url):
    text = str(url or "").strip()
    if not text:
        return None
    try:
        parts = urlsplit(text)
        host = (parts.hostname or "").casefold().rstrip(".")
    except ValueError:
        return None
    if parts.scheme.casefold() not in ("http", "https") or not host:
        return None
    return parts, host


def _first(query, name, pattern):
    for value in query.get(name) or ():
        value = str(value or "").strip()
        if pattern.match(value):
            return value
    return None


def _video_and_playlist(url):
    """``(host, id do vídeo, id da playlist)`` ou ``None`` se não é link de mídia do YouTube."""
    parsed = _parts(url)
    if parsed is None:
        return None
    parts, host = parsed
    query = parse_qs(parts.query)
    playlist_id = _first(query, "list", _PLAYLIST_ID)
    segments = [segment for segment in parts.path.split("/") if segment]

    if host == YOUTUBE_SHORT_HOST:
        video_id = segments[0] if segments and _VIDEO_ID.match(segments[0]) else None
        return (host, video_id, playlist_id) if video_id else None

    if host != YOUTUBE_MUSIC_HOST and host not in YOUTUBE_HOSTS:
        return None

    first = segments[0].casefold() if segments else ""
    if first == "watch" and len(segments) == 1:
        video_id = _first(query, "v", _VIDEO_ID)
        return (host, video_id, playlist_id) if video_id else None
    if first == "playlist" and len(segments) == 1:
        return (host, None, playlist_id) if playlist_id else None
    if first in _VIDEO_PATH_PREFIXES and len(segments) == 2 and _VIDEO_ID.match(segments[1]):
        return host, segments[1], playlist_id
    return None


def is_youtube_link(url) -> bool:
    """Se *url* é um vídeo ou uma playlist do YouTube ou do YouTube Music."""
    return _video_and_playlist(url) is not None


def normalize_youtube_link(url):
    """O endereço ``watch``/``playlist`` equivalente, que o player já sabe abrir.

    ``youtu.be``, ``shorts``, ``live`` e ``embed`` viram ``watch?v=``; um link do
    YouTube Music continua no ``music.youtube.com``. Outros links voltam iguais.
    """
    found = _video_and_playlist(url)
    if found is None:
        return str(url or "").strip()
    host, video_id, playlist_id = found
    base_host = YOUTUBE_MUSIC_HOST if host == YOUTUBE_MUSIC_HOST else "www.youtube.com"
    if video_id:
        # Um vídeo aberto de dentro de uma playlist toca só o vídeo, como no
        # navegador; a playlist inteira abre pelo link ``playlist?list=``.
        return f"https://{base_host}/watch?{urlencode({'v': video_id})}"
    return f"https://{base_host}/playlist?{urlencode({'list': playlist_id})}"


def youtube_playlist_id(url):
    """O id da playlist de um link ``playlist?list=``; ``None`` para vídeos e outros links."""
    found = _video_and_playlist(url)
    if found is None or found[1]:
        return None
    return found[2]
