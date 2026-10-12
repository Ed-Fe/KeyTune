from __future__ import annotations

import pathlib
import sys
import unittest


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.frames.youtube_music.resume_hints import ResumeHintsMixin
from player.youtube_music.models import YouTubeMediaSearchResult
from player.youtube_music.playlists import is_regular_youtube_media
from player.youtube_music.search import normalize_youtube_entry


class _Frame(ResumeHintsMixin):
    pass


class HistoryResumeTests(unittest.TestCase):
    def test_a_partly_watched_history_video_gets_its_resume_position(self):
        result = normalize_youtube_entry(
            {"id": "dQw4w9WgXcQ", "title": "Video", "duration_text": "43:56", "watched_percent": 10}
        )
        self.assertEqual(result.resume_seconds, 263)

    def test_barely_started_or_nearly_finished_videos_do_not_resume(self):
        for percent in (0, 2, 96, 100):
            result = normalize_youtube_entry(
                {"id": "dQw4w9WgXcQ", "title": "Video", "duration": 600, "watched_percent": percent}
            )
            self.assertEqual(result.resume_seconds, 0, percent)

    def test_hint_is_used_once_per_video(self):
        frame = _Frame()
        result = YouTubeMediaSearchResult(
            source="youtube", result_type="video", title="Video", video_id="dQw4w9WgXcQ", resume_seconds=90
        )
        frame._remember_youtube_resume_hint(result)
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        self.assertEqual(frame._take_youtube_resume_hint_ms(url), 90000)
        self.assertEqual(frame._take_youtube_resume_hint_ms(url), 0)


class RegularYouTubeMediaTests(unittest.TestCase):
    def test_only_regular_youtube_urls_count(self):
        self.assertTrue(is_regular_youtube_media("https://www.youtube.com/watch?v=dQw4w9WgXcQ"))
        self.assertTrue(is_regular_youtube_media("https://youtu.be/dQw4w9WgXcQ"))
        self.assertFalse(is_regular_youtube_media("https://music.youtube.com/watch?v=dQw4w9WgXcQ"))
        self.assertFalse(is_regular_youtube_media("ytmusic://dQw4w9WgXcQ"))
        self.assertFalse(is_regular_youtube_media(r"C:\musica\a.mp3"))


if __name__ == "__main__":
    unittest.main()
