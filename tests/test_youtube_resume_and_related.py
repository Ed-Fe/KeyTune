from __future__ import annotations

import pathlib
import sys
import unittest
from types import SimpleNamespace


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


URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def _video(resume_seconds, duration_seconds):
    return YouTubeMediaSearchResult(
        source="youtube",
        result_type="video",
        title="Video",
        video_id="dQw4w9WgXcQ",
        resume_seconds=resume_seconds,
        duration_seconds=duration_seconds,
    )


class HistoryResumeTests(unittest.TestCase):
    def test_a_partly_watched_video_gets_its_resume_position_and_duration(self):
        result = normalize_youtube_entry(
            {"id": "dQw4w9WgXcQ", "title": "Video", "duration_text": "43:56", "watched_percent": 10}
        )
        self.assertEqual(result.resume_seconds, 263)
        self.assertEqual(result.duration_seconds, 2636)

    def test_unwatched_or_fully_watched_videos_have_no_position(self):
        for percent in (0, 100):
            result = normalize_youtube_entry(
                {"id": "dQw4w9WgXcQ", "title": "Video", "duration": 600, "watched_percent": percent}
            )
            self.assertEqual(result.resume_seconds, 0, percent)

    def test_hint_is_used_once_per_video(self):
        frame = _Frame()
        frame._remember_youtube_resume_hint(_video(90, 1200))
        self.assertEqual(frame._take_youtube_resume_hint_ms(URL), 90000)
        self.assertEqual(frame._take_youtube_resume_hint_ms(URL), 0)

    def test_songs_and_short_videos_never_resume(self):
        # Uma música de quatro minutos ouvida pela metade no navegador recomeça do início.
        frame = _Frame()
        frame._remember_youtube_resume_hint(_video(120, 240))
        self.assertEqual(frame._take_youtube_resume_hint_ms(URL), 0)

    def test_positions_near_the_start_or_the_end_do_not_resume(self):
        for resume_seconds in (10, 590):
            frame = _Frame()
            frame._remember_youtube_resume_hint(_video(resume_seconds, 600))
            self.assertEqual(frame._take_youtube_resume_hint_ms(URL), 0, resume_seconds)

    def test_the_minimum_duration_follows_the_preferences(self):
        frame = _Frame()
        frame.settings = SimpleNamespace(
            smart_library_resume_enabled=True,
            smart_library_resume_minimum_ms=20 * 60 * 1000,
            smart_library_resume_edge_ms=30_000,
        )
        frame._remember_youtube_resume_hint(_video(300, 900))
        self.assertEqual(frame._take_youtube_resume_hint_ms(URL), 0)

        frame.settings.smart_library_resume_enabled = False
        frame._remember_youtube_resume_hint(_video(300, 3600))
        self.assertEqual(frame._take_youtube_resume_hint_ms(URL), 0)

    def test_without_the_duration_nothing_resumes(self):
        frame = _Frame()
        frame._remember_youtube_resume_hint(_video(300, 0))
        self.assertEqual(frame._take_youtube_resume_hint_ms(URL), 0)

    def test_a_video_already_played_here_ignores_an_older_list(self):
        # Ouvida até o fim no KeyTune, a barra antiga da lista não faz o vídeo voltar ao meio.
        frame = _Frame()
        frame._take_youtube_resume_hint_ms(URL)
        frame._remember_youtube_resume_hint(_video(300, 1200))
        self.assertEqual(frame._take_youtube_resume_hint_ms(URL), 0)


class RegularYouTubeMediaTests(unittest.TestCase):
    def test_only_regular_youtube_urls_count(self):
        self.assertTrue(is_regular_youtube_media("https://www.youtube.com/watch?v=dQw4w9WgXcQ"))
        self.assertTrue(is_regular_youtube_media("https://youtu.be/dQw4w9WgXcQ"))
        self.assertFalse(is_regular_youtube_media("https://music.youtube.com/watch?v=dQw4w9WgXcQ"))
        self.assertFalse(is_regular_youtube_media("ytmusic://dQw4w9WgXcQ"))
        self.assertFalse(is_regular_youtube_media(r"C:\musica\a.mp3"))


if __name__ == "__main__":
    unittest.main()
