"""O chat de uma transmissão ao vivo na lista da aba do KeyTube.

A lista mostra as mensagens e cresce sozinha: enquanto ela está na tela, a
janela pede as mensagens novas de poucos em poucos segundos, numa thread
própria, e fala as que chegaram.
"""

import threading
from dataclasses import dataclass

import wx

from player.youtube_music import live_chat as youtube_live_chat
from player.youtube_music.folders import send_chat_message_item
from player.youtube_music.models import YouTubeResultPage
from player.youtube_music.playlists import extract_video_id_from_text

from ... import interface_sounds
from ...i18n import _
from ...log import get_logger
from .navigation import YouTubeResultsView


_logger = get_logger(__name__)


@dataclass(frozen=True)
class LiveChatContext:
    """De que transmissão é o chat de uma lista."""

    media_url: str


class LiveChatMixin:
    def _youtube_music_live_chat_menu_entries(self, result):
        """O chat ao vivo de uma transmissão que está no ar, para o menu de ações."""
        if not getattr(result, "is_live", False) or not self._youtube_music_comments_url(result):
            return []
        return [(_("Ver o chat ao vivo"), lambda: self.show_youtube_music_live_chat(result))]

    def _youtube_music_live_chat_list_menu_entries(self):
        """Ligar e desligar a fala das mensagens, para o menu de ações da lista do chat."""
        if not isinstance(self._youtube_music_current_results_view().context, LiveChatContext):
            return []
        label = (
            _("Parar de falar as mensagens do chat")
            if self._youtube_live_chat_speaks()
            else _("Falar as mensagens do chat")
        )
        return [(label, self.toggle_youtube_live_chat_speech)]

    def _youtube_live_chat_speaks(self):
        return bool(getattr(self, "_youtube_live_chat_speech", True))

    def toggle_youtube_live_chat_speech(self):
        self._youtube_live_chat_speech = not self._youtube_live_chat_speaks()
        self._announce(
            _("As mensagens do chat serão faladas.")
            if self._youtube_live_chat_speech
            else _("As mensagens do chat não serão mais faladas.")
        )
        return True

    def show_youtube_music_live_chat(self, result=None):
        """Abre, na lista, o chat da transmissão ao vivo selecionada."""
        if result is None:
            result = self._selected_youtube_music_search_result()
        media_url = self._youtube_music_comments_url(result)
        if not media_url:
            self._announce(_("Este item não tem chat ao vivo."))
            return False
        return self._open_youtube_music_live_chat_view(media_url, getattr(result, "title", ""))

    def show_current_media_live_chat(self):
        """Abre a aba do KeyTube no chat da transmissão que está tocando."""
        state = self._get_active_playlist_state()
        media_path = str(getattr(state, "current_media_path", "") or "").strip()
        if not media_path or not extract_video_id_from_text(media_path):
            self._announce(_("A mídia atual não é do YouTube: não há chat ao vivo."))
            return False
        media_title = self._media_label(media_path)
        self.on_open_youtube_music(None)
        if self._get_youtube_music_panel() is None:
            return False
        return self._open_youtube_music_live_chat_view(media_path, media_title)

    def _open_youtube_music_live_chat_view(self, media_url, media_title):
        def fetch_page(start, _count):
            if start:
                # O chat não tem páginas: o que chega depois entra sozinho na lista.
                return YouTubeResultPage()
            update = youtube_live_chat.live_chat_update(media_url, restart=True)
            self._youtube_live_chat_viewer = update.viewer
            results = list(update.messages)
            if update.can_send or update.restriction:
                results.insert(0, send_chat_message_item(update.restriction))
            return YouTubeResultPage(results=tuple(results))

        view = YouTubeResultsView(
            title=youtube_live_chat.live_chat_view_title(media_title),
            fetch_page=fetch_page,
            context=LiveChatContext(media_url=media_url),
        )
        self._announce(_("Abrindo {title}.").format(title=view.title))
        started = self._load_youtube_music_results_view(
            view,
            mode="push",
            error_message=_("Não foi possível abrir o chat ao vivo."),
            focus_results=True,
        )
        if started:
            self._schedule_youtube_live_chat_update()
        return started

    def _youtube_live_chat_view(self):
        """A lista de chat aberta na aba, esteja ela na tela ou embaixo de outra; ``None`` sem nenhuma."""
        if self._get_youtube_music_panel() is None:
            return None
        for view in reversed(self._youtube_music_results_views()):
            if isinstance(view.context, LiveChatContext):
                return view
        return None

    def _stop_youtube_live_chat_updates(self):
        pending = getattr(self, "_youtube_live_chat_timer", None)
        self._youtube_live_chat_timer = None
        if pending is not None:
            try:
                pending.Stop()
            except Exception:
                pass

    def _schedule_youtube_live_chat_update(self):
        self._stop_youtube_live_chat_updates()
        self._youtube_live_chat_timer = wx.CallLater(
            youtube_live_chat.LIVE_CHAT_POLL_SECONDS * 1000, self._update_youtube_live_chat
        )

    def _update_youtube_live_chat(self):
        """Pede as mensagens novas, numa thread própria: não ocupa a aba nem bloqueia a troca de faixa."""
        self._youtube_live_chat_timer = None
        view = self._youtube_live_chat_view()
        if view is None:
            # A lista do chat saiu da pilha, ou a aba foi fechada: acabou o acompanhamento.
            return False
        if view is not self._youtube_music_current_results_view() or self._is_youtube_music_operation_in_progress():
            # Com outra lista por cima, ou a aba ocupada, o chat espera a vez dele.
            self._schedule_youtube_live_chat_update()
            return False
        media_url = view.context.media_url

        def worker():
            update = None
            try:
                update = youtube_live_chat.live_chat_update(media_url)
            except Exception as exc:
                _logger.info("The live chat could not be updated: %s", exc)
            try:
                wx.CallAfter(self._on_youtube_live_chat_updated, view, update)
            except Exception:
                # A janela fechou enquanto o pedido estava a caminho.
                pass

        threading.Thread(target=worker, daemon=True, name="youtube-live-chat").start()
        return True

    def _on_youtube_live_chat_updated(self, view, update):
        if self._youtube_live_chat_view() is not view:
            return
        if update is not None and update.ended:
            interface_sounds.play_for(self, interface_sounds.SOUND_CHAT_ENDED)
            self._announce(_("O chat ao vivo terminou."))
            return
        if update is not None and update.viewer:
            self._youtube_live_chat_viewer = update.viewer
        if update is not None and update.messages:
            self._append_youtube_live_chat_messages(view, update.messages)
        self._schedule_youtube_live_chat_update()

    def _append_youtube_live_chat_messages(self, view, messages):
        known_ids = {result.stable_id for result in view.results}
        new_messages = [message for message in messages if message.stable_id not in known_ids]
        if not new_messages:
            return
        rows = [result for result in view.results if getattr(result, "result_type", "") == "action"]
        kept = [result for result in view.results if getattr(result, "result_type", "") != "action"] + new_messages
        view.results = rows + kept[-youtube_live_chat.LIVE_CHAT_MAX_MESSAGES:]
        if view is self._youtube_music_current_results_view():
            self._show_youtube_music_results_view(announce=False, selected_id=self._youtube_music_selected_result_id())
            interface_sounds.play_for(
                self,
                youtube_live_chat.messages_sound(new_messages, getattr(self, "_youtube_live_chat_viewer", "")),
            )
            if self._youtube_live_chat_speaks():
                for text in youtube_live_chat.spoken_messages(new_messages):
                    self._announce(text)

    def send_youtube_live_chat_message(self, restriction=None):
        """Pede o texto e o envia ao chat da lista na tela; com *restriction*, só diz por que não dá."""
        if restriction:
            interface_sounds.play_for(self, interface_sounds.SOUND_FAILURE)
            self._announce(_("Você não pode escrever neste chat: {reason}").format(reason=restriction))
            return False
        view = self._youtube_music_current_results_view()
        if not isinstance(view.context, LiveChatContext) or not self._ensure_youtube_music_authenticated():
            return False
        dialog = wx.TextEntryDialog(
            self, _("Mensagem, enviada ao chat com a sua conta do YouTube:"), _("Enviar uma mensagem")
        )
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return False
            text = str(dialog.GetValue() or "").strip()
        finally:
            dialog.Destroy()
        if not text:
            self._announce(_("Nada foi escrito: a mensagem não foi enviada."))
            return False
        media_url = view.context.media_url

        def on_success(_result):
            interface_sounds.play_for(self, interface_sounds.SOUND_CHAT_SENT)
            self._announce(_("Mensagem enviada."))

        def on_error(exc):
            interface_sounds.play_for(self, interface_sounds.SOUND_FAILURE)
            wx.MessageBox(
                _("Não foi possível enviar a mensagem.")
                + "\n\n"
                + _("Detalhes: {detail}").format(detail=self._format_youtube_music_error_detail(exc)),
                "KeyTube",
                wx.OK | wx.ICON_ERROR,
                self,
            )

        return self._run_youtube_music_background_task(
            lambda: youtube_live_chat.send_live_chat_message(media_url, text),
            on_success,
            on_error=on_error,
        )

    def _read_youtube_live_chat_message(self, message):
        """Mostra a mensagem inteira numa caixa de leitura; a linha da lista corta as longas."""
        return self._show_reading_dialog(
            title=_("Mensagem de {author}").format(author=message.author),
            text=youtube_live_chat.message_reading_text(message),
            label=_("Mensagem"),
        )
