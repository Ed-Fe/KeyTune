"""Páginas de resultados do YouTube e do YouTube Music.

Cada função devolve um :class:`YouTubeResultPage` com os itens de ``start`` até
``start + count`` e a indicação de que há mais depois deles. É o que permite às
listas da busca carregar mais conforme o usuário chega ao fim, e abrir canais,
artistas, álbuns e playlists para ver o que há dentro.
"""

from __future__ import annotations

from urllib.parse import urlencode

from ..i18n import _
from ..log import get_logger
from . import youtubejs_runtime
from .browse import normalize_track_items, tolerant_watch_playlist_parsing
from .dependencies import ensure_yt_dlp_executable_available, youtubejs_resolver_enabled
from .models import (
    YOUTUBE_ARTIST_SECTION_ALBUMS,
    YOUTUBE_ARTIST_SECTION_RELATED,
    YOUTUBE_ARTIST_SECTION_SINGLES,
    YOUTUBE_ARTIST_SECTION_SONGS,
    YOUTUBE_ARTIST_SECTION_VIDEOS,
    YOUTUBE_CHANNEL_SECTION_PLAYLISTS,
    YOUTUBE_CHANNEL_SECTIONS,
    YOUTUBE_KIND_CHANNELS,
    YOUTUBE_KIND_PLAYLISTS,
    YOUTUBE_KIND_VIDEOS,
    YouTubeResultPage,
)
from .playlists import is_watch_playlist_id
from .search import (
    _clean_external_tool_error,
    normalize_music_album_result,
    normalize_music_artist_result,
    normalize_music_search_results,
    normalize_music_video_items,
    normalize_youtube_entry,
)
from .yt_dlp_runtime import extract_info as extract_yt_dlp_info


_logger = get_logger(__name__)

YOUTUBE_LISTING_SOCKET_TIMEOUT_SECONDS = 20
WATCH_PLAYLIST_LIMIT = 200

# Filtros da busca do YouTube (parâmetro ``sp`` da página de resultados).
_YOUTUBE_SEARCH_FILTERS = {
    YOUTUBE_KIND_CHANNELS: "EgIQAg==",
    YOUTUBE_KIND_PLAYLISTS: "EgIQAw==",
}
_CHANNEL_SECTION_IDS = {section.section_id for section in YOUTUBE_CHANNEL_SECTIONS}
_MISSING_CHANNEL_TAB_MARKER = "does not have a"


def _page_bounds(start, count):
    normalized_start = max(0, int(start or 0))
    normalized_count = max(1, int(count or 1))
    return normalized_start, normalized_count


def _slice_page(items, start, count):
    """Recorta a página de uma lista que foi pedida desde o começo."""
    items = list(items or [])
    return items[start:start + count], len(items) >= start + count


# -- YouTube (yt-dlp) -----------------------------------------------------------


def _normalized_entries_page(entries, has_more, *, show_owner=True):
    results = []
    for entry in entries:
        result = normalize_youtube_entry(entry, show_owner=show_owner)
        if result is not None:
            results.append(result)
    return YouTubeResultPage(results=tuple(results), has_more=has_more)


def _youtubejs_page(fetch, *, show_owner=True):
    """A página pelo YouTube.js, ou ``None`` quando ele está desligado ou falha (aí vale o yt-dlp)."""
    if not youtubejs_resolver_enabled():
        return None
    try:
        entries, has_more = fetch()
    except Exception as exc:
        _logger.warning("O YouTube.js não listou; usando o yt-dlp: %s", exc)
        return None
    return _normalized_entries_page(entries, has_more, show_owner=show_owner)


def _youtube_listing_page(target, start, count, *, show_owner=True):
    ensure_yt_dlp_executable_available()
    try:
        response = extract_yt_dlp_info(
            target,
            extract_flat="in_playlist",
            playlist_items=f"{start + 1}-{start + count}",
            socket_timeout_seconds=YOUTUBE_LISTING_SOCKET_TIMEOUT_SECONDS,
            quiet=True,
            no_warnings=True,
        )
    except Exception as exc:
        raise RuntimeError(
            _clean_external_tool_error(exc) or _("O yt-dlp não conseguiu listar o conteúdo do YouTube.")
        ) from exc

    entries = (response.data or {}).get("entries") or []
    return _normalized_entries_page(entries, len(entries) >= count, show_owner=show_owner)


def youtube_search_page(query, kind, start, count):
    normalized_query = str(query or "").strip()
    if not normalized_query:
        return YouTubeResultPage()

    start, count = _page_bounds(start, count)
    page = _youtubejs_page(lambda: youtubejs_runtime.search_page(normalized_query, kind, start=start, count=count))
    if page is not None:
        return page

    if kind in _YOUTUBE_SEARCH_FILTERS:
        target = "https://www.youtube.com/results?" + urlencode(
            {"search_query": normalized_query, "sp": _YOUTUBE_SEARCH_FILTERS[kind]}
        )
    else:
        target = f"ytsearch{start + count}:{normalized_query}"

    page = _youtube_listing_page(target, start, count)
    wanted_type = {
        YOUTUBE_KIND_CHANNELS: "channel",
        YOUTUBE_KIND_PLAYLISTS: "playlist",
        YOUTUBE_KIND_VIDEOS: "video",
    }.get(kind, "video")
    return YouTubeResultPage(
        results=tuple(result for result in page.results if result.result_type == wanted_type),
        has_more=page.has_more,
    )


