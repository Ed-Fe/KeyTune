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


if __name__ == "__main__":
    unittest.main()