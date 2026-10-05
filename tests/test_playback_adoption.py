"""A playback handed over by the quick player keeps playing in the main window."""

from __future__ import annotations

import pathlib
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player import mpv_backend
from player.frames.library_tabs.tabs import TabManagementMixin
from player.frames.playback.adoption import PlaybackAdoptionMixin
from player.frames.playback.backend import PlayerBackendMixin
from player.frames.session import FrameSessionMixin
from player.playback_handover import AdoptedPlayback
from player.playlists import PlaylistState


def _adopted(**overrides):
    values = {
        "player": Mock(get_time=Mock(return_value=41500)),
        "instance": Mock(),
        "paths": [r"C:\sons\um.wav", r"C:\sons\dois.wav"],
        "volume": 35,
        "playback_rate": 1.25,
        "paused": False,
    }
    values.update(overrides)
    return AdoptedPlayback(**values)


class AdoptPendingPlaybackTests(unittest.TestCase):
    def _frame(self, adopted):
        frame = PlaybackAdoptionMixin.__new__(PlaybackAdoptionMixin)
        frame._pending_adopted_playback = adopted
        frame.state = PlaylistState(title="Playlist 2")
        frame.calls = []
        frame._normalize_path = lambda path: path
        frame._remember_directory = Mock()
        frame._resolve_target_playlist_tab = Mock(return_value=(frame.state, 3))
        frame._active_player_key = "primary"
        frame._player_loaded = {}
        frame._set_player_loaded_media_path = lambda key, path: frame._player_loaded.__setitem__(key, path)
        frame.active_playlist_index = 0
        frame.notebook = Mock()
        frame.notebook.ChangeSelection.side_effect = lambda index: frame.calls.append(
            ("select", index, dict(frame._player_loaded), frame.active_playlist_index)
        )
        frame._activate_tab = Mock()
        frame._select_tab = Mock()
        frame._refresh_playlist_browser = Mock()
        frame._playback_request_serial = 7
        frame._next_playback_request_serial = Mock(return_value=8)
        frame._player_playback_request_serials = {}
        frame._finish_media_start = Mock()
        frame._set_status_message = Mock()
        frame._media_label = lambda path: path
        frame._refresh_smtc_state = Mock()
        frame._add_recent_media_paths = Mock()
        frame._open_media_paths = Mock(return_value=True)
        return frame

    def test_ties_the_playing_media_to_a_new_playlist_without_loading_it(self):
        adopted = _adopted()
        frame = self._frame(adopted)

        self.assertTrue(frame._adopt_pending_playback())

        self.assertIsNone(frame._pending_adopted_playback)
        self.assertEqual(frame.state.items, adopted.paths)
        self.assertEqual(frame.state.current_media_path, r"C:\sons\um.wav")
        self.assertEqual(frame.state.last_position_ms, 41500)
        self.assertTrue(frame.state.was_playing)
        # The tab must find the media already loaded when it is selected.
        self.assertEqual(frame.calls, [("select", 3, {"primary": r"C:\sons\um.wav"}, 3)])
        frame._activate_tab.assert_called_once_with(3, announce=False)
        # `_select_tab` would save the inherited position into the previous tab.
        frame._select_tab.assert_not_called()
        request = frame._finish_media_start.call_args.args[0]
        self.assertEqual(
            (request["serial"], request["media_path"], request["tab_index"], request["player_key"]),
            (8, r"C:\sons\um.wav", 3, "primary"),
        )
        self.assertEqual(request["announce_message"], "")
        self.assertEqual(frame._player_playback_request_serials, {"primary": 8})
        frame._refresh_smtc_state.assert_called_once_with()
        frame._open_media_paths.assert_not_called()

    def test_paused_media_stays_paused_in_the_playlist_state(self):
        frame = self._frame(_adopted(paused=True))

        frame._adopt_pending_playback()

        self.assertFalse(frame.state.was_playing)
        frame._set_status_message.assert_called_once()

    def test_media_that_ended_meanwhile_opens_as_a_new_media(self):
        frame = self._frame(_adopted(ended=True))

        self.assertTrue(frame._adopt_pending_playback())

        frame._open_media_paths.assert_called_once_with([r"C:\sons\um.wav", r"C:\sons\dois.wav"], verified=True)
        frame._finish_media_start.assert_not_called()

    def test_nothing_pending_does_nothing(self):
        frame = self._frame(None)

        self.assertFalse(frame._adopt_pending_playback())

        frame._resolve_target_playlist_tab.assert_not_called()


