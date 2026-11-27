"""Modo portátil: marcador, pasta data e atualização por zip."""

from __future__ import annotations

import hashlib
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import patch


SRC_ROOT = pathlib.Path(__file__).resolve().parents[1] / "src"
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.log import get_log_dir
from player.mpv_runtime import _runtime_cache_path
from player.optional_resources import get_optional_resource_dir
from player.plugins.service import PluginService
from player.portable import (
    PORTABLE_DIR_ENV,
    PORTABLE_MARKER_NAME,
    application_dir,
    is_portable,
    portable_data_dir,
    portable_storage_warning,
)
from player.preferences.storage import _get_storage_dir as preferences_storage_dir, load_settings
from player.session import get_app_storage_dir
from player.smart_library.database import default_database_path
from player.update import service as update_service
from player.portable_update import PORTABLE_UPDATE_LOG_NAME, PortableApplyError, apply_portable_update
from player.update.portable_apply import launch_portable_update
from player.constants import WINDOWS_UPDATER_EXECUTABLE_NAME
from player.youtube_music.auth import _get_storage_dir as auth_storage_dir
from player.youtube_music.auth import get_browser_auth_file_path
from player.youtube_music.feedback_store import FEEDBACK_FILE_NAME, YouTubeMusicFeedbackStore
from player.youtube_music.notification_store import NOTIFICATIONS_FILE_NAME, YouTubeNotificationStore
from player.youtube_music.youtubejs_runtime import _youtubejs_cache_dir
from player.youtube_music.yt_dlp_runtime import get_managed_yt_dlp_dir
from player.download.ffmpeg import get_managed_ffmpeg_dir
from player.interface_sounds.custom import custom_sounds_dir


def _same(path) -> str:
    # resolve() alinha o nome curto do temporário (EDUARD~1) com o nome longo.
    return os.path.normcase(str(pathlib.Path(path).resolve()))


def _process_output(completed: subprocess.CompletedProcess) -> str:
    chunks = []
    for stream in (completed.stdout, completed.stderr):
        if not stream:
            continue
        if isinstance(stream, bytes):
            chunks.append(stream.decode("utf-8", errors="replace"))
        else:
            chunks.append(str(stream))
    return "".join(chunks)


def _zip_names(archive: pathlib.Path) -> set[str]:
    with zipfile.ZipFile(archive) as bundle:
        names = set()
        for name in bundle.namelist():
            normalized = name.replace("\\", "/").lstrip("./")
            if normalized:
                names.add(normalized)
        return names


