from __future__ import annotations

import pathlib
import subprocess
import sys
import unittest


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
AUDIT_SCRIPT = PROJECT_ROOT / "scripts" / "audit_ui_accessibility.py"


@unittest.skipUnless(sys.platform == "win32", "the audit reads MSAA, which only exists on Windows")
class UiAccessibilityAuditTests(unittest.TestCase):
    def test_every_screen_passes_the_accessibility_audit(self):
        # Runs in its own process: the audit needs a real wx.App, which the other tests avoid.
        result = subprocess.run(
            [sys.executable, str(AUDIT_SCRIPT)],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr[-2000:])


if __name__ == "__main__":
    unittest.main()
