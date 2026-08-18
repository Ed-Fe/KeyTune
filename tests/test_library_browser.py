from __future__ import annotations

import pathlib
import sys
import unittest
from unittest.mock import Mock


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.library.browser import PlaylistBrowserPanel


class _FakeListCtrl:
    def __init__(self, *, selected=-1, focused=-1):
        self.selected = selected
        self.focused = focused
        self.focus_calls = []
        self.visible_calls = []

    def GetFirstSelected(self):
        return self.selected

    def GetFocusedItem(self):
        return self.focused

    def Select(self, selection, on=True):
        self.selected = selection if on else -1

    def Focus(self, selection):
        self.focused = selection
        self.focus_calls.append(selection)

    def EnsureVisible(self, selection):
        self.visible_calls.append(selection)

    def Refresh(self):
        self.refresh_calls = getattr(self, "refresh_calls", 0) + 1


class _FakeFolderEntry:
    def __init__(self, path, label, is_parent=False, is_directory=False):
        self.path = path
        self.label = label
        self.is_parent = is_parent
        self.is_directory = is_directory or is_parent


class PlaylistBrowserPanelTests(unittest.TestCase):
    def test_activate_selected_uses_focused_item_when_selection_is_missing(self):
        panel = PlaylistBrowserPanel.__new__(PlaylistBrowserPanel)
        panel._items = ["primeiro", "segundo"]
        panel.items_list = _FakeListCtrl(selected=-1, focused=0)
        panel._on_activate_item = Mock()

        panel._activate_selected()

        panel._on_activate_item.assert_called_once_with(0)
        self.assertEqual(panel.items_list.selected, 0)
        self.assertEqual(panel.items_list.focus_calls, [0])
        self.assertEqual(panel.items_list.visible_calls, [0])

    def test_activate_selected_prefers_focused_item_over_stale_selection(self):
        panel = PlaylistBrowserPanel.__new__(PlaylistBrowserPanel)
        panel._items = ["primeiro", "segundo"]
        panel.items_list = _FakeListCtrl(selected=0, focused=1)
        panel._on_activate_item = Mock()

        panel._activate_selected()

        panel._on_activate_item.assert_called_once_with(1)
        self.assertEqual(panel.items_list.selected, 1)
        self.assertEqual(panel.items_list.focus_calls, [1])
        self.assertEqual(panel.items_list.visible_calls, [1])


class PlaylistBrowserLibraryMarksTests(unittest.TestCase):
    def _playlist_panel(self):
        panel = PlaylistBrowserPanel.__new__(PlaylistBrowserPanel)
        panel._mode = "playlist"
        panel._has_placeholder = False
        panel._items = ["C:\\Musica\\Estrada.mp3", "C:\\Musica\\Cancao.mp3"]
        panel._base_labels = ["Estrada", "Canção"]
        panel._playlist_current_index = 0
        panel._library_marks = {}
        panel.items_list = _FakeListCtrl()
        return panel

    def test_items_render_without_marks_by_default(self):
        panel = self._playlist_panel()

        self.assertEqual(panel._get_display_label(1), "   2. Canção")

    def test_marks_are_appended_to_the_display_label(self):
        panel = self._playlist_panel()

        panel.set_library_marks({"C:\\Musica\\Estrada.mp3": "favorito, 5 estrelas"})

        self.assertEqual(panel._get_display_label(0), "▶ 1. Estrada — favorito, 5 estrelas")
        self.assertEqual(panel._get_display_label(1), "   2. Canção")

    def test_marks_do_not_leak_into_the_search_label(self):
        panel = self._playlist_panel()
        panel.set_library_marks({"C:\\Musica\\Estrada.mp3": "favorito"})

        self.assertEqual(panel._item_search_label(0), "Estrada")

    def test_setting_the_same_marks_again_skips_the_repaint(self):
        panel = self._playlist_panel()
        marks = {"C:\\Musica\\Estrada.mp3": "favorito"}

        self.assertTrue(panel.set_library_marks(marks))
        self.assertFalse(panel.set_library_marks(dict(marks)))
        self.assertEqual(panel.items_list.refresh_calls, 1)

    def test_clearing_marks_restores_the_plain_label(self):
        panel = self._playlist_panel()
        panel.set_library_marks({"C:\\Musica\\Estrada.mp3": "favorito"})

        panel.set_library_marks({})

        self.assertEqual(panel._get_display_label(0), "▶ 1. Estrada")

    def test_folder_files_show_marks_but_directories_do_not(self):
        panel = PlaylistBrowserPanel.__new__(PlaylistBrowserPanel)
        panel._mode = "folder"
        panel._has_placeholder = False
        panel._library_marks = {"C:\\Musica\\Estrada.mp3": "favorito"}
        panel.items_list = _FakeListCtrl()
        panel._items = [
            _FakeFolderEntry("C:\\", "[..] Pasta acima", is_parent=True),
            _FakeFolderEntry("C:\\Musica\\Rock", "Rock", is_directory=True),
            _FakeFolderEntry("C:\\Musica\\Estrada.mp3", "Estrada.mp3"),
        ]
        panel._current_folder_media_path = lambda: None

        self.assertEqual(panel._get_display_label(0), "[..] Pasta acima")
        self.assertEqual(panel._get_display_label(1), "Rock")
        self.assertEqual(panel._get_display_label(2), "Estrada.mp3 — favorito")


if __name__ == "__main__":
    unittest.main()
