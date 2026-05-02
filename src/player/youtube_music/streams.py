import re
from urllib.parse import urlparse
from dataclasses import dataclass

from .auth import (
    create_temporary_browser_auth_cookie_file,
    load_saved_playback_auth,
    sanitize_sensitive_text,
)
from .dependencies import import_yt_dlp_module
from .playlists import is_youtube_music_media


YTDLP_STREAM_SOCKET_TIMEOUT_SECONDS = 10
YTDLP_STREAM_OPERATION_TIMEOUT_SECONDS = 15
_ALLOWED_PLAYBACK_HEADER_NAMES = {
    "accept",
    "accept-language",
    "cookie",
    "origin",
    "referer",
    "user-agent",
}
_COOKIE_FORWARDING_ALLOWED_HOST_SUFFIXES = (
    "googlevideo.com",
    "youtube.com",
    "youtubei.googleapis.com",
    "ytimg.com",
)


@dataclass(slots=True)
class ResolvedStreamPlayback:
    stream_url: str
    http_headers: dict[str, str] | None = None


def resolve_stream_url(media_path):
    return resolve_stream_playback(media_path).stream_url


def resolve_stream_playback(media_path):
    normalized_media_path = str(media_path or "").strip()
    if not is_youtube_music_media(normalized_media_path):
        return ResolvedStreamPlayback(stream_url=normalized_media_path, http_headers={})

    yt_dlp = import_yt_dlp_module()

    playback_auth = load_saved_playback_auth()

    base_options = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
        "extract_flat": False,
        "ignore_no_formats_error": True,
        "format": "bestaudio/best",
        "socket_timeout": YTDLP_STREAM_SOCKET_TIMEOUT_SECONDS,
    }
    temporary_cookie_file_path = ""
    if playback_auth.cookie_header:
        temporary_cookie_file_path = create_temporary_browser_auth_cookie_file(playback_auth.cookie_header)

    if temporary_cookie_file_path:
        base_options["cookiefile"] = temporary_cookie_file_path
    elif playback_auth.cookie_file_path:
        base_options["cookiefile"] = playback_auth.cookie_file_path

    if playback_auth.yt_dlp_http_headers:
        base_options["http_headers"] = dict(playback_auth.yt_dlp_http_headers)

    extractor_profiles = [
        {},
        {"extractor_args": {"youtube": {"player_client": ["web", "android", "ios"]}}},
        {"extractor_args": {"youtube": {"player_client": ["web_music", "web"]}}},
    ]

    last_error = ""
    attempted_profiles = 0
    try:
        for profile in extractor_profiles:
            attempted_profiles += 1
            try:
                with yt_dlp.YoutubeDL({**base_options, **profile}) as ydl:
                    info = ydl.extract_info(normalized_media_path, download=False)
            except Exception as exc:
                last_error = _clean_external_tool_error(exc)
                continue

            if not info:
                last_error = "O yt-dlp não conseguiu abrir a faixa do YouTube Music."
                continue

            try:
                resolved_playback = _preferred_stream_from_info(
                    info,
                    playback_auth_headers=playback_auth.playback_http_headers,
                )
            except RuntimeError as exc:
                last_error = _clean_external_tool_error(exc) or str(exc)
                continue

            if resolved_playback.stream_url:
                return resolved_playback

            last_error = "O yt-dlp não conseguiu determinar uma URL de reprodução compatível para esta faixa."
    finally:
        _remove_temporary_cookie_file(temporary_cookie_file_path)

    raise RuntimeError(
        _build_stream_resolution_error_message(
            last_error,
            attempted_profiles=attempted_profiles,
        )
    )


def _preferred_stream_url_from_info(info):
    return _preferred_stream_from_info(info).stream_url


def _preferred_stream_from_info(info, *, playback_auth_headers=None):
    direct_url = str(info.get("url") or "").strip()
    top_level_http_headers = _merge_playback_http_headers(
        info.get("http_headers"),
        playback_auth_headers,
        target_stream_url=direct_url,
    )

    formats = _iter_stream_format_candidates(info)
    if not formats:
        if _is_direct_media_stream_url(direct_url):
            return ResolvedStreamPlayback(stream_url=direct_url, http_headers=top_level_http_headers)
        raise RuntimeError("O yt-dlp não retornou um stream de áudio compatível para esta faixa do YouTube Music.")

    audio_only_formats = [fmt for fmt in formats if _is_audio_only_stream_format(fmt)]
    audio_capable_formats = [fmt for fmt in formats if _is_audio_capable_stream_format(fmt)]
    preferred_formats = audio_only_formats or audio_capable_formats
    if not preferred_formats:
        if _is_direct_media_stream_url(direct_url):
            return ResolvedStreamPlayback(stream_url=direct_url, http_headers=top_level_http_headers)
        raise RuntimeError("O yt-dlp não retornou um stream de áudio compatível para esta faixa do YouTube Music.")

    best_format = max(preferred_formats, key=_stream_format_score)
    selected_stream_url = str(best_format.get("url") or direct_url).strip()
    return ResolvedStreamPlayback(
        stream_url=selected_stream_url,
        http_headers=_merge_playback_http_headers(
            info.get("http_headers"),
            best_format.get("http_headers"),
            playback_auth_headers,
            target_stream_url=selected_stream_url,
        ),
    )


