from __future__ import annotations

import re

from .dependencies import ensure_yt_dlp_executable_available
from .models import (
    YOUTUBE_SEARCH_SOURCE_MUSIC,
    YOUTUBE_SEARCH_SOURCE_YOUTUBE,
    YouTubeMediaSearchResult,
)
from ..i18n import _
from .playlists import build_watch_url, build_youtube_watch_url
from .yt_dlp_runtime import extract_info as extract_yt_dlp_info


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
        elif result_type == "album":
            normalized_result = normalize_music_album_result(item)
        elif result_type == "artist":
            normalized_result = normalize_music_artist_result(item)
        else:
            normalized_result = None

        if normalized_result is not None:
            normalized_results.append(normalized_result)

    return normalized_results


def search_youtube_videos(query, *, limit=15):
    normalized_query = str(query or "").strip()
    if not normalized_query:
        return []

    ensure_yt_dlp_executable_available()

    normalized_limit = max(1, int(limit or 15))
    search_query = f"ytsearch{normalized_limit}:{normalized_query}"
    try:
        response = extract_yt_dlp_info(
            search_query,
            extract_flat="in_playlist",
            playlist_end=normalized_limit,
            socket_timeout_seconds=YOUTUBE_SEARCH_SOCKET_TIMEOUT_SECONDS,
            quiet=True,
            no_warnings=True,
        )
        info = response.data
    except Exception as exc:
        raise RuntimeError(
            _clean_external_tool_error(exc) or _("O yt-dlp não conseguiu pesquisar vídeos no YouTube.")
        ) from exc

    results = []
    for entry in (info or {}).get("entries") or []:
        result = normalize_youtube_entry(entry)
        if result is not None and result.result_type == "video":
            results.append(result)

    return results


def normalize_youtube_entry(entry, *, show_owner=True):
    """Converte uma entrada da listagem do yt-dlp em vídeo, canal ou playlist do YouTube."""
    if not isinstance(entry, dict):
        return None

    entry_id = str(entry.get("id") or "").strip()
    entry_url = str(entry.get("url") or "").strip()
    title = str(entry.get("title") or "").strip()
    if not title or not (entry_id or entry_url):
        return None

    owner = str(entry.get("channel") or entry.get("uploader") or "").strip() if show_owner else ""

    if "/channel/" in entry_url or (not entry_url and entry_id.startswith("UC")):
        followers_text = _format_count(entry.get("channel_follower_count"), _(" inscritos"))
        return YouTubeMediaSearchResult(
            source=YOUTUBE_SEARCH_SOURCE_YOUTUBE,
            result_type="channel",
            title=title,
            detail_text=followers_text,
            browse_id=str(entry.get("channel_id") or entry_id).strip(),
            source_badge="YouTube",
        )

    if "list=" in entry_url:
        return YouTubeMediaSearchResult(
            source=YOUTUBE_SEARCH_SOURCE_YOUTUBE,
            result_type="playlist",
            title=title,
            subtitle=owner,
            playlist_id=entry_id,
            source_badge="YouTube",
        )

    video_id = entry_id or entry_url
    detail_parts = []
    if str(entry.get("live_status") or "").strip() == "is_live":
        detail_parts.append(_("ao vivo"))
    duration_text = _format_duration(entry.get("duration"))
    if duration_text:
        detail_parts.append(duration_text)
    view_count_text = _format_view_count(entry.get("view_count"))
    if view_count_text:
        detail_parts.append(view_count_text)

    return YouTubeMediaSearchResult(
        source=YOUTUBE_SEARCH_SOURCE_YOUTUBE,
        result_type="video",
        title=title,
        subtitle=owner,
        detail_text=" · ".join(detail_parts),
        video_id=video_id,
        playback_url=build_youtube_watch_url(video_id),
        source_badge="YouTube",
    )


def normalize_music_album_result(item, *, artist_name=""):
    """Álbum, single ou EP do YouTube Music; toca pela playlist do álbum."""
    title = str(item.get("title") or "").strip()
    playlist_id = str(item.get("playlistId") or item.get("audioPlaylistId") or "").strip()
    browse_id = str(item.get("browseId") or "").strip()
    if not title or not (playlist_id or browse_id):
        return None

    detail_parts = []
    for value in (item.get("type"), item.get("year")):
        normalized_value = str(value or "").strip()
        if normalized_value:
            detail_parts.append(normalized_value)

    return YouTubeMediaSearchResult(
        source=YOUTUBE_SEARCH_SOURCE_MUSIC,
        result_type="album",
        title=title,
        subtitle=_artists_text(item) or str(artist_name or "").strip(),
        detail_text=" · ".join(detail_parts),
        playlist_id=playlist_id,
        browse_id=browse_id,
        source_badge="YouTube Music",
    )


def normalize_music_artist_result(item):
    name = str(item.get("artist") or item.get("title") or "").strip()
    browse_id = str(item.get("browseId") or "").strip()
    if not name or not browse_id:
        return None

    subscribers = str(item.get("subscribers") or "").strip()
    return YouTubeMediaSearchResult(
        source=YOUTUBE_SEARCH_SOURCE_MUSIC,
        result_type="artist",
        title=name,
        detail_text=_("{count} inscritos").format(count=subscribers) if subscribers else "",
        browse_id=browse_id,
        source_badge="YouTube Music",
    )


def normalize_music_video_items(raw_items):
    """Vídeos de um artista: como faixas, mas anunciados como vídeo."""
    results = []
    seen_video_ids = set()
    for item in raw_items or []:
        if not isinstance(item, dict):
            continue
        result = _normalize_music_track_result(item, result_type="video")
        if result is None or result.video_id in seen_video_ids:
            continue
        seen_video_ids.add(result.video_id)
        results.append(result)
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
    return _format_count(view_count, _(" visualizações"))


def _format_count(value, suffix):
    try:
        normalized_value = int(value)
    except (TypeError, ValueError):
        return ""

    if normalized_value <= 0:
        return ""
    return f"{normalized_value:,}".replace(",", ".") + suffix


def _clean_external_tool_error(error):
    message = re.sub(r"\x1b\[[0-9;]*m", "", str(error or "")).strip()
    if "ERROR:" in message:
        message = message.split("ERROR:", 1)[1].strip()
    return message
