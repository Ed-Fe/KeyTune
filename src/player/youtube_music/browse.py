from __future__ import annotations

from dataclasses import dataclass, replace

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
        source_badge=str(badge or "").strip() or "Mood ou gênero",
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
    browse_endpoint = (
        ((tile.get("navigationEndpoint") or {}).get("browseEndpoint") or {})
        if isinstance(tile, dict)
        else {}
    )
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

    return {"playlistId": playlist_id, "title": title, "description": description}


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