class PortableDetectionTests(unittest.TestCase):
    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.root = pathlib.Path(self._temporary.name)

    def _without_env(self):
        return patch.dict(os.environ, {}, clear=False)

    def test_frozen_with_empty_marker_is_portable(self):
        executable = self.root / "KeyTune.exe"
        executable.write_bytes(b"")
        (self.root / PORTABLE_MARKER_NAME).write_text("", encoding="utf-8")
        with self._without_env():
            os.environ.pop(PORTABLE_DIR_ENV, None)
            with patch.object(sys, "frozen", True, create=True), patch.object(sys, "executable", str(executable)):
                self.assertTrue(is_portable())
                self.assertEqual(_same(application_dir()), _same(self.root))
                self.assertEqual(_same(portable_data_dir()), _same(self.root / "data"))
                self.assertTrue((self.root / "data").is_dir())

    def test_frozen_without_marker_is_not_portable(self):
        executable = self.root / "KeyTune.exe"
        executable.write_bytes(b"")
        with self._without_env():
            os.environ.pop(PORTABLE_DIR_ENV, None)
            with patch.object(sys, "frozen", True, create=True), patch.object(sys, "executable", str(executable)):
                self.assertFalse(is_portable())
                with self.assertRaises(RuntimeError):
                    portable_data_dir()

    def test_development_ignores_a_marker_next_to_the_executable(self):
        executable = self.root / "python.exe"
        executable.write_bytes(b"")
        (self.root / PORTABLE_MARKER_NAME).write_text("x", encoding="utf-8")
        with self._without_env():
            os.environ.pop(PORTABLE_DIR_ENV, None)
            with patch.object(sys, "frozen", False, create=True), patch.object(sys, "executable", str(executable)):
                self.assertFalse(is_portable())

    def test_marker_directory_does_not_count(self):
        executable = self.root / "KeyTune.exe"
        executable.write_bytes(b"")
        (self.root / PORTABLE_MARKER_NAME).mkdir()
        with self._without_env():
            os.environ.pop(PORTABLE_DIR_ENV, None)
            with patch.object(sys, "frozen", True, create=True), patch.object(sys, "executable", str(executable)):
                self.assertFalse(is_portable())

    def test_env_dir_forces_portable_mode_in_development(self):
        with patch.dict(os.environ, {PORTABLE_DIR_ENV: str(self.root)}), patch.object(sys, "frozen", False, create=True):
            self.assertTrue(is_portable())
            self.assertEqual(_same(portable_data_dir()), _same(self.root / "data"))

    def test_env_dir_wins_over_the_frozen_executable_directory(self):
        frozen_dir = self.root / "frozen"
        frozen_dir.mkdir()
        other = self.root / "override"
        other.mkdir()
        executable = frozen_dir / "KeyTune.exe"
        executable.write_bytes(b"")
        with patch.dict(os.environ, {PORTABLE_DIR_ENV: str(other)}), patch.object(sys, "frozen", True, create=True), patch.object(
            sys, "executable", str(executable)
        ):
            self.assertTrue(is_portable())
            self.assertEqual(_same(application_dir()), _same(other))

    def test_missing_env_dir_is_ignored(self):
        missing = self.root / "missing"
        with self._without_env():
            os.environ[PORTABLE_DIR_ENV] = str(missing)
            with patch.object(sys, "frozen", False, create=True):
                self.assertFalse(is_portable())


