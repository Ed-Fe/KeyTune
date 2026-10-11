"""Notificações da conta do YouTube: a caixa, marcar como lida e ocultar.

O YouTube.js lê a caixa com os cookies da conta. O YouTube não avisa o KeyTune
quando chega uma notificação: quem quer ser avisado consulta a caixa de tempos
em tempos e compara com o que já viu (:func:`unseen_notifications`).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..i18n import _
from . import youtubejs_runtime
from .account_session import require_account_session
from .models import YouTubeResultPage
from .playlists import build_youtube_watch_url


# Quantas notificações a consulta periódica olha: as novas chegam no topo da caixa.
NOTIFICATION_CHECK_COUNT = 20


@dataclass(frozen=True)
class YouTubeNotificationItem:
    """Uma notificação na lista: Enter toca o vídeo de que ela fala."""

    notification_id: str
    title: str
    published: str = ""
    read: bool = False
    video_id: str = ""
    # O comentário de que a notificação fala, quando ela é de um comentário ou de uma resposta.
    comment_id: str = ""

    # A lista trata a notificação como um vídeo que toca; a de um comentário também abre a conversa.
    result_type = "notification"
    source = ""
    playlist_id = ""
    browse_id = ""
    library_playlist = False
    opens_on_enter = False
    can_save = False

    @property
    def can_browse(self):
        return bool(self.video_id and self.comment_id)

    @property
    def playback_url(self):
        return build_youtube_watch_url(self.video_id) if self.video_id else ""

    @property
    def can_open(self):
        return bool(self.video_id)

    @property
    def stable_id(self):
        return f"notification:{self.notification_id}"

    @property
    def detail_text(self):
        parts = []
        if self.published:
            parts.append(self.published)
        if not self.read:
            parts.append(_("não lida"))
        return " · ".join(parts)

    @property
    def choice_label(self):
        return f"{self.title} — {self.detail_text}" if self.detail_text else self.title


def notification_from_entry(entry):
    if not isinstance(entry, dict):
        return None
    notification_id = str(entry.get("id") or "").strip()
    title = " ".join(str(entry.get("title") or "").split())
    if not notification_id or not title:
        return None
    return YouTubeNotificationItem(
        notification_id=notification_id,
        title=title,
        published=str(entry.get("published") or "").strip(),
        read=bool(entry.get("read")),
        video_id=str(entry.get("video_id") or "").strip(),
        comment_id=str(entry.get("comment_id") or "").strip(),
    )


def notifications_page(start, count):
    """As notificações da conta, da mais recente para a mais antiga."""
    cookie_header, account_index = require_account_session()
    entries, has_more = youtubejs_runtime.notifications_page(
        cookie_header, start=start, count=count, account_index=account_index
    )
    notifications = [notification_from_entry(entry) for entry in entries]
    return YouTubeResultPage(
        results=tuple(notification for notification in notifications if notification is not None),
        has_more=has_more,
    )


def mark_notification_read(notification):
    cookie_header, account_index = require_account_session()
    youtubejs_runtime.notification_action(
        cookie_header, notification.notification_id, "read", account_index=account_index
    )


def hide_notification(notification):
    """Tira a notificação da caixa da conta; o YouTube não a mostra mais."""
    cookie_header, account_index = require_account_session()
    youtubejs_runtime.notification_action(
        cookie_header, notification.notification_id, "hide", account_index=account_index
    )


def unseen_notifications(notifications, seen_ids):
    """As notificações não lidas de *notifications* que ainda não estão em *seen_ids*."""
    seen = set(seen_ids or ())
    return [
        notification
        for notification in notifications
        if not notification.read and notification.notification_id not in seen
    ]


def new_notifications_message(new_notifications):
    """O aviso falado quando chegam notificações; vazio sem nenhuma."""
    count = len(new_notifications)
    if count == 0:
        return ""
    if count == 1:
        return _("Nova notificação do YouTube: {title}").format(title=new_notifications[0].title)
    return _("{count} novas notificações do YouTube. A mais recente: {title}").format(
        count=count, title=new_notifications[0].title
    )
