from __future__ import annotations

import pathlib
import sys
import unittest
from unittest.mock import patch


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.youtube_music.service import YouTubeMusicService
from player.youtube_music.streams import ResolvedStreamPlayback


class YouTubeMusicServiceTests(unittest.TestCase):
    def test_cache_ttl_respects_expiring_signed_urls(self):
        service = YouTubeMusicService()
        media_path = "https://www.youtube.com/watch?v=abc123DEF45"
        resolved_playback = ResolvedStreamPlayback(
            stream_url="https://rr1---sn.example.googlevideo.com/videoplayback?expire=760&id=abc",
            http_headers={"User-Agent": "yt-test/1.0"},
        )

        with patch("player.youtube_music.service.time.time", return_value=600), patch(
            "player.youtube_music.service.time.monotonic", return_value=10
        ):
            service._cache_stream_playback(media_path, resolved_playback)

        cached_entry = service._stream_cache[media_path]
        self.assertEqual(cached_entry["expires_at"], 140)

    def test_cache_skips_urls_that_are_already_too_close_to_expiring(self):
        service = YouTubeMusicService()
        media_path = "https://www.youtube.com/watch?v=abc123DEF45"
        resolved_playback = ResolvedStreamPlayback(
            stream_url="https://rr1---sn.example.googlevideo.com/videoplayback?expire=620&id=abc",
            http_headers={"User-Agent": "yt-test/1.0"},
        )

        with patch("player.youtube_music.service.time.time", return_value=600), patch(
            "player.youtube_music.service.time.monotonic", return_value=10
        ):
            returned_playback = service._cache_stream_playback(media_path, resolved_playback)

        self.assertEqual(returned_playback.stream_url, resolved_playback.stream_url)
        self.assertNotIn(media_path, service._stream_cache)


if __name__ == "__main__":
    unittest.main()