class PortableStorageTests(unittest.TestCase):
    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        root = pathlib.Path(self._temporary.name)
        self.appdata = root / "appdata"
        self.config = root / "config"
        self.cache = root / "cache"
        self.portable_root = root / "portable"
        for directory in (self.appdata, self.config, self.cache, self.portable_root):
            directory.mkdir()
        self._base_env = {
            "APPDATA": str(self.appdata),
            "XDG_CONFIG_HOME": str(self.config),
            "XDG_CACHE_HOME": str(self.cache),
        }

    def _installed_env(self):
        return patch.dict(os.environ, self._base_env, clear=False)

    def _portable_env(self):
        env = dict(self._base_env)
        env[PORTABLE_DIR_ENV] = str(self.portable_root)
        return patch.dict(os.environ, env, clear=False)

    def _drop_portable_env(self):
        os.environ.pop(PORTABLE_DIR_ENV, None)

    def _paths(self) -> dict[str, str]:
        return {
            "storage": get_app_storage_dir(),
            "preferences": preferences_storage_dir(),
            "auth": auth_storage_dir(),
            "auth_file": get_browser_auth_file_path(),
            "youtubejs": _youtubejs_cache_dir(),
            "logs": get_log_dir(),
            "optional": str(get_optional_resource_dir("node")),
            "yt_dlp": str(get_managed_yt_dlp_dir()),
            "ffmpeg": str(get_managed_ffmpeg_dir()),
            "library": default_database_path(),
            "plugins": str(PluginService().plugins_dir),
            "sounds": str(custom_sounds_dir()),
            "feedback": YouTubeMusicFeedbackStore().path,
            "notifications": YouTubeNotificationStore().path,
            "pending_update": str(update_service._pending_update_path()),
            "mpv_cache": str(_runtime_cache_path()),
        }

    def _expected_config_root(self) -> str:
        if os.name == "nt":
            return str(self.appdata)
        return str(self.config)

    def _expected_cache_root(self) -> str:
        if os.name == "nt":
            return str(self.appdata)
        return str(self.cache)

    def test_installed_paths_keep_the_current_locations(self):
        legacy = pathlib.Path(self._expected_config_root()) / "KeyTuneVLC"
        legacy.mkdir()
        with self._installed_env():
            self._drop_portable_env()
            self.assertFalse(is_portable())
            storage = get_app_storage_dir()
            self.assertEqual(_same(storage), _same(legacy))
            self.assertFalse((pathlib.Path(self._expected_config_root()) / "KeyTune").exists())

            auth_dir = auth_storage_dir()
            self.assertEqual(_same(auth_dir), _same(pathlib.Path(self._expected_config_root()) / "KeyTune"))
            self.assertNotEqual(_same(auth_dir), _same(legacy))

            cache = _youtubejs_cache_dir()
            self.assertEqual(
                _same(cache),
                _same(pathlib.Path(self._expected_cache_root()) / "KeyTune" / "youtubejs-cache"),
            )

    def test_paths_move_under_data_only_while_portable(self):
        with self._installed_env():
            self._drop_portable_env()
            installed = {name: _same(path) for name, path in self._paths().items()}

        with self._portable_env():
            self.assertTrue(is_portable())
            data = _same(self.portable_root / "data")
            portable = self._paths()
            for name, path in portable.items():
                normalized = _same(path)
                self.assertNotEqual(normalized, installed[name], name)
                self.assertTrue(
                    normalized == data or normalized.startswith(data + os.sep),
                    f"{name} ficou fora de data: {path}",
                )
            self.assertEqual(_same(portable["storage"]), data)
            self.assertEqual(_same(portable["preferences"]), data)
            self.assertEqual(_same(portable["auth"]), data)
            self.assertEqual(_same(portable["auth_file"]), _same(pathlib.Path(data) / "ytmusic_browser.json"))
            self.assertEqual(_same(portable["youtubejs"]), _same(pathlib.Path(data) / "youtubejs-cache"))
            self.assertEqual(_same(portable["logs"]), _same(pathlib.Path(data) / "logs"))
            self.assertEqual(_same(portable["library"]), _same(pathlib.Path(data) / "smart_library.db"))
            self.assertEqual(_same(portable["plugins"]), _same(pathlib.Path(data) / "plugins"))
            self.assertEqual(_same(portable["sounds"]), _same(pathlib.Path(data) / "interface_sounds"))
            self.assertEqual(_same(portable["feedback"]), _same(pathlib.Path(data) / FEEDBACK_FILE_NAME))
            self.assertEqual(_same(portable["notifications"]), _same(pathlib.Path(data) / NOTIFICATIONS_FILE_NAME))
            self.assertEqual(_same(portable["pending_update"]), _same(pathlib.Path(data) / "pending_update.json"))
            self.assertTrue(_same(portable["optional"]).startswith(_same(pathlib.Path(data) / "resources")))
            self.assertTrue(_same(portable["yt_dlp"]).startswith(_same(pathlib.Path(data) / "resources")))
            self.assertTrue(_same(portable["ffmpeg"]).startswith(_same(pathlib.Path(data) / "resources")))
            self.assertTrue(_same(portable["mpv_cache"]).startswith(data))

        with self._installed_env():
            self._drop_portable_env()
            again = {name: _same(path) for name, path in self._paths().items()}
        self.assertEqual(again, installed)

    def test_unwritable_data_falls_back_to_local_settings_and_stays_portable(self):
        data = self.portable_root / "data"
        data.mkdir()
        local = pathlib.Path(self._expected_config_root()) / "KeyTune"
        local.mkdir()
        (local / "settings.json").write_text('{"language": "es"}', encoding="utf-8")
        with self._portable_env(), patch(
            "player.portable.tempfile.NamedTemporaryFile", side_effect=PermissionError("read-only volume")
        ) as probe, self.assertLogs("keytune.portable", "WARNING") as log:
            self.assertEqual(load_settings().language, "es")
            self.assertTrue(is_portable())
            self.assertEqual(_same(portable_data_dir()), _same(local))
            self.assertEqual(_same(auth_storage_dir()), _same(local))
            self.assertEqual(_same(portable_storage_warning()[0]), _same(data))

        self.assertIn("read-only volume", log.output[0])
        probe.assert_called_once()

    def test_data_creation_failure_uses_the_current_local_folder(self):
        local = pathlib.Path(self._expected_config_root()) / "KeyTune"
        (local.parent / "KeyTuneVLC").mkdir()
        original_mkdir = pathlib.Path.mkdir

        def mkdir(path, *args, **kwargs):
            if path == self.portable_root.resolve() / "data":
                raise PermissionError("read-only volume")
            return original_mkdir(path, *args, **kwargs)

        with self._portable_env(), patch.object(pathlib.Path, "mkdir", mkdir):
            self.assertEqual(_same(get_app_storage_dir()), _same(local))
            self.assertTrue(local.is_dir())
            self.assertTrue(is_portable())


