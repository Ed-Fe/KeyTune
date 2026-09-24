from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from player.frames.playback.backend import PlayerBackendMixin
from player.frames.playback.engine import PlaybackEngineMixin
from player.frames.playback.live import LIVE_RECONNECT_DELAYS_MS, LivePlaybackMixin

LIVE_URL = "https://www.youtube.com/watch?v=abc123DEF45"


class _LiveFrame(LivePlaybackMixin):
    def __init__(self):
        self._active_player_key = "primary"
        self._playback_request_serial = 5
        self.state = SimpleNamespace(current_media_path=LIVE_URL, was_playing=True)
        self._announce = Mock()
        self._set_status_message = Mock()
        self._queue_media_start = Mock()
        self._update_time_bar = Mock()
        self._refresh_playlist_browser = Mock()

    def _get_active_playlist_state(self):
        return self.state

    def _get_active_playlist_index(self):
        return 2

    def _get_playlist_state(self, _index=None):
        return self.state


class LiveReconnectTests(unittest.TestCase):
    def setUp(self):
        call_later_patch = patch("player.frames.playback.live.wx.CallLater")
        self.call_later = call_later_patch.start()
        self.addCleanup(call_later_patch.stop)
        call_after_patch = patch(
            "player.frames.playback.live.wx.CallAfter", side_effect=lambda fn, *args: fn(*args)
        )
        call_after_patch.start()
        self.addCleanup(call_after_patch.stop)
        self.frame = _LiveFrame()

    def test_losing_the_connection_schedules_the_first_reconnect_and_announces_once(self):
        self.frame._handle_live_ended("primary")

        self.call_later.assert_called_once()
        self.assertEqual(self.call_later.call_args.args[0], LIVE_RECONNECT_DELAYS_MS[0])
        self.assertEqual(self.call_later.call_args.args[2:], (LIVE_URL, 2, 5))
        self.frame._announce.assert_called_once()
        self.assertIn("Reconectando", self.frame._announce.call_args.args[0])

    def test_a_loss_on_the_inactive_slot_is_ignored(self):
        self.frame._handle_live_ended("secondary")

        self.call_later.assert_not_called()
        self.frame._announce.assert_not_called()

    def test_later_attempts_back_off_without_announcing_again(self):
        self.frame._handle_live_ended("primary")
        self.frame._handle_live_ended("primary")

        self.assertEqual(self.call_later.call_args.args[0], LIVE_RECONNECT_DELAYS_MS[1])
        self.frame._announce.assert_called_once()

    def test_giving_up_after_the_last_attempt_reports_and_stops_playback_state(self):
        for _attempt in LIVE_RECONNECT_DELAYS_MS:
            self.frame._handle_live_ended("primary")
        self.call_later.reset_mock()
        self.frame._announce.reset_mock()

        self.frame._handle_live_ended("primary")

        self.call_later.assert_not_called()
        self.assertIn("Não foi possível reconectar", self.frame._announce.call_args.args[0])
        self.assertFalse(self.frame.state.was_playing)

    def test_the_timer_requeues_the_live_as_a_reconnect(self):
        self.frame._reconnect_live(LIVE_URL, 2, 5)

        self.frame._queue_media_start.assert_called_once_with(
            LIVE_URL, tab_index=2, announce_message="", expect_live=True, live_reconnect=True
        )

    def test_the_timer_does_nothing_when_the_user_started_something_else(self):
        self.frame._playback_request_serial = 6
        self.frame._reconnect_live(LIVE_URL, 2, 5)
        self.frame._playback_request_serial = 5
        self.frame.state.current_media_path = "other.mp3"
        self.frame._reconnect_live(LIVE_URL, 2, 5)

        self.frame._queue_media_start.assert_not_called()

    def test_cancelling_stops_the_pending_timer_and_resets_the_attempts(self):
        self.frame._handle_live_ended("primary")
        timer = self.call_later.return_value

        self.frame._cancel_live_reconnect()

        timer.Stop.assert_called_once_with()
        self.assertEqual(self.frame._live_reconnect_attempts, 0)
        self.assertIsNone(self.frame._live_reconnect_timer)

    def test_a_confirmed_end_reports_that_the_broadcast_ended(self):
        self.frame._handle_live_finished()

        self.assertEqual(self.frame._announce.call_args.args[0], "A transmissão ao vivo terminou.")
        self.assertFalse(self.frame.state.was_playing)


