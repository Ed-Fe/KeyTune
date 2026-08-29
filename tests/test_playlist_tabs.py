from __future__ import annotations

import pathlib
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.frames.library_tabs.tabs import TabManagementMixin
from player.frames.playback.controls import PlaybackControlsMixin
from player.frames.session import FrameSessionMixin
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


class PlaybackLoadingTests(unittest.TestCase):
    def test_space_during_media_loading_does_not_open_media_dialog(self):
        frame = PlaybackControlsMixin.__new__(PlaybackControlsMixin)
        frame.player = SimpleNamespace(get_media=Mock(return_value=None))
        frame._get_playlist_state = Mock(return_value=PlaylistState(title="Músicas"))
        frame._media_start_is_pending = Mock(return_value=True)
        frame._announce = Mock()
        frame.on_open = Mock()

        frame._toggle_play_pause()

        frame.on_open.assert_not_called()
        frame._announce.assert_called_once_with("A mídia ainda está carregando.")


class SessionRestoreTests(unittest.TestCase):
    def test_restore_refreshes_autodj_ui_and_discards_transient_gain(self):
        frame = FrameSessionMixin.__new__(FrameSessionMixin)
        frame.settings = SimpleNamespace(remember_window_size=False)
        frame.playlists = [PlaylistState(title="Inicial")]
        frame.notebook = Mock()
        frame.current_volume = 80
        frame.current_playback_rate = 1.0
        frame.current_pitch_semitones = 0
        frame._reset_playlist_tabs = Mock()
        frame._create_empty_playlist_tab = Mock()
        frame._apply_current_volume = Mock()
        frame._apply_current_playback_rate = Mock()
        frame._apply_equalizer_state_to_current_playback = Mock()
        frame._get_current_tab_index = Mock(return_value=0)
        frame._activate_tab = Mock()
        frame._get_playlist_state = lambda index=None: frame.playlists[0]
        frame._refresh_autodj_session_ui = Mock()
        frame._describe_playlist_position = Mock(return_value="Item 1 de 1.")
        frame._announce = Mock()
        frame._set_status_message = Mock()
        payload = {
            "selected_tab": 0,
            "playlists": [{
                "title": "AutoDJ — Músicas",
                "items": ["musica.mp3"],
                "current_index": 0,
                "current_media_path": "musica.mp3",
                "was_playing": True,
                "playback_gain_db": -4.76,
                "autodj_session": True,
            }],
        }

        with patch("player.frames.session.load_session", return_value=payload):
            self.assertTrue(frame._restore_session())

        restored = frame.playlists[0]
        self.assertEqual(restored.playback_gain_db, 0.0)
        frame._refresh_autodj_session_ui.assert_called_once_with(restored)


if __name__ == "__main__":
    unittest.main()
