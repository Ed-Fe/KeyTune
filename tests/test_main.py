from __future__ import annotations

import pathlib
import sys
import unittest


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import main


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


if __name__ == "__main__":
    unittest.main()