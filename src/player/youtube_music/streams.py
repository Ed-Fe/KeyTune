import os
import re
import time
from urllib.parse import urlparse
from dataclasses import dataclass

from .auth import (
    create_temporary_browser_auth_cookie_file,
    load_saved_playback_auth,
    sanitize_sensitive_text,
)
from .dependencies import (
    ensure_yt_dlp_executable_available,
    install_or_update_youtube_dependencies,
    youtube_dependency_management_enabled,
    youtubejs_resolver_enabled,
)
from .playlists import is_youtube_music_media
from .yt_dlp_runtime import extract_info as extract_yt_dlp_info
from .yt_dlp_runtime import find_all_available_javascript_runtimes
from .yt_dlp_runtime import find_incompatible_javascript_runtimes
from .youtubejs_runtime import resolve_stream as resolve_youtubejs_stream
from ..log import get_logger
from ..i18n import _


_logger = get_logger(__name__)


YTDLP_STREAM_SOCKET_TIMEOUT_SECONDS = 20
YTDLP_STREAM_NETWORK_ATTEMPTS = 2
YTDLP_STREAM_NETWORK_RETRY_DELAY_SECONDS = 0.5
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

_STREAM_DIAGNOSTIC_SIGNAL_LABELS = {
    "auth_blocked": _("autenticação/bloqueio do YouTube"),
    "js_challenge": _("desafio JavaScript (EJS)"),
    "po_token": _("PO Token ausente"),
    "sabr_missing_url": _("formatos SABR sem URL direta"),
    "only_images": _("somente formatos de imagem"),
}

_PRERELEASE_SELF_HEAL_ATTEMPTED = False
_JAVASCRIPT_RUNTIME_REQUIRED_MARKERS = (
    "runtime javascript",
    "yt-dlp",
)
_TRANSIENT_NETWORK_ERROR_MARKERS = (
    "connection aborted",
    "connection reset",
    "demorou demais",
    "failed to resolve",
    "getaddrinfo failed",
    "name resolution",
    "network is unreachable",
    "remote end closed connection",
    "temporarily unavailable",
    "timed out",
    "timeout",
    "winerror 10054",
)


@dataclass(slots=True)
class ResolvedStreamPlayback:
    stream_url: str
    http_headers: dict[str, str] | None = None
    display_title: str = ""
    display_artist: str = ""


def is_missing_javascript_runtime_error_message(error_message):
    normalized_error_message = " ".join(str(error_message or "").split()).casefold()
    if not normalized_error_message:
        return False
    return all(marker in normalized_error_message for marker in _JAVASCRIPT_RUNTIME_REQUIRED_MARKERS) and any(
        marker in normalized_error_message
        for marker in ("deno 2.3+", "node.js 24+", "quickjs", "runtime compatível")
    )


def resolve_stream_url(media_path):
    return resolve_stream_playback(media_path).stream_url