class PortableUpdateSelectionTests(unittest.TestCase):
    ASSETS = [
        {"name": "KeyTune-Setup.exe", "browser_download_url": "https://example.invalid/setup"},
        {"name": "KeyTune-Setup.exe.sha256", "browser_download_url": "https://example.invalid/setup.sha"},
        {"name": "KeyTune-Portable.zip", "browser_download_url": "https://example.invalid/portable"},
        {"name": "KeyTune-Portable.zip.sha256", "browser_download_url": "https://example.invalid/portable.sha"},
        {"name": "release-notes.en.md", "browser_download_url": "https://example.invalid/notes"},
    ]

    def test_installed_mode_keeps_the_setup_assets(self):
        with patch("player.portable.is_portable", return_value=False):
            archive = update_service._select_archive_asset(self.ASSETS)
            checksum = update_service._select_checksum_asset(self.ASSETS)
        self.assertEqual(archive["name"], "KeyTune-Setup.exe")
        self.assertEqual(checksum["name"], "KeyTune-Setup.exe.sha256")

    def test_portable_mode_selects_the_zip_and_its_checksum(self):
        with patch("player.portable.is_portable", return_value=True):
            archive = update_service._select_archive_asset(self.ASSETS)
            checksum = update_service._select_checksum_asset(self.ASSETS)
        self.assertEqual(archive["name"], "KeyTune-Portable.zip")
        self.assertEqual(checksum["name"], "KeyTune-Portable.zip.sha256")

    def test_portable_mode_does_not_fall_back_to_the_installer(self):
        assets = [asset for asset in self.ASSETS if "Portable" not in asset["name"]]
        with patch("player.portable.is_portable", return_value=True):
            self.assertIsNone(update_service._select_archive_asset(assets))
            self.assertIsNone(update_service._select_checksum_asset(assets))

    def test_installed_checksum_fallback_skips_the_portable_hash(self):
        assets = [
            {"name": "KeyTune-Portable.zip.sha256"},
            {"name": "notes.sha256"},
        ]
        with patch("player.portable.is_portable", return_value=False):
            checksum = update_service._select_checksum_asset(assets)
        self.assertEqual(checksum["name"], "notes.sha256")

    def test_portable_download_requires_a_checksum_before_the_network(self):
        info = update_service.UpdateInfo(
            current_version="1.0.0",
            latest_version="1.0.1",
            release_name="1.0.1",
            release_page_url="https://example.invalid",
            release_notes="",
            archive_name="KeyTune-Portable.zip",
            archive_url="https://example.invalid/KeyTune-Portable.zip",
            archive_size_bytes=1,
        )
        with patch("player.portable.is_portable", return_value=True):
            with self.assertRaises(update_service.UpdateError) as caught:
                update_service.download_release_archive(info)
        self.assertIn("integridade", str(caught.exception))


