from __future__ import annotations

import re

from .dependencies import import_yt_dlp_module
from .models import (
    YOUTUBE_SEARCH_SOURCE_MUSIC,
    YOUTUBE_SEARCH_SOURCE_YOUTUBE,
    YouTubeMediaSearchResult,
)
from .playlists import build_watch_url, build_youtube_watch_url


YOUTUBE_SEARCH_SOCKET_TIMEOUT_SECONDS = 10


def normalize_music_search_results(raw_results):
    normalized_results = []
    for item in raw_results or []:
        if not isinstance(item, dict):
            continue

        result_type = str(item.get("resultType") or "").strip().lower()
        if result_type == "playlist":
            normalized_result = _normalize_music_playlist_result(item)
        elif result_type in {"song", "video"}:
            normalized_result = _normalize_music_track_result(item, result_type=result_type)
        else:
            normalized_result = None

        if normalized_result is not None:
            normalized_results.append(normalized_result)

    return normalized_results


def search_youtube_videos(query, *, limit=15):
    normalized_query = str(query or "").strip()
    if not normalized_query:
        return []

    yt_dlp = import_yt_dlp_module()

    normalized_limit = max(1, int(limit or 15))
    search_query = f"ytsearch{normalized_limit}:{normalized_query}"
    options = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": "in_playlist",
        "playlistend": normalized_limit,
        "socket_timeout": YOUTUBE_SEARCH_SOCKET_TIMEOUT_SECONDS,
    }

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(search_query, download=False)
    except Exception as exc:
        raise RuntimeError(
            _clean_external_tool_error(exc) or "O yt-dlp não conseguiu pesquisar vídeos no YouTube."
        ) from exc

    results = []
    for entry in (info or {}).get("entries") or []:
        if not isinstance(entry, dict):
            continue

        video_id = str(entry.get("id") or entry.get("url") or "").strip()
        title = str(entry.get("title") or "").strip()
        if not video_id or not title:
            continue

        subtitle = str(entry.get("channel") or entry.get("uploader") or "").strip()
        detail_parts = []
        duration_text = _format_duration(entry.get("duration"))
        if duration_text:
            detail_parts.append(duration_text)
        view_count_text = _format_view_count(entry.get("view_count"))
        if view_count_text:
            detail_parts.append(view_count_text)

        results.append(
            YouTubeMediaSearchResult(
                source=YOUTUBE_SEARCH_SOURCE_YOUTUBE,
                result_type="video",
                title=title,
                subtitle=subtitle,
                detail_text=" · ".join(detail_parts),
                video_id=video_id,
                playback_url=build_youtube_watch_url(video_id),
                source_badge="YouTube",
            )
        )

    return results


def _normalize_music_track_result(item, *, result_type):
    video_id = str(item.get("videoId") or "").strip()
    title = str(item.get("title") or "").strip()
    if not video_id or not title:
        return None

    subtitle = _artists_text(item) or str(item.get("artist") or "").strip()
    detail_parts = []
    duration_text = str(item.get("duration") or "").strip()
    if duration_text:
        detail_parts.append(duration_text)

    album_name = ""
    album = item.get("album") or {}
    if isinstance(album, dict):
        album_name = str(album.get("name") or "").strip()
    if album_name and result_type == "song":
        detail_parts.append(album_name)

    views_text = str(item.get("views") or "").strip()
    if views_text and result_type == "video":
        detail_parts.append(views_text)

    feedback_tokens = item.get("feedbackTokens") or {}
    if not isinstance(feedback_tokens, dict):
        feedback_tokens = {}
    feedback_add_token = str(feedback_tokens.get("add") or "").strip()
    feedback_remove_token = str(feedback_tokens.get("remove") or "").strip()

    return YouTubeMediaSearchResult(
        source=YOUTUBE_SEARCH_SOURCE_MUSIC,
        result_type=result_type,
        title=title,
        subtitle=subtitle,
        detail_text=" · ".join(detail_parts),
        video_id=video_id,
        playback_url=build_watch_url(video_id),
        source_badge="YouTube Music",
        feedback_add_token=feedback_add_token,
        feedback_remove_token=feedback_remove_token,
        like_status=str(item.get("likeStatus") or "").strip(),
        in_library=bool(item.get("inLibrary")) or bool(feedback_remove_token and not feedback_add_token),
    )


def _normalize_music_playlist_result(item):
    playlist_id = _playlist_id_from_result(item)
    title = str(item.get("title") or "").strip()
    if not playlist_id or not title:
        return None

    author = _author_text(item)
    item_count_text = _playlist_item_count_text(item.get("itemCount"))
    detail_parts = []
    if author:
        detail_parts.append(author)
    if item_count_text:
        detail_parts.append(item_count_text)

    return YouTubeMediaSearchResult(
        source=YOUTUBE_SEARCH_SOURCE_MUSIC,
        result_type="playlist",
        title=title,
        detail_text=" · ".join(detail_parts),
        playlist_id=playlist_id,
        browse_id=str(item.get("browseId") or "").strip(),
        source_badge="YouTube Music",
    )


def _playlist_id_from_result(item):
    playlist_id = str(item.get("playlistId") or "").strip()
    if playlist_id:
        return playlist_id

    browse_id = str(item.get("browseId") or "").strip()
    if browse_id.startswith("VL"):
        return browse_id[2:]
    if browse_id.startswith(("RD", "VM")):
        return browse_id
    return ""


def _artists_text(item):
    artist_names = []
    for artist in item.get("artists") or []:
        if isinstance(artist, dict):
            artist_name = str(artist.get("name") or "").strip()
        else:
            artist_name = str(artist or "").strip()
        if artist_name:
            artist_names.append(artist_name)
    return ", ".join(artist_names)


def _author_text(item):
    author = item.get("author")
    if isinstance(author, list):
        author_names = []
        for entry in author:
            if isinstance(entry, dict):
                entry_name = str(entry.get("name") or "").strip()
            else:
                entry_name = str(entry or "").strip()
            if entry_name:
                author_names.append(entry_name)
        return ", ".join(author_names)

    return str(author or "").strip()


def _playlist_item_count_text(item_count):
    if isinstance(item_count, int) and item_count > 0:
        suffix = "item" if item_count == 1 else "itens"
        return f"{item_count} {suffix}"

    normalized_item_count = str(item_count or "").strip()
    if not normalized_item_count:
        return ""
    if normalized_item_count.isdigit():
        numeric_count = int(normalized_item_count)
        suffix = "item" if numeric_count == 1 else "itens"
        return f"{numeric_count} {suffix}"
    return normalized_item_count


def _format_duration(duration_seconds):
    try:
        total_seconds = int(duration_seconds)
    except (TypeError, ValueError):
        return ""

    if total_seconds <= 0:
        return ""

    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02}:{seconds:02}"
    return f"{minutes}:{seconds:02}"


def _format_view_count(view_count):
    try:
        normalized_view_count = int(view_count)
    except (TypeError, ValueError):
        return ""

    if normalized_view_count <= 0:
        return ""
    return f"{normalized_view_count:,}".replace(",", ".") + " visualizações"


def _clean_external_tool_error(error):
    message = re.sub(r"\x1b\[[0-9;]*m", "", str(error or "")).strip()
    if "ERROR:" in message:
        message = message.split("ERROR:", 1)[1].strip()
    return message