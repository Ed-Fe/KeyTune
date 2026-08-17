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

from player.frames.commands.key_navigation import KeyNavigationMixin
from player.frames.commands.open_commands import OpenCommandsMixin
from player.playlists import ScreenTabState


class ClipboardShortcutTests(unittest.TestCase):
    def test_control_shift_c_uses_playing_media_even_on_screen_tab(self):
        frame = KeyNavigationMixin.__new__(KeyNavigationMixin)
        frame._get_browser_panel = Mock(return_value=None)
        frame._get_tab_state = Mock(return_value=ScreenTabState(title="YouTube Music", screen_id="youtube_music"))
        frame._handle_screen_tab_key_down = Mock(return_value=True)
        frame.on_copy_playing_media_path = Mock()

        event = Mock()
        event.GetKeyCode.return_value = ord("C")
        event.ControlDown.return_value = True
        event.ShiftDown.return_value = True
        event.AltDown.return_value = False

        with patch("player.frames.commands.key_navigation.wx.Window.FindFocus", return_value=None):
            frame.on_key_down(event)

        frame.on_copy_playing_media_path.assert_called_once_with(None)
        frame._handle_screen_tab_key_down.assert_not_called()

    def test_copy_playing_media_uses_active_playlist_instead_of_selection(self):
        frame = OpenCommandsMixin.__new__(OpenCommandsMixin)
        media_path = "https://music.youtube.com/watch?v=abc123DEF45"
        frame._get_active_playlist_state = Mock(return_value=SimpleNamespace(current_media_path=media_path))
        frame._copy_text_to_clipboard = Mock(return_value=True)
        frame._announce = Mock()

        result = frame.on_copy_playing_media_path()

        self.assertTrue(result)
        frame._copy_text_to_clipboard.assert_called_once_with(media_path)
        frame._announce.assert_called_once_with("Link da mídia atual copiado.")


if __name__ == "__main__":
    unittest.main()