def youtube_channel_page(channel_id, section_id, start, count):
    normalized_channel_id = str(channel_id or "").strip()
    if not normalized_channel_id:
        return YouTubeResultPage()
    if section_id not in _CHANNEL_SECTION_IDS:
        section_id = YOUTUBE_CHANNEL_SECTIONS[0].section_id

    start, count = _page_bounds(start, count)
    target = f"https://www.youtube.com/channel/{normalized_channel_id}/{section_id}"
    try:
        # Na aba de playlists o "dono" que o YouTube informa é só a palavra "Playlist".
        return _youtube_listing_page(
            target,
            start,
            count,
            show_owner=section_id != YOUTUBE_CHANNEL_SECTION_PLAYLISTS,
        )
    except RuntimeError as exc:
        if _MISSING_CHANNEL_TAB_MARKER in str(exc):
            # O canal não tem essa aba (por exemplo, nunca publicou Shorts).
            return YouTubeResultPage()
        raise


def youtube_playlist_page(playlist_id, start, count):
    normalized_playlist_id = str(playlist_id or "").strip()
    if not normalized_playlist_id:
        return YouTubeResultPage()

    start, count = _page_bounds(start, count)
    target = "https://www.youtube.com/playlist?" + urlencode({"list": normalized_playlist_id})
    page = _youtube_listing_page(target, start, count)
    return YouTubeResultPage(
        results=tuple(result for result in page.results if result.result_type == "video"),
        has_more=page.has_more,
    )


# -- YouTube Music (ytmusicapi) -------------------------------------------------


def music_search_page(client, query, music_filter, start, count):
    normalized_query = str(query or "").strip()
    if not normalized_query:
        return YouTubeResultPage()

    start, count = _page_bounds(start, count)
    # O ytmusicapi não retoma uma busca do meio: pede-se do começo até o fim da página.
    raw_results = client.search(normalized_query, filter=music_filter or None, limit=start + count)
    page_items, has_more = _slice_page(raw_results, start, count)
    return YouTubeResultPage(results=tuple(normalize_music_search_results(page_items)), has_more=has_more)


def music_playlist_page(client, playlist_id, start, count, *, as_videos=False):
    normalized_playlist_id = str(playlist_id or "").strip()
    if not normalized_playlist_id:
        return YouTubeResultPage()

    start, count = _page_bounds(start, count)
    if is_watch_playlist_id(normalized_playlist_id):
        with tolerant_watch_playlist_parsing():
            playlist = client.get_watch_playlist(playlistId=normalized_playlist_id, limit=WATCH_PLAYLIST_LIMIT)
        page_items, _has_more = _slice_page(playlist.get("tracks"), start, count)
        has_more = len(playlist.get("tracks") or []) > start + count
    else:
        playlist = client.get_playlist(normalized_playlist_id, limit=start + count)
        page_items, has_more = _slice_page(playlist.get("tracks"), start, count)

    normalize = normalize_music_video_items if as_videos else _normalize_tracks
    return YouTubeResultPage(results=tuple(normalize(page_items)), has_more=has_more)


def music_album_page(client, browse_id, playlist_id, start, count):
    normalized_browse_id = str(browse_id or "").strip()
    if not normalized_browse_id:
        return music_playlist_page(client, playlist_id, start, count)

    start, count = _page_bounds(start, count)
    album = client.get_album(normalized_browse_id)
    page_items, has_more = _slice_page(album.get("tracks"), start, count)
    has_more = len(album.get("tracks") or []) > start + count
    return YouTubeResultPage(results=tuple(_normalize_tracks(page_items)), has_more=has_more)


def music_artist_page(client, artist, section_id, start, count):
    """Página de uma seção de *artist* (a resposta de ``YTMusic.get_artist``)."""
    start, count = _page_bounds(start, count)
    artist = artist if isinstance(artist, dict) else {}
    section = artist.get(section_id) or {}
    if not isinstance(section, dict):
        section = {}
    preview = section.get("results") or []
    section_browse_id = str(section.get("browseId") or "").strip()
    section_params = str(section.get("params") or "").strip()

    if section_id in (YOUTUBE_ARTIST_SECTION_SONGS, YOUTUBE_ARTIST_SECTION_VIDEOS):
        as_videos = section_id == YOUTUBE_ARTIST_SECTION_VIDEOS
        if section_browse_id:
            return music_playlist_page(client, section_browse_id, start, count, as_videos=as_videos)
        page_items, _has_more = _slice_page(preview, start, count)
        normalize = normalize_music_video_items if as_videos else _normalize_tracks
        return YouTubeResultPage(results=tuple(normalize(page_items)), has_more=len(preview) > start + count)

    if section_id in (YOUTUBE_ARTIST_SECTION_ALBUMS, YOUTUBE_ARTIST_SECTION_SINGLES):
        albums = preview
        if section_browse_id and section_params:
            albums = client.get_artist_albums(section_browse_id, section_params, limit=None)
        albums = list(albums or [])
        artist_name = str(artist.get("name") or "").strip()
        results = []
        for item in albums[start:start + count]:
            result = normalize_music_album_result(item, artist_name=artist_name) if isinstance(item, dict) else None
            if result is not None:
                results.append(result)
        return YouTubeResultPage(results=tuple(results), has_more=len(albums) > start + count)

    if section_id == YOUTUBE_ARTIST_SECTION_RELATED:
        results = []
        for item in list(preview)[start:start + count]:
            result = normalize_music_artist_result(item) if isinstance(item, dict) else None
            if result is not None:
                results.append(result)
        return YouTubeResultPage(results=tuple(results), has_more=len(preview) > start + count)

    return YouTubeResultPage()


def _normalize_tracks(raw_items):
    return normalize_track_items(raw_items, badge="")
