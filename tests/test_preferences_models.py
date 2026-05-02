from __future__ import annotations

import pathlib
import sys
import unittest


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.preferences.models import AppSettings


class AppSettingsTests(unittest.TestCase):
    def test_audio_output_device_id_round_trips(self):
        settings = AppSettings(audio_output_device_id="wasapi/{device-1}")

        payload = settings.to_dict()
        restored_settings = AppSettings.from_dict(payload)

        self.assertEqual(payload["audio_output_device_id"], "wasapi/{device-1}")
        self.assertEqual(restored_settings.audio_output_device_id, "wasapi/{device-1}")

    def test_generic_audio_backend_is_not_persisted_as_device(self):
        settings = AppSettings(audio_output_device_id="openal")

        payload = settings.to_dict()
        restored_settings = AppSettings.from_dict(payload)

        self.assertEqual(payload["audio_output_device_id"], "")
        self.assertEqual(restored_settings.audio_output_device_id, "")

    def test_youtube_music_dependency_settings_round_trip(self):
        settings = AppSettings(
            youtube_music_manage_dependencies=True,
            youtube_music_auto_update_dependencies=False,
            youtube_music_dependency_update_interval_hours=48,
            youtube_music_dependency_last_auto_update_epoch=1700000000,
        )

        payload = settings.to_dict()
        restored_settings = AppSettings.from_dict(payload)

        self.assertTrue(payload["youtube_music_manage_dependencies"])
        self.assertFalse(payload["youtube_music_auto_update_dependencies"])
        self.assertEqual(payload["youtube_music_dependency_update_interval_hours"], 48)
        self.assertEqual(payload["youtube_music_dependency_last_auto_update_epoch"], 1700000000)
        self.assertTrue(restored_settings.youtube_music_manage_dependencies)
        self.assertFalse(restored_settings.youtube_music_auto_update_dependencies)
        self.assertEqual(restored_settings.youtube_music_dependency_update_interval_hours, 48)
        self.assertEqual(restored_settings.youtube_music_dependency_last_auto_update_epoch, 1700000000)

    def test_youtube_music_dependency_settings_are_clamped(self):
        restored_settings = AppSettings.from_dict(
            {
                "youtube_music_dependency_update_interval_hours": 0,
                "youtube_music_dependency_last_auto_update_epoch": -20,
            }
        )

        self.assertEqual(restored_settings.youtube_music_dependency_update_interval_hours, 1)
        self.assertEqual(restored_settings.youtube_music_dependency_last_auto_update_epoch, 0)


if __name__ == "__main__":
    unittest.main()