from __future__ import annotations

import pathlib
import sys
import unittest
from types import SimpleNamespace


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
        service = _FakeYouTubeMusicService(next_playback_mode="visionos")
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


if __name__ == "__main__":
    unittest.main()
