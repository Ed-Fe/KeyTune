from __future__ import annotations

import pathlib
import sys
import unittest
from unittest.mock import Mock, patch


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import main
from player.single_instance import build_pipe_address


class MainArgumentFilteringTests(unittest.TestCase):
    def test_collect_initial_paths_discards_current_executable_argument(self):
        initial_paths = main._collect_initial_paths(
            [r"D:\git\Media-Player\dist\KeyTune.exe", r"C:\midia\track.mp3"],
            launch_targets=[r"D:\git\Media-Player\dist\KeyTune.exe", r"D:\git\Media-Player\src\main.py"],
        )

        self.assertEqual(initial_paths, [r"C:\midia\track.mp3"])

    def test_collect_initial_paths_keeps_regular_external_files(self):
        initial_paths = main._collect_initial_paths(
            [r"C:\midia\track.mp3", r"C:\playlists\favoritas.m3u8"],
            launch_targets=[r"D:\git\Media-Player\dist\KeyTune.exe", r"D:\git\Media-Player\src\main.py"],
        )

        self.assertEqual(
            initial_paths,
            [r"C:\midia\track.mp3", r"C:\playlists\favoritas.m3u8"],
        )

    def test_development_instance_uses_a_separate_pipe(self):
        self.assertEqual(build_pipe_address(dev_mode=False), r"\\.\pipe\KeyTune_SingleInstance")
        self.assertEqual(build_pipe_address(dev_mode=True), r"\\.\pipe\KeyTune_SingleInstance_Dev")

    @patch("player.smtc.SmtcService")
    def test_smtc_smoke_test_starts_and_stops_service(self, service_class):
        service = Mock()
        service.start.return_value = True
        service_class.return_value = service

        result = main._run_smtc_smoke_test()

        self.assertEqual(result, 0)
        service.start.assert_called_once_with()
        service.stop.assert_called_once_with()

    @patch("player.smtc.SmtcService")
    def test_smtc_smoke_test_fails_when_service_cannot_start(self, service_class):
        service = Mock()
        service.start.return_value = False
        service_class.return_value = service

        result = main._run_smtc_smoke_test()

        self.assertEqual(result, 1)
        service.stop.assert_not_called()

    @patch("player.youtube_music.dependencies.import_ytmusicapi_module")
    def test_youtube_dependencies_smoke_test_imports_optional_package(self, import_ytmusicapi):
        result = main._run_youtube_dependencies_smoke_test()

        self.assertEqual(result, 0)
        import_ytmusicapi.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
