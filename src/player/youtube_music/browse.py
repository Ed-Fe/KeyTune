from __future__ import annotations

import re
from contextlib import contextmanager
from dataclasses import dataclass, replace

from ..i18n import _
from .models import YOUTUBE_SEARCH_SOURCE_MUSIC, YouTubeMediaSearchResult
from .search import _normalize_music_track_result


@dataclass(frozen=True)
class YouTubeMoodCategory:
    """A single "Moods & Genres" category, used to fetch its playlists."""

    title: str
    params: str
    section: str = ""


def normalize_mood_categories(raw_categories):
    """Flatten ``get_mood_categories`` into ordered ``(section, categories)`` pairs.

    ``raw_categories`` is the dict returned by ``YTMusic.get_mood_categories``
    (sections such as ``"For you"``, ``"Genres"``, ``"Moods & moments"`` mapping
    to lists of ``{"title", "params"}`` entries).  Sections and entries that are
    empty or malformed are skipped.
    """
    sections = []
    if not isinstance(raw_categories, dict):
        return sections

    for raw_section_title, entries in raw_categories.items():
        section_title = str(raw_section_title or "").strip()
        categories = []
        for entry in entries or []:
            if not isinstance(entry, dict):
                continue
            title = str(entry.get("title") or "").strip()
            params = str(entry.get("params") or "").strip()
            if not title or not params:
                continue
            categories.append(
                YouTubeMoodCategory(title=title, params=params, section=section_title)
            )
        if categories:
            sections.append((section_title, categories))

    return sections


def normalize_mood_playlists(raw_playlists, *, badge=None):
    if badge is None:
        badge = _("Mood ou gênero")
    """Normalize ``get_mood_playlists`` items into playlist search results."""
    results = []
    seen_playlist_ids = set()
    for item in raw_playlists or []:
        normalized_result = _normalize_browse_playlist(item, badge=badge)
        if normalized_result is None:
            continue
        if normalized_result.playlist_id in seen_playlist_ids:
            continue
        results.append(normalized_result)
        seen_playlist_ids.add(normalized_result.playlist_id)
    return results


def _normalize_browse_playlist(item, *, badge):
    if not isinstance(item, dict):
        return None

    playlist_id = str(item.get("playlistId") or "").strip()
    title = str(item.get("title") or "").strip()
    if not playlist_id or not title:
        return None

    detail_parts = []
    description = str(item.get("description") or "").strip()
    if description:
        detail_parts.append(description)
    count_text = str(item.get("count") or "").strip()
    if count_text:
        detail_parts.append(count_text)

    return YouTubeMediaSearchResult(
        source=YOUTUBE_SEARCH_SOURCE_MUSIC,
        result_type="playlist",
        title=title,
        detail_text=" · ".join(detail_parts),
        playlist_id=playlist_id,
        source_badge=str(badge or "").strip() or _("Mood ou gênero"),
    )


def extract_browse_playlists_from_response(response):
    """Extract playlist tiles from a raw ``moods_and_genres`` browse response.

    ytmusicapi 1.12.0's ``get_mood_playlists`` crashes on the *Genres* category
    pages because those lead with a carousel of songs
    (``musicResponsiveListItemRenderer``) that its playlist parser does not
    expect.  This walker is a resilient fallback: it scans the whole response
    for ``musicTwoRowItemRenderer`` tiles and keeps the ones pointing at a
    playlist, returning dicts shaped like ``get_library_playlists`` items so
    :func:`normalize_mood_playlists` can consume them unchanged.
    """
    tiles = []
    _collect_two_row_items(response, tiles)

    playlists = []
    seen_playlist_ids = set()
    for tile in tiles:
        playlist = _playlist_from_two_row_item(tile)
        if playlist is None:
            continue
        if playlist["playlistId"] in seen_playlist_ids:
            continue
        playlists.append(playlist)
        seen_playlist_ids.add(playlist["playlistId"])
    return playlists


def _collect_two_row_items(node, tiles):
    if isinstance(node, dict):
        tile = node.get("musicTwoRowItemRenderer")
        if isinstance(tile, dict):
            tiles.append(tile)
        for value in node.values():
            _collect_two_row_items(value, tiles)
        return
    if isinstance(node, list):
        for item in node:
            _collect_two_row_items(item, tiles)


