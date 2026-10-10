from __future__ import annotations

import pathlib
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

try:
    import wx

    from player.frames.commands.key_navigation import KeyNavigationMixin
    from player.frames.keyboard import FrameKeyboardMixin
    from player.keyboard import Keymap
except ImportError:  # pragma: no cover - wx ausente
    wx = None
    FrameKeyboardMixin = type("FrameKeyboardMixin", (), {})
    KeyNavigationMixin = type("KeyNavigationMixin", (), {})


class _Frame(FrameKeyboardMixin, KeyNavigationMixin):
    """O tratamento de teclas do player sem a janela: só o que ``on_key_down`` consulta."""

    def __init__(self, overrides):
        self._keymap = Keymap(overrides)
        self.settings = SimpleNamespace(seek_step_ms=5000, volume_step=5)
        self._seek_relative = Mock()
        self._play_adjacent_item = Mock()
        self._get_browser_panel = Mock(return_value=None)
        self._get_tab_state = Mock(return_value=None)
        self._focused_window_drives_playback = Mock(return_value=True)
        self._lyrics_text_is_focused = Mock(return_value=False)
        self._handle_screen_tab_key_down = Mock(return_value=False)
        self._explorer_has_focus = Mock(return_value=False)


def _key(key_code, *, ctrl=False, alt=False, shift=False):
    event = Mock()
    event.GetKeyCode.return_value = key_code
    event.ControlDown.return_value = ctrl
    event.AltDown.return_value = alt
    event.ShiftDown.return_value = shift
    event.MetaDown.return_value = False
    event.HasAnyModifiers.return_value = ctrl or alt
    return event


@unittest.skipIf(wx is None, "wx indisponível")
class DisplacedVariantTests(unittest.TestCase):
    def _press(self, frame, key_code, **modifiers):
        event = _key(key_code, **modifiers)
        with patch.object(wx.Window, "FindFocus", return_value=None):
            frame.on_key_down(event)
        return event

    def test_default_variants_keep_working_without_customization(self):
        frame = _Frame({})
        self._press(frame, wx.WXK_LEFT, ctrl=True)
        frame._seek_relative.assert_called_once_with(-5000)

    def test_variant_of_a_remapped_seek_no_longer_seeks(self):
        frame = _Frame({"seek_backward": "J"})
        event = self._press(frame, wx.WXK_LEFT, ctrl=True)
        frame._seek_relative.assert_not_called()
        event.Skip.assert_called_once_with()

        # O atalho novo volta, e Shift+Seta esquerda segue com o salto maior.
        self._press(frame, ord("J"))
        frame._seek_relative.assert_called_once_with(-5000)
        self._press(frame, wx.WXK_LEFT, shift=True)
        self.assertEqual(frame._seek_relative.call_count, 2)

    def test_variant_of_a_default_taken_by_another_action(self):
        frame = _Frame({"previous_track": "", "seek_backward": "Ctrl+PageUp"})
        self._press(frame, wx.WXK_PAGEUP, ctrl=True)
        frame._seek_relative.assert_called_once_with(-5000)
        self._press(frame, wx.WXK_PAGEUP, ctrl=True, shift=True)
        frame._play_adjacent_item.assert_not_called()


if __name__ == "__main__":
    unittest.main()
