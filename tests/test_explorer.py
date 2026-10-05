from __future__ import annotations

import os
import pathlib
import sys
import tempfile
import unittest

import wx
from unittest.mock import Mock, patch


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.frames.commands.app_commands import AppCommandsMixin
from player.frames.explorer import FrameExplorerMixin
from player.frames.library_navigation import FrameLibraryNavigationMixin
from player.frames.session import FrameSessionMixin
from player.library.explorer import (
    EXPLORER_ROOT,
    ExplorerState,
    collect_media_paths,
    explorer_parent_path,
    list_explorer_root,
    scan_explorer_folder,
)
from player.library.models import FOLDER_ENTRY_DIRECTORY, FOLDER_ENTRY_FILE, FolderBrowserEntry
from player.playlists import PlaylistState


def _run_inline(_owner, work, on_done):
    on_done(work())


class ExplorerFolderTests(unittest.TestCase):
    def test_collect_media_paths_walks_subfolders_in_name_order_without_duplicates(self):
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            (root / "B").mkdir()
            (root / "a").mkdir()
            files = [root / "a" / "2.mp3", root / "B" / "1.flac", root / "z.mp4"]
            for media_file in (*files, root / "notas.txt"):
                media_file.write_bytes(b"")

            collected = collect_media_paths([folder, str(root / "z.mp4"), str(root / "notas.txt"), ""])

        self.assertEqual(collected, [str(root / "z.mp4"), str(root / "a" / "2.mp3"), str(root / "B" / "1.flac")])

    def test_scan_keeps_a_way_back_to_the_parent(self):
        with tempfile.TemporaryDirectory() as folder:
            pathlib.Path(folder, "Sub").mkdir()
            pathlib.Path(folder, "faixa.mp3").write_bytes(b"")

            entries = scan_explorer_folder(folder)

        self.assertTrue(entries[0].is_parent)
        self.assertEqual([entry.label for entry in entries[1:]], ["Sub", "faixa.mp3"])

    def test_root_lists_each_folder_and_drive_once(self):
        entries = list_explorer_root()

        self.assertTrue(entries)
        self.assertTrue(all(entry.is_directory and not entry.is_parent for entry in entries))
        keys = [os.path.normcase(os.path.normpath(entry.path)) for entry in entries]
        self.assertEqual(len(keys), len(set(keys)))

    def test_parent_of_a_drive_root_is_the_explorer_root(self):
        drive_root = os.path.abspath(os.sep)

        self.assertEqual(explorer_parent_path(drive_root), EXPLORER_ROOT)
        self.assertIsNone(explorer_parent_path(EXPLORER_ROOT))

    def test_state_restore_does_not_touch_the_disk_and_discards_unknown_sort(self):
        state = ExplorerState()

        with patch("os.path.isdir") as isdir:
            visible = state.restore({"visible": True, "path": r"Z:\não\existe", "sort_by": "cor"})

        isdir.assert_not_called()
        self.assertTrue(visible)
        self.assertEqual(state.current_path, r"Z:\não\existe")
        self.assertEqual(state.sort_by, "name")
        self.assertFalse(ExplorerState().restore(None))

    def test_scanning_a_missing_folder_raises(self):
        with self.assertRaises(FileNotFoundError):
            scan_explorer_folder(os.path.join(tempfile.gettempdir(), "keytune-não-existe"))


class _ExplorerFrame(FrameExplorerMixin):
    def __init__(self):
        self._explorer_state = ExplorerState()
        self.explorer_panel = Mock()
        self.explorer_panel.IsShown.return_value = True
        self.announcements = []

    def __bool__(self):
        return True

    def _announce(self, message):
        self.announcements.append(message)

    def _normalize_path(self, path):
        return str(path)


