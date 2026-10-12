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

from player.frames.playback.youtube_history import YouTubeHistoryMixin
from player.frames.youtube_music.browse import BrowseMixin
from player.youtube_music import watch_history
from player.youtube_music.feedback_manager import YouTubeMusicFeedbackManager
from player.youtube_music.folders import FOLDER_HISTORY, FOLDER_WATCH_HISTORY, flat_folder_items


VIDEO_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
MUSIC_URL = "https://music.youtube.com/watch?v=dQw4w9WgXcQ"


class WatchHistoryTests(unittest.TestCase):
    def test_the_list_comes_from_the_account(self):
        entries = [{"id": "video000001", "title": "Vídeo visto", "channel": "Canal", "duration": 60}, {}]
        with patch.object(watch_history, "require_account_session", return_value=("SID=abc", 2)), patch.object(
            watch_history.youtubejs_runtime, "watch_history_page", return_value=(entries, True)
        ) as page_fn:
            page = watch_history.watch_history_page(20, 20)

        page_fn.assert_called_once_with("SID=abc", start=20, count=20, account_index=2)
        self.assertEqual([(video.result_type, video.title) for video in page.results], [("video", "Vídeo visto")])
        self.assertTrue(page.has_more)

    def test_a_watched_video_is_reported_with_the_account(self):
        with patch.object(watch_history, "optional_account_session", return_value=("SID=abc", 1)), patch.object(
            watch_history.youtubejs_runtime, "add_to_watch_history", return_value=True
        ) as add:
            self.assertTrue(watch_history.report_video_watched(VIDEO_URL))

        add.assert_called_once_with("SID=abc", VIDEO_URL, account_index=1)

    def test_without_the_account_or_a_video_nothing_is_reported(self):
        with patch.object(watch_history.youtubejs_runtime, "add_to_watch_history") as add:
            with patch.object(watch_history, "optional_account_session", return_value=("", 0)):
                self.assertFalse(watch_history.report_video_watched(VIDEO_URL))
            with patch.object(watch_history, "optional_account_session", return_value=("SID=abc", 0)):
                self.assertFalse(watch_history.report_video_watched("C:/musica.mp3"))

        add.assert_not_called()

    def test_plain_youtube_videos_go_through_youtubejs_and_music_through_ytmusicapi(self):
        manager = YouTubeMusicFeedbackManager.__new__(YouTubeMusicFeedbackManager)
        client = Mock()
        client.add_history_item.return_value = SimpleNamespace(status_code=204)
        manager._get_client = Mock(return_value=client)
        with patch.object(watch_history, "report_video_watched", return_value=True) as report:
            self.assertTrue(manager.report_playback_to_history(VIDEO_URL))
            self.assertTrue(manager.report_playback_to_history(MUSIC_URL))

        report.assert_called_once_with(VIDEO_URL)
        client.add_history_item.assert_called_once()

    def test_playback_of_a_youtube_video_is_tracked_for_the_history(self):
        frame = YouTubeHistoryMixin()

        self.assertTrue(frame._prepare_youtube_music_history_tracking(VIDEO_URL))
        self.assertEqual(frame._youtube_music_history_tracking["media_path"], VIDEO_URL)
        self.assertTrue(frame._prepare_youtube_music_history_tracking(MUSIC_URL))
        self.assertFalse(frame._prepare_youtube_music_history_tracking("C:/musica.mp3"))
        self.assertEqual(frame._youtube_music_history_tracking, {})

    def test_the_home_list_has_both_histories(self):
        folders = {folder.kind: folder for folder in flat_folder_items()}
        frame = BrowseMixin()
        frame._get_youtube_music_service = Mock()

        view = frame._build_youtube_music_folder_view(folders[FOLDER_WATCH_HISTORY])

        self.assertEqual(
            (folders[FOLDER_HISTORY].title, folders[FOLDER_WATCH_HISTORY].title),
            ("Histórico do YouTube Music", "Histórico do YouTube"),
        )
        self.assertEqual(view.title, "Histórico do YouTube")
        self.assertIs(view.fetch_page, watch_history.watch_history_page)
        self.assertTrue(folders[FOLDER_WATCH_HISTORY].requires_auth)


if __name__ == "__main__":
    unittest.main()
