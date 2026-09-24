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
from player.youtube_music.live_streams import (
    LiveNotStartedError,
    is_live_info,
    is_live_not_started_message,
    is_upcoming_info,
    live_display_title_from_info,
    live_status_from_info,
    select_live_format,
)
from player.youtube_music.service import YouTubeMusicService
from player.youtube_music.streams import ResolvedStreamPlayback, resolve_stream_playback

LIVE_URL = "https://www.youtube.com/watch?v=abc123DEF45"


def _hls(format_id, height, tbr, *, acodec="mp4a.40.2", vcodec="avc1.4d401f"):
    fmt = {
        "format_id": format_id,
        "url": f"https://manifest.googlevideo.com/live/{format_id}.m3u8",
        "protocol": "m3u8_native",
        "acodec": acodec,
        "vcodec": vcodec,
        "tbr": tbr,
    }
    if height:
        fmt["height"] = height
    return fmt


def _candidates(*formats):
    return [dict(fmt, _stream_url=fmt["url"]) for fmt in formats]


def _response(data, stderr_text=""):
    return SimpleNamespace(data=data, stdout_text="", stderr_text=stderr_text)


def _live_info(**overrides):
    info = {
        "id": "abc123DEF45",
        "live_status": "is_live",
        "is_live": True,
        "title": "Jornal ao vivo 2026-09-23 12:00",
        "fulltitle": "Jornal ao vivo",
        "channel": "Canal de Notícias",
        "formats": [
            _hls("91", 144, 100),
            _hls("93", 360, 500),
            _hls("95", 720, 2500),
            _hls("96", 1080, 5000),
            {"format_id": "sb0", "url": "https://i.ytimg.com/sb/sb0.mhtml", "protocol": "mhtml",
             "vcodec": "none", "acodec": "none"},
        ],
        "http_headers": {"User-Agent": "yt-test/1.0"},
    }
    info.update(overrides)
    return info


class LiveStatusTests(unittest.TestCase):
    def test_status_comes_from_live_status_and_falls_back_to_is_live(self):
        self.assertEqual(live_status_from_info({"live_status": "is_upcoming"}), "is_upcoming")
        self.assertEqual(live_status_from_info({"is_live": True}), "is_live")
        self.assertEqual(live_status_from_info({"is_live": False}), "")
        self.assertEqual(live_status_from_info(None), "")

    def test_only_is_live_counts_as_live(self):
        self.assertTrue(is_live_info({"live_status": "is_live"}))
        for finished_status in ("was_live", "post_live", "not_live"):
            self.assertFalse(is_live_info({"live_status": finished_status}))

    def test_upcoming_is_detected(self):
        self.assertTrue(is_upcoming_info({"live_status": "is_upcoming"}))
        self.assertFalse(is_upcoming_info({"live_status": "is_live"}))

    def test_not_started_message_matches_yt_dlp_wording(self):
        self.assertTrue(is_live_not_started_message("This live event will begin in a few moments."))
        self.assertTrue(is_live_not_started_message("Premieres in 2 hours"))
        self.assertFalse(is_live_not_started_message("Video unavailable"))

    def test_display_title_prefers_the_title_without_the_timestamp(self):
        self.assertEqual(live_display_title_from_info(_live_info()), "Jornal ao vivo")
        self.assertEqual(live_display_title_from_info({"title": "Só título"}), "Só título")


