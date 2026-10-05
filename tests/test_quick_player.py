from __future__ import annotations

import os
import pathlib
import sys
import tempfile
import unittest


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.preferences.models import AppSettings
from player.quick_player.launch import format_time_ms, initial_volume, quick_player_paths


class QuickPlayerPathsTests(unittest.TestCase):
    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)

    def _file(self, name):
        path = os.path.join(self._directory.name, name)
        with open(path, "wb"):
            pass
        return path

    def test_audio_file_plays_in_the_quick_player(self):
        path = self._file("som.WAV")

        self.assertEqual(quick_player_paths([f'"{path}"'], AppSettings()), [os.path.abspath(path)])

    def test_disabled_preference_sends_everything_to_the_full_player(self):
        settings = AppSettings(quick_player_enabled=False)

        self.assertEqual(quick_player_paths([self._file("som.wav")], settings), [])

    def test_playlists_folders_links_and_missing_files_need_the_full_player(self):
        audio_path = self._file("som.mp3")
        requests = (
            [],
            [self._file("lista.m3u8")],
            [self._directory.name],
            ["https://example.invalid/stream.mp3"],
            [os.path.join(self._directory.name, "sumiu.mp3")],
            [audio_path, self._file("lista.m3u")],
        )

        for paths in requests:
            with self.subTest(paths=paths):
                self.assertEqual(quick_player_paths(paths, AppSettings()), [])

    def test_video_file_only_plays_when_video_output_is_disabled(self):
        path = self._file("clipe.mp4")

        self.assertEqual(
            quick_player_paths([path], AppSettings(disable_video_output=True)), [os.path.abspath(path)]
        )
        self.assertEqual(quick_player_paths([path], AppSettings(disable_video_output=False)), [])


class QuickPlayerVolumeTests(unittest.TestCase):
    def test_uses_the_session_volume_when_the_session_is_restored(self):
        settings = AppSettings(default_volume=80, restore_session_on_startup=True)

        self.assertEqual(initial_volume(settings, {"volume": 35}), 35)
        self.assertEqual(initial_volume(settings, {"volume": 400}), 100)

    def test_falls_back_to_the_default_volume(self):
        restoring = AppSettings(default_volume=80, restore_session_on_startup=True)
        not_restoring = AppSettings(default_volume=80, restore_session_on_startup=False)

        self.assertEqual(initial_volume(restoring, None), 80)
        self.assertEqual(initial_volume(restoring, {"volume": "alto"}), 80)
        self.assertEqual(initial_volume(not_restoring, {"volume": 35}), 80)


class QuickPlayerTimeFormatTests(unittest.TestCase):
    def test_formats_minutes_and_hours(self):
        self.assertEqual(format_time_ms(0), "0:00")
        self.assertEqual(format_time_ms(65_400), "1:05")
        self.assertEqual(format_time_ms(3_725_000), "1:02:05")
        self.assertEqual(format_time_ms(-1), "0:00")


if __name__ == "__main__":
    unittest.main()
