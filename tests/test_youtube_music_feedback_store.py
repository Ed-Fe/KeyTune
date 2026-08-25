from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.youtube_music.feedback_manager import YouTubeMusicFeedbackManager
from player.youtube_music.feedback_store import YouTubeMusicFeedbackStore
from player.frames.library_tabs.playback_control import PlaylistPlaybackMixin
from player.playlists import PlaylistState


class YouTubeMusicFeedbackStoreTests(unittest.TestCase):
    def test_dislike_survives_store_recreation_for_the_same_account(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = pathlib.Path(temp_dir) / "feedback.json"
            store = YouTubeMusicFeedbackStore(path)
            store.set_active_account({"channelHandle": "@ouvinte", "accountName": "Ouvinte"})
            store.record("abc123DEF45", "DISLIKE")

            restored = YouTubeMusicFeedbackStore(path)

            self.assertTrue(restored.is_disliked("abc123DEF45"))

    def test_feedback_is_scoped_by_account(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = YouTubeMusicFeedbackStore(pathlib.Path(temp_dir) / "feedback.json")
            store.set_active_account({"channelHandle": "@primeira"})
            store.record("abc123DEF45", "DISLIKE")
            store.set_active_account({"channelHandle": "@segunda"})

            self.assertFalse(store.is_disliked("abc123DEF45"))

            store.set_active_account({"channelHandle": "@primeira"})
            self.assertTrue(store.is_disliked("abc123DEF45"))

    def test_channel_handle_keeps_feedback_when_the_display_name_changes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = YouTubeMusicFeedbackStore(pathlib.Path(temp_dir) / "feedback.json")
            store.set_active_account({"channelHandle": "@ouvinte", "accountName": "Nome antigo"})
            store.record("abc123DEF45", "DISLIKE")

            store.set_active_account({"channelHandle": "@ouvinte", "accountName": "Nome novo"})

            self.assertTrue(store.is_disliked("abc123DEF45"))

    def test_bulk_sync_ignores_ambiguous_indifferent_but_accepts_like(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = YouTubeMusicFeedbackStore(pathlib.Path(temp_dir) / "feedback.json")
            store.set_active_account({"channelHandle": "@ouvinte"})
            store.record("disliked", "DISLIKE")

            store.ingest_items([{"videoId": "disliked", "likeStatus": "INDIFFERENT"}])
            self.assertTrue(store.is_disliked("disliked"))

            store.ingest_items([{"videoId": "disliked", "likeStatus": "LIKE"}])
            self.assertFalse(store.is_disliked("disliked"))


class YouTubeMusicFeedbackSyncTests(unittest.TestCase):
    def test_account_sync_imports_dislikes_created_outside_keytune(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = pathlib.Path(temp_dir) / "feedback.json"
            client = Mock()
            client.get_account_info.return_value = {
                "channelHandle": "@ouvinte",
                "accountName": "Ouvinte",
            }
            client.get_history.return_value = [
                {"videoId": "mob123DEF45", "likeStatus": "DISLIKE"},
                {"videoId": "neutral", "likeStatus": "INDIFFERENT"},
            ]
            client.get_liked_songs.return_value = {
                "tracks": [{"videoId": "liked", "likeStatus": "LIKE"}]
            }
            manager = YouTubeMusicFeedbackManager(
                get_client_fn=lambda require_auth=True: client,
                import_module_fn=lambda: SimpleNamespace(),
                feedback_store=YouTubeMusicFeedbackStore(path),
            )

            observed_count = manager.sync_account_feedback(force=True)

            self.assertEqual(observed_count, 3)
            self.assertTrue(manager.is_media_disliked("https://music.youtube.com/watch?v=mob123DEF45"))
            restored = YouTubeMusicFeedbackStore(path)
            self.assertTrue(restored.is_disliked("mob123DEF45"))

    def test_remote_rating_updates_the_persistent_account_cache(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = pathlib.Path(temp_dir) / "feedback.json"
            client = Mock()
            client.get_account_info.return_value = {"channelHandle": "@ouvinte"}
            manager = YouTubeMusicFeedbackManager(
                get_client_fn=lambda require_auth=True: client,
                import_module_fn=lambda: SimpleNamespace(
                    LikeStatus=SimpleNamespace(LIKE="LIKE", DISLIKE="DISLIKE", INDIFFERENT="INDIFFERENT")
                ),
                feedback_store=YouTubeMusicFeedbackStore(path),
            )

            manager.rate_media_feedback("https://music.youtube.com/watch?v=abc123DEF45", "DISLIKE")

            client.rate_song.assert_called_once_with("abc123DEF45", "DISLIKE")
            self.assertTrue(YouTubeMusicFeedbackStore(path).is_disliked("abc123DEF45"))


class YouTubeMusicDislikedPlaybackTests(unittest.TestCase):
    def test_playback_order_advances_past_persistently_disliked_tracks(self):
        frame = PlaylistPlaybackMixin.__new__(PlaylistPlaybackMixin)
        state = PlaylistState(title="Rádio")
        state.set_items(
            [
                "https://music.youtube.com/watch?v=dislikedOne",
                "https://music.youtube.com/watch?v=dislikedTwo",
                "https://music.youtube.com/watch?v=allowedTrack",
            ]
        )
        frame._youtube_music_media_is_disliked = lambda path: "disliked" in path

        selected = frame._select_next_allowed_youtube_music_media(state)

        self.assertTrue(selected)
        self.assertEqual(state.current_media_path, "https://music.youtube.com/watch?v=allowedTrack")


if __name__ == "__main__":
    unittest.main()
