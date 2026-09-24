from pathlib import Path
import queue
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from player.constants import PROGRESS_GAUGE_RANGE
from player.frames.playback.backend import PlayerBackendMixin
from player.frames.playback.controls import PlaybackControlsMixin
from player.frames.playback.engine import PlaybackEngineMixin
from player.frames.playback.live import is_live_media

LIVE_URL = "https://www.youtube.com/watch?v=abc123DEF45"


class _WorkerFrame(PlaybackEngineMixin):
    """Engine mixin wired just enough to run one request through the worker."""

    def __init__(self, resolved_details, *, live_video=True):
        self._playback_request_serial = 1
        self._active_player_key = "primary"
        self._player_playback_request_serials = {}
        self._playback_queue = queue.Queue()
        self.current_volume = 70
        self.player = Mock()
        self.instance = Mock()
        self._resolved_details = resolved_details
        self._live_video = live_video
        self.marked_live_video = []
        self.finished = []

    def _resolve_media_for_playback_details(self, _media_path):
        return self._resolved_details

    def _managed_player(self, _key):
        return self.player

    def _instance_for_player(self, _key):
        return self.instance

    def _set_player_loaded_media_path(self, _key, _path):
        pass

    def _live_video_enabled(self):
        return self._live_video

    def _mark_player_showing_live_video(self, player_key):
        self.marked_live_video.append(player_key)

    def _finish_media_start(self, request, success, error_message):
        self.finished.append((request, success, error_message))
        # The worker keeps only the newest queued request, so stop it once this
        # one is done instead of queueing the shutdown up front.
        self._playback_queue.put({"kind": "shutdown"})

    def run_request(self, **request_overrides):
        request = {"kind": "play", "serial": 1, "media_path": LIVE_URL, "player_key": "primary"}
        request.update(request_overrides)
        self._playback_queue.put(request)
        with patch("player.frames.playback.engine.wx.CallAfter", side_effect=lambda fn, *args: fn(*args)):
            self._playback_worker_loop()
        return request


class LivePlaybackWorkerTests(unittest.TestCase):
    def test_live_media_is_flagged_and_asks_for_video_when_enabled(self):
        frame = _WorkerFrame(("https://live/95.m3u8", {"User-Agent": "x"}, "Jornal", "Canal", True))

        request = frame.run_request()

        frame.instance.media_new.assert_called_once_with(
            "https://live/95.m3u8", http_headers={"User-Agent": "x"}, is_live=True, video=True
        )
        self.assertTrue(request["is_live"])
        self.assertEqual(frame.marked_live_video, ["primary"])
        self.assertTrue(frame.finished[0][1])

    def test_live_media_plays_audio_only_when_live_video_is_off(self):
        frame = _WorkerFrame(("https://live/91.m3u8", {}, "Jornal", "Canal", True), live_video=False)

        frame.run_request()

        frame.instance.media_new.assert_called_once_with(
            "https://live/91.m3u8", http_headers={}, is_live=True, video=False
        )
        self.assertEqual(frame.marked_live_video, [])

    def test_live_media_ignores_the_resume_position(self):
        frame = _WorkerFrame(("https://live/95.m3u8", {}, "", "", True))

        frame.run_request(restore_position_ms=90000)

        # The backend drops start_seconds for a live; the worker still hands it over.
        frame.player.play.assert_called_once_with(start_seconds=90.0)
        self.assertTrue(frame.instance.media_new.call_args.kwargs["is_live"])

    def test_regular_media_keeps_the_original_media_new_call(self):
        frame = _WorkerFrame(("song.mp3", {}, "Faixa", "Artista", False))

        request = frame.run_request(media_path="song.mp3")

        frame.instance.media_new.assert_called_once_with("song.mp3", http_headers={})
        self.assertFalse(request["is_live"])
        self.assertEqual(frame.marked_live_video, [])

    def test_a_four_item_resolution_is_still_accepted(self):
        frame = _WorkerFrame(("song.mp3", {}, "Faixa", "Artista"))

        request = frame.run_request(media_path="song.mp3")

        frame.instance.media_new.assert_called_once_with("song.mp3", http_headers={})
        self.assertFalse(request["is_live"])
        self.assertTrue(frame.finished[0][1])


    def test_a_reconnect_that_resolves_to_a_recording_is_reported_as_ended(self):
        # The broadcast finished and YouTube now serves it as a regular video.
        frame = _WorkerFrame(("https://rr1.example.googlevideo.com/audio.webm", {}, "Jornal", "Canal", False))

        request = frame.run_request(expect_live=True, live_reconnect=True)

        frame.instance.media_new.assert_not_called()
        frame.player.play.assert_not_called()
        self.assertTrue(request["live_ended"])
        self.assertFalse(frame.finished[0][1])

    def test_a_reconnect_that_is_still_live_plays_normally(self):
        frame = _WorkerFrame(("https://live/95.m3u8", {}, "Jornal", "Canal", True))

        request = frame.run_request(expect_live=True, live_reconnect=True)

        frame.instance.media_new.assert_called_once()
        self.assertTrue(frame.finished[0][1])
        self.assertTrue(request["is_live"])


    def test_a_live_never_enters_a_crossfade_and_falls_back_to_a_regular_start(self):
        frame = _WorkerFrame(("https://live/95.m3u8", {}, "Jornal", "Canal", True))

        request = frame.run_request(crossfade=True)

        frame.instance.media_new.assert_not_called()
        frame.player.play.assert_not_called()
        self.assertFalse(frame.finished[0][1])
        self.assertFalse(request["live_ended"])


