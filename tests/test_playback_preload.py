import os
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from player.constants import REPEAT_OFF, REPEAT_ONE, REPEAT_STOP  # noqa: E402
from player.frames.playback.preload import (  # noqa: E402
    PRELOAD_CACHED_LEAD_MS,
    PRELOAD_LEAD_MS,
    PRELOAD_MIN_MARGIN_MS,
    PreloadMixin,
)


class FakePlayer:
    def __init__(self, time_ms=0, length_ms=200_000, playing=True, media="m", cached=False):
        self._cached = cached
        self._time = time_ms
        self._length = length_ms
        self._playing = playing
        self._media = media

    def get_time(self):
        return self._time

    def get_length(self):
        return self._length

    def is_playing(self):
        return self._playing

    def get_media(self):
        return self._media

    def is_fully_cached(self):
        return self._cached

    def get_diagnostics(self):
        return {"core-idle": False}


class FakeState:
    def __init__(self, current="a.mp3", next_path="b.mp3", repeat=REPEAT_OFF):
        self.current_media_path = current
        self.repeat_mode = repeat
        self.is_folder_tab = False
        self.autodj_session = None
        self._next = next_path

    def peek_in_playback_order(self, _direction, wrap=False):
        return self._next


class Host(PreloadMixin):
    def __init__(self, player=None, state=None, crossfade_ms=6000, autoplay=True):
        self.player = player or FakePlayer()
        self.state = state or FakeState()
        self._crossfade_ms = crossfade_ms
        self._crossfade_state = None
        self.settings = SimpleNamespace(autodj_enabled=False, autoplay_next=autoplay)
        self._players = {"primary": self.player, "secondary": FakePlayer(media=None)}
        self._active_player_key = "primary"
        self._loaded = {}
        self.stopped = []
        self.queued = []
        self._playback_request_serial = 7
        self._playback_queue = SimpleNamespace(put=self.queued.append)

    def _crossfade_duration_ms(self):
        return self._crossfade_ms

    def _crossfade_startup_headroom_ms(self):
        return 300

    def _get_active_playlist_state(self):
        return self.state

    def _get_active_playlist_index(self):
        return 0

    def _get_playlist_state(self, _index=None):
        return self.state

    def _autoplay_next_is_off(self, _state):
        return not self.settings.autoplay_next

    def _media_paths_match(self, a, b):
        return a == b

    def _youtube_music_media_is_disliked(self, _path):
        return False

    def _media_start_is_pending(self):
        return False

    def _inactive_player_key(self):
        return "secondary"

    def _managed_player(self, key=None):
        return self._players.get(key or self._active_player_key)

    def _player_loaded_media_path(self, key):
        return self._loaded.get(key)

    def _stop_player(self, key, *, unload=False):
        self.stopped.append((key, unload))
        if unload:
            self._loaded.pop(key, None)
            self._players[key]._media = None

    def _apply_equalizer_state_to_player(self, *_args):
        return True

    def _apply_volume_to_player(self, *_args):
        return True


