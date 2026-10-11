"""Notificações da conta do YouTube: a lista na aba do KeyTube e o aviso das que chegam."""

import threading
from dataclasses import replace

import wx

from player.youtube_music import notifications as youtube_notifications
from player.youtube_music.account_session import account_connected
from player.youtube_music.notification_store import YouTubeNotificationStore

from ... import interface_sounds
from ...i18n import _
from ...log import get_logger
from .comments import CommentsContext
from .navigation import YouTubeResultsView


_logger = get_logger(__name__)

# A primeira consulta espera o KeyTune terminar de abrir.
_FIRST_CHECK_DELAY_MS = 45_000


class NotificationsMixin:
    def _youtube_notification_store(self):
        store = getattr(self, "_youtube_notification_store_instance", None)
        if store is None:
            store = YouTubeNotificationStore()
            self._youtube_notification_store_instance = store
        return store

    def _build_youtube_notifications_view(self):
        def fetch_page(start, count):
            page = youtube_notifications.notifications_page(start, count)
            # O que foi mostrado na lista não precisa ser avisado depois.
            self._youtube_notification_store().remember(
                notification.notification_id for notification in page.results
            )
            return page

        return YouTubeResultsView(title=_("Notificações"), fetch_page=fetch_page)

    def _build_youtube_notification_conversation_view(self, notification):
        """Os comentários do vídeo de *notification*, começando pela conversa de que ela fala."""
        if not notification.can_browse:
            return None
        return self._build_youtube_music_comments_view(
            CommentsContext(
                media_url=notification.playback_url,
                title=_("Conversa da notificação"),
                linked_comment=notification.comment_id,
            )
        )

    def on_open_youtube_notifications(self, _event=None):
        """Abre a aba do KeyTube na caixa de notificações da conta."""
        self.on_open_youtube_music(None)
        if self._get_youtube_music_panel() is None:
            return False
        if not self._ensure_youtube_music_authenticated():
            return False
        if self._is_youtube_music_operation_in_progress():
            # A aba acabou de abrir e ainda carrega a biblioteca: as notificações vêm em seguida.
            self._queue_youtube_music_post_operation_callback(self._open_youtube_notifications_view)
            return True
        return self._open_youtube_notifications_view()

    def _open_youtube_notifications_view(self):
        view = self._build_youtube_notifications_view()
        self._announce(_("Abrindo {title}.").format(title=view.title))
        return self._load_youtube_music_results_view(
            view,
            mode="push",
            error_message=_("Não foi possível carregar as notificações agora."),
            focus_results=True,
        )

    def _youtube_notification_menu_entries(self, result):
        """As ações de uma notificação, para o menu de ações."""
        if getattr(result, "result_type", "") != "notification":
            return []
        entries = []
        if not result.read:
            entries.append(
                (_("Marcar como lida"), lambda: self._mark_youtube_notifications_read([result], announce=True))
            )
        entries.append((_("Ocultar esta notificação"), lambda: self._hide_youtube_notification(result)))
        return entries

    def _mark_youtube_notifications_read(self, results, *, announce=False):
        """Marca como lidas as notificações não lidas de *results*, sem travar a janela."""
        unread = [
            result
            for result in results or []
            if getattr(result, "result_type", "") == "notification" and not result.read
        ]
        if not unread:
            return False

        def worker():
            done = []
            for notification in unread:
                try:
                    youtube_notifications.mark_notification_read(notification)
                    done.append(notification)
                except Exception as exc:
                    _logger.warning("The YouTube notification was not marked as read: %s", exc)
            wx.CallAfter(self._on_youtube_notifications_marked_read, done, announce)

        threading.Thread(target=worker, daemon=True, name="youtube-notification-read").start()
        return True

    def _on_youtube_notifications_marked_read(self, notifications, announce):
        for notification in notifications:
            self._replace_youtube_music_result(notification, replace(notification, read=True))
        if announce:
            interface_sounds.play_for(
                self, interface_sounds.SOUND_SUCCESS if notifications else interface_sounds.SOUND_FAILURE
            )
            self._announce(
                _("Notificação marcada como lida.") if notifications else _("Não foi possível marcar a notificação como lida.")
            )

    def _hide_youtube_notification(self, notification):
        def worker():
            youtube_notifications.hide_notification(notification)

        def on_success(_result):
            self._replace_youtube_music_result(notification)
            interface_sounds.play_for(self, interface_sounds.SOUND_SUCCESS)
            self._announce(_("Notificação ocultada."))

        def on_error(exc):
            interface_sounds.play_for(self, interface_sounds.SOUND_FAILURE)
            wx.MessageBox(
                _("Não foi possível ocultar a notificação.")
                + "\n\n"
                + _("Detalhes: {detail}").format(detail=self._format_youtube_music_error_detail(exc)),
                "KeyTube",
                wx.OK | wx.ICON_ERROR,
                self,
            )

        return self._run_youtube_music_background_task(worker, on_success, on_error=on_error)

    # --- O aviso das notificações que chegam ---------------------------------

    def _youtube_notification_check_interval_ms(self):
        """De quanto em quanto tempo a caixa é consultada; 0 quando o aviso está desligado."""
        if not self._youtube_music_integration_enabled():
            return 0
        minutes = int(getattr(self.settings, "youtube_notification_check_minutes", 0) or 0)
        return max(0, minutes) * 60_000

    def _stop_youtube_notification_checks(self):
        pending = getattr(self, "_youtube_notification_check_timer", None)
        self._youtube_notification_check_timer = None
        if pending is not None:
            try:
                pending.Stop()
            except Exception:
                pass

    def _schedule_youtube_notification_check(self, *, first=False):
        """Marca a próxima consulta da caixa, ou cancela a marcada quando o aviso está desligado."""
        self._stop_youtube_notification_checks()
        interval_ms = self._youtube_notification_check_interval_ms()
        if not interval_ms:
            return False
        delay_ms = min(_FIRST_CHECK_DELAY_MS, interval_ms) if first else interval_ms
        self._youtube_notification_check_timer = wx.CallLater(delay_ms, self._check_youtube_notifications)
        return True

    def _check_youtube_notifications(self):
        """Consulta a caixa numa thread própria: não ocupa a aba nem bloqueia a troca de faixa."""
        self._youtube_notification_check_timer = None
        if getattr(self, "_youtube_notification_check_running", False):
            return False
        if getattr(self, "_youtube_music_dependency_update_in_progress", False):
            # Os recursos estão sendo trocados: a consulta fica para a próxima vez.
            self._schedule_youtube_notification_check()
            return False
        self._youtube_notification_check_running = True

        def worker():
            notifications = None
            try:
                if account_connected():
                    page = youtube_notifications.notifications_page(
                        0, youtube_notifications.NOTIFICATION_CHECK_COUNT
                    )
                    notifications = list(page.results)
            except Exception as exc:
                _logger.info("The YouTube notifications could not be checked: %s", exc)
            try:
                wx.CallAfter(self._on_youtube_notifications_checked, notifications)
            except Exception:
                # A janela fechou enquanto a consulta estava a caminho.
                pass

        threading.Thread(target=worker, daemon=True, name="youtube-notification-check").start()
        return True

    def _on_youtube_notifications_checked(self, notifications):
        self._youtube_notification_check_running = False
        try:
            if notifications is not None:
                self._announce_new_youtube_notifications(notifications)
        finally:
            self._schedule_youtube_notification_check()

    def _announce_new_youtube_notifications(self, notifications):
        store = self._youtube_notification_store()
        # Na primeira consulta de todas só se toma nota do que já estava na caixa.
        new_notifications = (
            youtube_notifications.unseen_notifications(notifications, store.seen_ids())
            if store.has_baseline
            else []
        )
        store.remember(notification.notification_id for notification in notifications)
        message = youtube_notifications.new_notifications_message(new_notifications)
        if not message:
            return False
        if hasattr(self, "_set_status_message"):
            self._set_status_message(message)
        # Com o KeyTune em segundo plano o aviso vai para o Windows: fica na central de
        # notificações e o leitor de tela o lê de lá, sem falar duas vezes.
        if self._youtube_notification_goes_to_windows() and self._show_youtube_windows_notification(message):
            return True
        interface_sounds.play_for(self, interface_sounds.SOUND_NOTIFICATION)
        self._announce(message)
        return True

    def _youtube_notification_goes_to_windows(self):
        if not getattr(self.settings, "youtube_notification_windows_toast", True):
            return False
        try:
            return not self.IsShown() or self.IsIconized() or not self.IsActive()
        except Exception:
            return False

    def _show_youtube_windows_notification(self, message):
        """Mostra *message* como notificação do Windows; ``False`` quando o sistema não deixa."""
        try:
            import wx.adv

            notification = wx.adv.NotificationMessage(_("Notificações do YouTube"), message, self)
            # O wxPython traz o tipo do evento de clique, mas não o binder pronto.
            click_event = getattr(wx.adv, "wxEVT_NOTIFICATION_MESSAGE_CLICK", None)
            if click_event is not None:
                notification.Bind(wx.PyEventBinder(click_event), self._on_youtube_windows_notification_click)
            shown = bool(notification.Show())
        except Exception as exc:
            _logger.info("The Windows notification could not be shown: %s", exc)
            return False
        # A notificação precisa continuar viva para o clique nela chegar aqui.
        self._youtube_windows_notification = notification if shown else None
        return shown

    def _on_youtube_windows_notification_click(self, _event):
        bring_to_front = getattr(self, "_bring_to_front", None)
        if callable(bring_to_front):
            bring_to_front()
        self.on_open_youtube_notifications()
