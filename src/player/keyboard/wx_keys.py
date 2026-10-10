"""Tradução entre os atalhos canônicos de ``shortcuts.py`` e as teclas do wx."""

from __future__ import annotations

import wx

from .shortcuts import normalize_shortcut, shortcut_parts

_SPECIAL_KEYS = {
    wx.WXK_SPACE: "Space",
    wx.WXK_LEFT: "Left",
    wx.WXK_RIGHT: "Right",
    wx.WXK_UP: "Up",
    wx.WXK_DOWN: "Down",
    wx.WXK_HOME: "Home",
    wx.WXK_END: "End",
    wx.WXK_PAGEUP: "PageUp",
    wx.WXK_PAGEDOWN: "PageDown",
    wx.WXK_INSERT: "Insert",
    wx.WXK_DELETE: "Delete",
    wx.WXK_BACK: "Back",
    wx.WXK_RETURN: "Enter",
    wx.WXK_NUMPAD_ENTER: "Enter",
    wx.WXK_TAB: "Tab",
    wx.WXK_ESCAPE: "Escape",
    wx.WXK_PAUSE: "Pause",
}
for _number in range(1, 25):
    _SPECIAL_KEYS[getattr(wx, f"WXK_F{_number}")] = f"F{_number}"

_KEY_CODES = {name: code for code, name in _SPECIAL_KEYS.items() if code != wx.WXK_NUMPAD_ENTER}

MODIFIER_KEY_CODES = frozenset(
    code
    for code in (
        wx.WXK_SHIFT,
        wx.WXK_CONTROL,
        wx.WXK_ALT,
        getattr(wx, "WXK_WINDOWS_LEFT", None),
        getattr(wx, "WXK_WINDOWS_RIGHT", None),
        getattr(wx, "WXK_WINDOWS_MENU", None),
        getattr(wx, "WXK_RAW_CONTROL", None),
        getattr(wx, "WXK_CAPITAL", None),
        getattr(wx, "WXK_NUMLOCK", None),
        getattr(wx, "WXK_SCROLL", None),
    )
    if code is not None
)


def key_name_from_code(key_code):
    """Nome canônico da tecla do evento; ``""`` para as que não podem ser atalho."""
    if key_code in _SPECIAL_KEYS:
        return _SPECIAL_KEYS[key_code]
    if 32 < key_code < 127:
        return normalize_shortcut(chr(key_code))
    return ""


def shortcut_from_key_event(event, *, allow_win=False):
    """Atalho canônico de um evento de tecla; ``""`` para um modificador sozinho."""
    key_code = event.GetKeyCode()
    if key_code in MODIFIER_KEY_CODES:
        return ""
    key = key_name_from_code(key_code)
    if not key:
        return ""
    parts = []
    if event.ControlDown():
        parts.append("Ctrl")
    if event.AltDown():
        parts.append("Alt")
    if event.ShiftDown():
        parts.append("Shift")
    if allow_win and event.MetaDown():
        parts.append("Win")
    parts.append(key)
    return normalize_shortcut("+".join(parts))


def key_code_from_name(key):
    if key in _KEY_CODES:
        return _KEY_CODES[key]
    if len(key) == 1:
        return ord(key)
    return None


def accelerator_entry(shortcut, command_id):
    """Entrada da tabela de aceleradores do frame; ``None`` se não couber numa."""
    modifiers, key = shortcut_parts(normalize_shortcut(shortcut))
    key_code = key_code_from_name(key) if key else None
    if key_code is None or "Win" in modifiers:
        return None
    flags = wx.ACCEL_NORMAL
    if "Ctrl" in modifiers:
        flags |= wx.ACCEL_CTRL
    if "Alt" in modifiers:
        flags |= wx.ACCEL_ALT
    if "Shift" in modifiers:
        flags |= wx.ACCEL_SHIFT
    return wx.AcceleratorEntry(flags, key_code, int(command_id))


def hotkey_arguments(shortcut):
    """``(modificadores, tecla)`` para ``wx.Window.RegisterHotKey``; ``None`` se não der."""
    modifiers, key = shortcut_parts(normalize_shortcut(shortcut))
    key_code = key_code_from_name(key) if key else None
    if key_code is None:
        return None
    flags = 0
    if "Ctrl" in modifiers:
        flags |= wx.MOD_CONTROL
    if "Alt" in modifiers:
        flags |= wx.MOD_ALT
    if "Shift" in modifiers:
        flags |= wx.MOD_SHIFT
    if "Win" in modifiers:
        flags |= wx.MOD_WIN
    return flags, key_code
