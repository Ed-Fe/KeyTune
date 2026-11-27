from __future__ import annotations

import hashlib
import shutil
import sys
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch


SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player import portable_update
from player.update import service


class PortableUpdateRecoveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name).resolve()
        self.app = root / "app"
        self.app.mkdir()
        self.data = self.app / "data"
        self.data.mkdir()
        (self.data / "settings.json").write_bytes(b"user data")
        self.executable = self.app / "KeyTune.exe"
        self.executable.write_bytes(b"old program")
        self.package = root / "KeyTune-Portable.zip"

    def _write_package(self, entries):
        with zipfile.ZipFile(self.package, "w") as archive:
            for name, contents in entries.items():
                archive.writestr(name, contents)

    def _apply(self, **kwargs):
        portable_update.apply_portable_update(
            self.app, self.package,
            restart_executable=self.executable.name,
            copy_attempts=1, retry_pause_seconds=0,
            **kwargs,
        )

    def _download(self, cancel_event=None):
        info = service.UpdateInfo(
            current_version="1.0.0",
            latest_version="1.0.1",
            release_name="1.0.1",
            release_page_url="https://example.invalid",
            release_notes="",
            archive_name=self.package.name,
            archive_url="https://example.invalid/KeyTune-Portable.zip",
            archive_size_bytes=self.package.stat().st_size,
            checksum_url="https://example.invalid/checksum",
        )
        received = self.package.with_name("received")
        received.mkdir()

        def download(_url, target, **_kwargs):
            shutil.copyfile(self.package, target)
            return info.archive_size_bytes, info.archive_size_bytes

        checksum = hashlib.sha256(self.package.read_bytes()).hexdigest()
        with (
            patch("player.portable.is_portable", return_value=True),
            patch.object(service.sys, "executable", str(self.executable)),
            patch.object(service.tempfile, "mkdtemp", return_value=str(received)),
            patch.object(service, "_download_file", side_effect=download),
            patch.object(service, "_download_expected_checksum", return_value=checksum),
        ):
            result = service.download_release_archive(info, cancel_event=cancel_event)
        self.assertEqual(result, received / self.package.name)

    def test_incomplete_restore_keeps_backup_and_attempts_remaining_entries(self):
        earlier = self.app / "00-earlier.txt"
        earlier.write_bytes(b"old")
        internal = self.app / "_internal"
        internal.mkdir()
        (internal / "old.dll").write_bytes(b"original dll")
        self._write_package({
            "00-earlier.txt": b"new",
            "01-added.txt": b"added",
            "_internal/new.dll": b"new dll",
            self.executable.name: b"new program",
        })
        copy = portable_update._copy_replacing
        remove = portable_update._remove_path

        def partial_copy(source, destination):
            if destination == internal:
                destination.mkdir()
                (destination / "new.dll").write_bytes(b"partial")
                raise OSError("copy failed")
            copy(source, destination)

        def remove_locked(destination):
            if destination == internal:
                raise PermissionError("partial DLL is locked")
            remove(destination)

        with (
            patch.object(portable_update, "_copy_replacing", side_effect=partial_copy),
            patch.object(portable_update, "_remove_path", side_effect=remove_locked),
            patch.object(portable_update, "_relaunch") as relaunch,
            self.assertRaises(portable_update.PortableApplyError) as caught,
        ):
            self._apply()

        backup, = self.data.glob("portable-update-backup-*")
        self.assertEqual((backup / "_internal" / "old.dll").read_bytes(), b"original dll")
        self.assertEqual(earlier.read_bytes(), b"old")
        self.assertFalse((self.app / "01-added.txt").exists())
        log = (self.data / portable_update.PORTABLE_UPDATE_LOG_NAME).read_text(encoding="utf-8")
        self.assertIn("partial DLL is locked", log)
        self.assertIn(str(backup), log)
        self.assertIn(str(backup), str(caught.exception))
        relaunch.assert_called_once_with(self.executable)

    def test_failed_initial_move_leaves_original_in_place(self):
        self._write_package({self.executable.name: b"new"})
        with (
            patch.object(portable_update.os, "replace", side_effect=PermissionError("locked")),
            self.assertRaises(portable_update.PortableApplyError),
        ):
            self._apply(relaunch=False)
        self.assertEqual(self.executable.read_bytes(), b"old program")
        self.assertEqual(list(self.data.glob("portable-update-backup-*")), [])

    def test_failed_executable_restore_keeps_old_binary_without_running_partial_update(self):
        self._write_package({self.executable.name: b"new", "zzz-added.txt": b"added"})
        copy = portable_update._copy_replacing

        def fail_after_executable(source, destination):
            if destination.name == "zzz-added.txt":
                raise OSError("copy failed")
            copy(source, destination)

        with (
            patch.object(portable_update, "_copy_replacing", side_effect=fail_after_executable),
            patch.object(portable_update, "_restore_entry", side_effect=PermissionError("locked")),
            patch.object(portable_update, "_relaunch") as relaunch,
            self.assertRaises(portable_update.PortableApplyError) as caught,
        ):
            self._apply()

        backup, = self.data.glob("portable-update-backup-*")
        self.assertEqual((backup / self.executable.name).read_bytes(), b"old program")
        self.assertIn(str(backup), str(caught.exception))
        self.assertIn("reabrir", str(caught.exception))
        relaunch.assert_not_called()

    def test_rejects_invalid_paths_and_collisions_before_touching_program_files(self):
        for entries in (
            {"Data/settings.json": b"replacement"},
            {"PORTABLE.INI": b"one", "portable.ini": b"two"},
            {"_Internal/one.dll": b"one", "_internal/two.dll": b"two"},
            {"docs": b"one", "docs/readme.txt": b"two"},
            {"data./settings.json": b"replacement"},
        ):
            with self.subTest(entries=entries):
                self._write_package({self.executable.name: b"new", **entries})
                with self.assertRaises(portable_update.PortableApplyError):
                    self._apply(relaunch=False)
                self.assertEqual(self.executable.read_bytes(), b"old program")
                self.assertEqual((self.data / "settings.json").read_bytes(), b"user data")

    def test_rejects_a_wrapped_zip_containing_data(self):
        self._write_package({"KeyTune/KeyTune.exe": b"new", "KeyTune/DATA/settings.json": b"replace"})
        with self.assertRaisesRegex(portable_update.PortableApplyError, "pasta de dados"):
            self._apply(relaunch=False)

    def test_download_checks_crc_even_when_the_checksum_matches(self):
        self._write_package({self.executable.name: b"payload-to-corrupt"})
        self.package.write_bytes(self.package.read_bytes().replace(b"payload-to-corrupt", b"payload-to-corrupT"))
        with self.assertRaisesRegex(service.UpdateError, "corrompido"):
            self._download()
        self.assertFalse(self.package.with_name("received").exists())

    def test_download_rejects_zip_without_executable(self):
        self._write_package({"readme.txt": b"no executable"})
        with self.assertRaisesRegex(service.UpdateError, "não contém o programa"):
            self._download()
        self.assertFalse(self.package.with_name("received").exists())

    def test_portable_download_accepts_a_valid_zip(self):
        self._write_package({self.executable.name: b"new"})
        self._download()

    def test_cancelling_while_reading_zip_is_reported_as_cancellation(self):
        self._write_package({self.executable.name: b"new"})
        cancelled = threading.Event()
        open_member = zipfile.ZipFile.open

        def open_and_cancel(archive, *args, **kwargs):
            cancelled.set()
            return open_member(archive, *args, **kwargs)

        with patch.object(zipfile.ZipFile, "open", open_and_cancel):
            with self.assertRaises(service.UpdateCancelledError):
                self._download(cancel_event=cancelled)
        self.assertFalse(self.package.with_name("received").exists())

    def test_extraction_failure_after_exit_relaunches_previous_version(self):
        self._write_package({self.executable.name: b"new"})
        with (
            patch.object(portable_update, "_wait_for_process_exit") as wait,
            patch.object(portable_update, "_relaunch") as relaunch,
        ):
            def disk_full(*_args):
                wait.assert_called_once()
                raise OSError("disk full")

            with patch.object(portable_update, "_extract_archive", side_effect=disk_full):
                with self.assertRaises(portable_update.PortableApplyError):
                    self._apply(parent_pid=12345)

        self.assertEqual(self.executable.read_bytes(), b"old program")
        relaunch.assert_called_once_with(self.executable)

    def test_wait_timeout_leaves_the_running_instance_alone(self):
        self._write_package({self.executable.name: b"new"})
        with (
            patch.object(portable_update, "_wait_for_process_exit", side_effect=portable_update.PortableApplyError("timeout")),
            patch.object(portable_update, "_relaunch") as relaunch,
            self.assertRaises(portable_update.PortableApplyError),
        ):
            self._apply(parent_pid=12345)
        self.assertEqual(self.executable.read_bytes(), b"old program")
        relaunch.assert_not_called()