@patch("player.frames.explorer.run_in_background", _run_inline)
class ExplorerWindowTests(unittest.TestCase):
    def test_entering_a_folder_announces_nothing(self):
        frame = _ExplorerFrame()
        with tempfile.TemporaryDirectory() as folder:
            pathlib.Path(folder, "a.mp3").write_bytes(b"")

            frame._explorer_navigate(folder)

        self.assertEqual(frame._explorer_state.current_path, folder)
        self.assertEqual([entry.label for entry in frame._explorer_state.entries if entry.is_file], ["a.mp3"])
        self.assertEqual(frame.announcements, [])

    def test_a_missing_folder_goes_back_to_where_the_explorer_was(self):
        frame = _ExplorerFrame()
        with tempfile.TemporaryDirectory() as folder:
            frame._explorer_navigate(folder)

            frame._explorer_navigate(os.path.join(folder, "sumiu"))

            self.assertEqual(frame._explorer_state.current_path, folder)
        self.assertEqual(frame.announcements, ["A pasta não está mais disponível."])
        self.assertFalse(frame._explorer_state.is_loading)

    def test_a_missing_saved_folder_falls_back_to_the_root_quietly(self):
        frame = _ExplorerFrame()
        frame.explorer_panel.IsShown.return_value = False
        frame.explorer_panel.is_item_navigation_active.return_value = False
        missing = os.path.join(tempfile.gettempdir(), "keytune-não-existe")

        with patch("player.frames.explorer.scan_explorer_folder", side_effect=lambda path, **_k: (_ for _ in ()).throw(FileNotFoundError(path)) if path else []):
            frame._restore_explorer_session({"visible": True, "path": missing})

        self.assertEqual(frame._explorer_state.current_path, EXPLORER_ROOT)
        self.assertEqual(frame.announcements, [])

    def _frame_with_entries(self):
        frame = _ExplorerFrame()
        frame._explorer_state.current_path = r"C:\Músicas"
        frame._explorer_state.set_entries([
            FolderBrowserEntry(path=r"C:\Músicas\Álbum", label="Álbum", entry_type=FOLDER_ENTRY_DIRECTORY),
            FolderBrowserEntry(path=r"C:\Músicas\a.mp3", label="a.mp3", entry_type=FOLDER_ENTRY_FILE),
        ])
        return frame

    def test_selected_files_are_delivered_without_touching_the_disk(self):
        frame = self._frame_with_entries()
        action = Mock()

        with patch("player.frames.explorer.collect_media_paths") as collect, patch("os.path.isdir") as isdir:
            frame._explorer_with_media([r"C:\Músicas\a.mp3"], action)

        collect.assert_not_called()
        isdir.assert_not_called()
        action.assert_called_once_with([r"C:\Músicas\a.mp3"])
        self.assertEqual(frame.announcements, [])

    def test_selected_folders_are_read_in_the_background(self):
        frame = self._frame_with_entries()
        action = Mock()

        with patch("player.frames.explorer.collect_media_paths", return_value=["x.mp3"]) as collect:
            frame._explorer_with_media([r"C:\Músicas\Álbum"], action)

        collect.assert_called_once_with([r"C:\Músicas\Álbum"])
        action.assert_called_once_with(["x.mp3"])
        self.assertEqual(frame.announcements, ["Lendo as pastas selecionadas..."])

    def _key_event(self, key_code, *, shift=False, control=False):
        event = Mock()
        event.GetKeyCode.return_value = key_code
        event.ShiftDown.return_value = shift
        event.ControlDown.return_value = control
        event.AltDown.return_value = False
        event.HasAnyModifiers.return_value = shift or control
        return event

    def test_shift_enter_adds_the_selection_without_playing(self):
        frame = self._frame_with_entries()
        frame.explorer_panel.get_selected_item_paths.return_value = [r"C:\Músicas\a.mp3"]
        frame._add_media_paths_without_playing = Mock()
        event = self._key_event(wx.WXK_RETURN, shift=True)

        frame._on_explorer_list_char_hook(event)

        frame._add_media_paths_without_playing.assert_called_once_with([r"C:\Músicas\a.mp3"], verified=True)
        event.Skip.assert_not_called()

    def test_plain_enter_is_left_to_the_list(self):
        frame = self._frame_with_entries()
        frame._add_media_paths_without_playing = Mock()
        event = self._key_event(wx.WXK_RETURN)

        frame._on_explorer_list_char_hook(event)

        frame._add_media_paths_without_playing.assert_not_called()
        event.Skip.assert_called_once_with()

    def test_control_enter_is_no_longer_an_explorer_shortcut(self):
        frame = self._frame_with_entries()
        frame.explorer_panel.get_selected_item_paths.return_value = [r"C:\Músicas\a.mp3"]

        self.assertFalse(frame._handle_explorer_key_down(self._key_event(wx.WXK_RETURN, control=True)))

    def test_a_whole_drive_is_refused(self):
        frame = _ExplorerFrame()
        drive_root = os.path.abspath(os.sep)
        frame._explorer_state.set_entries([
            FolderBrowserEntry(path=drive_root, label=drive_root, entry_type=FOLDER_ENTRY_DIRECTORY),
        ])
        action = Mock()

        with patch("player.frames.explorer.collect_media_paths") as collect:
            frame._explorer_with_media([drive_root], action)

        collect.assert_not_called()
        action.assert_not_called()
        self.assertEqual(len(frame.announcements), 1)


class _NavigationFrame(FrameLibraryNavigationMixin):
    def __init__(self, state):
        self.state = state
        self.announcements = []
        self._refresh_playlist_browser = Mock()
        self._play_media = Mock()
        self._remember_directory = Mock()
        self._add_recent_media_paths = Mock()
        self._resolve_playlist_state_index = Mock(return_value=0)

    def _announce(self, message):
        self.announcements.append(message)

    def _normalize_path(self, path):
        return str(path)

    def _playlist_state_for_external_media(self):
        return self.state

    def _get_playlist_state(self, index=None):
        return self.state

    def _is_current_playlist_state(self, state):
        return state is self.state


