from __future__ import annotations

import pathlib
import sys
import types
import unittest
from unittest.mock import patch


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.youtube_music.auth import YouTubeMusicPlaybackAuth
from player.youtube_music.streams import resolve_stream_playback


class _FakeYoutubeDL:
    last_options = None
    options_history = []
    info_sequence = []
    next_info = {
        "formats": [
            {
                "url": "https://rr1---sn.example.googlevideo.com/audio.webm",
                "vcodec": "none",
                "acodec": "opus",
                "protocol": "https",
                "abr": 128,
            }
        ],
        "http_headers": {"User-Agent": "yt-test/1.0"},
    }

    def __init__(self, options):
        type(self).last_options = dict(options)
        type(self).options_history.append(dict(options))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def extract_info(self, _url, download=False):
        if type(self).info_sequence:
            return type(self).info_sequence.pop(0)
        return type(self).next_info


class YouTubeMusicStreamsTests(unittest.TestCase):
    def setUp(self):
        _FakeYoutubeDL.last_options = None
        _FakeYoutubeDL.options_history = []
        _FakeYoutubeDL.info_sequence = []
        _FakeYoutubeDL.next_info = {
            "formats": [
                {
                    "url": "https://rr1---sn.example.googlevideo.com/audio.webm",
                    "vcodec": "none",
                    "acodec": "opus",
                    "protocol": "https",
                    "abr": 128,
                }
            ],
            "http_headers": {"User-Agent": "yt-test/1.0"},
        }

    def test_resolve_stream_playback_configures_ytdlp_and_uses_temporary_cookie_file(self):
        fake_module = types.SimpleNamespace(YoutubeDL=_FakeYoutubeDL)
        playback_auth = YouTubeMusicPlaybackAuth(
            cookie_header="SID=abc; HSID=def",
            user_agent="Mozilla/5.0 Teste",
            cookie_file_path="C:/tmp/ytmusic_cookies.txt",
        )

        with patch.dict(sys.modules, {"yt_dlp": fake_module}):
            with patch("player.youtube_music.streams.load_saved_playback_auth", return_value=playback_auth), patch(
                "player.youtube_music.streams.create_temporary_browser_auth_cookie_file",
                return_value="C:/tmp/ytmusic_runtime_cookies.txt",
            ) as create_temp_cookie_file, patch("os.remove") as remove_file:
                resolved_playback = resolve_stream_playback("https://www.youtube.com/watch?v=abc123DEF45")

        self.assertEqual(resolved_playback.stream_url, "https://rr1---sn.example.googlevideo.com/audio.webm")
        self.assertEqual(
            resolved_playback.http_headers,
            {
                "User-Agent": "Mozilla/5.0 Teste",
                "Cookie": "SID=abc; HSID=def",
            },
        )
        self.assertTrue(_FakeYoutubeDL.last_options["ignore_no_formats_error"])
        self.assertEqual(_FakeYoutubeDL.last_options["format"], "bestaudio/best")
        self.assertEqual(_FakeYoutubeDL.last_options["cookiefile"], "C:/tmp/ytmusic_runtime_cookies.txt")
        self.assertEqual(
            _FakeYoutubeDL.last_options["http_headers"],
            {"User-Agent": "Mozilla/5.0 Teste"},
        )
        create_temp_cookie_file.assert_called_once_with("SID=abc; HSID=def")
        remove_file.assert_called_once_with("C:/tmp/ytmusic_runtime_cookies.txt")

    def test_resolve_stream_playback_rejects_youtube_watch_url_without_playable_audio_formats(self):
        fake_module = types.SimpleNamespace(YoutubeDL=_FakeYoutubeDL)
        _FakeYoutubeDL.next_info = {
            "url": "https://www.youtube.com/watch?v=abc123DEF45",
            "formats": [
                {
                    "url": "https://media.example.invalid/video-only.mp4",
                    "vcodec": "avc1",
                    "acodec": "none",
                    "protocol": "https",
                    "tbr": 1800,
                }
            ],
            "http_headers": {"User-Agent": "yt-test/1.0"},
        }

        with patch.dict(sys.modules, {"yt_dlp": fake_module}):
            with patch("player.youtube_music.streams.load_saved_playback_auth", return_value=YouTubeMusicPlaybackAuth()):
                with self.assertRaisesRegex(RuntimeError, "stream de áudio compatível"):
                    resolve_stream_playback("https://www.youtube.com/watch?v=abc123DEF45")

    def test_resolve_stream_playback_accepts_direct_stream_url_without_formats(self):
        fake_module = types.SimpleNamespace(YoutubeDL=_FakeYoutubeDL)
        _FakeYoutubeDL.next_info = {
            "url": "https://rr1---sn.example.googlevideo.com/videoplayback?expire=9999999999&id=abc",
            "formats": [],
            "http_headers": {"User-Agent": "yt-test/1.0", "Referer": "https://music.youtube.com/"},
        }

        with patch.dict(sys.modules, {"yt_dlp": fake_module}):
            with patch("player.youtube_music.streams.load_saved_playback_auth", return_value=YouTubeMusicPlaybackAuth()):
                resolved_playback = resolve_stream_playback("https://www.youtube.com/watch?v=abc123DEF45")

        self.assertEqual(
            resolved_playback.stream_url,
            "https://rr1---sn.example.googlevideo.com/videoplayback?expire=9999999999&id=abc",
        )
        self.assertEqual(
            resolved_playback.http_headers,
            {"User-Agent": "yt-test/1.0", "Referer": "https://music.youtube.com/"},
        )

    def test_resolve_stream_playback_retries_next_profile_when_first_is_unplayable(self):
        fake_module = types.SimpleNamespace(YoutubeDL=_FakeYoutubeDL)
        _FakeYoutubeDL.info_sequence = [
            {
                "url": "https://www.youtube.com/watch?v=abc123DEF45",
                "formats": [
                    {
                        "url": "https://media.example.invalid/video-only.mp4",
                        "vcodec": "avc1",
                        "acodec": "none",
                        "protocol": "https",
                    }
                ],
                "http_headers": {"User-Agent": "yt-test/1.0"},
            },
            {
                "formats": [
                    {
                        "url": "https://media.example.invalid/audio-fallback.webm",
                        "vcodec": "none",
                        "acodec": "opus",
                        "protocol": "https",
                        "abr": 128,
                    }
                ],
                "http_headers": {"User-Agent": "yt-test/1.0"},
            },
        ]

        with patch.dict(sys.modules, {"yt_dlp": fake_module}):
            with patch("player.youtube_music.streams.load_saved_playback_auth", return_value=YouTubeMusicPlaybackAuth()):
                resolved_playback = resolve_stream_playback("https://www.youtube.com/watch?v=abc123DEF45")

        self.assertEqual(resolved_playback.stream_url, "https://media.example.invalid/audio-fallback.webm")
        self.assertEqual(len(_FakeYoutubeDL.options_history), 2)
        self.assertNotIn("extractor_args", _FakeYoutubeDL.options_history[0])
        self.assertEqual(
            _FakeYoutubeDL.options_history[1].get("extractor_args"),
            {"youtube": {"player_client": ["web", "android", "ios"]}},
        )

    def test_resolve_stream_playback_accepts_audio_with_missing_acodec_metadata(self):
        fake_module = types.SimpleNamespace(YoutubeDL=_FakeYoutubeDL)
        _FakeYoutubeDL.next_info = {
            "url": "https://www.youtube.com/watch?v=abc123DEF45",
            "formats": [
                {
                    "url": "https://media.example.invalid/audio-unknown-codec.webm",
                    "vcodec": "none",
                    "acodec": "",
                    "protocol": "https",
                    "abr": 96,
                }
            ],
            "http_headers": {"User-Agent": "yt-test/1.0"},
        }

        with patch.dict(sys.modules, {"yt_dlp": fake_module}):
            with patch("player.youtube_music.streams.load_saved_playback_auth", return_value=YouTubeMusicPlaybackAuth()):
                resolved_playback = resolve_stream_playback("https://www.youtube.com/watch?v=abc123DEF45")

        self.assertEqual(resolved_playback.stream_url, "https://media.example.invalid/audio-unknown-codec.webm")

    def test_resolve_stream_playback_does_not_forward_cookie_to_untrusted_stream_host(self):
        fake_module = types.SimpleNamespace(YoutubeDL=_FakeYoutubeDL)
        _FakeYoutubeDL.next_info = {
            "formats": [
                {
                    "url": "https://cdn.example.invalid/audio.webm",
                    "vcodec": "none",
                    "acodec": "opus",
                    "protocol": "https",
                    "abr": 128,
                    "http_headers": {"Referer": "https://music.youtube.com/"},
                }
            ],
            "http_headers": {"User-Agent": "yt-test/1.0"},
        }
        playback_auth = YouTubeMusicPlaybackAuth(
            cookie_header="SID=abc; HSID=def",
            user_agent="Mozilla/5.0 Teste",
        )

        with patch.dict(sys.modules, {"yt_dlp": fake_module}):
            with patch("player.youtube_music.streams.load_saved_playback_auth", return_value=playback_auth), patch(
                "player.youtube_music.streams.create_temporary_browser_auth_cookie_file",
                return_value="C:/tmp/ytmusic_runtime_cookies.txt",
            ), patch("os.remove"):
                resolved_playback = resolve_stream_playback("https://www.youtube.com/watch?v=abc123DEF45")

        self.assertEqual(resolved_playback.stream_url, "https://cdn.example.invalid/audio.webm")
        self.assertEqual(
            resolved_playback.http_headers,
            {
                "User-Agent": "Mozilla/5.0 Teste",
                "Referer": "https://music.youtube.com/",
            },
        )
        self.assertNotIn("Cookie", resolved_playback.http_headers)


if __name__ == "__main__":
    unittest.main()