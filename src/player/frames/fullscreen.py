"""Tela cheia do vídeo: a área do player da aba atual ocupa a tela inteira.

Some com o que fica em volta do vídeo (lista de itens, explorador, letras,
barra de tempo, menus e barra de status) e devolve tudo como estava ao sair.
"""

import wx

from ..i18n import _


class FrameFullscreenMixin:
    def _video_fullscreen_active(self):
        return getattr(self, "_video_fullscreen_state", None) is not None

    def on_toggle_video_fullscreen(self, _event=None):
        if self._video_fullscreen_active():
            self._exit_video_fullscreen()
        else:
            self._enter_video_fullscreen()

    def _enter_video_fullscreen(self):
        notebook = getattr(self, "notebook", None)
        page = notebook.GetCurrentPage() if notebook is not None else None
        video_panel = getattr(page, "video_panel", None)
        if not video_panel:
            self._announce(_("Esta aba não tem área de vídeo."))
            return

        focus = wx.Window.FindFocus()
        hidden = []
        for window in (
            getattr(self, "explorer_panel", None),
            getattr(self, "lyrics_panel", None),
            getattr(self, "progress_panel", None),
            getattr(page, "autodj_panel", None),
            getattr(page, "browser_panel", None),
        ):
            if isinstance(window, wx.Window) and window and window.IsShown():
                window.Hide()
                hidden.append(window)

        self._video_fullscreen_state = {"page": page, "hidden": hidden, "focus": focus, "moved_focus": False}
        self.ShowFullScreen(True, wx.FULLSCREEN_ALL)
        self._relayout_video_fullscreen(page)

        # O controle com foco pode ter sumido junto com a lista: o foco vai para
        # a área do player (o painel wx, nunca a janela nativa do vídeo).
        if focus is None or not focus or not focus.IsShownOnScreen():
            self._video_fullscreen_state["moved_focus"] = bool(self._focus_player_surface(video_panel))

        self._announce(_("Tela cheia ativada. Esc ou Alt+Enter para sair."))

    def _exit_video_fullscreen(self, announce=True):
        state = getattr(self, "_video_fullscreen_state", None)
        if state is None:
            return
        self._video_fullscreen_state = None

        self.ShowFullScreen(False)
        for window in state["hidden"]:
            if window:
                window.Show()
        page = state["page"]
        self._relayout_video_fullscreen(page if page else None)

        focus = state["focus"]
        if state["moved_focus"] and focus and focus.IsShownOnScreen():
            focus.SetFocus()

        if announce:
            self._announce(_("Tela cheia desativada."))

    def _relayout_video_fullscreen(self, page):
        if page is not None:
            page.Layout()
        notebook = getattr(self, "notebook", None)
        if notebook is not None:
            notebook.GetParent().Layout()
        self.Layout()
        if page is not None:
            self._layout_video_page(page)
        refresh_visual_hints = getattr(self, "_refresh_player_visual_hints", None)
        if callable(refresh_visual_hints):
            refresh_visual_hints()