class SelectLiveFormatTests(unittest.TestCase):
    def test_video_mode_picks_the_best_format_within_the_height_cap(self):
        formats = _candidates(_hls("91", 144, 100), _hls("95", 720, 2500), _hls("96", 1080, 5000))
        self.assertEqual(select_live_format(formats, prefer_video=True)["format_id"], "95")

    def test_video_mode_takes_the_lightest_when_everything_exceeds_the_cap(self):
        formats = _candidates(_hls("96", 1080, 5000), _hls("300", 2160, 15000))
        self.assertEqual(select_live_format(formats, prefer_video=True)["format_id"], "96")

    def test_audio_mode_prefers_an_audio_only_variant(self):
        formats = _candidates(
            _hls("93", 360, 500),
            _hls("233", 0, 48, vcodec="none", acodec="mp4a.40.5"),
            _hls("234", 0, 128, vcodec="none", acodec="mp4a.40.2"),
        )
        self.assertEqual(select_live_format(formats, prefer_video=False)["format_id"], "234")

    def test_audio_mode_without_audio_only_takes_the_lightest_muxed_format(self):
        formats = _candidates(_hls("95", 720, 2500), _hls("91", 144, 100), _hls("93", 360, 500))
        self.assertEqual(select_live_format(formats, prefer_video=False)["format_id"], "91")

    def test_video_only_and_storyboard_formats_are_ignored(self):
        video_only = _hls("299", 1080, 4000, acodec="none")
        storyboard = {"format_id": "sb0", "url": "https://i.ytimg.com/sb0.mhtml", "protocol": "mhtml",
                      "vcodec": "none", "acodec": "none"}
        self.assertIsNone(select_live_format(_candidates(video_only, storyboard), prefer_video=True))

    def test_hls_wins_over_other_protocols(self):
        dash = {"format_id": "d1", "url": "https://x.googlevideo.com/d1", "protocol": "http_dash_segments",
                "vcodec": "avc1", "acodec": "mp4a", "height": 720, "tbr": 9000}
        formats = _candidates(dash, _hls("93", 360, 500))
        self.assertEqual(select_live_format(formats, prefer_video=True)["format_id"], "93")

    def test_no_formats_returns_none(self):
        self.assertIsNone(select_live_format([], prefer_video=True))


