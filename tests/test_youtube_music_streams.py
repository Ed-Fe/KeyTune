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

from player.youtube_music.auth import YouTubeMusicPlaybackAuth
from player.youtube_music.dependencies import configure_youtube_dependency_management
import player.youtube_music.streams as youtube_music_streams
from player.youtube_music.streams import is_missing_javascript_runtime_error_message, resolve_stream_playback


def _response(data, stderr_text=""):
    return SimpleNamespace(data=data, stdout_text="", stderr_text=stderr_text)


class YouTubeMusicStreamsTests(unittest.TestCase):
    def setUp(self):
        configure_youtube_dependency_management(
            managed_install_enabled=False,
            auto_update_enabled=True,
        )
        youtube_music_streams._PRERELEASE_SELF_HEAL_ATTEMPTED = False
        self._js_runtime_patch = patch(
            "player.youtube_music.streams.find_all_available_javascript_runtimes",
            return_value={"node": "C:/fake/node.exe"},
        )
        self._js_runtime_patch.start()
        self.addCleanup(self._js_runtime_patch.stop)
        self._ensure_patch = patch("player.youtube_music.streams.ensure_yt_dlp_executable_available")
        self._ensure_mock = self._ensure_patch.start()
        self.addCleanup(self._ensure_patch.stop)
        self._youtubejs_patch = patch(
            "player.youtube_music.streams.resolve_youtubejs_stream",
            side_effect=RuntimeError("YouTube.js indisponível no teste"),
        )
        self._youtubejs_patch.start()
        self.addCleanup(self._youtubejs_patch.stop)

    def test_resolve_stream_playback_prefers_youtubejs_and_preserves_metadata(self):
        playback_auth = YouTubeMusicPlaybackAuth(
            cookie_header="SID=abc",
            user_agent="Mozilla/5.0 Teste",
        )
        youtubejs_result = SimpleNamespace(
            stream_url="https://rr1---sn.example.googlevideo.com/audio.m4a",
            display_title="Faixa pelo YouTube.js",
            display_artist="Artista pelo YouTube.js",
        )

        with patch("player.youtube_music.streams.load_saved_playback_auth", return_value=playback_auth), patch(
            "player.youtube_music.streams.resolve_youtubejs_stream",
            return_value=youtubejs_result,
        ) as youtubejs_resolver:
            resolved_playback = resolve_stream_playback("https://www.youtube.com/watch?v=abc123DEF45")

        self.assertEqual(resolved_playback.stream_url, youtubejs_result.stream_url)
        self.assertEqual(resolved_playback.display_title, "Faixa pelo YouTube.js")
        self.assertEqual(resolved_playback.display_artist, "Artista pelo YouTube.js")
        self.assertEqual(
            resolved_playback.http_headers,
            {"Cookie": "SID=abc", "User-Agent": "Mozilla/5.0 Teste"},
        )
        youtubejs_resolver.assert_called_once_with(
            "https://www.youtube.com/watch?v=abc123DEF45",
            cookie_header="",
            user_agent="Mozilla/5.0 Teste",
        )
        self._ensure_mock.assert_not_called()

    def test_missing_javascript_runtime_error_message_matches_expected_text(self):
        self.assertTrue(
            is_missing_javascript_runtime_error_message(
                "Para reproduzir do YouTube Music, o yt-dlp precisa de um runtime JavaScript instalado no sistema "
                "ou nos recursos adicionais do KeyTune. Recomendamos o Node.js 24+, que também "
                "é utilizado pelo YouTube.js."
            )
        )

    def test_missing_javascript_runtime_error_message_ignores_unrelated_errors(self):
        self.assertFalse(
            is_missing_javascript_runtime_error_message(
                "O yt-dlp não conseguiu determinar uma URL de reprodução compatível para esta faixa."
            )
        )

    def test_resolve_stream_playback_reports_installed_but_incompatible_runtime(self):
        with patch(
            "player.youtube_music.streams.find_all_available_javascript_runtimes",
            return_value={},
        ), patch(
            "player.youtube_music.streams.find_incompatible_javascript_runtimes",
            return_value={"node": "20.19.4"},
        ):
            with self.assertRaisesRegex(RuntimeError, "node 20.19.4"):
                resolve_stream_playback("https://www.youtube.com/watch?v=abc123DEF45")

    def test_resolve_stream_playback_configures_ytdlp_and_uses_temporary_cookie_file(self):
        playback_auth = YouTubeMusicPlaybackAuth(
            cookie_header="SID=abc; HSID=def",
            user_agent="Mozilla/5.0 Teste",
            cookie_file_path="C:/tmp/ytmusic_cookies.txt",
        )
        captured_calls = []

        def fake_extract(media_path, **kwargs):
            captured_calls.append((media_path, kwargs))
            return _response(
                {
                    "title": "Vídeo de teste",
                    "uploader": "Canal de teste",
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
            )

        with patch("player.youtube_music.streams.load_saved_playback_auth", return_value=playback_auth), patch(
            "player.youtube_music.streams.create_temporary_browser_auth_cookie_file",
            return_value="C:/tmp/ytmusic_runtime_cookies.txt",
        ) as create_temp_cookie_file, patch("os.remove") as remove_file, patch(
            "player.youtube_music.streams.extract_yt_dlp_info",
            side_effect=fake_extract,
        ):
            resolved_playback = resolve_stream_playback("https://www.youtube.com/watch?v=abc123DEF45")

        self.assertEqual(resolved_playback.stream_url, "https://rr1---sn.example.googlevideo.com/audio.webm")
        self.assertEqual(resolved_playback.display_title, "Vídeo de teste")
        self.assertEqual(resolved_playback.display_artist, "Canal de teste")
        self.assertEqual(
            resolved_playback.http_headers,
            {
                "User-Agent": "Mozilla/5.0 Teste",
                "Cookie": "SID=abc; HSID=def",
            },
        )
        self.assertEqual(len(captured_calls), 1)
        _media_path, kwargs = captured_calls[0]
        self.assertEqual(kwargs["format_selector"], "bestaudio/best")
        self.assertEqual(kwargs["cookie_file_path"], "C:/tmp/ytmusic_runtime_cookies.txt")
        self.assertEqual(kwargs["http_headers"], {"User-Agent": "Mozilla/5.0 Teste"})
        self.assertEqual(kwargs["extractor_args"], {"youtube": {"player_client": ["web_safari"]}})
        create_temp_cookie_file.assert_called_once_with("SID=abc; HSID=def")
        remove_file.assert_called_once_with("C:/tmp/ytmusic_runtime_cookies.txt")

    def test_resolve_stream_playback_rejects_youtube_watch_url_without_playable_audio_formats(self):
        with patch("player.youtube_music.streams.load_saved_playback_auth", return_value=YouTubeMusicPlaybackAuth()):
            with patch(
                "player.youtube_music.streams.extract_yt_dlp_info",
                return_value=_response(
                    {
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
                ),
            ):
                with self.assertRaisesRegex(RuntimeError, "stream de áudio compatível"):
                    resolve_stream_playback("https://www.youtube.com/watch?v=abc123DEF45")

    def test_resolve_stream_playback_accepts_direct_stream_url_without_formats(self):
        with patch("player.youtube_music.streams.load_saved_playback_auth", return_value=YouTubeMusicPlaybackAuth()):
            with patch(
                "player.youtube_music.streams.extract_yt_dlp_info",
                return_value=_response(
                    {
                        "url": "https://rr1---sn.example.googlevideo.com/videoplayback?expire=9999999999&id=abc",
                        "formats": [],
                        "http_headers": {"User-Agent": "yt-test/1.0", "Referer": "https://music.youtube.com/"},
                    }
                ),
            ):
                resolved_playback = resolve_stream_playback("https://www.youtube.com/watch?v=abc123DEF45")

        self.assertEqual(
            resolved_playback.stream_url,
            "https://rr1---sn.example.googlevideo.com/videoplayback?expire=9999999999&id=abc",
        )
        self.assertEqual(
            resolved_playback.http_headers,
            {"User-Agent": "yt-test/1.0", "Referer": "https://music.youtube.com/"},
        )

    def test_resolve_stream_playback_uses_only_the_selected_profile(self):
        responses = [
            _response(
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
                }
            ),
        ]
        captured_profiles = []

        def fake_extract(_media_path, **kwargs):
            captured_profiles.append(kwargs.get("extractor_args"))
            return responses.pop(0)

        with patch("player.youtube_music.streams.load_saved_playback_auth", return_value=YouTubeMusicPlaybackAuth()):
            with patch("player.youtube_music.streams.extract_yt_dlp_info", side_effect=fake_extract):
                with self.assertRaisesRegex(RuntimeError, "stream de áudio compatível"):
                    resolve_stream_playback("https://www.youtube.com/watch?v=abc123DEF45")

        self.assertEqual(
            captured_profiles,
            [
                {"youtube": {"player_client": ["visionos"]}},
            ],
        )

    def test_resolve_stream_playback_retries_transient_network_error_on_same_profile(self):
        playable_response = _response(
            {
                "formats": [
                    {
                        "url": "https://media.example.invalid/audio.webm",
                        "vcodec": "none",
                        "acodec": "opus",
                        "protocol": "https",
                    }
                ]
            }
        )
        with patch("player.youtube_music.streams.load_saved_playback_auth", return_value=YouTubeMusicPlaybackAuth()), patch(
            "player.youtube_music.streams.extract_yt_dlp_info",
            side_effect=[RuntimeError("Failed to resolve www.youtube.com"), playable_response],
        ) as extract_info, patch("player.youtube_music.streams.time.sleep"):
            resolved_playback = resolve_stream_playback("https://www.youtube.com/watch?v=abc123DEF45")

        self.assertEqual(resolved_playback.stream_url, "https://media.example.invalid/audio.webm")
        self.assertEqual(extract_info.call_count, 2)
        self.assertTrue(all(
            call.kwargs["extractor_args"] == {"youtube": {"player_client": ["visionos"]}}
            for call in extract_info.call_args_list
        ))

    def test_resolve_stream_playback_can_ignore_saved_account_cookies(self):
        playback_auth = YouTubeMusicPlaybackAuth(
            cookie_header="SID=abc; HSID=def",
            user_agent="Mozilla/5.0 Teste",
            cookie_file_path="C:/tmp/ytmusic_cookies.txt",
        )
        captured_calls = []

        def fake_extract(media_path, **kwargs):
            captured_calls.append((media_path, kwargs))
            return _response(
                {
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
            )

        with patch("player.youtube_music.streams.load_saved_playback_auth", return_value=playback_auth), patch(
            "player.youtube_music.streams.create_temporary_browser_auth_cookie_file",
        ) as create_temp_cookie_file, patch(
            "player.youtube_music.streams.extract_yt_dlp_info",
            side_effect=fake_extract,
        ):
            resolved_playback = resolve_stream_playback(
                "https://www.youtube.com/watch?v=abc123DEF45",
                use_account_cookies=False,
            )

        self.assertEqual(resolved_playback.http_headers, {"User-Agent": "yt-test/1.0"})
        self.assertEqual(len(captured_calls), 1)
        _media_path, kwargs = captured_calls[0]
        self.assertEqual(kwargs["cookie_file_path"], "")
        self.assertIsNone(kwargs["http_headers"])
        self.assertEqual(kwargs["extractor_args"], {"youtube": {"player_client": ["visionos"]}})
        create_temp_cookie_file.assert_not_called()

    def test_resolve_stream_playback_accepts_audio_with_missing_acodec_metadata(self):
        with patch("player.youtube_music.streams.load_saved_playback_auth", return_value=YouTubeMusicPlaybackAuth()):
            with patch(
                "player.youtube_music.streams.extract_yt_dlp_info",
                return_value=_response(
                    {
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
                ),
            ):
                resolved_playback = resolve_stream_playback("https://www.youtube.com/watch?v=abc123DEF45")

        self.assertEqual(resolved_playback.stream_url, "https://media.example.invalid/audio-unknown-codec.webm")

    def test_resolve_stream_playback_does_not_forward_cookie_to_untrusted_stream_host(self):
        playback_auth = YouTubeMusicPlaybackAuth(
            cookie_header="SID=abc; HSID=def",
            user_agent="Mozilla/5.0 Teste",
        )

        with patch("player.youtube_music.streams.load_saved_playback_auth", return_value=playback_auth), patch(
            "player.youtube_music.streams.create_temporary_browser_auth_cookie_file",
            return_value="C:/tmp/ytmusic_runtime_cookies.txt",
        ), patch("os.remove"), patch(
            "player.youtube_music.streams.extract_yt_dlp_info",
            return_value=_response(
                {
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
            ),
        ):
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

    def test_resolve_stream_playback_accepts_requested_download_without_audio_metadata(self):
        with patch("player.youtube_music.streams.load_saved_playback_auth", return_value=YouTubeMusicPlaybackAuth()):
            with patch(
                "player.youtube_music.streams.extract_yt_dlp_info",
                return_value=_response(
                    {
                        "url": "https://www.youtube.com/watch?v=abc123DEF45",
                        "requested_downloads": [
                            {
                                "format_id": "251",
                                "url": "https://rr1---sn.example.googlevideo.com/videoplayback?id=abc",
                                "protocol": "https",
                                "acodec": "none",
                                "vcodec": "avc1",
                            }
                        ],
                        "formats": [
                            {
                                "format_id": "18",
                                "url": "https://www.youtube.com/watch?v=abc123DEF45",
                                "protocol": "https",
                                "acodec": "none",
                                "vcodec": "avc1",
                            }
                        ],
                        "http_headers": {"User-Agent": "yt-test/1.0"},
                    }
                ),
            ):
                resolved_playback = resolve_stream_playback("https://www.youtube.com/watch?v=abc123DEF45")

        self.assertEqual(
            resolved_playback.stream_url,
            "https://rr1---sn.example.googlevideo.com/videoplayback?id=abc",
        )

    def test_resolve_stream_playback_accepts_top_level_manifest_url(self):
        with patch("player.youtube_music.streams.load_saved_playback_auth", return_value=YouTubeMusicPlaybackAuth()):
            with patch(
                "player.youtube_music.streams.extract_yt_dlp_info",
                return_value=_response(
                    {
                        "url": "https://www.youtube.com/watch?v=abc123DEF45",
                        "manifest_url": "https://manifest.googlevideo.com/api/manifest/hls_playlist/test.m3u8",
                        "formats": [],
                        "http_headers": {
                            "User-Agent": "yt-test/1.0",
                            "Referer": "https://music.youtube.com/",
                        },
                    }
                ),
            ):
                resolved_playback = resolve_stream_playback("https://www.youtube.com/watch?v=abc123DEF45")

        self.assertEqual(
            resolved_playback.stream_url,
            "https://manifest.googlevideo.com/api/manifest/hls_playlist/test.m3u8",
        )
        self.assertEqual(
            resolved_playback.http_headers,
            {
                "User-Agent": "yt-test/1.0",
                "Referer": "https://music.youtube.com/",
            },
        )

    def test_resolve_stream_playback_uses_nested_entry_when_top_level_is_unplayable(self):
        with patch("player.youtube_music.streams.load_saved_playback_auth", return_value=YouTubeMusicPlaybackAuth()):
            with patch(
                "player.youtube_music.streams.extract_yt_dlp_info",
                return_value=_response(
                    {
                        "url": "https://www.youtube.com/watch?v=abc123DEF45",
                        "formats": [
                            {
                                "format_id": "18",
                                "url": "https://www.youtube.com/watch?v=abc123DEF45",
                                "acodec": "none",
                                "vcodec": "avc1",
                                "protocol": "https",
                            }
                        ],
                        "entries": [
                            {
                                "formats": [
                                    {
                                        "format_id": "251",
                                        "url": "https://rr1---sn.example.googlevideo.com/videoplayback?itag=251&id=abc",
                                        "acodec": "opus",
                                        "vcodec": "none",
                                        "protocol": "https",
                                        "abr": 128,
                                    }
                                ],
                                "http_headers": {
                                    "User-Agent": "yt-test/1.0",
                                    "Referer": "https://music.youtube.com/",
                                },
                            }
                        ],
                        "http_headers": {"User-Agent": "yt-test/1.0"},
                    }
                ),
            ):
                resolved_playback = resolve_stream_playback("https://www.youtube.com/watch?v=abc123DEF45")

        self.assertEqual(
            resolved_playback.stream_url,
            "https://rr1---sn.example.googlevideo.com/videoplayback?itag=251&id=abc",
        )
        self.assertEqual(
            resolved_playback.http_headers,
            {
                "User-Agent": "yt-test/1.0",
                "Referer": "https://music.youtube.com/",
            },
        )

    def test_resolve_stream_playback_reports_js_challenge_guidance(self):
        stderr_text = "\n".join(
            [
                "WARNING: [youtube] abc123DEF45: n challenge solving failed: Some formats may be missing.",
                "WARNING: Only images are available for download.",
            ]
        )

        with patch("player.youtube_music.streams.load_saved_playback_auth", return_value=YouTubeMusicPlaybackAuth()):
            with patch(
                "player.youtube_music.streams.extract_yt_dlp_info",
                return_value=_response(
                    {
                        "url": "https://www.youtube.com/watch?v=abc123DEF45",
                        "formats": [
                            {
                                "format_id": "137",
                                "url": "https://media.example.invalid/video-only.mp4",
                                "acodec": "none",
                                "vcodec": "avc1",
                                "protocol": "https",
                            }
                        ],
                        "http_headers": {"User-Agent": "yt-test/1.0"},
                    },
                    stderr_text=stderr_text,
                ),
            ):
                with self.assertRaisesRegex(RuntimeError, "validação JavaScript"):
                    resolve_stream_playback("https://www.youtube.com/watch?v=abc123DEF45")

    def test_resolve_stream_playback_retries_after_prerelease_self_heal(self):
        configure_youtube_dependency_management(
            managed_install_enabled=True,
            auto_update_enabled=True,
        )

        responses = [
            _response(
                {
                    "url": "https://www.youtube.com/watch?v=abc123DEF45",
                    "formats": [
                        {
                            "format_id": "137",
                            "url": "https://media.example.invalid/video-only.mp4",
                            "acodec": "none",
                            "vcodec": "avc1",
                            "protocol": "https",
                        }
                    ],
                    "http_headers": {"User-Agent": "yt-test/1.0"},
                },
                stderr_text=(
                    "WARNING: [youtube] abc123DEF45: n challenge solving failed: Some formats may be missing.\n"
                    "WARNING: Only images are available for download."
                ),
            ),
            _response(
                {
                    "formats": [
                        {
                            "url": "https://rr1---sn.example.googlevideo.com/audio-after-update.webm",
                            "vcodec": "none",
                            "acodec": "opus",
                            "protocol": "https",
                            "abr": 128,
                        }
                    ],
                    "http_headers": {"User-Agent": "yt-test/1.0"},
                }
            ),
        ]

        with patch("player.youtube_music.streams.load_saved_playback_auth", return_value=YouTubeMusicPlaybackAuth()):
            with patch(
                "player.youtube_music.streams.extract_yt_dlp_info",
                side_effect=lambda *_args, **_kwargs: responses.pop(0),
            ):
                with patch("player.youtube_music.streams.install_or_update_youtube_dependencies") as update_mock:
                    resolved_playback = resolve_stream_playback("https://www.youtube.com/watch?v=abc123DEF45")

        self.assertEqual(
            resolved_playback.stream_url,
            "https://rr1---sn.example.googlevideo.com/audio-after-update.webm",
        )
        update_mock.assert_called_once_with(force=True, include_prerelease=True)


if __name__ == "__main__":
    unittest.main()
