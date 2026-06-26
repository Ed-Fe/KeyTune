from __future__ import annotations

import pathlib
import sys
import unittest


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player import mpv_backend


class _FakePlayerCore:
    def __init__(self):
        self.pause = False
        self.volume = 100
        self.time_pos = 0
        self.duration = 180
        self.audio_device = "auto"
        self.audio_device_list = [
            {"name": "auto", "description": "Padrão do sistema"},
            {"name": "wasapi/{device-1}", "description": "Alto-falantes USB"},
        ]
        self.wid = None
        self.core_idle = True
        self.current_ao = "wasapi"
        self.loaded = []
        self.stopped = 0
        self.terminated = 0
        self.callbacks = {}
        self.option_sets = []
        self.http_header_fields = []

    def event_callback(self, *event_names):
        def decorator(callback):
            for event_name in event_names:
                self.callbacks[event_name] = callback
            return callback

        return decorator

    def observe_property(self, property_name, callback):
        self.property_observers = getattr(self, "property_observers", {})
        self.property_observers.setdefault(property_name, []).append(callback)

    def command(self, name, *args):
        self.commands = getattr(self, "commands", [])
        self.commands.append((name, args))

    def loadfile(self, path, mode, **options):
        self.loaded.append((path, mode))
        self.core_idle = False

    def stop(self):
        self.stopped += 1
        self.core_idle = True

    def terminate(self):
        self.terminated += 1

    def __setitem__(self, key, value):
        self.option_sets.append((key, value))
        setattr(self, key.replace("-", "_"), value)

    def __getitem__(self, key):
        return getattr(self, key.replace("-", "_"))


class _FakeMPVModule:
    class MpvEventEndFile:
        # Mirror python-mpv's actual enum names: reason 2 is ``ABORTED``.
        EOF = 0
        RESTARTED = 1
        ABORTED = 2
        QUIT = 3
        ERROR = 4
        REDIRECT = 5

    def __init__(self):
        self.created_players = []

    def MPV(self, **kwargs):
        player = _FakePlayerCore()
        player.created_with_kwargs = dict(kwargs)
        self.created_players.append(player)
        return player