def resolve_stream_playback(media_path, *, use_account_cookies=True, anonymous_player_client=""):
    global _PRERELEASE_SELF_HEAL_ATTEMPTED

    normalized_media_path = str(media_path or "").strip()
    if not is_youtube_music_media(normalized_media_path):
        return ResolvedStreamPlayback(stream_url=normalized_media_path, http_headers={})

    _logger.info("Resolving stream for: %s", sanitize_sensitive_text(normalized_media_path))
    playback_auth = load_saved_playback_auth()
    use_saved_auth = bool(use_account_cookies)
    cookie_header = playback_auth.cookie_header if use_saved_auth else ""
    cookie_file_path = playback_auth.cookie_file_path if use_saved_auth else ""
    yt_dlp_http_headers = playback_auth.yt_dlp_http_headers if use_saved_auth else {}
    playback_http_headers = playback_auth.playback_http_headers if use_saved_auth else {}

    if youtubejs_resolver_enabled():
        youtubejs_started_at = time.monotonic()
        try:
            youtubejs_stream = resolve_youtubejs_stream(
                normalized_media_path,
                cookie_header="",
                user_agent=playback_auth.user_agent if use_saved_auth else "",
            )
            _logger.info(
                "YouTube.js resolved the stream in %.2f second(s)",
                time.monotonic() - youtubejs_started_at,
            )
            return ResolvedStreamPlayback(
                stream_url=youtubejs_stream.stream_url,
                http_headers=_merge_playback_http_headers(
                    playback_http_headers,
                    target_stream_url=youtubejs_stream.stream_url,
                ),
                display_title=youtubejs_stream.display_title,
                display_artist=youtubejs_stream.display_artist,
            )
        except Exception as exc:
            _logger.warning(
                "YouTube.js stream resolution failed after %.2f second(s); falling back to yt-dlp: %s",
                time.monotonic() - youtubejs_started_at,
                sanitize_sensitive_text(exc),
            )

    ensure_yt_dlp_executable_available()

    available_js_runtimes = find_all_available_javascript_runtimes()
    if not available_js_runtimes:
        incompatible_js_runtimes = find_incompatible_javascript_runtimes()
        if incompatible_js_runtimes:
            runtime_versions = ", ".join(
                f"{runtime_name} {version or _('versão desconhecida')}"
                for runtime_name, version in incompatible_js_runtimes.items()
            )
            raise RuntimeError(
                _("O yt-dlp encontrou runtime JavaScript instalado, mas nenhuma versão é compatível: "
                  "{runtimes}. Ative ou atualize os recursos adicionais para instalar o Node.js 24+.")
                .format(runtimes=runtime_versions)
            )
        raise RuntimeError(
            _("Para reproduzir do YouTube Music, o yt-dlp precisa de um runtime JavaScript instalado no sistema "
              "ou nos recursos adicionais do KeyTune. Recomendamos o Node.js 24+, que também "
              "é utilizado pelo YouTube.js. "
              "Sem um runtime compatível, o yt-dlp não consegue resolver as assinaturas "
              "de áudio/vídeo do YouTube e nenhum cliente retorna formatos reproduzíveis. "
              "Ative ou atualize os recursos adicionais e tente novamente.")
        )

    base_options = {
        "quiet": True,
        "no_warnings": False,
        "noplaylist": True,
        "skip_download": True,
        "extract_flat": False,
        "ignore_no_formats_error": True,
        "socket_timeout": YTDLP_STREAM_SOCKET_TIMEOUT_SECONDS,
        # yt-dlp only enables non-Deno JS challenge providers when they are
        # explicitly selected, so pass every compatible runtime discovered.
        "js_runtimes": dict(available_js_runtimes),
    }
    temporary_cookie_file_path = ""
    if cookie_header:
        temporary_cookie_file_path = create_temporary_browser_auth_cookie_file(cookie_header)

    if temporary_cookie_file_path:
        base_options["cookiefile"] = temporary_cookie_file_path
    elif cookie_file_path:
        base_options["cookiefile"] = cookie_file_path

    if yt_dlp_http_headers:
        base_options["http_headers"] = dict(yt_dlp_http_headers)

    has_account_cookies = bool(cookie_header) or bool(cookie_file_path)

    # Keep one explicitly selected profile per resolution. Profile fallback is
    # coordinated by YouTubeMusicService only after the returned URL itself is
    # rejected, avoiding repeated extractor calls for global DNS/time-out errors.
    normalized_player_client = str(anonymous_player_client or "").strip()
    if not normalized_player_client:
        normalized_player_client = "web_safari" if has_account_cookies else "visionos"
    extractor_profiles = [
        {"extractor_args": {"youtube": {"player_client": [normalized_player_client]}}},
    ]

    format_selectors = ["bestaudio/best"]

    warning_messages: list[str] = []

    def _attempt_resolution():
        local_last_error = ""
        local_attempted_profiles = 0
        for format_selector in format_selectors:
            for profile in extractor_profiles:
                local_attempted_profiles += 1
                response = None
                for network_attempt in range(YTDLP_STREAM_NETWORK_ATTEMPTS):
                    try:
                        response = extract_yt_dlp_info(
                            normalized_media_path,
                            format_selector=format_selector,
                            cookie_file_path=base_options.get("cookiefile", ""),
                            http_headers=base_options.get("http_headers"),
                            extractor_args=profile.get("extractor_args"),
                            js_runtimes=base_options.get("js_runtimes"),
                            socket_timeout_seconds=base_options.get("socket_timeout", 0),
                            noplaylist=bool(base_options.get("noplaylist")),
                            extract_flat=base_options.get("extract_flat"),
                            ignore_no_formats_error=bool(base_options.get("ignore_no_formats_error")),
                        )
                        break
                    except Exception as exc:
                        local_last_error = _clean_external_tool_error(exc)
                        if (
                            network_attempt + 1 >= YTDLP_STREAM_NETWORK_ATTEMPTS
                            or not _is_transient_network_error(local_last_error)
                        ):
                            break
                        _logger.warning("Transient yt-dlp network failure; retrying the same profile")
                        time.sleep(YTDLP_STREAM_NETWORK_RETRY_DELAY_SECONDS)

                if response is None:
                    continue
                info = response.data
                warning_messages.extend(_warning_messages_from_stderr(response.stderr_text))

                if not info:
                    local_last_error = _("O yt-dlp não conseguiu abrir a faixa do YouTube Music.")
                    continue

                try:
                    resolved_playback = _preferred_stream_from_info(
                        info,
                        playback_auth_headers=playback_http_headers,
                    )
                except RuntimeError as exc:
                    local_last_error = _clean_external_tool_error(exc) or str(exc)
                    continue

                if resolved_playback.stream_url:
                    return resolved_playback, local_last_error, local_attempted_profiles

                local_last_error = _("O yt-dlp não conseguiu determinar uma URL de reprodução compatível para esta faixa.")

        return None, local_last_error, local_attempted_profiles

    last_error = ""
    attempted_profiles = 0
    prerelease_retry_attempted = False
    try:
        resolved_playback, last_error, attempted_profiles = _attempt_resolution()
        if resolved_playback is not None:
            return resolved_playback

        diagnostic_signals = _collect_stream_resolution_diagnostic_signals(
            warning_messages,
            last_error,
        )
        if (
            not _PRERELEASE_SELF_HEAL_ATTEMPTED
            and _should_retry_stream_resolution_with_prerelease(
                diagnostic_signals,
                management_enabled=youtube_dependency_management_enabled(),
            )
        ):
            _PRERELEASE_SELF_HEAL_ATTEMPTED = True
            prerelease_retry_attempted = True
            _logger.info("Attempting stream resolution self-heal via prerelease yt-dlp update")
            try:
                install_or_update_youtube_dependencies(force=True, include_prerelease=True)
                resolved_playback, retry_last_error, retry_attempted_profiles = _attempt_resolution()
                attempted_profiles = max(attempted_profiles, retry_attempted_profiles)
                if retry_last_error:
                    last_error = retry_last_error
                if resolved_playback is not None:
                    return resolved_playback
            except Exception as exc:
                retry_error = _clean_external_tool_error(exc) or str(exc)
                _logger.warning("Prerelease self-heal update failed: %s", retry_error)
                if retry_error:
                    if last_error:
                        last_error = last_error + " " + _("Atualização avançada: {detail}").format(detail=retry_error)
                    else:
                        last_error = _("Atualização avançada: {detail}").format(detail=retry_error)
    finally:
        _remove_temporary_cookie_file(temporary_cookie_file_path)

    diagnostic_signals = _collect_stream_resolution_diagnostic_signals(
        warning_messages,
        last_error,
    )

    _logger.error(
        "Stream resolution failed for %s after %d profile(s). Signals: %s. Last error: %s",
        sanitize_sensitive_text(normalized_media_path),
        attempted_profiles,
        diagnostic_signals or "none",
        last_error or "unknown",
    )
    raise RuntimeError(
        _build_stream_resolution_error_message(
            last_error,
            attempted_profiles=attempted_profiles,
            diagnostic_signals=diagnostic_signals,
            prerelease_retry_attempted=prerelease_retry_attempted,
        )
    )