class PortableApplyTests(unittest.TestCase):
    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.root = pathlib.Path(self._temporary.name)

    def _apply(self, archive: pathlib.Path, app_dir: pathlib.Path, **kwargs):
        apply_portable_update(
            app_dir,
            archive,
            restart_executable="KeyTune.exe",
            parent_pid=2147483647,
            relaunch=False,
            retry_pause_seconds=0,
            **kwargs,
        )

    def test_apply_preserves_marker_and_data_and_replaces_program_files(self):
        app_dir = self.root / "app"
        (app_dir / "mpv").mkdir(parents=True)
        (app_dir / "data").mkdir()
        (app_dir / "KeyTune.exe").write_bytes(b"old")
        (app_dir / "portable.ini").write_text("keep-me\n", encoding="utf-8")
        (app_dir / "data" / "settings.json").write_text("user", encoding="utf-8")
        (app_dir / "mpv" / "old.txt").write_text("old-mpv", encoding="utf-8")
        (app_dir / "mpv" / "lib.txt").write_text("old-lib", encoding="utf-8")
        (app_dir / "extra.txt").write_text("user-file", encoding="utf-8")

        archive = self.root / "KeyTune-Portable.zip"
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("KeyTune.exe", b"new")
            bundle.writestr("PORTABLE.INI", b"")
            bundle.writestr("mpv/lib.txt", b"new-lib")
            bundle.writestr("docs/readme.txt", b"doc")

        self._apply(archive, app_dir)
        self.assertEqual((app_dir / "KeyTune.exe").read_bytes(), b"new")
        self.assertEqual((app_dir / "portable.ini").read_text(encoding="utf-8"), "keep-me\n")
        self.assertEqual((app_dir / "data" / "settings.json").read_text(encoding="utf-8"), "user")
        self.assertFalse((app_dir / "mpv" / "old.txt").exists())
        self.assertEqual((app_dir / "mpv" / "lib.txt").read_text(encoding="utf-8"), "new-lib")
        self.assertEqual((app_dir / "docs" / "readme.txt").read_text(encoding="utf-8"), "doc")
        self.assertEqual((app_dir / "extra.txt").read_text(encoding="utf-8"), "user-file")
        self.assertIn("conclu", (app_dir / "data" / PORTABLE_UPDATE_LOG_NAME).read_text(encoding="utf-8"))

    def test_missing_marker_is_copied_from_the_archive(self):
        app_dir = self.root / "app"
        app_dir.mkdir()
        (app_dir / "KeyTune.exe").write_bytes(b"old")
        archive = self.root / "KeyTune-Portable.zip"
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("KeyTune.exe", b"new")
            bundle.writestr("portable.ini", b"from-zip")

        self._apply(archive, app_dir)
        self.assertEqual((app_dir / "portable.ini").read_bytes(), b"from-zip")

    def test_single_wrapping_folder_is_unpacked_at_the_app_root(self):
        app_dir = self.root / "app"
        app_dir.mkdir()
        (app_dir / "KeyTune.exe").write_bytes(b"old")
        archive = self.root / "wrapped.zip"
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("KeyTune/KeyTune.exe", b"nested")
            bundle.writestr("KeyTune/readme.txt", b"hi")

        self._apply(archive, app_dir)
        self.assertEqual((app_dir / "KeyTune.exe").read_bytes(), b"nested")
        self.assertEqual((app_dir / "readme.txt").read_bytes(), b"hi")
        self.assertFalse((app_dir / "KeyTune" / "KeyTune.exe").exists())

    def test_locked_file_is_retried(self):
        app_dir = self.root / "app"
        app_dir.mkdir()
        (app_dir / "KeyTune.exe").write_bytes(b"old")
        archive = self.root / "KeyTune-Portable.zip"
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("KeyTune.exe", b"new")
        real_copy = __import__("shutil").copy2
        calls = {"count": 0}

        def flaky(source, destination, *args, **kwargs):
            calls["count"] += 1
            if calls["count"] < 3:
                raise OSError("locked")
            return real_copy(source, destination, *args, **kwargs)

        with patch("player.portable_update.shutil.copy2", side_effect=flaky):
            self._apply(archive, app_dir, copy_attempts=5)
        self.assertEqual((app_dir / "KeyTune.exe").read_bytes(), b"new")
        self.assertGreaterEqual(calls["count"], 3)

    def test_failed_copy_restores_the_previous_files_and_reopens_the_old_program(self):
        app_dir = self.root / "app"
        (app_dir / "mpv").mkdir(parents=True)
        (app_dir / "data").mkdir()
        (app_dir / "KeyTune.exe").write_bytes(b"old-exe")
        (app_dir / "keep.txt").write_bytes(b"old")
        (app_dir / "mpv" / "old.txt").write_text("old-mpv", encoding="utf-8")
        (app_dir / "portable.ini").write_text("keep-me\n", encoding="utf-8")
        (app_dir / "data" / "settings.json").write_text("user", encoding="utf-8")
        archive = self.root / "KeyTune-Portable.zip"
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("KeyTune.exe", b"new-exe")
            bundle.writestr("keep.txt", b"new")
            bundle.writestr("added.txt", b"fresh")
            bundle.writestr("mpv/lib.txt", b"new-lib")
            bundle.writestr("portable.ini", b"")
            bundle.writestr("zzz-fail.txt", b"x")

        real_copy = __import__("shutil").copy2

        def fail_last(source, destination, *args, **kwargs):
            if pathlib.Path(source).name == "zzz-fail.txt":
                raise OSError("locked")
            return real_copy(source, destination, *args, **kwargs)

        with patch("player.portable_update.shutil.copy2", side_effect=fail_last), patch(
            "player.portable_update.subprocess.Popen"
        ) as popen:
            with self.assertRaises(PortableApplyError) as caught:
                apply_portable_update(
                    app_dir,
                    archive,
                    restart_executable="KeyTune.exe",
                    parent_pid=2147483647,
                    relaunch=True,
                    copy_attempts=1,
                    retry_pause_seconds=0,
                )
        self.assertIn("restaurada", str(caught.exception))
        self.assertEqual((app_dir / "KeyTune.exe").read_bytes(), b"old-exe")
        self.assertEqual((app_dir / "keep.txt").read_bytes(), b"old")
        self.assertFalse((app_dir / "added.txt").exists())
        self.assertFalse((app_dir / "zzz-fail.txt").exists())
        self.assertEqual((app_dir / "mpv" / "old.txt").read_text(encoding="utf-8"), "old-mpv")
        self.assertFalse((app_dir / "mpv" / "lib.txt").exists())
        self.assertEqual((app_dir / "portable.ini").read_text(encoding="utf-8"), "keep-me\n")
        self.assertEqual((app_dir / "data" / "settings.json").read_text(encoding="utf-8"), "user")
        log_text = (app_dir / "data" / PORTABLE_UPDATE_LOG_NAME).read_text(encoding="utf-8")
        self.assertIn("restaurada", log_text)
        popen.assert_called_once()
        self.assertEqual(_same(popen.call_args.args[0][0]), _same(app_dir / "KeyTune.exe"))
        self.assertNotIn("VERYSILENT", " ".join(popen.call_args.args[0]))


