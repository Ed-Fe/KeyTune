from __future__ import annotations

import pathlib
import sys
import unittest


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.audio_output import (
    audio_output_device_from_mpv_entry,
    is_selectable_audio_output_device_id,
    normalize_audio_output_device_id,
)
from player.frames.playback.audio_output import AudioOutputMixin


class AudioOutputHelperTests(unittest.TestCase):
    def test_normalize_audio_output_device_id_treats_auto_as_default(self):
        self.assertEqual(normalize_audio_output_device_id("auto"), "")
        self.assertEqual(normalize_audio_output_device_id("default"), "")
        self.assertEqual(normalize_audio_output_device_id("wasapi/{device-1}"), "wasapi/{device-1}")

    def test_builds_menu_label_from_mpv_entry(self):
        device = audio_output_device_from_mpv_entry(
            {
                "name": "wasapi/{device-1}",
                "description": "Fones Bluetooth",
            }
        )

        self.assertIsNotNone(device)
        self.assertEqual(device.device_id, "wasapi/{device-1}")
        self.assertEqual(device.menu_label, "Fones Bluetooth")

    def test_filters_generic_backend_entries(self):
        self.assertFalse(is_selectable_audio_output_device_id("openal"))
        self.assertTrue(is_selectable_audio_output_device_id("wasapi/{device-1}"))
        self.assertIsNone(
            audio_output_device_from_mpv_entry(
                {
                    "name": "openal",
                    "description": "Default (openal)",
                }
            )
        )

    def test_device_change_is_applied_to_the_autodj_sound_player(self):
        class SoundPlayer:
            def __init__(self):
                self.device_id = None
                self.reload_calls = 0

            def set_audio_output_device(self, device_id):
                self.device_id = device_id

            def reload_audio_output(self):
                self.reload_calls += 1

        class Frame(AudioOutputMixin):
            player = None
            _player_keys = ()

            def _best_playback_snapshot_for_audio_swap(self, _active_player):
                return None

        frame = Frame()
        frame._autodj_sound_player = SoundPlayer()

        frame._apply_audio_output_device_to_players("wasapi/{device-1}")

        self.assertEqual(frame._autodj_sound_player.device_id, "wasapi/{device-1}")
        self.assertEqual(frame._autodj_sound_player.reload_calls, 1)


if __name__ == "__main__":
    unittest.main()
