"""Inscrições da conta do YouTube: os vídeos novos, os canais, inscrever-se e o sino.

Só o YouTube.js faz isso, com os cookies que a conta do YouTube já salvou.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..i18n import _
from . import youtubejs_runtime
from .auth import load_saved_playback_auth
from .dependencies import youtubejs_resolver_enabled
from .models import YouTubeResultPage
from .search import normalize_youtube_entry


def _account():
    """``(cookies, índice da conta)`` da sessão salva."""
    if not youtubejs_resolver_enabled():
        raise RuntimeError(
            _("As inscrições precisam do YouTube.js, ativado em Preferências > Recursos adicionais.")
        )
    playback_auth = load_saved_playback_auth()
    if not playback_auth.cookie_header:
        raise RuntimeError(_("Conecte a conta do YouTube para ver as inscrições."))
    return playback_auth.cookie_header, playback_auth.account_index


def _page(entries, has_more):
    results = [normalize_youtube_entry(entry) for entry in entries]
    return YouTubeResultPage(results=tuple(result for result in results if result is not None), has_more=has_more)


def subscription_videos_page(start, count):
    """Os vídeos novos dos canais em que a conta está inscrita, do mais recente para o mais antigo."""
    cookie_header, account_index = _account()
    return _page(
        *youtubejs_runtime.subscription_videos_page(
            cookie_header, start=start, count=count, account_index=account_index
        )
    )


def subscribed_channels_page(start, count):
    """Os canais em que a conta está inscrita."""
    cookie_header, account_index = _account()
    return _page(
        *youtubejs_runtime.subscribed_channels_page(
            cookie_header, start=start, count=count, account_index=account_index
        )
    )


BELL_ALL = "all"
BELL_PERSONALIZED = "personalized"
BELL_NONE = "none"


@dataclass(frozen=True)
class ChannelSubscription:
    """Se a conta está inscrita num canal e o que o sino dele avisa (vazio sem inscrição)."""

    subscribed: bool = False
    notifications: str = ""


def bell_label(level):
    return {
        BELL_ALL: _("todas as notificações"),
        BELL_PERSONALIZED: _("notificações personalizadas"),
        BELL_NONE: _("nenhuma notificação"),
    }.get(level, "")


def channel_subscription(channel_id):
    """A inscrição da conta em *channel_id*."""
    cookie_header, account_index = _account()
    state = youtubejs_runtime.channel_state(cookie_header, channel_id, account_index=account_index)
    return ChannelSubscription(
        subscribed=bool(state.get("subscribed")),
        notifications=str(state.get("notifications") or ""),
    )


def _channel_action(channel_id, operation):
    cookie_header, account_index = _account()
    youtubejs_runtime.channel_action(cookie_header, channel_id, operation, account_index=account_index)


def subscribe_to_channel(channel_id):
    _channel_action(channel_id, "subscribe")


def unsubscribe_from_channel(channel_id):
    _channel_action(channel_id, "unsubscribe")


def set_channel_notifications(channel_id, level):
    """Muda o sino de um canal em que a conta está inscrita: tudo, personalizado ou nada."""
    if level not in (BELL_ALL, BELL_PERSONALIZED, BELL_NONE):
        raise ValueError(f"Nível de notificação desconhecido: {level}")
    _channel_action(channel_id, f"notify_{level}")
