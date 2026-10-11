from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch


SRC_ROOT = pathlib.Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

try:
    from player.update import service
except ModuleNotFoundError:  # wxPython ausente (ambiente sem UI)
    service = None


@unittest.skipIf(service is None, "requer wxPython")
class PendingUpdateTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        patcher = patch("player.session.get_app_storage_dir", return_value=directory.name)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_no_marker_means_nothing_to_report(self):
        self.assertIsNone(service.take_failed_update())

    def test_marker_for_newer_version_reports_failure_once(self):
        with patch.object(service, "APP_VERSION", "2.3.1"):
            service.record_pending_update("2.4.0")
            failed = service.take_failed_update()
            self.assertEqual((failed.target_version, failed.current_version), ("2.4.0", "2.3.1"))
            self.assertIsNone(service.take_failed_update())

    def test_marker_for_installed_version_is_discarded(self):
        with patch.object(service, "APP_VERSION", "2.4.0"):
            service.record_pending_update("v2.4.0")
            self.assertIsNone(service.take_failed_update())


if __name__ == "__main__":
    unittest.main()
