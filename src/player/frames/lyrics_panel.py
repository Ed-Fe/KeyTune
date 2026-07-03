import threading

import wx

from ..accessibility import attach_named_accessible
from ..i18n import _
from ..lyrics import fetch_lyrics


class LyricsPanel(wx.Panel):
    """Read-only panel that displays lyrics for the current track."""

    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        self.SetName(_("Painel de letras"))
        self._current_request_id = 0

        root_sizer = wx.BoxSizer(wx.VERTICAL)

        self.lyrics_text_ctrl = wx.TextCtrl(
            self,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.VSCROLL | wx.WANTS_CHARS,
        )
        # EVT_CHAR_HOOK captures keys BEFORE the main player's global shortcuts steal them
        self.lyrics_text_ctrl.Bind(wx.EVT_CHAR_HOOK, self._on_text_char_hook)
        self._attach_accessible(_("Letra da música"))

        root_sizer.Add(self.lyrics_text_ctrl, 1, wx.EXPAND | wx.ALL, 10)

        # Button permanently at the bottom
        self.copy_button = wx.Button(self, label=_("Copiar letra completa"))
        self.copy_button.Bind(wx.EVT_BUTTON, self._on_copy_button_click)
        self.copy_button.Bind(wx.EVT_CHAR_HOOK, self._on_button_char_hook)
        
        root_sizer.Add(self.copy_button, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.SetSizer(root_sizer)

    def update_lyrics(self, text):
        if text:
            self.lyrics_text_ctrl.SetValue(text)
        else:
            self.lyrics_text_ctrl.SetValue(_("Letra não encontrada para esta mídia."))
            
        # Force layout recalculation and refresh so the button stays firmly visible at the bottom
        self.Layout()
        self.Refresh()

    def load_lyrics_for_track(self, artist, title):
        artist_str = str(artist or "").strip()
        title_str = str(title or "").strip()
        self._attach_accessible(self._accessible_name_for(artist_str, title_str))

        if not artist_str and not title_str:
            self.update_lyrics(_("Informações da faixa incompletas para buscar a letra."))
            return

        self.lyrics_text_ctrl.SetValue(_("Buscando letra..."))
        self.Layout()
        self.Refresh()

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
            self.Layout()
            self.Refresh()

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

    def _on_text_char_hook(self, event):
        """Intercept keys before parent accelerators steal them."""
        key_code = event.GetKeyCode()
        
        # 1. Block standalone 'C' from copying the link globally
        if not event.HasAnyModifiers() and key_code in (ord('C'), ord('c')):
            return  # Consume event silently
            
        # 2. Intercept Ctrl shortcuts to prevent leakage to the main player
        if event.ControlDown() and not event.ShiftDown() and not event.AltDown():
            if key_code in (ord('C'), ord('c')):
                self.lyrics_text_ctrl.Copy()
                wx.MessageBox(_("Letra copiada com sucesso!"), _("Sucesso"), wx.OK | wx.ICON_INFORMATION, self)
                return
            elif key_code in (ord('A'), ord('a')):
                self.lyrics_text_ctrl.SelectAll()
                return
            elif key_code == wx.WXK_END:
                self.lyrics_text_ctrl.SetInsertionPointEnd()
                return
            elif key_code == wx.WXK_HOME:
                self.lyrics_text_ctrl.SetInsertionPoint(0)
                return

        # 3. Handle Down Arrow to navigate to the copy button
        if key_code == wx.WXK_DOWN and not event.HasAnyModifiers():
            last_pos = self.lyrics_text_ctrl.GetLastPosition()
            if self.lyrics_text_ctrl.GetInsertionPoint() >= last_pos:
                self.copy_button.SetFocus()
                return

        event.Skip()

    def _on_button_char_hook(self, event):
        """Handle keyboard navigation on the copy button via CHAR_HOOK."""
        key_code = event.GetKeyCode()
        
        if key_code == wx.WXK_UP and not event.HasAnyModifiers():
            self.lyrics_text_ctrl.SetFocus()
            self.lyrics_text_ctrl.SetInsertionPointEnd()
            return
            
        event.Skip()

    def _on_copy_button_click(self, event):
        """Copy the entire lyrics content to the system clipboard."""
        text = self.lyrics_text_ctrl.GetValue()
        if text:
            if wx.TheClipboard.Open():
                wx.TheClipboard.SetData(wx.TextDataObject(text))
                wx.TheClipboard.Close()
                wx.MessageBox(_("Letra copiada com sucesso!"), _("Sucesso"), wx.OK | wx.ICON_INFORMATION, self)