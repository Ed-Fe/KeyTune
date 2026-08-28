from __future__ import annotations

import pathlib
import sys
import unittest
from unittest.mock import Mock


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.frames.library_tabs.tabs import TabManagementMixin
from player.playlists import PlaylistState, build_playlist_title, is_youtube_watch_reference


class PreparedPlaylistTests(unittest.TestCase):
    def test_selects_empty_tab_before_preparing_autoplay_item(self):
        frame = TabManagementMixin.__new__(TabManagementMixin)
        state = PlaylistState(title="Playlist vazia")
        frame.notebook = Mock()
        frame._resolve_target_playlist_tab = Mock(return_value=(state, 2))
        frame._refresh_playlist_browser = Mock()
        frame._play_media = Mock()

        def assert_empty_during_selection(_index, *, announce):
            self.assertFalse(announce)
            self.assertEqual(state.items, [])
            self.assertIsNone(state.current_media_path)

        frame._select_tab = Mock(side_effect=assert_empty_during_selection)

        result = frame._open_prepared_media_playlist(
            ["https://music.youtube.com/watch?v=track1"],
            "Minha playlist",
            browser_item_labels=["Primeira faixa"],
            announce_message="Playlist carregada.",
        )

        self.assertEqual(result, 2)
        self.assertEqual(state.current_media_path, "https://music.youtube.com/watch?v=track1")
        frame._play_media.assert_called_once_with(
            media_path="https://music.youtube.com/watch?v=track1",
            index=2,
            announce_message="Playlist carregada.",
        )


class PlaylistTitleTests(unittest.TestCase):
    def test_youtube_watch_url_uses_generic_playlist_title(self):
        media_path = "https://music.youtube.com/watch?v=abc123DEF45"

        self.assertTrue(is_youtube_watch_reference(media_path))
        self.assertEqual(build_playlist_title([media_path]), "Seleção do YouTube Music")

    def test_local_file_with_youtube_text_keeps_its_file_name(self):
        media_path = r"C:\Músicas\youtube.com tutorial.mp3"

        self.assertFalse(is_youtube_watch_reference(media_path))
        self.assertEqual(build_playlist_title([media_path]), "youtube.com tutorial")


if __name__ == "__main__":
    unittest.main()