def _preferred_stream_url_from_info(info):
    return _preferred_stream_from_info(info).stream_url


def _preferred_stream_from_info(info, *, playback_auth_headers=None, _depth=0):
    direct_stream_urls = _iter_direct_stream_url_candidates(info)
    direct_url = direct_stream_urls[0] if direct_stream_urls else ""
    top_level_http_headers = _merge_playback_http_headers(
        info.get("http_headers"),
        playback_auth_headers,
        target_stream_url=direct_url,
    )

    formats = _iter_stream_format_candidates(info)
    if not formats:
        direct_stream_playback = _resolved_playback_from_direct_stream_urls(
            direct_stream_urls,
            http_headers=top_level_http_headers,
        )
        if direct_stream_playback is not None:
            return direct_stream_playback
        nested_entry_stream_playback = _preferred_stream_from_nested_entries(
            info,
            playback_auth_headers=playback_auth_headers,
            depth=_depth,
        )
        if nested_entry_stream_playback is not None:
            return nested_entry_stream_playback
        raise RuntimeError(_("O yt-dlp não retornou um stream de áudio compatível para esta faixa do YouTube Music."))

    audio_only_formats = [fmt for fmt in formats if _is_audio_only_stream_format(fmt)]
    audio_capable_formats = [fmt for fmt in formats if _is_audio_capable_stream_format(fmt)]
    requested_fallback_formats = [fmt for fmt in formats if _is_requested_stream_format(fmt)]
    preferred_formats = audio_only_formats or audio_capable_formats or requested_fallback_formats
    if not preferred_formats:
        direct_stream_playback = _resolved_playback_from_direct_stream_urls(
            direct_stream_urls,
            http_headers=top_level_http_headers,
        )
        if direct_stream_playback is not None:
            return direct_stream_playback
        nested_entry_stream_playback = _preferred_stream_from_nested_entries(
            info,
            playback_auth_headers=playback_auth_headers,
            depth=_depth,
        )
        if nested_entry_stream_playback is not None:
            return nested_entry_stream_playback
        raise RuntimeError(_("O yt-dlp não retornou um stream de áudio compatível para esta faixa do YouTube Music."))

    best_format = max(preferred_formats, key=_stream_format_score)
    selected_stream_url = _stream_url_from_candidate(best_format)
    if not selected_stream_url:
        selected_stream_url = direct_url

    if not selected_stream_url:
        direct_stream_playback = _resolved_playback_from_direct_stream_urls(
            direct_stream_urls,
            http_headers=top_level_http_headers,
        )
        if direct_stream_playback is not None:
            return direct_stream_playback
        nested_entry_stream_playback = _preferred_stream_from_nested_entries(
            info,
            playback_auth_headers=playback_auth_headers,
            depth=_depth,
        )
        if nested_entry_stream_playback is not None:
            return nested_entry_stream_playback
        raise RuntimeError(_("O yt-dlp não retornou uma URL reproduzível para esta faixa do YouTube Music."))

    return ResolvedStreamPlayback(
        stream_url=selected_stream_url,
        http_headers=_merge_playback_http_headers(
            info.get("http_headers"),
            best_format.get("http_headers"),
            playback_auth_headers,
            target_stream_url=selected_stream_url,
        ),
        display_title=_display_title_from_info(info),
        display_artist=_display_artist_from_info(info),
    )


