"""Atalhos globais: funcionam com o KeyTune minimizado, na bandeja ou sem foco.

Usam ``wx.Window.RegisterHotKey``, que só existe de fato no Windows. Nos demais
sistemas o registro falha e a opção fica desativada na tela de personalização.
"""

from __future__ import annotations

import sys

import wx

from ..keyboard.shortcuts import SCOPE_GLOBAL, actions, effective_bindings
from ..keyboard.wx_keys import hotkey_arguments
from ..log import get_logger

_logger = get_logger(__name__)

# Faixa de ids que o Windows reserva aos aplicativos (0x0000 a 0xBFFF).
_HOTKEY_ID_BASE = 0xB000


class FrameGlobalHotkeysMixin:
    def _global_hotkeys_supported(self):
        return sys.platform == "win32" and hasattr(self, "RegisterHotKey")

    def _apply_global_hotkeys(self):
        """Registra os atalhos globais em vigor; devolve os que outro programa já usa."""
        self._unregister_global_hotkeys()
        if not self.settings.global_hotkeys_enabled or not self._global_hotkeys_supported():
            return []

        bindings = effective_bindings(self.settings.global_hotkeys, SCOPE_GLOBAL)
        failed = []
        self._global_hotkey_actions = {}
        for index, action in enumerate(actions(SCOPE_GLOBAL)):
            shortcut = bindings.get(action.action_id, "")
            arguments = hotkey_arguments(shortcut) if shortcut else None
            if arguments is None:
                continue
            hotkey_id = _HOTKEY_ID_BASE + index
            try:
                registered = self.RegisterHotKey(hotkey_id, *arguments)
            except Exception:
                _logger.exception("RegisterHotKey failed for %s", shortcut)
                registered = False
            if not registered:
                failed.append(shortcut)
                continue
            self._global_hotkey_actions[hotkey_id] = action
            self.Bind(wx.EVT_HOTKEY, self._on_global_hotkey, id=hotkey_id)
        if failed:
            _logger.warning("Global hotkeys already in use: %s", ", ".join(failed))
        return failed

    def _unregister_global_hotkeys(self):
        for hotkey_id in list(getattr(self, "_global_hotkey_actions", {})):
            try:
                self.UnregisterHotKey(hotkey_id)
            except Exception:
                pass
            self.Unbind(wx.EVT_HOTKEY, id=hotkey_id)
        self._global_hotkey_actions = {}

    def _on_global_hotkey(self, event):
        action = getattr(self, "_global_hotkey_actions", {}).get(event.GetId())
        if action is None or not getattr(self, "_startup_ready", False):
            return
        self._run_key_action(action)
