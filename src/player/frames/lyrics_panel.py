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
        # EVT_CHAR_HOOK lets the panel own copy/navigation keys before the main
        # player's global shortcuts can act on them.
        self.lyrics_text_ctrl.Bind(wx.EVT_CHAR_HOOK, self._on_text_char_hook)
        self._attach_accessible(_("Letra da música"))

        root_sizer.Add(self.lyrics_text_ctrl, 1, wx.EXPAND | wx.ALL, 10)

        self.copy_button = wx.Button(self, label=_("Copiar letra completa"))
        self.copy_button.Bind(wx.EVT_BUTTON, self._on_copy_button_click)
        self.copy_button.Bind(wx.EVT_CHAR_HOOK, self._on_button_char_hook)
        root_sizer.Add(self.copy_button, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

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

    def _announce(self, message):
        # The panel has no announcer of its own; route feedback through the
        # owning frame so it follows the app's screen-reader settings instead of
        # popping a modal dialog.
        if not message:
            return
        frame = wx.GetTopLevelParent(self)
        announce = getattr(frame, "_announce", None)
        if callable(announce):
            announce(message)

    def _copy_to_clipboard(self, text):
        text = str(text or "")
        if not text or not wx.TheClipboard.Open():
            return False
        try:
            wx.TheClipboard.SetData(wx.TextDataObject(text))
        finally:
            wx.TheClipboard.Close()
        return True

    def _copy_selection_or_all(self):
        selection = self.lyrics_text_ctrl.GetStringSelection()
        if self._copy_to_clipboard(selection or self.lyrics_text_ctrl.GetValue()):
            self._announce(_("Trecho da letra copiado.") if selection else _("Letra copiada."))
        else:
            self._announce(_("Não há letra para copiar."))

    def _copy_all(self):
        if self._copy_to_clipboard(self.lyrics_text_ctrl.GetValue()):
            self._announce(_("Letra completa copiada."))
        else:
            self._announce(_("Não há letra para copiar."))

    def _on_text_char_hook(self, event):
        """Own copy and navigation keys before the frame's global shortcuts."""
        key_code = event.GetKeyCode()
        no_mods = not event.ControlDown() and not event.AltDown() and not event.ShiftDown()
        ctrl_only = event.ControlDown() and not event.ShiftDown() and not event.AltDown()

        # Swallow a bare 'C' so the player's global "copy media link" shortcut
        # does not fire while the reader is inside the lyrics text.
        if no_mods and key_code in (ord("C"), ord("c")):
            return

        if ctrl_only:
            if key_code in (ord("C"), ord("c")):
                self._copy_selection_or_all()
                return
            if key_code in (ord("A"), ord("a")):
                self.lyrics_text_ctrl.SelectAll()
                return
            if key_code == wx.WXK_END:
                self.lyrics_text_ctrl.SetInsertionPointEnd()
                return
            if key_code == wx.WXK_HOME:
                self.lyrics_text_ctrl.SetInsertionPoint(0)
                return

        # Down at the end of the text jumps to the copy button (Tab also works).
        if no_mods and key_code == wx.WXK_DOWN:
            if self.lyrics_text_ctrl.GetInsertionPoint() >= self.lyrics_text_ctrl.GetLastPosition():
                self.copy_button.SetFocus()
                return

        event.Skip()

    def _on_button_char_hook(self, event):
        """Up returns focus from the copy button to the lyrics text."""
        if (
            event.GetKeyCode() == wx.WXK_UP
            and not event.ControlDown()
            and not event.AltDown()
            and not event.ShiftDown()
        ):
            self.lyrics_text_ctrl.SetFocus()
            self.lyrics_text_ctrl.SetInsertionPointEnd()
            return
        event.Skip()

    def _on_copy_button_click(self, event):
        self._copy_all()
