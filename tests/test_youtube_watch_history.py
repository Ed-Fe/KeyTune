from __future__ import annotations

import pathlib
import sys
import threading
import time
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

    def test_the_watched_position_is_reported_with_the_account(self):
        with patch.object(watch_history, "optional_account_session", return_value=("SID=abc", 1)), patch.object(
            watch_history.youtubejs_runtime, "update_watch_time", return_value=True
        ) as update:
            self.assertTrue(watch_history.report_watch_position(VIDEO_URL, 93.5))
            self.assertFalse(watch_history.report_watch_position("C:/musica.mp3", 10))

        update.assert_called_once_with("SID=abc", VIDEO_URL, 93.5, account_index=1)

    def _playing_frame(self, media_path, position_ms):
        frame = YouTubeHistoryMixin()
        frame._media_paths_match = lambda first, second: first == second
        frame._player_loaded_media_path = lambda: media_path
        frame.player = Mock()
        frame.player.get_time.return_value = position_ms
        frame._prepare_youtube_music_history_tracking(media_path)
        return frame

    def test_the_position_goes_to_youtube_only_after_the_video_is_in_the_history(self):
        frame = self._playing_frame(VIDEO_URL, 40_000)
        sent = []
        frame._send_youtube_watch_time = lambda state: sent.append(state["position_ms"]) or True

        self.assertFalse(frame._maybe_report_youtube_watch_time())
        frame._youtube_music_history_tracking["reported"] = True
        self.assertTrue(frame._maybe_report_youtube_watch_time())

        self.assertEqual(sent, [40_000])

    def test_music_tracks_do_not_report_a_position(self):
        frame = self._playing_frame(MUSIC_URL, 40_000)
        frame._youtube_music_history_tracking["reported"] = True

        self.assertFalse(frame._maybe_report_youtube_watch_time())

    def test_the_position_is_sent_again_only_when_it_moved_and_once_more_when_the_video_leaves(self):
        frame = self._playing_frame(VIDEO_URL, 40_000)
        state = frame._youtube_music_history_tracking
        state["reported"] = True
        done = threading.Event()
        with patch.object(watch_history, "report_watch_position", side_effect=lambda *_args: done.set()) as report:
            self.assertTrue(frame._maybe_report_youtube_watch_time())
            self.assertTrue(done.wait(5))
            while state.get("watch_time_busy"):
                time.sleep(0.01)
            # Dentro do intervalo, ou parado no mesmo ponto, nada novo é mandado.
            self.assertFalse(frame._maybe_report_youtube_watch_time())
            self.assertFalse(frame._flush_youtube_watch_time())

            done.clear()
            frame.player.get_time.return_value = 55_000
            frame._maybe_report_youtube_watch_time()
            frame._prepare_youtube_music_history_tracking("C:/musica.mp3")
            self.assertTrue(done.wait(5))

        self.assertEqual([call.args for call in report.call_args_list], [(VIDEO_URL, 40.0), (VIDEO_URL, 55.0)])

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
