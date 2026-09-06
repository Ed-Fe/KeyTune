from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("validate_main_bundle", ROOT / "scripts/validate_main_bundle.py")
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


class ValidateMainBundleTests(unittest.TestCase):
    def test_clean_bundle_is_accepted(self):
        with tempfile.TemporaryDirectory() as temporary:
            internal_dir = Path(temporary) / "_internal"
            internal_dir.mkdir()
            (internal_dir / "wx").mkdir()

            self.assertEqual(validator.find_bundled_optional_dependencies(Path(temporary)), [])

    def test_optional_modules_and_distribution_metadata_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            internal_dir = Path(temporary) / "_internal"
            internal_dir.mkdir()
            (internal_dir / "numpy").mkdir()
            (internal_dir / "librosa-0.11.0.dist-info").mkdir()

            self.assertEqual(
                validator.find_bundled_optional_dependencies(Path(temporary)),
                ["librosa", "numpy"],
            )


if __name__ == "__main__":
    unittest.main()
