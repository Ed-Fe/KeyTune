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

from player.frames.playback.backend import PlayerBackendMixin


class _FakeYouTubeMusicService:
    def __init__(self, *, next_playback_mode):
        self.next_playback_mode = next_playback_mode
        self.switch_calls = 0

    def advance_stream_playback_after_http_403(self):
        self.switch_calls += 1
        return self.next_playback_mode


class _DummyFrame(PlayerBackendMixin):
    def __init__(self, *, service):
        self._active_player_key = "primary"
        self._crossfade_state = None
        self._service = service
        self._media_path = "https://music.youtube.com/watch?v=abc123DEF45"
        self.queued_starts = []
        self.status_messages = []
        self.announcements = []

    def _player_loaded_media_path(self, _player_key=None):
        return self._media_path

    def _youtube_music_service_for_playback(self):
        return self._service

    def _get_active_playlist_index(self):
        return 0

    def _get_playlist_state(self, _index=None):
        return SimpleNamespace(current_media_path=self._media_path)

    def _queue_media_start(self, media_path, **kwargs):
        self.queued_starts.append((media_path, kwargs))

    def _set_status_message(self, message, **_kwargs):
        self.status_messages.append(message)

    def _announce(self, message):
        self.announcements.append(message)


class PlayerBackendYouTubeMusicFallbackTests(unittest.TestCase):
    def test_http_403_switches_session_to_anonymous_and_retries_once(self):
        service = _FakeYouTubeMusicService(next_playback_mode="web_embedded")
        frame = _DummyFrame(service=service)

        frame._handle_player_error("primary", "HTTP 403")

        self.assertEqual(service.switch_calls, 1)
        self.assertEqual(len(frame.queued_starts), 1)
        self.assertEqual(frame.queued_starts[0][0], frame._media_path)
        self.assertEqual(frame.queued_starts[0][1]["announce_message"], "")
        self.assertEqual(frame.announcements, [])

    def test_http_403_in_anonymous_mode_announces_final_failure(self):
        service = _FakeYouTubeMusicService(next_playback_mode="")
        frame = _DummyFrame(service=service)

        frame._handle_player_error("primary", "HTTP 403")

        self.assertEqual(frame.queued_starts, [])
        self.assertEqual(frame.announcements, ["Não foi possível reproduzir a mídia: HTTP 403."])


class PlayerBackendAutoDJSoundTests(unittest.TestCase):
    def test_transition_sound_uses_the_preinitialized_mpv_on_the_selected_device(self):
        class FakePlayer:
            def __init__(self):
                self.calls = []

            def stop(self): self.calls.append(("stop",))
            def set_media(self, media): self.calls.append(("set_media", media))
            def audio_set_volume(self, volume): self.calls.append(("volume", volume))
            def play(self): self.calls.append(("play",))

        class FakeInstance:
            def __init__(self): self.player = FakePlayer()
            def media_player_new(self): return self.player
            def media_new(self, path): return path

        class Frame(PlayerBackendMixin):
            current_volume = 63
            _autodj_sound_instance = None
            _autodj_sound_player = None

            def _current_audio_output_device_id(self):
                return "wasapi/{device-1}"

        instance = FakeInstance()
        with patch("player.frames.playback.backend.create_player_instance", return_value=instance) as create:
            frame = Frame()
            self.assertTrue(frame._create_autodj_sound_player())
            self.assertTrue(frame._play_autodj_transition_sound("party"))

        create.assert_called_once_with(
            video_output_enabled=False,
            audio_output_device_id="wasapi/{device-1}",
        )
        self.assertEqual(instance.player.calls[0], ("stop",))
        self.assertEqual(instance.player.calls[-2:], [("volume", 63), ("play",)])

    def test_delayed_file_loaded_event_does_not_promote_a_paused_autodj_track(self):
        class Player:
            def is_playing(self):
                return False

        class Frame(PlayerBackendMixin):
            _active_player_key = "primary"

            def __init__(self):
                self._crossfade_state = {
                    "phase": "pending",
                    "autodj": True,
                    "incoming_key": "secondary",
                }
                self.begin_calls = 0

            def _managed_player(self, _player_key=None):
                return Player()

            def _begin_pending_crossfade(self):
                self.begin_calls += 1

            def _refresh_active_runtime_stream_title(self, **_kwargs):
                pass

        frame = Frame()
        frame._handle_player_started("secondary")

        self.assertEqual(frame.begin_calls, 0)


if __name__ == "__main__":
    unittest.main()
