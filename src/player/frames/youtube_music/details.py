"""Detalhes de um vídeo ou música do YouTube, numa caixa de leitura."""

import wx

from player.youtube_music import details as youtube_details
from player.youtube_music.playlists import extract_video_id_from_text

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
            self._show_youtube_music_reading_dialog(
                title=_("Detalhes de {title}").format(title=details.title) if details.title else _("Detalhes"),
                text=youtube_details.details_reading_text(details),
                name=_("Detalhes"),
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

    def _show_youtube_music_reading_dialog(self, *, title, text, name):
        """Caixa só de leitura, com o cursor no começo do texto; Esc fecha."""
        dialog = wx.Dialog(self, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        try:
            text_ctrl = wx.TextCtrl(dialog, value=text, style=wx.TE_MULTILINE | wx.TE_READONLY, size=(520, 260))
            text_ctrl.SetName(name)
            close_button = wx.Button(dialog, wx.ID_CLOSE, _("&Fechar"))
            close_button.Bind(wx.EVT_BUTTON, lambda _event: dialog.EndModal(wx.ID_CLOSE))
            dialog.SetEscapeId(wx.ID_CLOSE)

            sizer = wx.BoxSizer(wx.VERTICAL)
            sizer.Add(text_ctrl, 1, wx.ALL | wx.EXPAND, 10)
            sizer.Add(close_button, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.ALIGN_RIGHT, 10)
            dialog.SetSizerAndFit(sizer)
            text_ctrl.SetInsertionPoint(0)
            dialog.CentreOnParent()
            dialog.ShowModal()
        finally:
            dialog.Destroy()
        return True