class PendingAdoptionProtectsThePlayerTests(unittest.TestCase):
    def test_session_restore_keeps_the_inherited_volume_and_leaves_the_player_alone(self):
        frame = FrameSessionMixin.__new__(FrameSessionMixin)
        frame._pending_adopted_playback = _adopted()
        frame.settings = SimpleNamespace(remember_window_size=False)
        frame.playlists = [PlaylistState(title="Inicial")]
        frame.notebook = Mock()
        frame.current_volume = 80
        frame.current_playback_rate = 1.0
        frame.current_pitch_semitones = 0
        frame._reset_playlist_tabs = Mock()
        frame._create_empty_playlist_tab = Mock()
        frame._apply_current_volume = Mock()
        frame._apply_current_playback_rate = Mock()
        frame._apply_equalizer_state_to_current_playback = Mock()
        frame._get_current_tab_index = Mock(return_value=0)
        frame._activate_tab = Mock()
        frame._select_tab = Mock()
        frame._get_playlist_state = lambda index=None: frame.playlists[0]
        frame._announce = Mock()
        payload = {
            "selected_tab": 0,
            "volume": 90,
            "playback_rate": 2.0,
            "playlists": [{
                "title": "Músicas",
                "items": ["musica.mp3"],
                "current_index": 0,
                "current_media_path": "musica.mp3",
                "was_playing": True,
            }],
        }

        with patch("player.frames.session.load_session", return_value=payload):
            self.assertTrue(frame._restore_session())

        self.assertEqual(frame.current_volume, 35)
        self.assertEqual(frame.current_playback_rate, 1.25)
        self.assertEqual(frame.playlists[0].title, "Músicas")
        for untouched in (
            frame._apply_current_volume,
            frame._apply_current_playback_rate,
            frame._apply_equalizer_state_to_current_playback,
            frame._activate_tab,
            frame._select_tab,
        ):
            untouched.assert_not_called()

    def test_resuming_a_tab_does_not_unload_the_inherited_player(self):
        frame = TabManagementMixin.__new__(TabManagementMixin)
        frame._pending_adopted_playback = _adopted()
        frame.playlists = [PlaylistState(title="Vazia")]
        frame.notebook = Mock()
        frame._unload_player = Mock()
        frame._queue_media_start = Mock()
        frame._apply_equalizer_state = Mock()

        self.assertFalse(frame._resume_playlist_tab(0, announce=False))

        frame._unload_player.assert_not_called()
        frame._queue_media_start.assert_not_called()
        frame._apply_equalizer_state.assert_not_called()

    def test_end_of_the_inherited_media_is_only_recorded(self):
        frame = PlayerBackendMixin.__new__(PlayerBackendMixin)
        adopted = _adopted()
        frame._pending_adopted_playback = adopted
        frame._active_player_key = "primary"
        frame._handle_media_end = Mock()

        frame._handle_player_end_reached("primary")

        self.assertTrue(adopted.ended)
        frame._handle_media_end.assert_not_called()


class AdoptedPlayerBackendTests(unittest.TestCase):
    def test_the_first_slot_takes_the_adopted_player_and_drops_its_old_listeners(self):
        old_listener = Mock()
        event_manager = mpv_backend.MPVEventManager()
        event_manager.event_attach(mpv_backend.PlayerEventType.MEDIA_PLAYER_END_REACHED, old_listener)
        adopted = _adopted(player=Mock(event_manager=Mock(return_value=event_manager)))
        frame = PlayerBackendMixin.__new__(PlayerBackendMixin)
        frame.settings = SimpleNamespace(disable_video_output=True, audio_output_device_id="")
        frame.current_volume = 80
        frame._selected_audio_output_device_id = Mock(return_value="")
        frame._current_audio_output_device_id = Mock(return_value="")
        frame._install_audio_output_device_observer = Mock()
        frame._validate_initial_audio_output_device = Mock()
        frame._playback_worker_loop = Mock()
        frame._on_media_end_reached = Mock()
        frame._on_media_player_playing = Mock()
        frame._on_media_player_error = Mock()
        frame._on_media_live_ended = Mock()
        created = []

        def build_instance(**_kwargs):
            instance = Mock()
            instance.media_player_new.side_effect = lambda: created.append(Mock()) or created[-1]
            return instance

        with patch("player.frames.playback.backend.create_player_instance", side_effect=build_instance):
            frame._create_player_backend(adopted=adopted)

        self.assertIs(frame.player, adopted.player)
        self.assertIs(frame._players["primary"], adopted.player)
        self.assertIs(frame._player_instances["primary"], adopted.instance)
        self.assertIsNot(frame._players["secondary"], adopted.player)
        event_manager.emit(mpv_backend.PlayerEventType.MEDIA_PLAYER_END_REACHED, None)
        old_listener.assert_not_called()
        frame._on_media_end_reached.assert_called_once_with(None, "primary")


class _FakeCore:
    def __init__(self):
        self.option_sets = []

    def event_callback(self, *_names):
        return lambda callback: callback

    def observe_property(self, *_args):
        return None

    def __setitem__(self, key, value):
        self.option_sets.append((key, value))

    def __getitem__(self, key):
        return ""


class AudioFilterTests(unittest.TestCase):
    def setUp(self):
        self._previous_module = mpv_backend._mpv_module
        self.core = _FakeCore()
        mpv_backend._mpv_module = SimpleNamespace(MPV=lambda **_kwargs: self.core, MpvEventEndFile=None)
        self.player = mpv_backend.MPVPlayer(video_output_enabled=False)
        self.core.option_sets.clear()

    def tearDown(self):
        mpv_backend._mpv_module = self._previous_module

    def test_clearing_filters_that_were_never_set_does_not_touch_the_audio_chain(self):
        self.player.set_audio_filters("")

        self.assertEqual(self.core.option_sets, [])

    def test_filters_are_applied_and_then_really_cleared(self):
        self.player.set_audio_filters("equalizer=f=60:g=3")
        self.player.set_audio_filters("")

        self.assertEqual(self.core.option_sets, [("af", "equalizer=f=60:g=3"), ("af", "")])

    def test_writing_the_chain_that_is_already_there_does_not_touch_the_audio_chain(self):
        self.player.set_audio_filters("equalizer=f=60:g=3")
        self.player.set_audio_filters("equalizer=f=60:g=3")

        self.assertEqual(self.core.option_sets, [("af", "equalizer=f=60:g=3")])

    def test_a_chain_with_labelled_filters_is_always_written_again(self):
        chain = "@autodj_mix:lavfi=[equalizer=f=80:g=0]"
        self.player.set_audio_filters(chain)
        self.player.set_audio_filters(chain)

        self.assertEqual(self.core.option_sets, [("af", chain), ("af", chain)])


if __name__ == "__main__":
    unittest.main()