class PortableUpdateLaunchTests(unittest.TestCase):
    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.root = pathlib.Path(self._temporary.name)
        self.app_dir = self.root / "app"
        self.app_dir.mkdir()
        self.archive = self.root / "KeyTune-Portable.zip"
        self.archive.write_bytes(b"zip")
        (self.app_dir / WINDOWS_UPDATER_EXECUTABLE_NAME).write_bytes(b"updater")

    def test_helper_is_started_without_the_installer_and_records_the_pending_update(self):
        with patch.dict(os.environ, {PORTABLE_DIR_ENV: str(self.app_dir)}), patch.object(
            update_service, "can_self_update", return_value=True
        ), patch("player.update.portable_apply.subprocess.Popen") as popen:
            launch_portable_update(self.archive, target_version="9.9.9")

        command = popen.call_args.args[0]
        rendered = " ".join(command)
        self.assertTrue(command[0].endswith(WINDOWS_UPDATER_EXECUTABLE_NAME))
        self.assertNotEqual(_same(pathlib.Path(command[0]).parent), _same(self.app_dir))
        self.assertTrue(pathlib.Path(command[0]).is_file())
        self.assertNotIn("VERYSILENT", rendered)
        self.assertNotIn("KeyTune-Setup.exe", rendered)
        self.assertNotIn("powershell.exe", command[0].lower())
        self.assertEqual(_same(command[command.index("--app-dir") + 1]), _same(self.app_dir))
        self.assertIn("--parent-pid", command)
        self.assertIn("--restart-executable", command)
        pending = self.app_dir / "data" / "pending_update.json"
        self.assertIn("9.9.9", pending.read_text(encoding="utf-8"))
        self.assertFalse((self.app_dir / "keytune-update-probe.tmp").exists())

    def test_a_failed_launch_clears_the_pending_update(self):
        with patch.dict(os.environ, {PORTABLE_DIR_ENV: str(self.app_dir)}), patch.object(
            update_service, "can_self_update", return_value=True
        ), patch("player.update.portable_apply.subprocess.Popen", side_effect=OSError("no powershell")):
            with self.assertRaises(update_service.UpdateError):
                launch_portable_update(self.archive, target_version="9.9.9")
        self.assertFalse((self.app_dir / "data" / "pending_update.json").exists())

    def test_installed_mode_does_not_start_the_helper(self):
        with patch.dict(os.environ, {}, clear=False), patch.object(update_service, "can_self_update", return_value=True), patch(
            "player.update.portable_apply.subprocess.Popen"
        ) as popen:
            os.environ.pop(PORTABLE_DIR_ENV, None)
            with self.assertRaises(update_service.UpdateError):
                launch_portable_update(self.archive, target_version="9.9.9")
        popen.assert_not_called()

    def test_unwritable_folder_is_reported_before_closing_the_app(self):
        with patch.dict(os.environ, {PORTABLE_DIR_ENV: str(self.app_dir)}), patch.object(
            update_service, "can_self_update", return_value=True
        ), patch("player.update.portable_apply.subprocess.Popen") as popen, patch(
            "player.update.portable_apply.tempfile.NamedTemporaryFile", side_effect=PermissionError("denied")
        ):
            with self.assertRaises(update_service.UpdateError) as caught:
                launch_portable_update(self.archive, target_version="9.9.9")
        self.assertIn("permissão de escrita", str(caught.exception))
        popen.assert_not_called()
        self.assertFalse((self.app_dir / "data" / "pending_update.json").exists())


