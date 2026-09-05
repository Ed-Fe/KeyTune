from pathlib import Path
import queue
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from player.frames.playback.engine import PlaybackEngineMixin
from player.frames.playback.crossfade import CrossfadeMixin
from player.frames.playback.controls import PlaybackControlsMixin
from player.frames.library_tabs.playback_control import PlaylistPlaybackMixin
from player.playlists import PlaylistState


class PlaybackRaceTests(unittest.TestCase):
    def test_stale_completion_preserves_new_load_in_same_slot(self):
        frame = PlaybackEngineMixin()
        frame._playback_request_serial = 2
        frame._pending_playback_request_serial = 2
        frame._active_player_key = "primary"
        frame._player_playback_request_serials = {"primary": 2}
        frame._stop_player = Mock()
        frame._finish_media_start({"serial": 1, "player_key": "primary"}, True, "")
        frame._stop_player.assert_not_called()
        self.assertEqual(frame._pending_playback_request_serial, 2)

    def test_cancelled_load_is_stopped_when_slot_still_belongs_to_it(self):
        frame = PlaybackEngineMixin()
        frame._playback_request_serial = 2
        frame._active_player_key = "primary"
        frame._player_playback_request_serials = {"primary": 1}
        frame._stop_player = Mock()
        frame._finish_media_start({"serial": 1, "player_key": "primary"}, True, "")
        frame._stop_player.assert_called_once_with("primary", unload=True)

    def test_request_cancelled_during_resolution_never_touches_backend(self):
        frame = PlaybackEngineMixin()
        frame._playback_request_serial = 1
        frame._active_player_key = "primary"
        frame._playback_queue = queue.Queue()
        frame._playback_queue.put({"kind": "play", "serial": 1, "media_path": "old.mp3"})
        frame._managed_player = Mock()

        def resolve(_path):
            frame._playback_request_serial = 2
            frame._playback_queue.put({"kind": "shutdown"})
            return "old.mp3", {}, "", ""

        frame._resolve_media_for_playback_details = resolve
        frame._playback_worker_loop()
        frame._managed_player.assert_not_called()

    def test_delayed_pause_does_not_pause_new_media(self):
        class Frame(PlaybackControlsMixin, CrossfadeMixin):
            pass

        frame = Frame()
        state = PlaylistState(title="Playlist")
        state.set_items(["a.mp3", "b.mp3"])
        frame._get_playlist_state = lambda *_args: state
        player = Mock()
        player.get_media.return_value = object()
        player.is_playing.return_value = True
        frame.player = player
        frame._managed_player = lambda _key: player
        frame._active_player_key = "primary"
        frame._crossfade_state = None
        frame._playback_request_serial = 1
        frame.current_volume = 70
        frame._apply_volume_to_player = Mock()
        callbacks = []
        done = threading.Event()

        def call_after(callback):
            callbacks.append(callback)
            done.set()

        with patch("player.frames.playback.crossfade.wx.CallAfter", side_effect=call_after):
            frame._toggle_play_pause()
            self.assertTrue(done.wait(3))
        state.select_index(1)
        frame._playback_request_serial = 2
        player.get_media.return_value = object()
        callbacks[0]()
        player.pause.assert_not_called()

    def test_pause_during_preload_restores_queue_and_current_track(self):
        class Frame(PlaylistPlaybackMixin, PlaybackControlsMixin, CrossfadeMixin):
            pass

        frame = Frame()
        state = PlaylistState(title="AutoDJ")
        state.set_items(["a.mp3", "b.mp3", "c.mp3"])
        state.autodj_session = True
        state.custom_queue = ["b.mp3", "c.mp3"]
        frame._get_playlist_state = lambda *_args: state
        frame._get_active_playlist_index = lambda: 0
        frame._active_player_key = "primary"
        frame._crossfade_state = None
        frame.player = Mock()
        frame.player.get_time.return_value = 19000
        frame.player.get_length.return_value = 20000
        frame._prepared_autodj_transition = lambda _s: None
        frame._crossfade_duration_ms = lambda: 2000
        frame._can_crossfade_to_media = lambda *a, **k: True
        frame._describe_playlist_position = lambda _s: ""

        def start(**_kwargs):
            frame._crossfade_state = {
                "phase": "pending", "media_path": state.current_media_path,
                "incoming_key": "secondary", "outgoing_key": "primary", "tab_index": 0,
            }

        frame._play_media = start
        for name in ("_stop_player", "_next_playback_request_serial", "_restore_autodj_mix_filters",
                     "_stop_crossfade_timer", "_apply_current_volume", "_apply_current_playback_rate",
                     "_update_title", "_refresh_playlist_browser", "_perform_short_fade_out"):
            setattr(frame, name, Mock())
        self.assertTrue(frame._maybe_start_automatic_crossfade())
        self.assertEqual(state.current_media_path, "b.mp3")
        frame._toggle_play_pause()
        self.assertEqual(state.current_media_path, "a.mp3")
        self.assertEqual(state.custom_queue, ["b.mp3", "c.mp3"])
        self.assertEqual(state.autodj_history, [])
        self.assertEqual(state.move_in_playback_order(1), "b.mp3")
