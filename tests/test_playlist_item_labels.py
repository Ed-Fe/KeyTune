import pathlib
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from player.playlists import PlaylistState
from player.frames.library_tabs.item_removal import PlaylistItemRemovalMixin


class PlaylistItemLabelsTests(unittest.TestCase):
    def test_removal_keeps_names_attached_to_tracks(self):
        for online in (False, True):
            for indexes in ([0], [1], [0, 2]):
                with self.subTest(online=online, indexes=indexes):
                    paths = ([f"https://youtube.com/watch?v={i}" for i in range(4)]
                             if online else [f"track{i}.mp3" for i in range(4)])
                    labels = ["Dogs", "Fleas", "Cats", "Birds"]
                    state = PlaylistState(title="Test")
                    state.set_items_prepared(list(paths), dict(zip(paths, range(4))), labels)
                    frame = PlaylistItemRemovalMixin()
                    frame._get_playlist_state = lambda: state
                    frame._is_active_playlist_state = lambda state: False
                    frame._block_sensitive_action_during_youtube_music = lambda action: False
                    frame._media_label = lambda path: path
                    frame._refresh_playlist_browser = Mock()
                    frame._announce = Mock()
                    frame._remove_items_from_current_playlist(indexes)
                    self.assertEqual(list(zip(state.items, state.browser_item_labels)),
                                     [(p, label) for i, (p, label) in enumerate(zip(paths, labels))
                                      if i not in indexes])

    def test_reorder_preserves_custom_names_and_current_track(self):
        state = PlaylistState(title="Test")
        state.set_items_prepared(["a", "b", "c"], {"a": 0, "b": 1, "c": 2},
                                 ["Dogs", "Fleas", "Cats"])
        state.reorder_items(["c", "b", "a"])
        self.assertEqual(state.browser_item_labels, ["Cats", "Fleas", "Dogs"])
        self.assertEqual(state.current_media_path, "a")
        self.assertEqual(state.current_index, 2)