def _display_title_from_info(info):
    if not isinstance(info, dict):
        return ""

    for key in ("track", "title", "fulltitle", "alt_title"):
        normalized_title = str(info.get(key) or "").strip()
        if normalized_title:
            return normalized_title

    return ""


def _display_artist_from_info(info):
    if not isinstance(info, dict):
        return ""

    for key in ("artist", "uploader", "channel", "creator"):
        normalized_artist = str(info.get(key) or "").strip()
        if normalized_artist:
            return normalized_artist

    return ""


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

            stream_url = _stream_url_from_candidate(fmt)
            if not stream_url:
                continue

            format_key = (str(fmt.get("format_id") or "").strip(), stream_url)
            if format_key in seen_formats:
                continue

            seen_formats.add(format_key)
            candidate = dict(fmt)
            candidate["_stream_url"] = stream_url
            candidate["_source_key"] = key
            collected_formats.append(candidate)

    return collected_formats


def _iter_direct_stream_url_candidates(info):
    direct_stream_urls = []
    seen_stream_urls = set()
    for key in ("url", "manifest_url", "hls_manifest_url"):
        stream_url = str(info.get(key) or "").strip()
        if not stream_url or stream_url in seen_stream_urls:
            continue
        seen_stream_urls.add(stream_url)
        direct_stream_urls.append(stream_url)

    return direct_stream_urls