def _playlist_from_two_row_item(tile):
    browse_endpoint = _browse_endpoint_from_two_row_item(tile)
    browse_id = str(browse_endpoint.get("browseId") or "").strip()
    page_type = str(
        (
            (browse_endpoint.get("browseEndpointContextSupportedConfigs") or {})
            .get("browseEndpointContextMusicConfig")
            or {}
        ).get("pageType")
        or ""
    ).strip()

    is_playlist = browse_id.startswith("VL") or page_type == "MUSIC_PAGE_TYPE_PLAYLIST"
    if not is_playlist:
        return None

    playlist_id = browse_id[2:] if browse_id.startswith("VL") else browse_id
    if not playlist_id:
        return None

    title_runs = (tile.get("title") or {}).get("runs") or []
    title = str(title_runs[0].get("text") or "").strip() if title_runs else ""
    if not title:
        return None

    subtitle_runs = (tile.get("subtitle") or {}).get("runs") or []
    description = "".join(str(run.get("text") or "") for run in subtitle_runs).strip()

    playlist = {"playlistId": playlist_id, "title": title, "description": description}

    # Mirror how ytmusicapi reads the track count out of a "<author> • Playlist
    # • <n> músicas" subtitle, so callers see the same shape either way.
    if len(subtitle_runs) == 3:
        count_text = str(subtitle_runs[2].get("text") or "").strip()
        if re.search(r"\d+ ", count_text):
            playlist["count"] = count_text.split(" ")[0]

    return playlist


def _browse_endpoint_from_two_row_item(tile):
    """Return the tile's ``browseEndpoint``, checking both places it appears.

    Most tiles carry it at the top level, but ytmusicapi reads it off the first
    title run instead — and library playlist tiles are not always consistent.
    Trying both keeps this parser usable as a fallback for either shape.
    """
    if not isinstance(tile, dict):
        return {}

    candidates = [tile.get("navigationEndpoint")]
    title_runs = (tile.get("title") or {}).get("runs") or []
    if title_runs and isinstance(title_runs[0], dict):
        candidates.append(title_runs[0].get("navigationEndpoint"))

    for candidate in candidates:
        browse_endpoint = (candidate or {}).get("browseEndpoint") or {}
        if browse_endpoint.get("browseId"):
            return browse_endpoint
    return {}


@contextmanager
def tolerant_library_playlist_parsing():
    """Temporarily make ytmusicapi's library playlist parser skip bad tiles.

    ``ytmusicapi.parsers.browsing.parse_playlist`` navigates to the tile
    thumbnail *without* ``none_if_absent``, so a single library tile served
    without cover art (``thumbnail: {}``) raises ``KeyError`` and aborts the
    whole listing.  Still unguarded as of ytmusicapi 1.12.1.

    ``ytmusicapi.mixins.library`` imports that function into its own namespace
    and both the first page and the continuations resolve it there, so swapping
    that one name covers the entire fetch — unlike parsing the raw response,
    which would stop at the first page.  Tiles the original parser chokes on are
    rebuilt by :func:`_playlist_from_two_row_item` (the thumbnail is dropped,
    which no caller here uses).

    Falls through as a no-op when the module layout no longer matches, leaving
    the caller with ytmusicapi's own behavior rather than a new failure.
    """
    try:
        from ytmusicapi.mixins import library as library_mixin
    except Exception:
        yield
        return

    original_parse_playlist = getattr(library_mixin, "parse_playlist", None)
    if not callable(original_parse_playlist):
        yield
        return

    def parse_playlist_tolerantly(tile):
        try:
            return original_parse_playlist(tile)
        except (KeyError, IndexError, TypeError, AttributeError):
            return _playlist_from_two_row_item(tile) or {}

    library_mixin.parse_playlist = parse_playlist_tolerantly
    try:
        yield
    finally:
        library_mixin.parse_playlist = original_parse_playlist


def normalize_track_items(raw_items, *, badge):
    """Normalize ``get_liked_songs``/``get_history`` items into song results.

    Reuses the search-track normalizer so artists, album, duration and
    like/feedback tokens are parsed exactly like search results, then stamps a
    custom *badge* (e.g. ``"Curtida"`` or ``"Histórico"``).  Items are
    deduplicated by ``videoId`` keeping the first occurrence, so a history
    listing collapses repeated plays into their most recent entry.
    """
    normalized_badge = str(badge or "").strip()
    results = []
    seen_video_ids = set()
    for item in raw_items or []:
        if not isinstance(item, dict):
            continue
        normalized_result = _normalize_music_track_result(item, result_type="song")
        if normalized_result is None:
            continue
        if normalized_result.video_id in seen_video_ids:
            continue
        seen_video_ids.add(normalized_result.video_id)
        if normalized_badge:
            normalized_result = replace(normalized_result, source_badge=normalized_badge)
        results.append(normalized_result)
    return results
