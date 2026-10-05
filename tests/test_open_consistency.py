"""Abrir, colar, recentes e a busca do YouTube Music seguem a mesma regra.

O que entra vai para a playlist atual e toca; com Shift, entra sem tocar.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

import wx


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.frames.commands.open_commands import OpenCommandsMixin
from player.frames.library_navigation import FrameLibraryNavigationMixin
from player.frames.youtube_music.search import SearchMixin
from player.playlists import PlaylistState
from player.youtube_music.panel import YouTubeMusicTabPanel


class RecentFilesTests(unittest.TestCase):
    def _frame(self, path):
        frame = OpenCommandsMixin.__new__(OpenCommandsMixin)
        frame._recent_menu_actions = {7: ("open", "recent_media_files", path)}
        frame._play_media_paths_in_current_playlist = Mock(return_value=True)
        frame._open_media_paths = Mock(return_value=True)
        frame._remove_recent_path = Mock()
        frame._announce = Mock()
        return frame

    def test_a_recent_file_plays_in_the_current_playlist(self):
        with tempfile.TemporaryDirectory() as folder:
            media_file = pathlib.Path(folder, "a.mp3")
            media_file.write_bytes(b"")
            frame = self._frame(str(media_file))

            frame.on_recent_menu_action(SimpleNamespace(GetId=lambda: 7))

        frame._play_media_paths_in_current_playlist.assert_called_once_with([str(media_file)])
        frame._open_media_paths.assert_not_called()
        frame._remove_recent_path.assert_not_called()

    def test_a_missing_recent_file_is_removed_from_the_list(self):
        missing = str(pathlib.Path(tempfile.gettempdir(), "keytune-recente-sumiu.mp3"))
        frame = self._frame(missing)

        frame.on_recent_menu_action(SimpleNamespace(GetId=lambda: 7))

        frame._play_media_paths_in_current_playlist.assert_not_called()
        frame._remove_recent_path.assert_called_once_with("recent_media_files", missing)
        frame._announce.assert_called_once_with("O item recente selecionado não está mais disponível.")


class _SearchFrame(SearchMixin, FrameLibraryNavigationMixin):
    def __init__(self, state, prepared_items):
        self.state = state
        self.prepared_items = prepared_items
        self.announcements = []
        self.active_playlist_index = None
        self._selected_youtube_music_search_results = Mock(return_value=[object()])
        self._resolve_youtube_music_player_playlist_target = Mock(return_value=state)
        self._get_youtube_music_service = Mock()
        self._prepare_youtube_music_search_results_for_playlist = Mock(
            return_value=(prepared_items, list(prepared_items), 0, 0)
        )
        self._resolve_playlist_state_index = Mock(return_value=2)
        self._add_recent_media_paths = Mock()
        self._refresh_playlist_browser = Mock()
        self._update_title = Mock()
        self._play_media = Mock()
        self._select_tab = Mock()

    def _announce(self, message):
        self.announcements.append(message)

    def _run_youtube_music_background_task(self, worker, on_success, on_error=None):
        on_success(worker())
        return True


class YouTubeMusicSearchResultsTests(unittest.TestCase):
    def _state(self):
        state = PlaylistState(title="Rádio", source_path="radio.m3u8")
        state.set_items(["https://example.com/a"], start_index=0)
        return state

    def test_enter_adds_the_selection_and_plays_it_without_leaving_the_tab(self):
        state = self._state()
        frame = _SearchFrame(state, ["https://example.com/b", "https://example.com/c"])

        frame._add_youtube_music_search_results_to_current_playlist(play=True)

        self.assertEqual(state.items, ["https://example.com/a", "https://example.com/b", "https://example.com/c"])
        self.assertEqual(state.current_media_path, "https://example.com/b")
        self.assertEqual(frame.active_playlist_index, 2)
        frame._play_media.assert_called_once_with(index=2)
        frame._select_tab.assert_not_called()

    def test_shift_enter_only_adds(self):
        state = self._state()
        frame = _SearchFrame(state, ["https://example.com/b"])

        frame._add_youtube_music_search_results_to_current_playlist()

        self.assertEqual(len(state.items), 2)
        self.assertEqual(state.current_media_path, "https://example.com/a")
        frame._play_media.assert_not_called()

    def test_enter_on_an_item_already_in_the_playlist_plays_it(self):
        state = self._state()
        state.items.append("https://example.com/b")
        state.refresh_browser_item_labels()
        frame = _SearchFrame(state, ["https://example.com/b"])

        frame._add_youtube_music_search_results_to_current_playlist(play=True)

        self.assertEqual(len(state.items), 2)
        self.assertEqual(state.current_media_path, "https://example.com/b")
        frame._play_media.assert_called_once_with(index=2)
        self.assertEqual(frame.announcements, [])


class YouTubeMusicSearchListKeysTests(unittest.TestCase):
    def _press(self, *, shift=False, control=False):
        panel = YouTubeMusicTabPanel.__new__(YouTubeMusicTabPanel)
        panel.get_selected_search_results = Mock(return_value=[object()])
        panel._can_go_back = False
        panel._has_more_results = False
        panel._on_results_back = Mock()
        panel._on_add_search_results_to_current_playlist = Mock()
        event = Mock()
        event.GetKeyCode.return_value = wx.WXK_RETURN
        event.ShiftDown.return_value = shift
        event.ControlDown.return_value = control
        event.AltDown.return_value = False

        panel._on_search_list_key_down(event)
        return panel, event

    def test_enter_plays_and_shift_enter_adds_without_playing(self):
        panel, _event = self._press()
        panel._on_add_search_results_to_current_playlist.assert_called_once_with(play=True)

        panel, _event = self._press(shift=True)
        panel._on_add_search_results_to_current_playlist.assert_called_once_with(play=False)

    def test_control_enter_is_no_longer_a_shortcut(self):
        panel, event = self._press(control=True)

        panel._on_add_search_results_to_current_playlist.assert_not_called()
        event.Skip.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