class AddWithoutPlayingTests(unittest.TestCase):
    def test_appends_to_the_playlist_and_leaves_the_current_track_alone(self):
        # Uma playlist salva mantém o próprio título quando recebe itens.
        state = PlaylistState(title="Rádio", source_path="radio.m3u8")
        state.set_items(["https://example.com/a.mp3"], start_index=0)
        frame = _NavigationFrame(state)

        added = frame._add_media_paths_without_playing(["https://example.com/b.mp3", "https://example.com/c.mp3"])

        self.assertTrue(added)
        self.assertEqual(len(state.items), 3)
        self.assertEqual(state.current_media_path, "https://example.com/a.mp3")
        self.assertEqual(state.peek_in_playback_order(1), "https://example.com/b.mp3")
        frame._play_media.assert_not_called()
        self.assertEqual(frame.announcements, ["2 itens adicionados a Rádio, sem tocar."])

    def test_verified_paths_are_appended_without_consulting_the_disk(self):
        state = PlaylistState(title="Rádio", source_path="radio.m3u8")
        state.set_items(["https://example.com/a.mp3"], start_index=0)
        frame = _NavigationFrame(state)

        with patch("os.path.isfile") as isfile:
            added = frame._add_media_paths_without_playing([r"Z:\rede\b.mp3"], verified=True)

        isfile.assert_not_called()
        self.assertTrue(added)
        self.assertEqual(state.items[-1], r"Z:\rede\b.mp3")

    def test_unverified_missing_files_are_still_left_out(self):
        state = PlaylistState(title="Rádio", source_path="radio.m3u8")
        state.set_items(["https://example.com/a.mp3"], start_index=0)
        frame = _NavigationFrame(state)

        self.assertFalse(frame._add_media_paths_without_playing([os.path.join(tempfile.gettempdir(), "keytune-sumiu.mp3")]))
        self.assertEqual(len(state.items), 1)

    def test_repeated_items_are_reported_instead_of_duplicated(self):
        state = PlaylistState(title="Rádio", source_path="radio.m3u8")
        state.set_items(["https://example.com/a.mp3"], start_index=0)
        frame = _NavigationFrame(state)

        self.assertFalse(frame._add_media_paths_without_playing(["https://example.com/a.mp3"]))
        self.assertEqual(len(state.items), 1)
        self.assertEqual(frame.announcements, ["Os itens já estavam em Rádio."])


class EnqueuePathsTests(unittest.TestCase):
    def test_new_files_join_the_playlist_and_the_queue_without_toggling(self):
        state = PlaylistState(title="Rádio")
        state.set_items(["a.mp3", "b.mp3"], start_index=0)
        state.enqueue_item("b.mp3")
        frame = AppCommandsMixin.__new__(AppCommandsMixin)
        frame._get_active_playlist_state = Mock(return_value=state)
        frame._is_current_playlist_state = Mock(return_value=True)
        frame._refresh_playlist_browser = Mock()
        frame._queue_entry_label = lambda _state, path: path
        frame._announce = Mock()

        self.assertTrue(frame._enqueue_media_paths(["b.mp3", "c.mp3"]))

        self.assertEqual(state.custom_queue, ["b.mp3", "c.mp3"])
        self.assertEqual(state.items, ["a.mp3", "b.mp3", "c.mp3"])
        frame._announce.assert_called_once_with("c.mp3 adicionado à fila de reprodução.")


class LegacyFolderTabSessionTests(unittest.TestCase):
    def test_folder_tabs_from_old_sessions_move_to_the_explorer(self):
        frame = FrameSessionMixin.__new__(FrameSessionMixin)
        frame.playlists = [PlaylistState(title="Playlist 1")]
        frame.notebook = Mock()
        frame.settings = Mock(remember_window_size=False)
        frame._reset_playlist_tabs = Mock()
        frame._create_empty_playlist_tab = Mock()
        frame._apply_current_volume = Mock()
        frame._apply_current_playback_rate = Mock()
        frame._apply_equalizer_state_to_current_playback = Mock()
        frame._get_current_tab_index = Mock(return_value=0)
        frame._activate_tab = Mock()
        frame._resume_playlist_tab = Mock()
        frame._select_tab = Mock()
        frame._get_playlist_state = Mock(return_value=None)
        frame._announce = Mock()
        frame._restore_explorer_session = Mock()
        payload = {
            "selected_tab": 1,
            "playlists": [
                {"title": "Músicas", "tab_type": "folder", "folder_current_path": r"C:\Músicas"},
                {"title": "Rádio", "items": ["a.mp3"]},
            ],
        }

        with patch("player.frames.session.load_session", return_value=payload):
            self.assertTrue(frame._restore_session())

        self.assertEqual([state.title for state in frame.playlists], ["Rádio"])
        frame._restore_explorer_session.assert_called_once_with(None, fallback_folder=r"C:\Músicas")
        frame._activate_tab.assert_called_once_with(0, announce=False)


if __name__ == "__main__":
    unittest.main()