def _iter_stream_format_candidates(info):
    collected_formats = []
    seen_formats = set()
    for key in ("requested_formats", "requested_downloads", "formats"):
        raw_formats = info.get(key)
        if isinstance(raw_formats, dict):
            normalized_raw_formats = [raw_formats]
        elif isinstance(raw_formats, list):
            normalized_raw_formats = raw_formats
        else:
            continue

        for fmt in normalized_raw_formats:
            if not isinstance(fmt, dict):
                continue

            stream_url = str(fmt.get("url") or "").strip()
            if not stream_url:
                continue

            format_key = (str(fmt.get("format_id") or "").strip(), stream_url)
            if format_key in seen_formats:
                continue

            seen_formats.add(format_key)
            collected_formats.append(fmt)

    return collected_formats


def _is_audio_only_stream_format(fmt):
    return _is_audio_capable_stream_format(fmt) and str(fmt.get("vcodec") or "").strip().lower() == "none"


def _is_audio_capable_stream_format(fmt):
    acodec = str(fmt.get("acodec") or "").strip().lower()
    if acodec == "none":
        return False
    if acodec:
        return True

    vcodec = str(fmt.get("vcodec") or "").strip().lower()
    if vcodec == "none":
        return True

    format_note = str(fmt.get("format_note") or "").strip().lower()
    resolution = str(fmt.get("resolution") or "").strip().lower()
    if "audio" in format_note or "audio" in resolution:
        return True

    if _safe_float(fmt.get("abr")) > 0 or _safe_float(fmt.get("asr")) > 0:
        return True

    ext = str(fmt.get("ext") or "").strip().lower()
    if ext in {"m4a", "mp3", "aac", "opus", "ogg", "oga", "flac", "wav", "mka", "weba"} and vcodec in {
        "",
        "none",
        "unknown",
    }:
        return True

    return False


def _is_direct_media_stream_url(stream_url):
    normalized_stream_url = str(stream_url or "").strip()
    if not normalized_stream_url:
        return False

    parsed_url = urlparse(normalized_stream_url)
    if parsed_url.scheme not in {"http", "https"}:
        return False

    normalized_host = str(parsed_url.hostname or "").strip().lower()
    if not normalized_host:
        return False

    return not is_youtube_music_media(normalized_stream_url)


def _merge_playback_http_headers(*header_groups, target_stream_url=""):
    merged_headers = {}
    allow_cookie_header = _is_cookie_forwarding_allowed(target_stream_url)

    for headers in header_groups:
        if not isinstance(headers, dict):
            continue
        for key, value in headers.items():
            normalized_key = str(key or "").strip()
            normalized_value = str(value or "").strip()
            if not normalized_key or not normalized_value:
                continue
            if not _is_supported_playback_header(normalized_key):
                continue
            if normalized_key.lower() == "cookie" and not allow_cookie_header:
                continue
            merged_headers[normalized_key] = normalized_value
    return merged_headers


def _is_supported_playback_header(header_name):
    normalized_header_name = str(header_name or "").strip().lower()
    return normalized_header_name in _ALLOWED_PLAYBACK_HEADER_NAMES


def _is_cookie_forwarding_allowed(stream_url):
    normalized_stream_url = str(stream_url or "").strip()
    if not normalized_stream_url:
        return False

    parsed_stream_url = urlparse(normalized_stream_url)
    normalized_host = str(parsed_stream_url.hostname or "").strip().lower()
    if not normalized_host:
        return False

    return any(
        normalized_host == allowed_suffix or normalized_host.endswith(f".{allowed_suffix}")
        for allowed_suffix in _COOKIE_FORWARDING_ALLOWED_HOST_SUFFIXES
    )


def _stream_format_score(fmt):
    protocol = str(fmt.get("protocol") or "").lower()
    return (
        1 if _is_audio_only_stream_format(fmt) else 0,
        1 if _is_audio_capable_stream_format(fmt) else 0,
        1 if protocol in {"https", "http"} else 0,
        _safe_float(fmt.get("abr")),
        _safe_float(fmt.get("tbr")),
        _safe_float(fmt.get("asr")),
    )


def _safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _clean_external_tool_error(error):
    message = re.sub(r"\x1b\[[0-9;]*m", "", str(error or "")).strip()
    if "ERROR:" in message:
        message = message.split("ERROR:", 1)[1].strip()
    return sanitize_sensitive_text(message)


def _remove_temporary_cookie_file(temp_cookie_file_path):
    normalized_cookie_file_path = str(temp_cookie_file_path or "").strip()
    if not normalized_cookie_file_path:
        return

    try:
        import os

        os.remove(normalized_cookie_file_path)
    except OSError:
        return


def _build_stream_resolution_error_message(last_error, *, attempted_profiles):
    normalized_last_error = sanitize_sensitive_text(last_error)
    base_message = "O yt-dlp não conseguiu abrir a faixa do YouTube Music."

    if normalized_last_error:
        base_message = f"{base_message} Detalhes técnicos: {normalized_last_error}."

    if attempted_profiles > 1:
        base_message = f"{base_message} Perfis testados: {attempted_profiles}."

    lowered_error = normalized_last_error.lower()
    if any(term in lowered_error for term in ("not a bot", "sign in", "captcha", "429", "403")):
        return (
            f"{base_message} Atualize os recursos adicionais do YouTube Music e refaça a autenticação do navegador "
            "antes de tentar novamente."
        )

    if any(term in lowered_error for term in ("po token", "pot", "missing_pot")):
        return (
            f"{base_message} O YouTube pode estar exigindo um token adicional no cliente atual. "
            "Atualize os recursos adicionais e tente novamente em alguns instantes."
        )

    return base_message
