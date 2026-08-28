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

    def test_autodj_settings_round_trip_and_reject_invalid_choices(self):
        settings = AppSettings(
            autodj_enabled=True,
            autodj_transition_sounds_enabled=True,
            autodj_profile="electronic",
            autodj_beats=32,
        )

        restored_settings = AppSettings.from_dict(settings.to_dict())

        self.assertTrue(restored_settings.autodj_enabled)
        self.assertTrue(restored_settings.autodj_transition_sounds_enabled)
        self.assertEqual(restored_settings.autodj_profile, "electronic")
        self.assertEqual(restored_settings.autodj_beats, 32)

        invalid_settings = AppSettings.from_dict(
            {"autodj_enabled": True, "autodj_profile": "aggressive", "autodj_beats": 12}
        )
        self.assertTrue(invalid_settings.autodj_enabled)
        self.assertEqual(invalid_settings.autodj_profile, "smooth")
        self.assertEqual(invalid_settings.autodj_beats, 16)

    def test_smart_library_settings_round_trip(self):
        settings = AppSettings(
            smart_library_enabled=False,
            smart_library_index_opened_folders=False,
            smart_library_history_enabled=False,
            smart_library_history_limit=1200,
            smart_library_resume_enabled=False,
            smart_library_resume_minimum_minutes=25,
            smart_library_resume_edge_seconds=45,
            smart_library_cache_limit=9000,
            smart_library_indexed_folders=["C:\\Musica", "  ", "D:\\Podcasts"],
        )

        restored_settings = AppSettings.from_dict(settings.to_dict())

        self.assertFalse(restored_settings.smart_library_enabled)
        self.assertFalse(restored_settings.smart_library_index_opened_folders)
        self.assertFalse(restored_settings.smart_library_history_enabled)
        self.assertEqual(restored_settings.smart_library_history_limit, 1200)
        self.assertFalse(restored_settings.smart_library_resume_enabled)
        self.assertEqual(restored_settings.smart_library_resume_minimum_minutes, 25)
        self.assertEqual(restored_settings.smart_library_resume_edge_seconds, 45)
        self.assertEqual(restored_settings.smart_library_cache_limit, 9000)
        self.assertEqual(restored_settings.smart_library_indexed_folders, ["C:\\Musica", "D:\\Podcasts"])

    def test_smart_library_numbers_are_clamped(self):
        restored_settings = AppSettings.from_dict(
            {
                "smart_library_history_limit": 3,
                "smart_library_resume_minimum_minutes": 0,
                "smart_library_resume_edge_seconds": 9000,
                "smart_library_cache_limit": 1,
            }
        )

        self.assertEqual(restored_settings.smart_library_history_limit, 50)
        self.assertEqual(restored_settings.smart_library_resume_minimum_minutes, 1)
        self.assertEqual(restored_settings.smart_library_resume_edge_seconds, 300)
        self.assertEqual(restored_settings.smart_library_cache_limit, 100)

    def test_smart_library_resume_windows_are_exposed_in_milliseconds(self):
        settings = AppSettings(
            smart_library_resume_minimum_minutes=10,
            smart_library_resume_edge_seconds=30,
        )

        self.assertEqual(settings.smart_library_resume_minimum_ms, 600000)
        self.assertEqual(settings.smart_library_resume_edge_ms, 30000)

    def test_smart_library_defaults_survive_an_old_settings_file(self):
        restored_settings = AppSettings.from_dict({"default_volume": 70})

        self.assertTrue(restored_settings.smart_library_enabled)
        self.assertTrue(restored_settings.smart_library_history_enabled)
        self.assertTrue(restored_settings.smart_library_resume_enabled)
        self.assertEqual(restored_settings.smart_library_indexed_folders, [])


if __name__ == "__main__":
    unittest.main()
