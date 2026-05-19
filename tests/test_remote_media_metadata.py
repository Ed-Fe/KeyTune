from __future__ import annotations

import pathlib
import sys
import unittest
from unittest.mock import patch


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.remote_media_metadata import resolve_remote_media_metadata, resolve_remote_media_playback


class FakeYoutubeDL:
    def __init__(self, _options):
        return

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def extract_info(self, _url, download=False):
        assert download is False
        return {
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


class RemoteMediaMetadataTests(unittest.TestCase):
    def test_resolve_remote_media_metadata_uses_ytdlp_for_supported_remote_page(self):
        fake_module = type("FakeYtDlpModule", (), {"YoutubeDL": FakeYoutubeDL})

        with patch("player.remote_media_metadata.import_yt_dlp_module", return_value=fake_module):
            metadata = resolve_remote_media_metadata("https://example.com/watch?v=123")

        self.assertEqual(metadata.title, "Video de teste")
        self.assertEqual(metadata.artist, "Canal de teste")

    def test_resolve_remote_media_metadata_skips_youtube_urls(self):
        with patch("player.remote_media_metadata.import_yt_dlp_module") as import_mock:
            metadata = resolve_remote_media_metadata("https://www.youtube.com/watch?v=abc123DEF45")

        self.assertEqual(metadata.title, "")
        self.assertEqual(metadata.artist, "")
        import_mock.assert_not_called()

    def test_resolve_remote_media_playback_uses_best_stream_and_allowed_headers(self):
        fake_module = type("FakeYtDlpModule", (), {"YoutubeDL": FakeYoutubeDL})

        with patch("player.remote_media_metadata.import_yt_dlp_module", return_value=fake_module):
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
        fake_module = type("FakeYtDlpModule", (), {"YoutubeDL": FakeYoutubeDL})

        class ManifestFirstYoutubeDL(FakeYoutubeDL):
            def extract_info(self, _url, download=False):
                assert download is False
                return {
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

        fake_module = type("FakeYtDlpModule", (), {"YoutubeDL": ManifestFirstYoutubeDL})

        with patch("player.remote_media_metadata.import_yt_dlp_module", return_value=fake_module):
            playback = resolve_remote_media_playback("https://example.com/watch?v=123")

        self.assertEqual(playback.stream_url, "https://cdn.example.invalid/archive/audio.mp4")
