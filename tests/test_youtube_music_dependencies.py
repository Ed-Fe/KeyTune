from __future__ import annotations

import pathlib
import subprocess
import sys
import types
import unittest
from unittest.mock import patch


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.youtube_music.dependencies import (
    configure_youtube_dependency_management,
    ensure_yt_dlp_executable_available,
    import_ytmusicapi_module,
    install_or_update_youtube_dependencies,
    is_youtube_dependency_auto_update_due,
)
import player.youtube_music.dependencies as youtube_dependencies


class YouTubeMusicDependenciesTests(unittest.TestCase):
    def setUp(self):
        configure_youtube_dependency_management(
            managed_install_enabled=False,
            auto_update_enabled=True,
        )

    def test_auto_update_is_due_when_timestamp_is_missing(self):
        self.assertTrue(
            is_youtube_dependency_auto_update_due(
                0,
                interval_hours=24,
                now_epoch_seconds=1_000,
            )
        )

    def test_auto_update_is_not_due_before_interval(self):
        self.assertFalse(
            is_youtube_dependency_auto_update_due(
                1_000,
                interval_hours=24,
                now_epoch_seconds=1_000 + 60,
            )
        )

    def test_ensure_yt_dlp_raises_guidance_when_management_is_disabled(self):
        with patch("player.youtube_music.dependencies.yt_dlp_executable_available", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "Recursos adicionais"):
                ensure_yt_dlp_executable_available()

    def test_ensure_yt_dlp_attempts_install_when_management_is_enabled(self):
        configure_youtube_dependency_management(
            managed_install_enabled=True,
            auto_update_enabled=True,
            prefer_nightly_yt_dlp=True,
        )

        with patch(
            "player.youtube_music.dependencies.yt_dlp_executable_available",
            side_effect=[False, True],
        ):
            with patch.object(youtube_dependencies, "install_or_update_youtube_dependencies") as install_mock:
                ensure_yt_dlp_executable_available()

        install_mock.assert_called_once_with(force=False, include_prerelease=True)

    def test_import_ytmusicapi_attempts_install_when_management_is_enabled(self):
        configure_youtube_dependency_management(
            managed_install_enabled=True,
            auto_update_enabled=True,
        )

        fake_module = types.SimpleNamespace(__version__="1.11.5")
        with patch("player.youtube_music.dependencies.activate_youtube_dependency_target_dir"):
            with patch.object(youtube_dependencies, "install_or_update_youtube_dependencies") as install_mock:
                with patch.object(
                    youtube_dependencies.importlib,
                    "import_module",
                    side_effect=[ImportError("missing"), fake_module],
                ):
                    imported_module = import_ytmusicapi_module()

        self.assertIs(imported_module, fake_module)
        install_mock.assert_called_once_with(force=False, include_prerelease=False)

    def test_install_update_skips_work_when_all_dependencies_are_ready(self):
        with patch("player.youtube_music.dependencies.activate_youtube_dependency_target_dir"):
            with patch("player.youtube_music.dependencies._dependency_spec_available", return_value=True):
                with patch("player.youtube_music.dependencies._can_import_dependency", return_value=True):
                    with patch("player.youtube_music.dependencies.yt_dlp_executable_available", return_value=True):
                        with patch(
                            "player.youtube_music.dependencies.get_managed_yt_dlp_executable_path",
                            return_value=pathlib.Path("C:/tmp/ytmusic-bin/yt-dlp.exe"),
                        ):
                            with patch("pathlib.Path.is_file", return_value=True):
                                with patch(
                                    "player.youtube_music.dependencies.get_installed_youtube_dependency_versions",
                                    return_value={"yt-dlp": "2026.1.31", "ytmusicapi": "1.11.5"},
                                ):
                                    result = install_or_update_youtube_dependencies(force=False)

        self.assertFalse(result.updated)
        self.assertEqual(result.versions["yt-dlp"], "2026.1.31")

    def test_install_update_runs_pip_and_ytdlp_installer_when_forced(self):
        target_dir = pathlib.Path("C:/tmp/ytmusic-site-packages")
        completed_process = subprocess.CompletedProcess(
            args=["pip"],
            returncode=0,
            stdout="ok",
            stderr="",
        )

        with patch("player.youtube_music.dependencies.activate_youtube_dependency_target_dir", return_value=target_dir):
            with patch("player.youtube_music.dependencies._run_pip_install", return_value=completed_process) as run_mock:
                with patch("player.youtube_music.dependencies._can_import_dependency", return_value=True):
                    with patch(
                        "player.youtube_music.dependencies.get_managed_yt_dlp_executable_path",
                        return_value=pathlib.Path("C:/tmp/ytmusic-bin/yt-dlp.exe"),
                    ):
                        with patch(
                            "player.youtube_music.dependencies.install_or_update_yt_dlp_executable",
                            return_value="2026.1.31",
                        ) as ytdlp_install_mock:
                            with patch(
                                "player.youtube_music.dependencies.youtube_dependencies_available",
                                return_value=True,
                            ):
                                with patch(
                                    "player.youtube_music.dependencies.get_installed_youtube_dependency_versions",
                                    return_value={"yt-dlp": "2026.1.31", "ytmusicapi": "1.11.5"},
                                ):
                                    result = install_or_update_youtube_dependencies(
                                        force=True,
                                        timeout_seconds=33,
                                        include_prerelease=True,
                                    )

        self.assertTrue(result.updated)
        run_args, run_kwargs = run_mock.call_args
        command = run_args[0]
        self.assertIn("--target", command)
        self.assertIn(str(target_dir), command)
        self.assertIn("ytmusicapi", command)
        self.assertEqual(run_kwargs["timeout_seconds"], 33)
        ytdlp_install_mock.assert_called_once_with(
            force=True,
            include_prerelease=True,
            timeout_seconds=33,
        )


if __name__ == "__main__":
    unittest.main()