class LiveVideoToggleTests(unittest.TestCase):
    def _frame(self, *, live_video_enabled=True, media=None):
        frame = _LiveFrame()
        frame.settings = SimpleNamespace(live_video_enabled=live_video_enabled)
        frame._live_video_enabled = lambda: frame.settings.live_video_enabled
        frame._save_settings = Mock()
        frame.player = Mock()
        frame.player.get_media.return_value = media
        return frame

    def test_toggling_flips_saves_and_announces_when_nothing_live_is_playing(self):
        frame = self._frame(live_video_enabled=True, media=SimpleNamespace(is_live=False))

        frame._toggle_live_video()

        self.assertFalse(frame.settings.live_video_enabled)
        frame._save_settings.assert_called_once_with()
        self.assertEqual(frame._announce.call_args.args[0], "Vídeo das transmissões ao vivo desativado.")
        frame._queue_media_start.assert_not_called()

    def test_toggling_during_a_live_restarts_it_with_the_new_mode(self):
        frame = self._frame(live_video_enabled=False, media=SimpleNamespace(is_live=True))

        frame._toggle_live_video()

        self.assertTrue(frame.settings.live_video_enabled)
        frame._queue_media_start.assert_called_once_with(
            LIVE_URL,
            tab_index=2,
            announce_message="Vídeo das transmissões ao vivo ativado.",
            expect_live=True,
            pause_after_start=False,
        )
        frame._announce.assert_not_called()

    def test_a_paused_live_stays_paused_after_the_restart(self):
        frame = self._frame(media=SimpleNamespace(is_live=True))
        frame.state.was_playing = False

        frame._toggle_live_video()

        self.assertTrue(frame._queue_media_start.call_args.kwargs["pause_after_start"])


class LivePlayerErrorTests(unittest.TestCase):
    def setUp(self):
        for target, kwargs in (
            ("player.frames.playback.live.wx.CallLater", {}),
            ("player.frames.playback.live.wx.CallAfter", {"side_effect": lambda fn, *args: fn(*args)}),
        ):
            active_patch = patch(target, **kwargs)
            active_patch.start()
            self.addCleanup(active_patch.stop)

    def _frame(self, media):
        class Frame(LivePlaybackMixin, PlayerBackendMixin):
            pass

        frame = Frame()
        frame._active_player_key = "primary"
        frame._playback_request_serial = 5
        frame._crossfade_state = None
        frame.state = SimpleNamespace(current_media_path=LIVE_URL, was_playing=True)
        frame._get_active_playlist_state = lambda: frame.state
        frame._get_active_playlist_index = lambda: 0
        frame._player_loaded_media_path = lambda _key: LIVE_URL
        player = Mock()
        player.get_media.return_value = media
        frame._managed_player = lambda _key: player
        frame._announce = Mock()
        frame._set_status_message = Mock()
        return frame

    def test_a_network_error_on_a_live_starts_a_reconnect(self):
        frame = self._frame(SimpleNamespace(is_live=True))

        frame._handle_player_error("primary", "")

        self.assertEqual(frame._live_reconnect_attempts, 1)
        self.assertIn("Reconectando", frame._announce.call_args.args[0])

    def test_a_playback_error_on_a_track_keeps_the_regular_message(self):
        frame = self._frame(SimpleNamespace(is_live=False))

        frame._handle_player_error("primary", "")

        self.assertEqual(getattr(frame, "_live_reconnect_attempts", 0), 0)
        self.assertEqual(frame._announce.call_args.args[0], "Não foi possível reproduzir a mídia.")


class LiveStartFailureTests(unittest.TestCase):
    def _frame(self):
        class Frame(PlaybackEngineMixin, LivePlaybackMixin):
            pass

        frame = Frame()
        frame._playback_request_serial = 5
        frame._pending_playback_request_serial = 5
        frame._active_player_key = "primary"
        frame.state = SimpleNamespace(current_media_path=LIVE_URL, was_playing=True)
        frame._get_playlist_state = lambda _index=None: frame.state
        frame._get_active_playlist_state = lambda: frame.state
        frame._get_active_playlist_index = lambda: 0
        frame._set_player_loaded_media_path = Mock()
        frame._announce = Mock()
        frame._set_status_message = Mock()
        frame._update_time_bar = Mock()
        frame._refresh_playlist_browser = Mock()
        frame._schedule_live_reconnect = Mock()
        return frame

    def _request(self, **overrides):
        request = {"serial": 5, "player_key": "primary", "tab_index": 0, "media_path": LIVE_URL}
        request.update(overrides)
        return request

    def test_a_reconnect_that_resolves_to_a_finished_broadcast_reports_it_ended(self):
        frame = self._frame()

        frame._finish_media_start(
            self._request(live_reconnect=True, live_ended=True), False, "A transmissão ao vivo terminou."
        )

        self.assertEqual(frame._announce.call_args.args[0], "A transmissão ao vivo terminou.")
        frame._schedule_live_reconnect.assert_not_called()

    def test_a_reconnect_that_fails_to_resolve_tries_again(self):
        frame = self._frame()

        frame._finish_media_start(self._request(live_reconnect=True), False, "Failed to resolve")

        frame._schedule_live_reconnect.assert_called_once_with()
        frame._announce.assert_not_called()

    def test_a_regular_failure_keeps_announcing_the_error(self):
        frame = self._frame()

        frame._finish_media_start(self._request(), False, "Vídeo indisponível")

        self.assertIn("Vídeo indisponível", frame._announce.call_args.args[0])
        frame._schedule_live_reconnect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