@unittest.skipUnless(sys.platform.startswith("win"), "o pacote portátil é gerado no Windows")
class PortablePackageScriptTests(unittest.TestCase):
    def test_zip_contains_the_app_folder_plus_an_empty_marker_and_a_checksum(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            source = root / "KeyTune"
            (source / "docs").mkdir(parents=True)
            (source / "data").mkdir()
            (source / "KeyTune.exe").write_bytes(b"exe")
            (source / "docs" / "manual.md").write_text("oi", encoding="utf-8")
            (source / "data" / "secret.txt").write_text("secret", encoding="utf-8")
            updater = root / WINDOWS_UPDATER_EXECUTABLE_NAME
            updater.write_bytes(b"updater")
            destination = root / "dist" / "KeyTune-Portable.zip"
            completed = subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(PROJECT_ROOT / "scripts" / "package_portable_zip.ps1"),
                    "-SourceDir",
                    str(source),
                    "-DestinationZip",
                    str(destination),
                    "-ExtraFile",
                    str(updater),
                ],
                capture_output=True,
                timeout=60,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            self.assertEqual(completed.returncode, 0, _process_output(completed))
            self.assertTrue(destination.is_file())
            self.assertFalse((source / "portable.ini").exists())
            self.assertTrue((source / "data" / "secret.txt").is_file())
            names = _zip_names(destination)
            self.assertIn("KeyTune.exe", names)
            self.assertIn("docs/manual.md", names)
            self.assertIn("portable.ini", names)
            self.assertIn(WINDOWS_UPDATER_EXECUTABLE_NAME, names)
            self.assertFalse((source / WINDOWS_UPDATER_EXECUTABLE_NAME).exists())
            self.assertFalse(any(name == "data" or name.startswith("data/") for name in names))
            with zipfile.ZipFile(destination) as bundle:
                marker_name = next(name for name in bundle.namelist() if name.replace("\\", "/").endswith("portable.ini"))
                self.assertEqual(bundle.read(marker_name), b"")
            checksum_path = pathlib.Path(str(destination) + ".sha256")
            checksum = checksum_path.read_text(encoding="ascii")
            digest = hashlib.sha256(destination.read_bytes()).hexdigest()
            self.assertTrue(checksum.lower().startswith(digest + "  "))
            self.assertIn("KeyTune-Portable.zip", checksum)


if __name__ == "__main__":
    unittest.main()
