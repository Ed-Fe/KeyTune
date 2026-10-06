"""Ícone na bandeja do sistema: esconder a janela e controlar o player por ele.

A janela vai para a bandeja pelo menu Arquivo, por um atalho (local ou global)
e, se o usuário quiser, ao minimizar ou ao fechar. O ícone fica visível
enquanto a janela está escondida ou enquanto uma dessas opções estiver ligada.
"""

from __future__ import annotations

import sys

import wx

from ..constants import APP_TITLE
from ..i18n import _
from ..log import get_logger

_logger = get_logger(__name__)

try:  # pragma: no cover - wx.adv existe em todas as builds do wxPython usadas
    import wx.adv as _wx_adv
except Exception:  # pragma: no cover
    _wx_adv = None


def _tray_icon_image():
    if getattr(sys, "frozen", False):
        # O ícone do executável; sem ele o wx abriria uma caixa de erro.
        no_log = wx.LogNull()
        icon = wx.Icon(f"{sys.executable};0", wx.BITMAP_TYPE_ICO)
        del no_log
        if icon.IsOk():
            return icon
    return wx.ArtProvider.GetIcon(wx.ART_EXECUTABLE_FILE, wx.ART_OTHER, (16, 16))


if _wx_adv is not None:

    class KeyTuneTrayIcon(_wx_adv.TaskBarIcon):
        """O menu do ícone repete os controles básicos do player."""

        def __init__(self, frame):
            super().__init__()
            self._frame = frame
            self.Bind(_wx_adv.EVT_TASKBAR_LEFT_DOWN, lambda _event: frame._toggle_tray_visibility())

        def CreatePopupMenu(self):
            frame = self._frame
            menu = wx.Menu()
            entries = (
                (_("&Ocultar KeyTune") if frame.IsShown() else _("&Mostrar KeyTune"), frame._toggle_tray_visibility),
                None,
                (_("&Reproduzir ou pausar"), lambda: frame.on_play_pause(None)),
                (_("Faixa &anterior"), lambda: frame.on_previous_track(None)),
                (_("&Próxima faixa"), lambda: frame.on_next_track(None)),
                (_("P&arar"), lambda: frame.on_stop(None)),
                (_("Anunciar &status"), lambda: frame.on_announce_status(None)),
                None,
                (_("&Sair do KeyTune"), frame._exit_from_tray),
            )
            for entry in entries:
                if entry is None:
                    menu.AppendSeparator()
                    continue
                label, callback = entry
                item = menu.Append(wx.ID_ANY, label)
                # CallAfter: o menu do ícone precisa fechar antes de a ação abrir
                # uma janela ou encerrar o programa.
                self.Bind(wx.EVT_MENU, lambda _event, cb=callback: wx.CallAfter(cb), item)
            return menu

else:  # pragma: no cover
    KeyTuneTrayIcon = None


class FrameTrayMixin:
    def _tray_supported(self):
        return KeyTuneTrayIcon is not None and _wx_adv.TaskBarIcon.IsAvailable()

    def _tray_wanted(self):
        return bool(
            getattr(self, "_hidden_in_tray", False)
            or self.settings.minimize_to_tray
            or self.settings.close_to_tray
        )

    def _refresh_tray_icon(self):
        """Mostra ou tira o ícone conforme a janela e as preferências."""
        if not self._tray_supported():
            return
        icon = getattr(self, "_tray_icon", None)
        if not self._tray_wanted():
            if icon is not None:
                icon.RemoveIcon()
                icon.Destroy()
                self._tray_icon = None
            return
        if icon is None:
            try:
                icon = self._tray_icon = KeyTuneTrayIcon(self)
            except Exception:
                _logger.exception("Could not create the tray icon")
                self._tray_icon = None
                return
        icon.SetIcon(_tray_icon_image(), APP_TITLE)

    def _shutdown_tray(self):
        icon = getattr(self, "_tray_icon", None)
        self._tray_icon = None
        if icon is not None:
            icon.RemoveIcon()
            icon.Destroy()

    def _hide_to_tray(self):
        if not self._tray_supported():
            # Sem bandeja, esconder deixaria a janela inalcançável: minimiza.
            self.Iconize(True)
            return
        if getattr(self, "_hidden_in_tray", False):
            return
        self._focus_before_tray = wx.Window.FindFocus()
        self._hidden_in_tray = True
        self._refresh_tray_icon()
        self._announce(_("KeyTune na bandeja do sistema."))
        self.Hide()

    def _restore_from_tray(self):
        was_hidden = getattr(self, "_hidden_in_tray", False)
        self._hidden_in_tray = False
        self.Show()
        if self.IsIconized():
            self.Iconize(False)
        self.Raise()
        self._refresh_tray_icon()
        if was_hidden:
            # Volta para o controle que tinha o foco, como uma janela que nunca
            # saiu. Se ele não existe mais e o Windows não devolveu o foco a
            # ninguém, ele vai para o player, como ao abrir o KeyTune de novo.
            previous = getattr(self, "_focus_before_tray", None)
            self._focus_before_tray = None
            if isinstance(previous, wx.Window) and previous and previous.IsShownOnScreen():
                previous.SetFocus()
            elif wx.Window.FindFocus() is None:
                self._focus_player_surface()

    def _toggle_tray_visibility(self):
        if getattr(self, "_hidden_in_tray", False) or not self.IsShown():
            self._restore_from_tray()
        else:
            self._hide_to_tray()

    def _toggle_minimized(self):
        if getattr(self, "_hidden_in_tray", False) or not self.IsShown():
            self._restore_from_tray()
        elif self.IsIconized():
            self.Iconize(False)
            self.Raise()
        else:
            self.Iconize(True)

    def _bring_to_front(self):
        if getattr(self, "_hidden_in_tray", False) or not self.IsShown() or self.IsIconized():
            self._restore_from_tray()
            return
        self.Raise()

    def on_hide_to_tray(self, _event):
        self._hide_to_tray()

    def _on_iconize_to_tray(self, event):
        event.Skip()
        if event.IsIconized() and self.settings.minimize_to_tray and self._tray_supported():
            wx.CallAfter(self._hide_to_tray)

    def _close_to_tray_requested(self, event):
        """Se fechar a janela deve só escondê-la; nesse caso já a esconde."""
        if (
            not self.settings.close_to_tray
            or getattr(self, "_exit_requested", False)
            or getattr(self, "_update_restart_pending", False)
            or not event.CanVeto()
            or not self._tray_supported()
        ):
            return False
        event.Veto()
        self._hide_to_tray()
        return True

    def _exit_from_tray(self):
        self._exit_requested = True
        if getattr(self, "_hidden_in_tray", False):
            # A confirmação de saída precisa de uma janela visível como dona.
            self._restore_from_tray()
        self.Close()
