"""A página "Sobre" de um canal do YouTube: descrição, números, país e links.

Só o YouTube.js a lê; não precisa da conta.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..i18n import _
from . import youtubejs_runtime
from .dependencies import youtubejs_resolver_enabled


@dataclass(frozen=True)
class YouTubeChannelAbout:
    title: str
    description: str = ""
    subscribers: str = ""
    video_count: str = ""
    view_count: str = ""
    joined: str = ""
    country: str = ""
    url: str = ""
    links: tuple = ()


def channel_about(channel_id):
    """O "Sobre" de *channel_id*."""
    if not youtubejs_resolver_enabled():
        raise RuntimeError(_("Os dados do canal precisam do YouTube.js, ativado em Preferências > Recursos adicionais."))
    data = youtubejs_runtime.channel_about(channel_id)

    def text(key):
        return str(data.get(key) or "").strip()

    return YouTubeChannelAbout(
        title=text("title"),
        description=text("description"),
        subscribers=text("subscribers"),
        video_count=text("video_count"),
        view_count=text("view_count"),
        joined=text("joined"),
        country=text("country"),
        url=text("url"),
        links=tuple(str(link).strip() for link in data.get("links") or [] if str(link).strip()),
    )


def about_reading_text(about):
    """O "Sobre" em texto, para a caixa de leitura."""
    lines = [about.title] if about.title else []
    numbers = [part for part in (about.subscribers, about.video_count, about.view_count) if part]
    if numbers:
        lines.append(" · ".join(numbers))
    if about.joined:
        lines.append(about.joined)
    if about.country:
        lines.append(_("País: {country}").format(country=about.country))
    if about.description:
        lines.extend(["", about.description])
    if about.links:
        lines.extend(["", _("Links:"), *about.links])
    if about.url:
        lines.extend(["", about.url])
    return "\n".join(lines)
