from __future__ import annotations

import pathlib
import sys
import tempfile
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


def _run_inline(_owner, work, on_done):
    on_done(work())


@patch("player.frames.commands.open_commands.run_in_background", _run_inline)
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

    def test_explorer_shortcuts_win_over_global_ones_while_it_has_focus(self):
        frame = KeyNavigationMixin.__new__(KeyNavigationMixin)
        frame._get_browser_panel = Mock(return_value=None)
        frame._get_tab_state = Mock(return_value=PlaylistState(title="Playlist"))
        frame._explorer_has_focus = Mock(return_value=True)
        frame._handle_explorer_key_down = Mock(return_value=True)
        frame.on_copy_current_item = Mock()

        event = Mock()
        event.GetKeyCode.return_value = ord("C")
        event.ControlDown.return_value = True
        event.ShiftDown.return_value = False
        event.AltDown.return_value = False

        with patch("player.frames.commands.key_navigation.wx.Window.FindFocus", return_value=None):
            frame.on_key_down(event)

        frame._handle_explorer_key_down.assert_called_once_with(event)
        frame.on_copy_current_item.assert_not_called()

    def test_control_v_pastes_and_shift_pastes_without_playing(self):
        for shift_down, expected in ((False, "on_paste_open_from_clipboard"), (True, "on_paste_without_playing")):
            frame = KeyNavigationMixin.__new__(KeyNavigationMixin)
            frame._get_browser_panel = Mock(return_value=None)
            frame._get_tab_state = Mock(return_value=PlaylistState(title="Playlist"))
            frame.on_paste_open_from_clipboard = Mock()
            frame.on_paste_without_playing = Mock()

            event = Mock()
            event.GetKeyCode.return_value = ord("V")
            event.ControlDown.return_value = True
            event.ShiftDown.return_value = shift_down
            event.AltDown.return_value = False

            with patch("player.frames.commands.key_navigation.wx.Window.FindFocus", return_value=None):
                frame.on_key_down(event)

            getattr(frame, expected).assert_called_once_with(None)

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

    def _paste_frame(self):
        frame = OpenCommandsMixin.__new__(OpenCommandsMixin)
        frame._announce = Mock()
        frame._normalize_path = lambda path: str(path)
        frame._play_media_paths_in_current_playlist = Mock(return_value=True)
        frame._add_media_paths_without_playing = Mock(return_value=True)
        frame._open_playlist_source = Mock(return_value=True)
        return frame

    def test_pasted_folder_expands_to_its_media_including_subfolders(self):
        frame = self._paste_frame()
        with tempfile.TemporaryDirectory() as folder:
            nested = pathlib.Path(folder, "Álbum")
            nested.mkdir()
            first = pathlib.Path(folder, "a.mp3")
            second = nested / "b.flac"
            for media_file in (first, second, pathlib.Path(folder, "capa.jpg")):
                media_file.write_bytes(b"")

            with patch("player.frames.commands.open_commands.run_in_background", _run_inline):
                frame._open_clipboard_sources([folder])

        frame._play_media_paths_in_current_playlist.assert_called_once_with([str(first), str(second)])
        frame._announce.assert_called_once_with("Lendo as pastas coladas...")

    def test_pasted_folder_is_read_outside_the_interface_thread(self):
        frame = self._paste_frame()
        with tempfile.TemporaryDirectory() as folder:
            with patch("player.frames.commands.open_commands.run_in_background") as run_in_background:
                with patch("player.frames.commands.open_commands.collect_media_paths") as collect:
                    frame._open_clipboard_sources([folder])

        run_in_background.assert_called_once()
        collect.assert_not_called()
        frame._play_media_paths_in_current_playlist.assert_not_called()

    def test_paste_without_playing_only_appends(self):
        frame = self._paste_frame()
        with tempfile.TemporaryDirectory() as folder:
            media_file = pathlib.Path(folder, "a.mp3")
            media_file.write_bytes(b"")

            frame._open_clipboard_sources([str(media_file), "https://example.com/b.mp3"], play=False)

        frame._add_media_paths_without_playing.assert_called_once_with(
            [str(media_file), "https://example.com/b.mp3"],
            verified=True,
        )

    def test_open_and_paste_play_in_the_current_playlist_and_keep_advancing(self):
        frame = OpenCommandsMixin.__new__(OpenCommandsMixin)
        frame._get_playlist_state = Mock(return_value=PlaylistState(title="Lista"))
        frame._open_external_media_paths = Mock(return_value=True)
        frame._suppress_next_auto_advance = True

        self.assertTrue(frame._play_media_paths_in_current_playlist(["a.mp3", "b.mp3"]))

        frame._open_external_media_paths.assert_called_once_with(["a.mp3", "b.mp3"], verified=True)
        self.assertFalse(frame._suppress_next_auto_advance)

    def test_opened_files_go_to_the_current_playlist_like_pasted_ones(self):
        frame = self._paste_frame()

        frame._open_split_selected_files(["a.mp3"], [], "Abrir arquivos")

        frame._play_media_paths_in_current_playlist.assert_called_once_with(["a.mp3"])

    def test_pasted_local_files_are_checked_outside_the_interface_thread(self):
        frame = self._paste_frame()
        with patch("player.frames.commands.open_commands.run_in_background") as run_in_background:
            with patch("os.path.isfile") as isfile, patch("os.path.isdir") as isdir:
                frame._open_clipboard_sources([r"Z:\rede\a.mp3", r"Z:\rede\b.mp3"])

        run_in_background.assert_called_once()
        isfile.assert_not_called()
        isdir.assert_not_called()
        frame._play_media_paths_in_current_playlist.assert_not_called()

    def test_single_pasted_playlist_file_opens_as_playlist(self):
        frame = self._paste_frame()
        with tempfile.TemporaryDirectory() as folder:
            playlist_file = pathlib.Path(folder, "lista.m3u8")
            playlist_file.write_text("", encoding="utf-8")

            frame._open_clipboard_sources([str(playlist_file)])

        frame._open_playlist_source.assert_called_once_with(str(playlist_file))
        frame._play_media_paths_in_current_playlist.assert_not_called()

    def test_empty_folder_paste_reports_that_nothing_was_found(self):
        frame = self._paste_frame()
        with tempfile.TemporaryDirectory() as folder:
            with patch("player.frames.commands.open_commands.run_in_background", _run_inline):
                frame._open_clipboard_sources([folder])

        frame._play_media_paths_in_current_playlist.assert_not_called()
        frame._announce.assert_called_with("Nenhuma mídia compatível foi encontrada no conteúdo colado.")

    def test_copied_files_take_precedence_over_clipboard_text(self):
        frame = OpenCommandsMixin.__new__(OpenCommandsMixin)
        copied_files = [r"C:\Músicas\Faixa.mp3", r"C:\Músicas\Álbum"]

        with patch("player.frames.commands.open_commands.wx") as wx_module:
            wx_module.TheClipboard.Open.return_value = True
            wx_module.TheClipboard.IsSupported.return_value = True
            wx_module.TheClipboard.GetData.return_value = True
            wx_module.FileDataObject.return_value.GetFilenames.return_value = copied_files
            sources = frame._read_clipboard_sources()

        self.assertEqual(sources, copied_files)
        wx_module.TheClipboard.Close.assert_called_once_with()

    def test_clipboard_text_is_split_into_clean_lines(self):
        frame = OpenCommandsMixin.__new__(OpenCommandsMixin)

        self.assertEqual(
            frame._clipboard_text_sources('"C:\\Músicas\\a.mp3"\r\n\r\n  https://example.com/b.mp3 '),
            ["C:\\Músicas\\a.mp3", "https://example.com/b.mp3"],
        )

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

    def test_copy_current_item_publishes_the_selection_as_text_and_files(self):
        frame = OpenCommandsMixin.__new__(OpenCommandsMixin)
        selected_paths = [r"C:\Músicas\Faixa.mp3", "https://example.com/b.mp3"]
        browser = SimpleNamespace(get_selected_item_paths=Mock(return_value=selected_paths))
        frame._get_tab_state = Mock(return_value=PlaylistState(title="Playlist"))
        frame._get_browser_panel = Mock(return_value=browser)
        frame._copy_items_to_clipboard = Mock(return_value=True)
        frame._announce = Mock()

        frame.on_copy_current_item()

        frame._copy_items_to_clipboard.assert_called_once_with(selected_paths)
        frame._announce.assert_called_once_with("2 itens copiados.")

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
