from __future__ import annotations

from dataclasses import dataclass

from .library import is_remote_media_path
from .youtube_music.dependencies import import_yt_dlp_module
from .youtube_music.playlists import is_youtube_music_media


YTDLP_METADATA_SOCKET_TIMEOUT_SECONDS = 10


@dataclass(slots=True)
class RemoteMediaMetadata:
    title: str = ""
    artist: str = ""


@dataclass(slots=True)
class RemoteMediaPlayback:
    stream_url: str = ""
    http_headers: dict[str, str] | None = None
    title: str = ""
    artist: str = ""


_REMOTE_PLAYBACK_ALLOWED_HEADER_NAMES = {
    "accept",
    "accept-language",
    "cookie",
    "origin",
    "referer",
    "user-agent",
}


def resolve_remote_media_playback(media_path: str) -> RemoteMediaPlayback:
    normalized_media_path = str(media_path or "").strip()
    if not normalized_media_path or not is_remote_media_path(normalized_media_path):
        return RemoteMediaPlayback(stream_url=normalized_media_path, http_headers={})

    if is_youtube_music_media(normalized_media_path):
        return RemoteMediaPlayback(stream_url=normalized_media_path, http_headers={})

    info = _extract_remote_media_info(normalized_media_path)
    if not isinstance(info, dict):
        return RemoteMediaPlayback(stream_url=normalized_media_path, http_headers={})

    selected_stream_url, selected_headers = _preferred_stream_from_info(info)
    if not selected_stream_url:
        return RemoteMediaPlayback(stream_url=normalized_media_path, http_headers={})

    return RemoteMediaPlayback(
        stream_url=selected_stream_url,
        http_headers=selected_headers,
        title=_normalize_metadata_text(
            info.get("title") or info.get("fulltitle") or info.get("track") or info.get("alt_title")
        ),
        artist=_normalize_metadata_text(
            info.get("artist") or info.get("uploader") or info.get("channel") or info.get("creator")
        ),
    )


def resolve_remote_media_metadata(media_path: str) -> RemoteMediaMetadata:
    normalized_media_path = str(media_path or "").strip()
    if not normalized_media_path or not is_remote_media_path(normalized_media_path):
        return RemoteMediaMetadata()

    if is_youtube_music_media(normalized_media_path):
        return RemoteMediaMetadata()

    info = _extract_remote_media_info(normalized_media_path)
    if not isinstance(info, dict):
        return RemoteMediaMetadata()

    return RemoteMediaMetadata(
        title=_normalize_metadata_text(
            info.get("title") or info.get("fulltitle") or info.get("track") or info.get("alt_title")
        ),
        artist=_normalize_metadata_text(
            info.get("artist") or info.get("uploader") or info.get("channel") or info.get("creator")
        ),
    )


def _normalize_metadata_text(value) -> str:
    return str(value or "").strip()


def _extract_remote_media_info(media_path: str):
    try:
        yt_dlp = import_yt_dlp_module()
    except Exception:
        return None

    options = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "extract_flat": False,
        "socket_timeout": YTDLP_METADATA_SOCKET_TIMEOUT_SECONDS,
    }
    try:
        with yt_dlp.YoutubeDL(options) as downloader:
            return downloader.extract_info(media_path, download=False)
    except Exception:
        return None


def _preferred_stream_from_info(info):
    direct_url = _normalize_metadata_text(info.get("url"))
    direct_headers = _normalize_http_headers(info.get("http_headers"))
    if direct_url and _looks_like_direct_media_url(direct_url):
        return direct_url, direct_headers

    formats = info.get("formats")
    if not isinstance(formats, list):
        return direct_url, direct_headers

    best_candidate_url = ""
    best_candidate_headers = {}
    best_candidate_score = None
    for raw_format in formats:
        if not isinstance(raw_format, dict):
            continue
        candidate_url = _normalize_metadata_text(
            raw_format.get("url") or raw_format.get("manifest_url") or raw_format.get("hls_manifest_url")
        )
        if not candidate_url:
            continue

        candidate_score = _stream_format_score(raw_format)
        if best_candidate_score is None or candidate_score > best_candidate_score:
            best_candidate_score = candidate_score
            best_candidate_url = candidate_url
            best_candidate_headers = _merge_http_headers(
                info.get("http_headers"),
                raw_format.get("http_headers"),
            )

    if best_candidate_url:
        return best_candidate_url, best_candidate_headers

    return direct_url, direct_headers


def _merge_http_headers(*header_groups):
    merged_headers = {}
    for header_group in header_groups:
        normalized_headers = _normalize_http_headers(header_group)
        for key, value in normalized_headers.items():
            merged_headers[key] = value
    return merged_headers


def _normalize_http_headers(raw_headers):
    normalized_headers = {}
    if not isinstance(raw_headers, dict):
        return normalized_headers

    for key, value in raw_headers.items():
        normalized_key = str(key or "").strip()
        normalized_value = str(value or "").strip()
        if not normalized_key or not normalized_value:
            continue
        if normalized_key.casefold() not in _REMOTE_PLAYBACK_ALLOWED_HEADER_NAMES:
            continue
        normalized_headers[normalized_key] = normalized_value

    return normalized_headers


def _looks_like_direct_media_url(stream_url: str) -> bool:
    normalized_stream_url = _normalize_metadata_text(stream_url).casefold()
    if not normalized_stream_url:
        return False

    return any(
        marker in normalized_stream_url
        for marker in (
            ".m3u8",
            ".mpd",
            ".mp4",
            ".m4a",
            ".mp3",
            ".webm",
            ".aac",
            ".ogg",
            ".wav",
            ".flac",
            ".ts",
            ".mkv",
        )
    )


def _looks_like_manifest_stream_url(stream_url: str) -> bool:
    normalized_stream_url = _normalize_metadata_text(stream_url).casefold()
    if not normalized_stream_url:
        return False

    return ".m3u8" in normalized_stream_url or ".mpd" in normalized_stream_url


def _stream_format_score(raw_format):
    stream_url = _normalize_metadata_text(
        raw_format.get("url") or raw_format.get("manifest_url") or raw_format.get("hls_manifest_url")
    )
    audio_codec = _normalize_metadata_text(raw_format.get("acodec")).casefold()
    video_codec = _normalize_metadata_text(raw_format.get("vcodec")).casefold()
    protocol = _normalize_metadata_text(raw_format.get("protocol")).casefold()
    extension = _normalize_metadata_text(raw_format.get("ext")).casefold()
    bitrate = raw_format.get("abr") or raw_format.get("tbr") or 0
    try:
        normalized_bitrate = float(bitrate or 0)
    except (TypeError, ValueError):
        normalized_bitrate = 0.0

    return (
        1 if audio_codec and audio_codec != "none" else 0,
        1 if video_codec == "none" else 0,
        1 if protocol in {"https", "http"} else 0,
        1 if not _looks_like_manifest_stream_url(stream_url) else 0,
        1 if extension in {"m4a", "mp3", "webm", "aac", "ogg", "wav", "flac", "mp4"} else 0,
        normalized_bitrate,
    )
