from __future__ import annotations

import pathlib
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.frames.commands.open_commands import OpenCommandsMixin  # noqa: E402
from player.frames.explorer import FrameExplorerMixin  # noqa: E402
from player.frames.library_navigation import FrameLibraryNavigationMixin  # noqa: E402
from player.frames.library_tabs.item_removal import PlaylistItemRemovalMixin  # noqa: E402
from player.constants import REPEAT_ALL, REPEAT_OFF  # noqa: E402
from player.library.explorer import ExplorerState  # noqa: E402
from player.playlists import PlaylistState  # noqa: E402
from player.preferences.models import AppSettings  # noqa: E402


class _Frame(FrameExplorerMixin, OpenCommandsMixin, FrameLibraryNavigationMixin):
    def __init__(self, playlists, *, alone=True):
        self.playlists = list(playlists)
        self.selected = self.playlists[0]
        self.settings = SimpleNamespace(play_opened_files_alone=alone)
        self._explorer_state = ExplorerState()
        self.notebook = Mock()
        self.announcements = []
        self._refresh_playlist_browser = Mock()
        self._play_media = Mock()
        self._select_tab = Mock()
        self._remember_directory = Mock()
        self._add_recent_media_paths = Mock()
        self._play_media_paths_in_current_playlist = Mock(return_value=True)
        self._open_external_media_paths = Mock(return_value=True)

    def _block_sensitive_action_during_youtube_music(self, *_args, **_kwargs):
        return False

    def _explorer_path_is_folder(self, path):
        return False

    def _announce(self, message, category=None):
        self.announcements.append(message)

    def _normalize_path(self, path):
        return str(path)

    def _resolve_playlist_state_index(self, state):
        return self.playlists.index(state)

    def _get_playlist_state(self, index=None):
        return self.playlists[index]

    def _is_current_playlist_state(self, state):
        return state is self.selected

    def _create_empty_playlist_tab(self, select=False):
        self.playlists.append(PlaylistState(title="Playlist nova"))
        return len(self.playlists) - 1