class LiveTimeBarTests(unittest.TestCase):
    def _frame(self, media):
        class Frame(PlaybackControlsMixin):
            pass

        frame = Frame()
        frame._crossfade_state = None
        frame.player = Mock()
        frame.player.get_media.return_value = media
        frame.progress_label = Mock()
        frame.progress_gauge = Mock()
        frame._maybe_refresh_player_visual_hints = Mock()
        frame._announce = Mock()
        return frame

    def test_is_live_media_requires_an_explicit_true_flag(self):
        self.assertTrue(is_live_media(SimpleNamespace(is_live=True)))
        self.assertFalse(is_live_media(SimpleNamespace(is_live=False)))
        self.assertFalse(is_live_media(Mock()))
        self.assertFalse(is_live_media(None))

    def test_time_bar_shows_a_fixed_live_label_and_a_full_gauge(self):
        frame = self._frame(SimpleNamespace(is_live=True))

        frame._update_time_bar()

        frame.progress_label.SetLabel.assert_called_once_with("Tempo: transmissão ao vivo")
        frame.progress_gauge.SetValue.assert_called_once_with(PROGRESS_GAUGE_RANGE)
        frame.player.get_time.assert_not_called()

    def test_seeking_a_live_is_refused_and_announced(self):
        frame = self._frame(SimpleNamespace(is_live=True))

        frame._seek_relative(5000)
        frame._seek_to_start()
        frame._seek_to_end()

        frame.player.set_time.assert_not_called()
        frame.player.set_position.assert_not_called()
        self.assertEqual(frame._announce.call_count, 3)

    def test_seeking_regular_media_still_works(self):
        frame = self._frame(SimpleNamespace(is_live=False))
        frame.player.get_time.return_value = 10000
        frame._update_time_bar = Mock()

        frame._seek_relative(5000)

        frame.player.set_time.assert_called_once_with(15000)

    def test_announced_time_of_a_live_is_the_watched_time(self):
        frame = self._frame(SimpleNamespace(is_live=True))
        frame.player.get_time.return_value = 125000

        frame._announce_playback_time()

        message = frame._announce.call_args.args[0]
        self.assertIn("ao vivo", message)
        self.assertIn("2:05", message)


class LiveVideoSlotTests(unittest.TestCase):
    def _backend(self, *, disable_video_output, live_video_enabled):
        class Frame(PlayerBackendMixin):
            pass

        frame = Frame()
        frame.settings = SimpleNamespace(
            disable_video_output=disable_video_output,
            live_video_enabled=live_video_enabled,
        )
        panel = Mock()
        panel.GetHandle.return_value = 4321
        frame._get_video_panel = lambda _index=None: panel
        return frame

    def test_handle_is_available_for_a_live_even_with_video_output_disabled(self):
        frame = self._backend(disable_video_output=True, live_video_enabled=True)

        self.assertEqual(frame._video_output_handle(), 4321)

    def test_no_handle_when_neither_video_nor_live_video_is_enabled(self):
        frame = self._backend(disable_video_output=True, live_video_enabled=False)

        self.assertIsNone(frame._video_output_handle())

    def test_slot_that_showed_live_video_is_tracked_until_recreated(self):
        frame = self._backend(disable_video_output=True, live_video_enabled=True)

        self.assertFalse(frame._player_showed_live_video("primary"))
        frame._mark_player_showing_live_video("primary")
        self.assertTrue(frame._player_showed_live_video("primary"))
        self.assertFalse(frame._player_showed_live_video("secondary"))

    def test_next_media_rebuilds_a_slot_that_showed_live_video(self):
        class Frame(PlayerBackendMixin, PlaybackEngineMixin):
            pass

        frame = Frame()
        frame.settings = SimpleNamespace(disable_video_output=True, live_video_enabled=True)
        frame._active_player_key = "primary"
        frame._playback_request_serial = 0
        frame._playback_queue = queue.Queue()
        frame.current_volume = 70
        frame._managed_player = lambda _key: Mock()
        frame._player_loaded_media_path = lambda _key: LIVE_URL
        frame._video_output_handle = lambda _index=None: None
        frame._bind_player_to_window = Mock()
        frame._recreate_player_slot = Mock()
        frame._mark_player_showing_live_video("primary")

        with patch("player.frames.playback.engine.sys", SimpleNamespace(platform="win32")):
            frame._queue_media_start("song.mp3", tab_index=0)

        frame._recreate_player_slot.assert_called_once_with("primary", index=0)

    def test_regular_audio_after_regular_audio_does_not_rebuild_the_slot(self):
        class Frame(PlayerBackendMixin, PlaybackEngineMixin):
            pass

        frame = Frame()
        frame.settings = SimpleNamespace(disable_video_output=True, live_video_enabled=True)
        frame._active_player_key = "primary"
        frame._playback_request_serial = 0
        frame._playback_queue = queue.Queue()
        frame.current_volume = 70
        frame._managed_player = lambda _key: Mock()
        frame._player_loaded_media_path = lambda _key: "old.mp3"
        frame._video_output_handle = lambda _index=None: None
        frame._bind_player_to_window = Mock()
        frame._recreate_player_slot = Mock()

        with patch("player.frames.playback.engine.sys", SimpleNamespace(platform="win32")):
            frame._queue_media_start("song.mp3", tab_index=0)

        frame._recreate_player_slot.assert_not_called()


if __name__ == "__main__":
    unittest.main()
