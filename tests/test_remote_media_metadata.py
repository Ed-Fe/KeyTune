from __future__ import annotations

import pathlib
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.remote_media_metadata import resolve_remote_media_metadata, resolve_remote_media_playback


def _response(data):
    return SimpleNamespace(data=data, stdout_text="", stderr_text="")


class RemoteMediaMetadataTests(unittest.TestCase):
    def test_resolve_remote_media_metadata_uses_ytdlp_for_supported_remote_page(self):
        with patch("player.remote_media_metadata.ensure_yt_dlp_executable_available"):
            with patch(
                "player.remote_media_metadata.extract_yt_dlp_info",
                return_value=_response(
                    {
                        "title": "Video de teste",
                        "uploader": "Canal de teste",
                        "formats": [
                            {
                                "url": "https://cdn.example.invalid/video.mp4",
                                "acodec": "aac",
                                "vcodec": "avc1",
                                "protocol": "https",
                                "ext": "mp4",
                                "http_headers": {"Referer": "https://example.com/", "X-Ignore": "nope"},
                            }
                        ],
                        "http_headers": {"User-Agent": "yt-test/1.0"},
                    }
                ),
            ):
                metadata = resolve_remote_media_metadata("https://example.com/watch?v=123")

        self.assertEqual(metadata.title, "Video de teste")
        self.assertEqual(metadata.artist, "Canal de teste")

    def test_resolve_remote_media_metadata_skips_youtube_urls(self):
        with patch("player.remote_media_metadata.ensure_yt_dlp_executable_available") as ensure_mock:
            metadata = resolve_remote_media_metadata("https://www.youtube.com/watch?v=abc123DEF45")

        self.assertEqual(metadata.title, "")
        self.assertEqual(metadata.artist, "")
        ensure_mock.assert_not_called()

    def test_resolve_remote_media_playback_uses_best_stream_and_allowed_headers(self):
        with patch("player.remote_media_metadata.ensure_yt_dlp_executable_available"):
            with patch(
                "player.remote_media_metadata.extract_yt_dlp_info",
                return_value=_response(
                    {
                        "title": "Video de teste",
                        "uploader": "Canal de teste",
                        "formats": [
                            {
                                "url": "https://cdn.example.invalid/video.mp4",
                                "acodec": "aac",
                                "vcodec": "avc1",
                                "protocol": "https",
                                "ext": "mp4",
                                "http_headers": {"Referer": "https://example.com/", "X-Ignore": "nope"},
                            }
                        ],
                        "http_headers": {"User-Agent": "yt-test/1.0"},
                    }
                ),
            ):
                playback = resolve_remote_media_playback("https://example.com/watch?v=123")

        self.assertEqual(playback.stream_url, "https://cdn.example.invalid/video.mp4")
        self.assertEqual(
            playback.http_headers,
            {
                "User-Agent": "yt-test/1.0",
                "Referer": "https://example.com/",
            },
        )
        self.assertEqual(playback.title, "Video de teste")
        self.assertEqual(playback.artist, "Canal de teste")

    def test_resolve_remote_media_playback_prefers_direct_file_over_manifest_for_seekable_playback(self):
        with patch("player.remote_media_metadata.ensure_yt_dlp_executable_available"):
            with patch(
                "player.remote_media_metadata.extract_yt_dlp_info",
                return_value=_response(
                    {
                        "title": "Video de teste",
                        "uploader": "Canal de teste",
                        "formats": [
                            {
                                "url": "https://cdn.example.invalid/live/master.m3u8",
                                "acodec": "aac",
                                "vcodec": "none",
                                "protocol": "m3u8_native",
                                "ext": "mp4",
                                "abr": 256,
                            },
                            {
                                "url": "https://cdn.example.invalid/archive/audio.mp4",
                                "acodec": "aac",
                                "vcodec": "none",
                                "protocol": "https",
                                "ext": "mp4",
                                "abr": 128,
                            },
                        ],
                    }
                ),
            ):
                playback = resolve_remote_media_playback("https://example.com/watch?v=123")

        self.assertEqual(playback.stream_url, "https://cdn.example.invalid/archive/audio.mp4")


if __name__ == "__main__":
    unittest.main()