class ExplorerPlayAloneTests(unittest.TestCase):
    def test_enter_plays_in_its_own_tab_and_leaves_the_playlist_alone(self):
        playlist = PlaylistState(title="Minhas músicas")
        playlist.set_items(["https://example.com/a.mp3", "https://example.com/b.mp3"])
        frame = _Frame([playlist])

        frame._explorer_play_paths(["https://example.com/c.mp3"])

        self.assertEqual(playlist.items, ["https://example.com/a.mp3", "https://example.com/b.mp3"])
        alone = frame.playlists[1]
        self.assertTrue(alone.standalone_tab)
        self.assertEqual(alone.items, ["https://example.com/c.mp3"])
        self.assertEqual(alone.title, "Fora da playlist")
        frame._play_media.assert_called_once_with(index=1)
        # A aba à vista e o foco no explorador ficam onde estavam.
        frame._select_tab.assert_not_called()
        frame._play_media_paths_in_current_playlist.assert_not_called()

    def test_next_enter_replaces_the_tab_instead_of_piling_up(self):
        frame = _Frame([PlaylistState(title="Minhas músicas")])
        frame._explorer_play_paths(["https://example.com/c.mp3"])
        frame._explorer_play_paths(["https://example.com/a.mp3"])

        self.assertEqual(len(frame.playlists), 2)
        self.assertEqual(frame.playlists[1].items, ["https://example.com/a.mp3"])

    def test_editing_the_tab_turns_it_into_a_normal_playlist(self):
        frame = _Frame([PlaylistState(title="Minhas músicas")])
        frame._explorer_play_paths(["https://example.com/c.mp3"])
        alone = frame.playlists[1]

        alone.append_items(["https://example.com/x.mp3"])
        self.assertFalse(alone.standalone_tab)

        frame._explorer_play_paths(["https://example.com/d.mp3"])
        self.assertEqual(alone.items, ["https://example.com/c.mp3", "https://example.com/x.mp3"])
        self.assertEqual(frame.playlists[2].items, ["https://example.com/d.mp3"])

    def test_option_off_keeps_adding_to_the_current_playlist(self):
        frame = _Frame([PlaylistState(title="Minhas músicas")], alone=False)

        frame._explorer_play_paths(["https://example.com/c.mp3"])

        frame._play_media_paths_in_current_playlist.assert_called_once_with(["https://example.com/c.mp3"])
        self.assertEqual(len(frame.playlists), 1)

    def test_windows_open_uses_the_same_tab_as_the_explorer(self):
        frame = _Frame([PlaylistState(title="Minhas músicas")])
        frame._explorer_play_paths(["https://example.com/c.mp3"])

        self.assertTrue(frame._open_split_external_files(["https://example.com/w.mp3"], []))

        self.assertEqual(len(frame.playlists), 2)
        self.assertEqual(frame.playlists[1].items, ["https://example.com/w.mp3"])
        frame._open_external_media_paths.assert_not_called()

    def test_windows_open_with_option_off_appends_as_before(self):
        frame = _Frame([PlaylistState(title="Minhas músicas")], alone=False)

        frame._open_split_external_files(["https://example.com/w.mp3"], [])

        frame._open_external_media_paths.assert_called_once_with(["https://example.com/w.mp3"], verified=True)

    def test_tab_plays_once_whatever_the_new_playlist_defaults_are(self):
        frame = _Frame([PlaylistState(title="Minhas músicas")])
        original = frame._create_empty_playlist_tab

        def create(select=False):
            index = original(select)
            frame.playlists[index].repeat_mode = REPEAT_ALL
            frame.playlists[index].shuffle_enabled = True
            return index

        frame._create_empty_playlist_tab = create
        frame._explorer_play_paths(["https://example.com/c.mp3"])

        self.assertEqual(frame.playlists[1].repeat_mode, REPEAT_OFF)
        self.assertFalse(frame.playlists[1].shuffle_enabled)

    def test_video_with_video_output_on_keeps_the_old_path(self):
        frame = _Frame([PlaylistState(title="Minhas músicas")])
        frame.settings.disable_video_output = False

        frame._explorer_play_paths([r"C:ilmes.mp4"])

        frame._play_media_paths_in_current_playlist.assert_called_once_with([r"C:ilmes.mp4"])
        self.assertEqual(len(frame.playlists), 1)

    def test_video_with_video_output_off_plays_alone(self):
        frame = _Frame([PlaylistState(title="Minhas músicas")])
        frame.settings.disable_video_output = True

        frame._explorer_play_paths([r"C:ilmes.mp4"])

        self.assertTrue(frame.playlists[1].standalone_tab)

    def test_tab_marker_survives_the_session(self):
        state = PlaylistState(title="Fora da playlist")
        state.set_items(["https://example.com/c.mp3"])
        state.standalone_tab = True
        self.assertTrue(PlaylistState.from_dict(state.to_dict()).standalone_tab)

    def test_setting_defaults_on_and_round_trips(self):
        settings = AppSettings()
        self.assertTrue(settings.play_opened_files_alone)
        settings.play_opened_files_alone = False
        self.assertFalse(AppSettings.from_dict(settings.to_dict()).play_opened_files_alone)



class _CloseHost(PlaylistItemRemovalMixin):
    def __init__(self, visible, active):
        self.visible = visible
        self.active = active
        self.announcements = []
        self._unload_player = Mock()
        self._update_title = Mock()
        self._refresh_playlist_browser = Mock()
        self._remove_item_from_current_playlist = Mock()

    def _get_tab_state(self, index=None):
        return self.visible

    def _get_playlist_state(self, index=None):
        return self.visible

    def _get_active_playlist_state(self):
        return self.active

    def _block_sensitive_action_during_youtube_music(self, *_args, **_kwargs):
        return False

    def _announce(self, message, category=None):
        self.announcements.append(message)


class CloseMediaTests(unittest.TestCase):
    def test_close_media_stops_the_standalone_file_and_leaves_the_visible_playlist(self):
        visible = PlaylistState(title="Minhas músicas")
        visible.set_items(["https://example.com/a.mp3", "https://example.com/b.mp3"])
        alone = PlaylistState(title="Fora da playlist")
        alone.set_items(["https://example.com/c.mp3"])
        alone.standalone_tab = True
        host = _CloseHost(visible, alone)

        host._close_current_media()

        host._remove_item_from_current_playlist.assert_not_called()
        host._unload_player.assert_called_once()
        self.assertEqual(visible.items, ["https://example.com/a.mp3", "https://example.com/b.mp3"])
        self.assertEqual(alone.items, [])
        self.assertTrue(alone.standalone_tab)

    def test_close_media_on_a_normal_playlist_is_unchanged(self):
        visible = PlaylistState(title="Minhas músicas")
        visible.set_items(["https://example.com/a.mp3"])
        host = _CloseHost(visible, visible)

        host._close_current_media()

        host._remove_item_from_current_playlist.assert_called_once()


if __name__ == "__main__":
    unittest.main()
