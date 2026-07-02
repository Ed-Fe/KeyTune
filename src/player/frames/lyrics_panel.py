import threading

import wx

from ..accessibility import attach_named_accessible
from ..i18n import _
from ..lyrics import fetch_lyrics


class LyricsPanel(wx.Panel):
    """Read-only panel that displays lyrics for the current track.

    UI only: the actual lookup (network + parsing) lives in ``player.lyrics``.
    Each lookup runs on a background thread and is tagged with a request id so a
    stale result from a previous track cannot overwrite the current one.
    """

    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        self.SetName(_("Painel de letras"))
        self._current_request_id = 0

        root_sizer = wx.BoxSizer(wx.VERTICAL)

        self.lyrics_text_ctrl = wx.TextCtrl(
            self,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.VSCROLL,
        )
        self._attach_accessible(_("Letra da música"))

        root_sizer.Add(self.lyrics_text_ctrl, 1, wx.EXPAND | wx.ALL, 10)
        self.SetSizer(root_sizer)

    def update_lyrics(self, text):
        """Set the lyrics text on the main UI thread."""
        if text:
            self.lyrics_text_ctrl.SetValue(text)
        else:
            self.lyrics_text_ctrl.SetValue(_("Letra não encontrada para esta mídia."))

    def load_lyrics_for_track(self, artist, title):
        """Start a background lookup for the given track without blocking the UI."""
        artist_str = str(artist or "").strip()
        title_str = str(title or "").strip()
        self._attach_accessible(self._accessible_name_for(artist_str, title_str))

        if not artist_str and not title_str:
            self.update_lyrics(_("Informações da faixa incompletas para buscar a letra."))
            return

        self.lyrics_text_ctrl.SetValue(_("Buscando letra..."))

        self._current_request_id += 1
        request_id = self._current_request_id
        thread = threading.Thread(
            target=self._fetch_lyrics_worker,
            args=(request_id, artist_str, title_str),
            daemon=True,
        )
        thread.start()

    def _fetch_lyrics_worker(self, request_id, artist, title):
        def on_progress(message):
            wx.CallAfter(self._apply_progress, request_id, message)

        result = fetch_lyrics(artist, title, on_progress=on_progress)
        if result:
            wx.CallAfter(self._apply_result, request_id, result)
        else:
            query = f"{artist} {title}".strip()
            message = _("Letra não encontrada em nenhum banco de dados para: {query}").format(query=query)
            wx.CallAfter(self._apply_result, request_id, message)

    def _apply_progress(self, request_id, message):
        if request_id == self._current_request_id:
            self.lyrics_text_ctrl.SetValue(message)

    def _apply_result(self, request_id, text):
        if request_id == self._current_request_id:
            self.update_lyrics(text)

    def _accessible_name_for(self, artist, title):
        if title and artist:
            info = f"{title}, {artist}"
        elif title:
            info = title
        else:
            info = _("desconhecida")
        return _("Letra da música {info}").format(info=info)

    def _attach_accessible(self, name):
        self.lyrics_text_ctrl.SetName(name)
        attach_named_accessible(
            self.lyrics_text_ctrl,
            name=name,
            description=_("Área de leitura das letras. Use as setas para navegar pelo texto."),
            value_provider=lambda: self.lyrics_text_ctrl.GetValue(),
        )
