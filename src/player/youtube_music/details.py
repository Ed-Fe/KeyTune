"""Detalhes de um vídeo ou música do YouTube: descrição, canal, números e data.

O YouTube.js traz tudo já escrito no idioma do conteúdo. Sem ele, o yt-dlp
entrega os mesmos dados, mais devagar e com os números crus.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..i18n import _
from ..log import get_logger
from . import youtubejs_runtime
from .dependencies import ensure_yt_dlp_executable_available, youtubejs_resolver_enabled
from .search import _clean_external_tool_error, _format_count, _format_duration
from .yt_dlp_runtime import extract_info as extract_yt_dlp_info


_logger = get_logger(__name__)

YT_DLP_DETAILS_SOCKET_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class YouTubeMediaDetails:
    title: str
    channel: str = ""
    channel_id: str = ""
    subscribers: str = ""
    description: str = ""
    duration: str = ""
    views: str = ""
    likes: str = ""
    published: str = ""
    is_live: bool = False


def media_details(media_url):
    """Os detalhes de *media_url*."""
    media_url = str(media_url or "").strip()
    if youtubejs_resolver_enabled():
        try:
            return _details_from_youtubejs(youtubejs_runtime.media_details(media_url))
        except Exception as exc:
            _logger.warning("O YouTube.js não trouxe os detalhes; usando o yt-dlp: %s", exc)
    return _details_from_yt_dlp(media_url)


def _likes_text(value):
    count = _format_count(value, "")
    return _("{count} curtidas").format(count=count) if count else ""


def _details_from_youtubejs(data):
    published = str(data.get("published") or "").strip()
    relative_date = str(data.get("relative_date") or "").strip()
    if published and relative_date:
        published = f"{published} ({relative_date})"
    return YouTubeMediaDetails(
        title=str(data.get("title") or "").strip(),
        channel=str(data.get("channel") or "").strip(),
        channel_id=str(data.get("channel_id") or "").strip(),
        subscribers=str(data.get("subscribers") or "").strip(),
        description=str(data.get("description") or "").strip(),
        duration=_format_duration(data.get("duration")),
        views=str(data.get("view_count_text") or "").strip() or _format_count(data.get("view_count"), _(" visualizações")),
        likes=_likes_text(data.get("like_count")),
        published=published or relative_date,
        is_live=bool(data.get("is_live")),
    )


def _details_from_yt_dlp(media_url):
    ensure_yt_dlp_executable_available()
    try:
        response = extract_yt_dlp_info(
            media_url,
            noplaylist=True,
            ignore_no_formats_error=True,
            socket_timeout_seconds=YT_DLP_DETAILS_SOCKET_TIMEOUT_SECONDS,
            quiet=True,
            no_warnings=True,
        )
    except Exception as exc:
        raise RuntimeError(
            _clean_external_tool_error(exc) or _("O yt-dlp não conseguiu trazer os detalhes.")
        ) from exc

    data = response.data or {}
    upload_date = str(data.get("upload_date") or "").strip()
    if len(upload_date) == 8 and upload_date.isdigit():
        upload_date = f"{upload_date[6:]}/{upload_date[4:6]}/{upload_date[:4]}"
    return YouTubeMediaDetails(
        title=str(data.get("title") or "").strip(),
        channel=str(data.get("channel") or data.get("uploader") or "").strip(),
        channel_id=str(data.get("channel_id") or "").strip(),
        subscribers=_format_count(data.get("channel_follower_count"), _(" inscritos")),
        description=str(data.get("description") or "").strip(),
        duration=_format_duration(data.get("duration")),
        views=_format_count(data.get("view_count"), _(" visualizações")),
        likes=_likes_text(data.get("like_count")),
        published=upload_date,
        is_live=bool(data.get("is_live")),
    )


def details_reading_text(details):
    """Os detalhes em texto corrido, uma informação por linha, para a caixa de leitura."""
    lines = [details.title]
    if details.channel:
        channel = _("Canal: {name}").format(name=details.channel)
        lines.append(f"{channel} ({details.subscribers})" if details.subscribers else channel)
    if details.is_live:
        lines.append(_("Transmissão ao vivo"))
    elif details.duration:
        lines.append(_("Duração: {duration}").format(duration=details.duration))
    for value in (details.views, details.likes):
        if value:
            lines.append(value)
    if details.published:
        lines.append(_("Publicado: {date}").format(date=details.published))
    lines.append("")
    if details.description:
        lines.append(_("Descrição:"))
        lines.append(details.description)
    else:
        lines.append(_("Sem descrição."))
    return "\n".join(lines)
