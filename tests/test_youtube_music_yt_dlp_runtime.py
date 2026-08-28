from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest
from subprocess import CompletedProcess
from unittest.mock import patch


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import player.youtube_music.yt_dlp_runtime as yt_dlp_runtime


class YouTubeMusicYtDlpRuntimeTests(unittest.TestCase):
    def test_find_all_available_javascript_runtimes_filters_unsupported_versions(self):
        version_outputs = {
            "C:/runtime/deno": "deno 2.3.1\nv8 13.0",
            "C:/runtime/node": "v22.1.0",
            "C:/runtime/qjs": "QuickJS version 2025-04-26",
            "C:/runtime/bun": "1.3.15",
        }

        with patch(
            "player.youtube_music.yt_dlp_runtime._find_javascript_runtime_executable",
            side_effect=lambda executable_name: f"C:/runtime/{executable_name}",
        ), patch(
            "player.youtube_music.yt_dlp_runtime._get_executable_version_output",
            side_effect=lambda executable_path, _args: version_outputs[executable_path],
        ):
            discovered = yt_dlp_runtime.find_all_available_javascript_runtimes()
            incompatible = yt_dlp_runtime.find_incompatible_javascript_runtimes()

        self.assertEqual(
            discovered,
            {
                "deno": "C:/runtime/deno",
                "node": "C:/runtime/node",
                "quickjs": "C:/runtime/qjs",
            },
        )
        self.assertEqual(incompatible, {"bun": "1.3.15"})

    def test_inspect_javascript_runtimes_rejects_outdated_versions(self):
        version_outputs = {
            "C:/runtime/deno": "deno 2.2.9",
            "C:/runtime/node": "v20.19.4",
            "C:/runtime/qjs": "QuickJS version 2023-12-08",
            "C:/runtime/bun": "1.2.10",
        }

        with patch(
            "player.youtube_music.yt_dlp_runtime._find_javascript_runtime_executable",
            side_effect=lambda executable_name: f"C:/runtime/{executable_name}",
        ), patch(
            "player.youtube_music.yt_dlp_runtime._get_executable_version_output",
            side_effect=lambda executable_path, _args: version_outputs[executable_path],
        ):
            runtime_infos = yt_dlp_runtime.inspect_javascript_runtimes()

        self.assertTrue(runtime_infos)
        self.assertTrue(all(not runtime_info.supported for runtime_info in runtime_infos))

    def test_inspect_javascript_runtimes_accepts_quickjs_ng(self):
        with patch(
            "player.youtube_music.yt_dlp_runtime._find_javascript_runtime_executable",
            side_effect=lambda executable_name: "C:/runtime/qjs" if executable_name == "qjs" else "",
        ), patch(
            "player.youtube_music.yt_dlp_runtime._get_executable_version_output",
            return_value="QuickJS-ng version 0.10.1",
        ):
            runtime_infos = yt_dlp_runtime.inspect_javascript_runtimes()

        self.assertEqual(len(runtime_infos), 1)
        self.assertEqual(runtime_infos[0].runtime_name, "quickjs")
        self.assertTrue(runtime_infos[0].supported)

    def test_find_javascript_runtime_executable_checks_yt_dlp_directory(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            runtime_dir = pathlib.Path(temporary_dir)
            yt_dlp_path = runtime_dir / yt_dlp_runtime.YTDLP_EXECUTABLE_NAME
            runtime_path = runtime_dir / (
                "node.exe" if sys.platform.startswith("win") else "node"
            )
            yt_dlp_path.touch()
            runtime_path.touch()

            with patch("player.youtube_music.yt_dlp_runtime.shutil.which", return_value=None), patch(
                "player.youtube_music.yt_dlp_runtime.find_yt_dlp_executable_path",
                return_value=yt_dlp_path,
            ):
                discovered_path = yt_dlp_runtime._find_javascript_runtime_executable("node")

        self.assertEqual(pathlib.Path(discovered_path), runtime_path)

    def test_download_media_uses_managed_runtime_and_returns_safe_paths(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            destination = pathlib.Path(temporary_dir) / "downloads"
            executable = pathlib.Path(temporary_dir) / yt_dlp_runtime.YTDLP_EXECUTABLE_NAME
            executable.touch()

            def run(command, **_kwargs):
                downloaded = destination / "video.mp4"
                downloaded.parent.mkdir(parents=True, exist_ok=True)
                downloaded.write_bytes(b"video")
                self.assertIn("--ignore-config", command)
                self.assertIn("--no-playlist", command)
                self.assertIn("best[ext=mp4]/best", command)
                self.assertEqual(command[-1], "https://youtu.be/example")
                return CompletedProcess(command, 0, stdout=str(downloaded), stderr="")

            with patch(
                "player.youtube_music.yt_dlp_runtime.find_yt_dlp_executable_path",
                return_value=executable,
            ), patch("player.youtube_music.yt_dlp_runtime.subprocess.run", side_effect=run):
                result = yt_dlp_runtime.download_media(
                    "https://youtu.be/example",
                    destination_directory=str(destination),
                )

        self.assertEqual(result, [str(destination / "video.mp4")])

    def test_download_media_rejects_paths_in_filename_template(self):
        with tempfile.TemporaryDirectory() as temporary_dir, patch(
            "player.youtube_music.yt_dlp_runtime.find_yt_dlp_executable_path",
            return_value=pathlib.Path(temporary_dir) / "yt-dlp",
        ):
            with self.assertRaises(RuntimeError):
                yt_dlp_runtime.download_media(
                    "https://youtu.be/example",
                    destination_directory=temporary_dir,
                    filename_template="../escape.%(ext)s",
                )


if __name__ == "__main__":
    unittest.main()
