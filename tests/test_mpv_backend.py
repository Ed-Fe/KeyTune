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

    def loadfile(self, path, mode):
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
        ERROR = "error"
        EOF = "eof"

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


if __name__ == "__main__":
    unittest.main()