class PreloadTests(unittest.TestCase):
    def test_target_is_next_track_when_everything_applies(self):
        self.assertEqual(Host()._preload_next_target(), ("b.mp3", 0))

    def test_no_target_without_crossfade_or_with_autoplay_off_or_repeat_one(self):
        self.assertIsNone(Host(crossfade_ms=0)._preload_next_target())
        self.assertIsNone(Host(autoplay=False)._preload_next_target())
        self.assertIsNone(Host(state=FakeState(repeat=REPEAT_ONE))._preload_next_target())
        self.assertIsNone(Host(state=FakeState(repeat=REPEAT_STOP))._preload_next_target())
        self.assertIsNone(Host(state=FakeState(next_path=None))._preload_next_target())

    def test_autodj_never_preloads(self):
        host = Host()
        host.settings.autodj_enabled = True
        self.assertIsNone(host._preload_next_target())

    def test_time_window(self):
        window = 6000 + 300 + PRELOAD_MIN_MARGIN_MS
        total = 200_000
        self.assertFalse(Host(player=FakePlayer(time_ms=total - PRELOAD_LEAD_MS - 1))._preload_time_window_is_open())
        self.assertTrue(Host(player=FakePlayer(time_ms=total - PRELOAD_LEAD_MS))._preload_time_window_is_open())
        self.assertTrue(Host(player=FakePlayer(time_ms=total - window - 1))._preload_time_window_is_open())
        self.assertFalse(Host(player=FakePlayer(time_ms=total - window))._preload_time_window_is_open())
        self.assertFalse(
            Host(player=FakePlayer(time_ms=total - 20_000, playing=False))._preload_time_window_is_open()
        )

    def test_starts_early_when_the_current_track_is_fully_cached(self):
        total = 200_000
        # Cache completo e já passou o começo: pode carregar bem antes do prazo.
        self.assertTrue(Host(player=FakePlayer(time_ms=10_000, cached=True))._preload_time_window_is_open())
        # Ainda no começo da faixa: espera o primeiro buffer.
        self.assertFalse(Host(player=FakePlayer(time_ms=1_000, cached=True))._preload_time_window_is_open())
        # Cache incompleto: só no prazo de segurança.
        self.assertFalse(Host(player=FakePlayer(time_ms=10_000, cached=False))._preload_time_window_is_open())
        self.assertTrue(
            Host(player=FakePlayer(time_ms=total - PRELOAD_LEAD_MS, cached=False))._preload_time_window_is_open()
        )
        # Faixa longa com cache completo: espera chegar perto do fim.
        long_total = PRELOAD_CACHED_LEAD_MS * 3
        self.assertFalse(
            Host(
                player=FakePlayer(time_ms=10_000, length_ms=long_total, cached=True)
            )._preload_time_window_is_open()
        )
        self.assertTrue(
            Host(
                player=FakePlayer(time_ms=long_total - PRELOAD_CACHED_LEAD_MS, length_ms=long_total, cached=True)
            )._preload_time_window_is_open()
        )
        # Cache completo, mas perto demais do fim: tarde para carregar.
        self.assertFalse(Host(player=FakePlayer(time_ms=total - 5_000, cached=True))._preload_time_window_is_open())

    def test_check_requests_a_paused_silent_load_in_the_free_slot(self):
        host = Host(player=FakePlayer(time_ms=200_000 - 20_000))
        host._maybe_preload_next_track()
        self.assertEqual(len(host.queued), 1)
        request = host.queued[0]
        self.assertEqual(request["player_key"], "secondary")
        self.assertEqual(request["media_path"], "b.mp3")
        self.assertTrue(request["pause_after_start"])
        self.assertTrue(request["crossfade"])
        self.assertTrue(request["preload"])
        self.assertEqual(request["initial_volume"], 0)
        # Usa o número da requisição atual, sem invalidar nada em andamento.
        self.assertEqual(request["serial"], 7)
        # Só pede uma vez.
        host._maybe_preload_next_track()
        self.assertEqual(len(host.queued), 1)

    def test_no_request_before_the_window(self):
        host = Host(player=FakePlayer(time_ms=10_000))
        host._maybe_preload_next_track()
        self.assertEqual(host.queued, [])

    def _ready_host(self):
        host = Host(player=FakePlayer(time_ms=200_000 - 20_000))
        host._maybe_preload_next_track()
        request = host.queued[0]
        host._players["secondary"]._media = "loaded"
        host._loaded["secondary"] = "b.mp3"
        request["resolved_display_title"] = "Titulo"
        host._finish_preload(request, True, "")
        return host

    def test_finish_marks_ready_and_keeps_titles(self):
        host = self._ready_host()
        self.assertTrue(host._preload["ready"])
        self.assertEqual(host._preload["resolved_display_title"], "Titulo")

    def test_take_returns_the_preload_only_for_the_same_media(self):
        host = self._ready_host()
        taken = host._take_preloaded_incoming("b.mp3", 0, "secondary")
        self.assertIsNotNone(taken)
        self.assertIsNone(host._preload)

        host = self._ready_host()
        self.assertIsNone(host._take_preloaded_incoming("c.mp3", 0, "secondary"))
        self.assertIsNone(host._preload)
        self.assertIn(("secondary", True), host.stopped)

    def test_take_refuses_a_preload_that_is_not_ready(self):
        host = Host(player=FakePlayer(time_ms=200_000 - 20_000))
        host._maybe_preload_next_track()
        self.assertIsNone(host._take_preloaded_incoming("b.mp3", 0, "secondary"))
        self.assertIsNone(host._preload)

    def test_changed_next_track_discards_the_preload(self):
        host = self._ready_host()
        host.state._next = "z.mp3"
        host._maybe_preload_next_track()
        self.assertIn(("secondary", True), host.stopped)
        self.assertIsNone(host._preload)

    def test_failed_preload_is_not_retried_for_the_same_pair(self):
        host = Host(player=FakePlayer(time_ms=200_000 - 20_000))
        host._maybe_preload_next_track()
        host._finish_preload(host.queued[0], False, "boom")
        self.assertIsNone(host._preload)
        host._maybe_preload_next_track()
        self.assertEqual(len(host.queued), 1)

    def test_late_result_after_discard_frees_the_slot(self):
        host = Host(player=FakePlayer(time_ms=200_000 - 20_000))
        host._maybe_preload_next_track()
        request = host.queued[0]
        host._discard_preload("teste")
        host.stopped.clear()
        host._finish_preload(request, True, "")
        self.assertIn(("secondary", True), host.stopped)


if __name__ == "__main__":
    unittest.main()
