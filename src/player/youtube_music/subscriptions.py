"""Inscrições da conta do YouTube: os vídeos novos e os canais.

Só o YouTube.js lê isso, com os cookies que a conta do YouTube já salvou.
É só leitura: inscrever-se ou cancelar continua sendo feito no YouTube.
"""

from __future__ import annotations

from ..i18n import _
from . import youtubejs_runtime
from .auth import load_saved_playback_auth
from .dependencies import youtubejs_resolver_enabled
from .models import YouTubeResultPage
from .search import normalize_youtube_entry


def _account_cookie():
    if not youtubejs_resolver_enabled():
        raise RuntimeError(
            _("As inscrições precisam do YouTube.js, ativado em Preferências > Recursos adicionais.")
        )
    cookie_header = load_saved_playback_auth().cookie_header
    if not cookie_header:
        raise RuntimeError(_("Conecte a conta do YouTube para ver as inscrições."))
    return cookie_header


def _page(entries, has_more):
    results = [normalize_youtube_entry(entry) for entry in entries]
    return YouTubeResultPage(results=tuple(result for result in results if result is not None), has_more=has_more)


def subscription_videos_page(start, count):
    """Os vídeos novos dos canais em que a conta está inscrita, do mais recente para o mais antigo."""
    return _page(*youtubejs_runtime.subscription_videos_page(_account_cookie(), start=start, count=count))


def subscribed_channels_page(start, count):
    """Os canais em que a conta está inscrita."""
    return _page(*youtubejs_runtime.subscribed_channels_page(_account_cookie(), start=start, count=count))