def _resolved_playback_from_direct_stream_urls(direct_stream_urls, *, http_headers):
    for stream_url in direct_stream_urls or []:
        if not _is_direct_media_stream_url(stream_url):
            continue
        return ResolvedStreamPlayback(stream_url=stream_url, http_headers=dict(http_headers or {}))

    return None


def _preferred_stream_from_nested_entries(info, *, playback_auth_headers=None, depth=0):
    if depth >= 2:
        return None

    raw_entries = info.get("entries")
    if isinstance(raw_entries, dict):
        normalized_entries = [raw_entries]
    elif isinstance(raw_entries, list):
        normalized_entries = raw_entries
    else:
        return None

    for entry in normalized_entries[:10]:
        if not isinstance(entry, dict):
            continue

        try:
            return _preferred_stream_from_info(
                entry,
                playback_auth_headers=playback_auth_headers,
                _depth=depth + 1,
            )
        except RuntimeError:
            continue

    return None


def _stream_url_from_candidate(fmt):
    if not isinstance(fmt, dict):
        return ""

    for key in ("_stream_url", "url", "manifest_url", "hls_manifest_url"):
        stream_url = str(fmt.get(key) or "").strip()
        if stream_url:
            return stream_url

    return ""


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


def _is_requested_stream_format(fmt):
    source_key = str(fmt.get("_source_key") or "").strip().lower()
    return source_key in {"requested_formats", "requested_downloads"}


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
    stream_url = _stream_url_from_candidate(fmt)
    parsed_stream_url = urlparse(stream_url)
    host = str(parsed_stream_url.hostname or "").strip().lower()
    is_googlevideo_stream = host.endswith("googlevideo.com") if host else False
    return (
        1 if _is_requested_stream_format(fmt) else 0,
        1 if _is_audio_only_stream_format(fmt) else 0,
        1 if _is_audio_capable_stream_format(fmt) else 0,
        1 if protocol in {"https", "http"} else 0,
        1 if is_googlevideo_stream else 0,
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


def _is_transient_network_error(error_message):
    normalized_error_message = str(error_message or "").casefold()
    return any(marker in normalized_error_message for marker in _TRANSIENT_NETWORK_ERROR_MARKERS)


def _warning_messages_from_stderr(stderr_text):
    messages = []
    for line in str(stderr_text or "").splitlines():
        cleaned_message = _clean_external_tool_error(line)
        if not cleaned_message:
            continue
        lowered_message = cleaned_message.casefold()
        if not any(
            marker in lowered_message
            for marker in (
                "warning:",
                "error:",
                "n challenge",
                "js challenge",
                "only images",
                "sabr",
                "po token",
                "missing_pot",
                "not a bot",
                "captcha",
            )
        ):
            continue
        messages.append(cleaned_message)
    return messages


def _remove_temporary_cookie_file(temp_cookie_file_path):
    normalized_cookie_file_path = str(temp_cookie_file_path or "").strip()
    if not normalized_cookie_file_path:
        return

    try:
        os.remove(normalized_cookie_file_path)
    except OSError:
        return


def _collect_stream_resolution_diagnostic_signals(messages, last_error):
    normalized_messages = [str(message or "").strip() for message in (messages or []) if str(message or "").strip()]
    normalized_last_error = str(last_error or "").strip()
    combined_text = "\n".join([*normalized_messages, normalized_last_error]).casefold()
    signals = set()

    if any(term in combined_text for term in ("not a bot", "sign in", "captcha", "429", "403")):
        signals.add("auth_blocked")

    if any(
        term in combined_text
        for term in (
            "n challenge",
            "js challenge",
            "challenge solver",
            "yt-dlp/wiki/ejs",
            "js runtime",
            "jsc",
        )
    ):
        signals.add("js_challenge")

    if any(term in combined_text for term in ("po token", "missing_pot", " gvs ", "pot")):
        signals.add("po_token")

    if "only images" in combined_text:
        signals.add("only_images")

    if "sabr" in combined_text and any(term in combined_text for term in ("missing a url", "forcing")):
        signals.add("sabr_missing_url")

    return signals


def _should_retry_stream_resolution_with_prerelease(diagnostic_signals, *, management_enabled):
    if not management_enabled:
        return False

    normalized_diagnostic_signals = set(diagnostic_signals or ())
    # Only the JS/N challenge symptom can plausibly be helped by updating yt-dlp /
    # yt-dlp-ejs to a prerelease. SABR/only-images is caused by missing PO Token
    # and cannot be fixed by upgrading yt-dlp itself, so do not waste time retrying.
    return "js_challenge" in normalized_diagnostic_signals


def _build_stream_resolution_error_message(
    last_error,
    *,
    attempted_profiles,
    diagnostic_signals=None,
    prerelease_retry_attempted=False,
):
    normalized_last_error = sanitize_sensitive_text(last_error)
    normalized_diagnostic_signals = set(diagnostic_signals or ())
    base_message = _("O yt-dlp não conseguiu abrir a faixa do YouTube Music.")

    if normalized_last_error:
        base_message = base_message + " " + _("Detalhes técnicos: {detail}.").format(detail=normalized_last_error)

    if attempted_profiles > 1:
        base_message = base_message + " " + _("Perfis testados: {count}.").format(count=attempted_profiles)

    if prerelease_retry_attempted:
        base_message = base_message + " " + _("Foi tentada uma atualização avançada do yt-dlp.")

    if normalized_diagnostic_signals:
        signal_labels = [
            _STREAM_DIAGNOSTIC_SIGNAL_LABELS.get(signal, signal)
            for signal in sorted(normalized_diagnostic_signals)
        ]
        base_message = base_message + " " + _("Sinais detectados: {signals}.").format(signals=", ".join(signal_labels))

    guidance_parts = []
    if "auth_blocked" in normalized_diagnostic_signals:
        guidance_parts.append(
            _("Atualize os recursos adicionais do YouTube Music e tente novamente. "
              "Faixas que exigem uma conta podem não estar disponíveis nos perfis de reprodução compatíveis.")
        )

    if "js_challenge" in normalized_diagnostic_signals:
        guidance_parts.append(
            _("O YouTube exigiu validação JavaScript. Ative ou atualize os recursos adicionais para instalar "
              "o Node.js 24+ e tente novamente.")
        )

    if "sabr_missing_url" in normalized_diagnostic_signals or "only_images" in normalized_diagnostic_signals:
        guidance_parts.append(
            _("O YouTube não forneceu um stream de áudio direto para esta faixa. "
              "Atualize os recursos adicionais e tente novamente; o conteúdo pode exigir um PO Token "
              "que não está disponível no perfil atual.")
        )

    if "po_token" in normalized_diagnostic_signals:
        guidance_parts.append(
            _("Este conteúdo exige um PO Token que o yt-dlp não consegue gerar sozinho. "
              "Atualize os recursos adicionais e tente novamente mais tarde.")
        )

    if guidance_parts:
        return f"{base_message} {' '.join(guidance_parts)}"

    lowered_error = normalized_last_error.lower()
    if any(term in lowered_error for term in ("not a bot", "sign in", "captcha", "429", "403")):
        return base_message + " " + _(
            "Atualize os recursos adicionais do YouTube Music e refaça a autenticação do navegador "
            "antes de tentar novamente."
        )

    if any(term in lowered_error for term in ("po token", "pot", "missing_pot")):
        return base_message + " " + _(
            "O YouTube pode estar exigindo um token adicional no cliente atual. "
            "Atualize os recursos adicionais e tente novamente em alguns instantes."
        )

    return base_message
