"""Detalhes de um vídeo ou música do YouTube, numa caixa de leitura."""

import wx

from player.youtube_music import details as youtube_details
from player.youtube_music.models import (
    YOUTUBE_SEARCH_SOURCE_MUSIC,
    YOUTUBE_SEARCH_SOURCE_YOUTUBE,
    YouTubeMediaSearchResult,
)
from player.youtube_music.playlists import extract_video_id_from_text, is_music_youtube_url

# As faixas do YouTube Music ficam num canal automático, "Artista - Topic",
# cujo identificador é o do artista no YouTube Music.
TOPIC_CHANNEL_SUFFIX = " - Topic"

from ...i18n import _


class DetailsMixin:
    def show_youtube_music_details(self, result=None):
        """Mostra os detalhes do vídeo ou da música selecionada na lista."""
        if result is None:
            result = self._selected_youtube_music_search_result()
        media_url = self._youtube_music_comments_url(result)
        if not media_url:
            self._announce(_("Este item não tem detalhes para mostrar."))
            return False
        return self._open_youtube_music_details(media_url)

    def show_current_media_details(self):
        """Mostra os detalhes da mídia que está tocando."""
        state = self._get_active_playlist_state()
        media_path = str(getattr(state, "current_media_path", "") or "").strip()
        if not media_path or not extract_video_id_from_text(media_path):
            self._announce(_("A mídia atual não é do YouTube: não há detalhes para mostrar."))
            return False
        return self._open_youtube_music_details(media_path)

    def _open_youtube_music_details(self, media_url):
        def worker():
            return youtube_details.media_details(media_url)

        def on_success(details):
            actions = []
            owner = self._youtube_music_details_owner(media_url, details)
            if owner is not None:
                label = _("Ir para o &artista") if owner.result_type == "artist" else _("Ir para o &canal")
                actions.append((label, lambda: self._open_youtube_music_details_owner(owner)))
            self._show_youtube_music_reading_dialog(
                title=_("Detalhes de {title}").format(title=details.title) if details.title else _("Detalhes"),
                text=youtube_details.details_reading_text(details),
                name=_("Detalhes"),
                actions=actions,
            )

        def on_error(exc):
            wx.MessageBox(
                _("Não foi possível carregar os detalhes agora.")
                + "\n\n"
                + _("Detalhes: {detail}").format(detail=self._format_youtube_music_error_detail(exc)),
                "KeyTube",
                wx.OK | wx.ICON_ERROR,
                self,
            )

        self._announce(_("Carregando os detalhes."))
        return self._run_youtube_music_background_task(worker, on_success, on_error=on_error)

    @staticmethod
    def _youtube_music_details_owner(media_url, details):
        """O artista (faixa do YouTube Music) ou o canal da mídia, para ir até ele; ``None`` sem ele."""
        if not details.channel_id:
            return None
        if is_music_youtube_url(media_url) and details.channel.endswith(TOPIC_CHANNEL_SUFFIX):
            return YouTubeMediaSearchResult(
                source=YOUTUBE_SEARCH_SOURCE_MUSIC,
                result_type="artist",
                title=details.channel[: -len(TOPIC_CHANNEL_SUFFIX)],
                browse_id=details.channel_id,
                source_badge="YouTube Music",
            )
        return YouTubeMediaSearchResult(
            source=YOUTUBE_SEARCH_SOURCE_YOUTUBE,
            result_type="channel",
            title=details.channel,
            browse_id=details.channel_id,
            source_badge="YouTube",
        )

    def _open_youtube_music_details_owner(self, owner):
        """Abre o KeyTube no artista ou canal da mídia cujos detalhes estavam na tela."""
        self.on_open_youtube_music(None)
        if self._get_youtube_music_panel() is None:
            return False
        return self.on_browse_youtube_music_search_result(owner, focus_results=True)

    def _show_youtube_music_reading_dialog(self, *, title, text, name, actions=()):
        """Caixa só de leitura, com o cursor no começo do texto; Esc fecha.

        *actions*: pares ``(rótulo, função)``; cada um vira um botão que fecha a
        caixa e só então chama a função.
        """
        chosen = []
        dialog = wx.Dialog(self, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        try:
            text_ctrl = wx.TextCtrl(dialog, value=text, style=wx.TE_MULTILINE | wx.TE_READONLY, size=(520, 260))
            text_ctrl.SetName(name)
            buttons = wx.BoxSizer(wx.HORIZONTAL)
            for label, callback in actions:
                action_button = wx.Button(dialog, wx.ID_ANY, label)

                def on_action(_event, callback=callback):
                    chosen.append(callback)
                    dialog.EndModal(wx.ID_OK)

                action_button.Bind(wx.EVT_BUTTON, on_action)
                buttons.Add(action_button, 0, wx.RIGHT, 8)
            close_button = wx.Button(dialog, wx.ID_CLOSE, _("&Fechar"))
            close_button.Bind(wx.EVT_BUTTON, lambda _event: dialog.EndModal(wx.ID_CLOSE))
            buttons.Add(close_button, 0)
            dialog.SetEscapeId(wx.ID_CLOSE)

            sizer = wx.BoxSizer(wx.VERTICAL)
            sizer.Add(text_ctrl, 1, wx.ALL | wx.EXPAND, 10)
            sizer.Add(buttons, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.ALIGN_RIGHT, 10)
            dialog.SetSizerAndFit(sizer)
            text_ctrl.SetInsertionPoint(0)
            dialog.CentreOnParent()
            dialog.ShowModal()
        finally:
            dialog.Destroy()
        for callback in chosen:
            callback()
        return True