class ResolveLiveStreamTests(unittest.TestCase):
    def setUp(self):
        configure_youtube_dependency_management(managed_install_enabled=False, auto_update_enabled=True)
        for target, kwargs in (
            ("player.youtube_music.streams.find_all_available_javascript_runtimes",
             {"return_value": {"node": "C:/fake/node.exe"}}),
            ("player.youtube_music.streams.ensure_yt_dlp_executable_available", {}),
            ("player.youtube_music.streams.resolve_youtubejs_stream",
             {"side_effect": RuntimeError("YouTube.js indisponível no teste")}),
            ("player.youtube_music.streams.load_saved_playback_auth",
             {"return_value": YouTubeMusicPlaybackAuth()}),
        ):
            active_patch = patch(target, **kwargs)
            active_patch.start()
            self.addCleanup(active_patch.stop)

    def _resolve(self, info, **kwargs):
        with patch("player.youtube_music.streams.extract_yt_dlp_info", return_value=_response(info)):
            return resolve_stream_playback(LIVE_URL, **kwargs)

    def test_live_video_mode_resolves_the_capped_muxed_format(self):
        resolved = self._resolve(_live_info(), prefer_video=True)

        self.assertTrue(resolved.is_live)
        self.assertEqual(resolved.stream_url, "https://manifest.googlevideo.com/live/95.m3u8")
        self.assertEqual(resolved.display_title, "Jornal ao vivo")
        self.assertEqual(resolved.display_artist, "Canal de Notícias")
        self.assertEqual(resolved.http_headers, {"User-Agent": "yt-test/1.0"})

    def test_live_audio_mode_resolves_the_lightest_format(self):
        resolved = self._resolve(_live_info(), prefer_video=False)

        self.assertTrue(resolved.is_live)
        self.assertEqual(resolved.stream_url, "https://manifest.googlevideo.com/live/91.m3u8")

    def test_live_without_usable_formats_falls_back_to_the_master_playlist(self):
        resolved = self._resolve(
            _live_info(
                formats=[],
                manifest_url="https://manifest.googlevideo.com/api/manifest/hls_playlist/live.m3u8",
            ),
            prefer_video=True,
        )

        self.assertTrue(resolved.is_live)
        self.assertEqual(
            resolved.stream_url,
            "https://manifest.googlevideo.com/api/manifest/hls_playlist/live.m3u8",
        )

    def test_scheduled_broadcast_raises_live_not_started(self):
        with self.assertRaises(LiveNotStartedError):
            self._resolve(_live_info(live_status="is_upcoming", is_live=False, formats=[]))

    def test_scheduled_broadcast_reported_as_an_error_raises_live_not_started(self):
        with patch(
            "player.youtube_music.streams.extract_yt_dlp_info",
            side_effect=RuntimeError("ERROR: [youtube] abc123DEF45: This live event will begin in a few moments."),
        ):
            with self.assertRaises(LiveNotStartedError):
                resolve_stream_playback(LIVE_URL)

    def test_empty_default_client_response_retries_once_with_the_live_capable_client(self):
        # The anonymous "visionos" client answers a live with only a title.
        responses = [_response({"title": "LIVE: Jornal", "channel": "Canal de Notícias"}), _response(_live_info())]
        captured_profiles = []

        def fake_extract(_media_path, **kwargs):
            captured_profiles.append(kwargs.get("extractor_args"))
            return responses.pop(0)

        with patch("player.youtube_music.streams.extract_yt_dlp_info", side_effect=fake_extract):
            resolved = resolve_stream_playback(LIVE_URL, prefer_video=True)

        self.assertTrue(resolved.is_live)
        self.assertEqual(resolved.stream_url, "https://manifest.googlevideo.com/live/95.m3u8")
        self.assertEqual(
            captured_profiles,
            [
                {"youtube": {"player_client": ["visionos"]}},
                {"youtube": {"player_client": ["web_safari"]}},
            ],
        )

    def test_empty_response_is_not_retried_when_the_live_client_was_already_used(self):
        with patch(
            "player.youtube_music.streams.extract_yt_dlp_info",
            return_value=_response({"title": "Sem formatos"}),
        ) as extract_info:
            with self.assertRaises(RuntimeError):
                resolve_stream_playback(LIVE_URL, anonymous_player_client="web_safari")

        self.assertEqual(extract_info.call_count, 1)

    def test_finished_broadcast_keeps_the_regular_audio_path(self):
        resolved = self._resolve(
            {
                "live_status": "was_live",
                "formats": [
                    {
                        "url": "https://rr1---sn.example.googlevideo.com/audio.webm",
                        "vcodec": "none",
                        "acodec": "opus",
                        "protocol": "https",
                        "abr": 128,
                    }
                ],
            },
            prefer_video=True,
        )

        self.assertFalse(resolved.is_live)
        self.assertEqual(resolved.stream_url, "https://rr1---sn.example.googlevideo.com/audio.webm")


class LiveServiceTests(unittest.TestCase):
    def test_live_playback_is_never_cached(self):
        service = YouTubeMusicService()
        live_playback = ResolvedStreamPlayback(
            stream_url="https://manifest.googlevideo.com/live/95.m3u8",
            is_live=True,
        )

        with patch(
            "player.youtube_music.service.resolve_music_stream_playback",
            return_value=live_playback,
        ) as resolve_stream:
            service.resolve_stream_playback(LIVE_URL)
            service.resolve_stream_playback(LIVE_URL)

        self.assertEqual(resolve_stream.call_count, 2)
        self.assertNotIn(LIVE_URL, service._stream_cache)

    def test_prefer_video_is_forwarded_to_the_resolver(self):
        service = YouTubeMusicService()

        with patch(
            "player.youtube_music.service.resolve_music_stream_playback",
            return_value=ResolvedStreamPlayback(stream_url="https://media.example.invalid/live.m3u8", is_live=True),
        ) as resolve_stream:
            service.resolve_stream_playback(LIVE_URL, prefer_video=True)
            service.resolve_stream_playback(LIVE_URL)

        self.assertEqual(
            [call.kwargs["prefer_video"] for call in resolve_stream.call_args_list],
            [True, False],
        )


if __name__ == "__main__":
    unittest.main()
