from __future__ import annotations

import pathlib
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, call, patch


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.frames.commands.key_navigation import KeyNavigationMixin
from player.frames.commands.open_commands import OpenCommandsMixin
from player.playlists import PlaylistState, ScreenTabState


class ClipboardShortcutTests(unittest.TestCase):
    def test_control_r_starts_a_radio_from_the_current_track(self):
        frame = KeyNavigationMixin.__new__(KeyNavigationMixin)
        frame._get_browser_panel = Mock(return_value=None)
        frame._get_tab_state = Mock(return_value=PlaylistState(title="Playlist"))
        frame._handle_screen_tab_key_down = Mock(return_value=False)
        frame.on_start_radio_from_current = Mock()

        event = Mock()
        event.GetKeyCode.return_value = ord("R")
        event.ControlDown.return_value = True
        event.ShiftDown.return_value = False
        event.AltDown.return_value = False

        with patch("player.frames.commands.key_navigation.wx.Window.FindFocus", return_value=None):
            frame.on_key_down(event)

        frame.on_start_radio_from_current.assert_called_once_with(None)

    def test_control_r_stays_global_on_an_auxiliary_screen(self):
        frame = KeyNavigationMixin.__new__(KeyNavigationMixin)
        frame._get_browser_panel = Mock(return_value=None)
        frame._get_tab_state = Mock(return_value=ScreenTabState(title="YouTube Music", screen_id="youtube_music"))
        frame._handle_screen_tab_key_down = Mock(return_value=True)
        frame.on_start_radio_from_current = Mock()

        event = Mock()
        event.GetKeyCode.return_value = ord("R")
        event.ControlDown.return_value = True
        event.ShiftDown.return_value = False
        event.AltDown.return_value = False

        with patch("player.frames.commands.key_navigation.wx.Window.FindFocus", return_value=None):
            frame.on_key_down(event)

        frame.on_start_radio_from_current.assert_called_once_with(None)
        frame._handle_screen_tab_key_down.assert_not_called()

    def test_control_space_opens_sort_menu_in_the_folder_browser(self):
        frame = KeyNavigationMixin.__new__(KeyNavigationMixin)
        browser = SimpleNamespace(
            items_list=object(),
            is_item_navigation_active=Mock(return_value=True),
        )
        frame._get_browser_panel = Mock(return_value=browser)
        frame._get_tab_state = Mock(return_value=PlaylistState(title="Músicas", tab_type="folder"))
        frame.on_show_folder_sort_menu = Mock()

        event = Mock()
        event.GetKeyCode.return_value = 32
        event.ControlDown.return_value = True
        event.ShiftDown.return_value = False
        event.AltDown.return_value = False

        with patch("player.frames.commands.key_navigation.wx.Window.FindFocus", return_value=None):
            frame.on_key_down(event)

        frame.on_show_folder_sort_menu.assert_called_once_with(browser, browser.items_list)

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

    def test_control_shift_c_copies_selected_path_on_folder_tab(self):
        frame = KeyNavigationMixin.__new__(KeyNavigationMixin)
        folder_state = PlaylistState(title="Músicas", tab_type="folder")
        frame._get_browser_panel = Mock(return_value=None)
        frame._get_tab_state = Mock(return_value=folder_state)
        frame.on_copy_current_item_path = Mock()
        frame.on_copy_playing_media_path = Mock()

        event = Mock()
        event.GetKeyCode.return_value = ord("C")
        event.ControlDown.return_value = True
        event.ShiftDown.return_value = True
        event.AltDown.return_value = False

        with patch("player.frames.commands.key_navigation.wx.Window.FindFocus", return_value=None):
            frame.on_key_down(event)

        frame.on_copy_current_item_path.assert_called_once_with(None)
        frame.on_copy_playing_media_path.assert_not_called()

    def test_control_c_uses_context_aware_copy_command(self):
        frame = KeyNavigationMixin.__new__(KeyNavigationMixin)
        frame._get_browser_panel = Mock(return_value=None)
        frame._get_tab_state = Mock(return_value=PlaylistState(title="Playlist"))
        frame._handle_screen_tab_key_down = Mock(return_value=False)
        frame.on_copy_current_item = Mock()

        event = Mock()
        event.GetKeyCode.return_value = ord("C")
        event.ControlDown.return_value = True
        event.ShiftDown.return_value = False
        event.AltDown.return_value = False

        with patch("player.frames.commands.key_navigation.wx.Window.FindFocus", return_value=None):
            frame.on_key_down(event)

        frame.on_copy_current_item.assert_called_once_with(None)

    def test_copy_current_item_uses_file_clipboard_on_folder_tab(self):
        frame = OpenCommandsMixin.__new__(OpenCommandsMixin)
        selected_paths = [r"C:\Músicas\Faixa.mp3", r"C:\Músicas\Álbum"]
        browser = SimpleNamespace(get_selected_item_paths=Mock(return_value=selected_paths))
        frame._get_tab_state = Mock(return_value=PlaylistState(title="Músicas", tab_type="folder"))
        frame._get_browser_panel = Mock(return_value=browser)
        frame._copy_files_to_clipboard = Mock(return_value=True)
        frame._announce = Mock()

        frame.on_copy_current_item()

        frame._copy_files_to_clipboard.assert_called_once_with(selected_paths)
        frame._announce.assert_called_once_with("2 itens copiados.")

    def test_copy_current_item_keeps_text_copy_on_playlist_tab(self):
        frame = OpenCommandsMixin.__new__(OpenCommandsMixin)
        frame._get_tab_state = Mock(return_value=PlaylistState(title="Playlist"))
        frame.on_copy_current_item_path = Mock()

        frame.on_copy_current_item()

        frame.on_copy_current_item_path.assert_called_once_with(None)

    @patch("player.frames.commands.open_commands.wx.FileDataObject")
    def test_copy_files_to_clipboard_publishes_every_selected_path(self, file_data_object_class):
        frame = OpenCommandsMixin.__new__(OpenCommandsMixin)
        data = file_data_object_class.return_value
        paths = [r"C:\Músicas\Faixa.mp3", r"C:\Músicas\Álbum"]

        with patch("player.frames.commands.open_commands.wx.TheClipboard") as clipboard:
            clipboard.Open.return_value = True
            clipboard.SetData.return_value = True
            result = frame._copy_files_to_clipboard(paths)

        self.assertTrue(result)
        self.assertEqual([call.args[0] for call in data.AddFile.call_args_list], paths)
        clipboard.SetData.assert_called_once_with(data)
        clipboard.Close.assert_called_once_with()

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
