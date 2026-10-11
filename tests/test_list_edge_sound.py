from __future__ import annotations

import pathlib
import sys
import unittest


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import wx

from player import interface_sounds
from player.library.browser import PlaylistBrowserPanel
from player.list_edge_sound import list_edge_reached, play_list_edge_sound


class ListEdgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = wx.App()
        cls.frame = wx.Frame(None)

    @classmethod
    def tearDownClass(cls):
        cls.frame.Destroy()
        cls.app.Destroy()

    def _list(self, style=0):
        return wx.ListBox(self.frame, choices=["um", "dois", "três"], style=style)

    def test_up_on_the_first_item_and_down_on_the_last_reach_the_edge(self):
        listbox = self._list()
        listbox.SetSelection(0)
        self.assertTrue(list_edge_reached(listbox, wx.WXK_UP))
        self.assertFalse(list_edge_reached(listbox, wx.WXK_DOWN))
        listbox.SetSelection(2)
        self.assertTrue(list_edge_reached(listbox, wx.WXK_DOWN))
        self.assertFalse(list_edge_reached(listbox, wx.WXK_UP))

    def test_the_middle_other_keys_and_other_controls_are_not_an_edge(self):
        listbox = self._list()
        listbox.SetSelection(1)
        self.assertFalse(list_edge_reached(listbox, wx.WXK_UP))
        listbox.SetSelection(0)
        self.assertFalse(list_edge_reached(listbox, wx.WXK_HOME))
        self.assertFalse(list_edge_reached(wx.Button(self.frame), wx.WXK_UP))
        self.assertFalse(list_edge_reached(None, wx.WXK_UP))

    def test_a_multiple_selection_list_uses_its_single_selected_item(self):
        listbox = self._list(wx.LB_EXTENDED)
        listbox.SetSelection(2)
        self.assertTrue(list_edge_reached(listbox, wx.WXK_DOWN))
        listbox.SetSelection(1)
        self.assertFalse(list_edge_reached(listbox, wx.WXK_DOWN))

    def test_in_an_empty_list_every_arrow_reaches_the_edge(self):
        empty = wx.ListBox(self.frame)
        self.assertTrue(list_edge_reached(empty, wx.WXK_DOWN))
        self.assertTrue(list_edge_reached(empty, wx.WXK_UP))
        self.assertFalse(list_edge_reached(empty, wx.WXK_HOME))

    def _key(self, key_code, modifiers=False, repeat=False):
        return SimpleNamespace(
            GetKeyCode=lambda: key_code, HasAnyModifiers=lambda: modifiers, IsAutoRepeat=lambda: repeat
        )

    def test_the_edge_sound_plays_with_the_window_preferences(self):
        self.frame.settings = SimpleNamespace(interface_sounds_enabled=True, interface_sounds_volume=50)
        empty = wx.ListBox(self.frame)
        with patch.object(interface_sounds, "play", return_value=True) as play:
            self.assertTrue(play_list_edge_sound(empty, self._key(wx.WXK_DOWN)))
            self.assertFalse(play_list_edge_sound(empty, self._key(wx.WXK_DOWN, modifiers=True)))
            self.assertFalse(play_list_edge_sound(empty, self._key(wx.WXK_SPACE)))
            self.assertFalse(play_list_edge_sound(empty, self._key(wx.WXK_DOWN, repeat=True)))

        play.assert_called_once_with(interface_sounds.SOUND_LIST_EDGE, 50, "")

    def test_the_empty_playlist_plays_it_on_any_arrow(self):
        self.frame.settings = SimpleNamespace(interface_sounds_enabled=True, interface_sounds_volume=50)
        panel = PlaylistBrowserPanel(self.frame, on_activate_item=lambda *_a: None, on_remove_item=lambda *_a: None)
        panel._show_placeholder("Playlist vazia.")
        event = MagicMock()
        event.GetKeyCode.return_value = wx.WXK_UP
        event.GetUnicodeKey.return_value = 0
        event.ControlDown.return_value = event.AltDown.return_value = event.ShiftDown.return_value = False
        event.HasAnyModifiers.return_value = False
        event.IsAutoRepeat.return_value = False
        with patch.object(interface_sounds, "play", return_value=True) as play:
            panel.on_key_down(event)

        play.assert_called_once()
        event.DoAllowNextEvent.assert_called_once()


if __name__ == "__main__":
    unittest.main()