class MPVPlayerTests(unittest.TestCase):
    def setUp(self):
        self._previous_module = mpv_backend._mpv_module
        self.fake_module = _FakeMPVModule()
        mpv_backend._mpv_module = self.fake_module

    def tearDown(self):
        mpv_backend._mpv_module = self._previous_module

    def _make_player_with_loaded_media(self, path="song.mp3"):
        player = mpv_backend.MPVPlayer(video_output_enabled=False)
        media = mpv_backend.MPVMedia(path=path)
        player.set_media(media)
        player.play()
        core = self.fake_module.created_players[0]
        # Simulate MPV confirming the file is loaded and playing.
        core.callbacks["file-loaded"](object())
        return player, core

    def _emit_end_file(self, core, reason):
        end_event = type("_EndEvent", (), {"reason": reason})()
        event = type("_Event", (), {"data": end_event})()
        core.callbacks["end-file"](event)

    def _set_eof_reached(self, core, value):
        for callback in core.property_observers.get("eof-reached", []):
            callback("eof-reached", value)

    def _count_end_reached(self, player):
        events = []
        player.event_manager().event_attach(
            mpv_backend.PlayerEventType.MEDIA_PLAYER_END_REACHED,
            lambda event: events.append(event),
        )
        return events

    def _count_errors(self, player):
        events = []
        player.event_manager().event_attach(
            mpv_backend.PlayerEventType.MEDIA_PLAYER_ERROR,
            lambda event: events.append(event),
        )
        return events

    def test_eof_reached_property_emits_end_of_track(self):
        # With keep-open=yes MPV signals a natural end via the eof-reached
        # property, not the end-file event.
        player, core = self._make_player_with_loaded_media()
        end_reached = self._count_end_reached(player)

        self._set_eof_reached(core, True)

        self.assertEqual(len(end_reached), 1)

    def test_eof_reached_emits_only_on_rising_edge(self):
        player, core = self._make_player_with_loaded_media()
        end_reached = self._count_end_reached(player)

        self._set_eof_reached(core, True)
        self._set_eof_reached(core, True)  # No False in between: still one end.

        self.assertEqual(len(end_reached), 1)

    def test_eof_reached_emits_again_after_new_load(self):
        player, core = self._make_player_with_loaded_media()
        end_reached = self._count_end_reached(player)

        self._set_eof_reached(core, True)
        # Advancing to the next track reloads and clears the end state.
        player.set_media(mpv_backend.MPVMedia(path="next.mp3"))
        player.play()
        self._set_eof_reached(core, True)

        self.assertEqual(len(end_reached), 2)

    def test_eof_reached_false_does_not_emit(self):
        player, core = self._make_player_with_loaded_media()
        end_reached = self._count_end_reached(player)

        self._set_eof_reached(core, False)

        self.assertEqual(len(end_reached), 0)

    def test_natural_eof_end_file_emits_end_of_track(self):
        # Fallback path when keep-open is off: MPV still delivers EOF via the
        # end-file event.
        player, core = self._make_player_with_loaded_media()
        end_reached = self._count_end_reached(player)

        self._emit_end_file(core, self.fake_module.MpvEventEndFile.EOF)

        self.assertEqual(len(end_reached), 1)

    def test_aborted_end_file_does_not_emit_end_of_track(self):
        # A STOP/ABORTED end-file (manual skip, stop, replace) is not an end of
        # track — natural ends come through eof-reached instead.
        player, core = self._make_player_with_loaded_media()
        end_reached = self._count_end_reached(player)

        self._emit_end_file(core, self.fake_module.MpvEventEndFile.ABORTED)

        self.assertEqual(len(end_reached), 0)

    def test_quit_end_file_does_not_emit_end_of_track(self):
        player, core = self._make_player_with_loaded_media()
        end_reached = self._count_end_reached(player)

        self._emit_end_file(core, self.fake_module.MpvEventEndFile.QUIT)

        self.assertEqual(len(end_reached), 0)

    def test_error_end_file_emits_error(self):
        player, core = self._make_player_with_loaded_media()
        errors = self._count_errors(player)
        end_reached = self._count_end_reached(player)

        self._emit_end_file(core, self.fake_module.MpvEventEndFile.ERROR)

        self.assertEqual(len(errors), 1)
        self.assertEqual(len(end_reached), 0)

    def test_resume_after_pause_does_not_reload_media(self):
        player = mpv_backend.MPVPlayer(video_output_enabled=False)
        media = mpv_backend.MPVMedia(path="song.mp3")
        player.set_media(media)

        player.play()
        core = self.fake_module.created_players[0]
        self.assertEqual(core.loaded, [("song.mp3", "replace")])

        player.pause()
        core.core_idle = True

        player.play()

        self.assertEqual(core.loaded, [("song.mp3", "replace")])
        self.assertFalse(core.pause)

    def test_replay_after_stop_still_reloads_media(self):
        player = mpv_backend.MPVPlayer(video_output_enabled=False)
        media = mpv_backend.MPVMedia(path="song.mp3")
        player.set_media(media)

        player.play()
        core = self.fake_module.created_players[0]

        player.stop()
        player.play()

        self.assertEqual(core.loaded, [("song.mp3", "replace"), ("song.mp3", "replace")])

    def test_lists_available_audio_output_devices(self):
        player = mpv_backend.MPVPlayer(video_output_enabled=False)
        self.fake_module.created_players[0].audio_device_list.append(
            {"name": "openal", "description": "Default (openal)"}
        )

        devices = player.list_audio_output_devices()

        self.assertEqual([device.device_id for device in devices], ["wasapi/{device-1}"])
        self.assertEqual(devices[0].menu_label, "Alto-falantes USB")

    def test_sets_specific_audio_output_device(self):
        player = mpv_backend.MPVPlayer(video_output_enabled=False)
        core = self.fake_module.created_players[0]

        player.set_audio_output_device("wasapi/{device-1}")

        self.assertEqual(core.audio_device, "wasapi/{device-1}")
        self.assertEqual(player.get_audio_output_device(), "wasapi/{device-1}")

    def test_applies_audio_output_device_after_player_creation(self):
        mpv_backend.MPVPlayer(
            video_output_enabled=False,
            audio_output_device_id="wasapi/{device-1}",
        )

        core = self.fake_module.created_players[0]

        self.assertNotIn("audio_device", core.created_with_kwargs)
        self.assertIn(("audio-device", "wasapi/{device-1}"), core.option_sets)

    def test_applies_system_default_audio_output_after_player_creation(self):
        mpv_backend.MPVPlayer(video_output_enabled=False)

        core = self.fake_module.created_players[0]
        expected_option = "wasapi" if mpv_backend.sys.platform.startswith("win") else "auto"

        self.assertIn(("audio-device", expected_option), core.option_sets)

    def test_disables_internal_ytdl_hook(self):
        mpv_backend.MPVPlayer(video_output_enabled=False)

        core = self.fake_module.created_players[0]

        self.assertIn("ytdl", core.created_with_kwargs)
        self.assertFalse(core.created_with_kwargs["ytdl"])

    def test_normalizes_default_audio_output_device(self):
        player = mpv_backend.MPVPlayer(video_output_enabled=False)
        core = self.fake_module.created_players[0]
        expected_option = "wasapi" if mpv_backend.sys.platform.startswith("win") else "auto"

        player.set_audio_output_device("")

        self.assertEqual(core.audio_device, expected_option)
        self.assertEqual(player.get_audio_output_device(), "")

    def test_ignores_generic_backend_as_selected_audio_device(self):
        player = mpv_backend.MPVPlayer(video_output_enabled=False)
        core = self.fake_module.created_players[0]
        core.audio_device = "openal"

        self.assertEqual(player.get_audio_output_device(), "")

    def test_treats_wasapi_default_backend_as_system_default_selection(self):
        player = mpv_backend.MPVPlayer(video_output_enabled=False)
        core = self.fake_module.created_players[0]
        core.audio_device = "wasapi"

        self.assertEqual(player.get_audio_output_device(), "")

    def test_applies_http_headers_before_loading_media(self):
        player = mpv_backend.MPVPlayer(video_output_enabled=False)
        media = mpv_backend.MPVMedia(
            path="https://example.invalid/audio",
            http_headers={
                "User-Agent": "Teste/1.0",
                "Cookie": "SID=abc",
            },
        )
        player.set_media(media)

        player.play()

        core = self.fake_module.created_players[0]
        self.assertIn(
            (
                "http-header-fields",
                ["User-Agent: Teste/1.0", "Cookie: SID=abc"],
            ),
            core.option_sets,
        )

    def test_play_uses_stable_media_reference_when_media_is_cleared_mid_start(self):
        player = mpv_backend.MPVPlayer(video_output_enabled=False)
        media = mpv_backend.MPVMedia(
            path="https://example.invalid/audio",
            http_headers={"User-Agent": "Teste/1.0"},
        )
        player.set_media(media)

        original_apply_media_http_headers = player._apply_media_http_headers

        def _apply_and_clear(current_media=None):
            original_apply_media_http_headers(current_media)
            player.set_media(None)

        player._apply_media_http_headers = _apply_and_clear

        player.play()

        core = self.fake_module.created_players[0]
        self.assertEqual(core.loaded, [("https://example.invalid/audio", "replace")])

    def test_audio_output_device_list_observer_filters_devices(self):
        player = mpv_backend.MPVPlayer(video_output_enabled=False)
        core = self.fake_module.created_players[0]

        received: list[list] = []
        player.observe_audio_output_devices(lambda devices: received.append(devices))

        observers = core.property_observers.get("audio-device-list", [])
        self.assertEqual(len(observers), 1)

        observers[0](
            "audio-device-list",
            [
                {"name": "auto", "description": "Padrão"},
                {"name": "wasapi/{device-2}", "description": "Fones Bluetooth"},
                {"name": "openal", "description": "Default (openal)"},
            ],
        )

        self.assertEqual(len(received), 1)
        self.assertEqual([d.device_id for d in received[0]], ["wasapi/{device-2}"])
        self.assertEqual(received[0][0].menu_label, "Fones Bluetooth")

    def _patch_audio_device_reset(self, core, *, reset_time, reset_pause):
        original_setitem = type(core).__setitem__

        def _setitem(self_core, key, value):
            original_setitem(self_core, key, value)
            if key == "audio-device":
                self_core.time_pos = reset_time
                self_core.pause = reset_pause

        # Dunder methods are looked up on the type, not the instance, so patch
        # the class for the duration of the test.
        type(core).__setitem__ = _setitem
        self.addCleanup(setattr, type(core), "__setitem__", original_setitem)

    def test_snapshot_restore_recovers_position_and_pause_state(self):
        player = mpv_backend.MPVPlayer(video_output_enabled=False)
        media = mpv_backend.MPVMedia(path="song.mp3")
        player.set_media(media)
        player.play()

        core = self.fake_module.created_players[0]
        core.time_pos = 42.5
        core.pause = False

        snapshot = player.snapshot_playback_state()
        self.assertEqual(snapshot, (42.5, False))

        self._patch_audio_device_reset(core, reset_time=0, reset_pause=True)
        player.set_audio_output_device("wasapi/{device-1}")

        # MPV's async reset has flipped state away from the snapshot.
        self.assertEqual(core.time_pos, 0)
        self.assertTrue(core.pause)

        self.assertTrue(player.restore_playback_state(snapshot))

        self.assertAlmostEqual(core.time_pos, 42.5)
        self.assertFalse(core.pause)

    def test_snapshot_restore_preserves_paused_media(self):
        player = mpv_backend.MPVPlayer(video_output_enabled=False)
        media = mpv_backend.MPVMedia(path="song.mp3")
        player.set_media(media)
        player.play()

        core = self.fake_module.created_players[0]
        core.time_pos = 10.0
        core.pause = True

        snapshot = player.snapshot_playback_state()
        self._patch_audio_device_reset(core, reset_time=0, reset_pause=False)

        player.set_audio_output_device("wasapi/{device-1}")
        player.restore_playback_state(snapshot)

        self.assertAlmostEqual(core.time_pos, 10.0)
        self.assertTrue(core.pause)

    def test_snapshot_restore_does_not_rewind_to_earlier_position(self):
        # When MPV has actually advanced past the snapshot (e.g. the audio
        # chain reinit was a no-op), restore must not yank the user back.
        player = mpv_backend.MPVPlayer(video_output_enabled=False)
        media = mpv_backend.MPVMedia(path="song.mp3")
        player.set_media(media)
        player.play()

        core = self.fake_module.created_players[0]
        core.time_pos = 30.0
        core.pause = False

        snapshot = player.snapshot_playback_state()

        core.time_pos = 32.0  # Audio kept playing through the device switch.
        player.restore_playback_state(snapshot)

        self.assertEqual(core.time_pos, 32.0)
        self.assertFalse(core.pause)

    def test_snapshot_returns_none_when_no_media_loaded(self):
        player = mpv_backend.MPVPlayer(video_output_enabled=False)
        self.assertIsNone(player.snapshot_playback_state())

    def test_reload_audio_output_invokes_audio_reload_command(self):
        player = mpv_backend.MPVPlayer(video_output_enabled=False)
        core = self.fake_module.created_players[0]

        self.assertTrue(player.reload_audio_output())

        commands = getattr(core, "commands", [])
        self.assertTrue(
            any(name in ("ao-reload", "audio-reload") for name, _ in commands),
            commands,
        )

    def test_audio_fallback_to_null_is_enabled_for_hotplug_recovery(self):
        mpv_backend.MPVPlayer(video_output_enabled=False)
        core = self.fake_module.created_players[0]

        self.assertEqual(core.created_with_kwargs.get("audio_fallback_to_null"), "yes")

    def test_get_current_audio_output_returns_running_ao(self):
        player = mpv_backend.MPVPlayer(video_output_enabled=False)
        core = self.fake_module.created_players[0]
        core.current_ao = "null"

        self.assertEqual(player.get_current_audio_output(), "null")


if __name__ == "__main__":
    unittest.main()