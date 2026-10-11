"""A busca de dentro de um canal do YouTube: os vídeos dele que batem com o texto.

Só o YouTube.js a faz; não precisa da conta.
"""

from __future__ import annotations

from ..i18n import _
from . import youtubejs_runtime
from .dependencies import youtubejs_resolver_enabled
from .models import YouTubeResultPage
from .search import normalize_youtube_entry


def channel_search_page(channel_id, query, start, count):
    """Os vídeos de *channel_id* que a busca dele acha para *query*."""
    if not youtubejs_resolver_enabled():
        raise RuntimeError(_("A busca no canal precisa do YouTube.js, ativado em Preferências > Recursos adicionais."))
    entries, has_more = youtubejs_runtime.channel_search_page(channel_id, query, start=start, count=count)
    # Todos os vídeos são do canal em que se buscou: o nome dele não precisa se repetir em cada linha.
    results = [normalize_youtube_entry(entry, show_owner=False) for entry in entries]
    return YouTubeResultPage(results=tuple(result for result in results if result is not None), has_more=has_more)


def channel_search_view_title(query, channel_title):
    return _("Busca por {query} em {channel}").format(query=query, channel=str(channel_title or "").strip())
