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
from player.playlists import PlaylistState, ScreenTabState


class ClipboardShortcutTests(unittest.TestCase):
    def _autodj_navigation_frame(self, panel):
        frame = KeyNavigationMixin.__new__(KeyNavigationMixin)
        state = PlaylistState(title="AutoDJ")
        state.autodj_session = True
        frame._get_playlist_state = Mock(return_value=state)
        frame._get_autodj_panel = Mock(return_value=panel)
        frame._focus_item_navigation = Mock()
        frame._focus_player_controls = Mock()
        return frame

    def test_tab_from_autodj_list_enters_controls_but_shift_tab_does_not(self):
        panel = Mock()
        panel.IsShown.return_value = True
        panel.focus_first_control.return_value = True
        frame = self._autodj_navigation_frame(panel)

        self.assertTrue(frame._focus_autodj_controls_from_list(backward=False))
        self.assertFalse(frame._focus_autodj_controls_from_list(backward=True))
        panel.focus_first_control.assert_called_once_with()

    def test_tab_leaves_autodj_control_edges_in_the_expected_direction(self):
        panel = Mock()
        panel.IsShown.return_value = True
        panel.contains_focus.return_value = True
        panel.focus_adjacent_control.return_value = False
        frame = self._autodj_navigation_frame(panel)

        self.assertTrue(frame._navigate_autodj_controls(backward=True))
        frame._focus_item_navigation.assert_called_once_with(announce=False)
        self.assertTrue(frame._navigate_autodj_controls(backward=False))
        frame._focus_player_controls.assert_called_once_with(announce=False)

    def test_shift_tab_from_player_enters_last_autodj_control(self):
        panel = Mock()
        panel.IsShown.return_value = True
        panel.focus_last_control.return_value = True
        frame = self._autodj_navigation_frame(panel)

        self.assertTrue(frame._focus_autodj_controls_from_player(backward=True))
        self.assertFalse(frame._focus_autodj_controls_from_player(backward=False))
        panel.focus_last_control.assert_called_once_with()

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

    def test_control_v_opens_clipboard_even_on_screen_tab(self):
        frame = KeyNavigationMixin.__new__(KeyNavigationMixin)
        frame._get_browser_panel = Mock(return_value=None)
        frame._get_tab_state = Mock(return_value=ScreenTabState(title="YouTube Music", screen_id="youtube_music"))
        frame._handle_screen_tab_key_down = Mock(return_value=True)
        frame.on_paste_open_from_clipboard = Mock()

        event = Mock()
        event.GetKeyCode.return_value = ord("V")
        event.ControlDown.return_value = True
        event.ShiftDown.return_value = False
        event.AltDown.return_value = False

        with patch("player.frames.commands.key_navigation.wx.Window.FindFocus", return_value=None):
            frame.on_key_down(event)

        frame.on_paste_open_from_clipboard.assert_called_once_with(None)
        frame._handle_screen_tab_key_down.assert_not_called()

    def test_youtube_music_playlist_link_uses_playlist_loader(self):
        frame = OpenCommandsMixin.__new__(OpenCommandsMixin)
        frame._load_youtube_music_playlist_by_id = Mock()
        frame._announce = Mock()

        frame._open_from_clipboard_text(
            "https://music.youtube.com/playlist?list=PL9gxAtk_mlbN37YGXDWDvdRBn9PB3qdT0"
        )

        frame._load_youtube_music_playlist_by_id.assert_called_once_with(
            "PL9gxAtk_mlbN37YGXDWDvdRBn9PB3qdT0",
            fallback_title="Playlist do YouTube Music",
        )
        frame._announce.assert_not_called()

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
