import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build_optional_resources", ROOT / "scripts/build_optional_resources.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class OptionalResourceBuildTests(unittest.TestCase):
    def test_youtubejs_build_resolves_node_before_locating_npm(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            node = root / "Node with spaces" / "node.exe"
            npm_cli = node.parent / "node_modules/npm/bin/npm-cli.js"
            npm_cli.parent.mkdir(parents=True)
            npm_cli.touch()
            args = SimpleNamespace(node_executable="node", app_version="2.0.0", architecture="x64")

            def install(command, *, cwd, check):
                self.assertEqual(command, [str(node), str(npm_cli), "ci", "--omit=dev"])
                package = cwd / "node_modules/youtubei.js/package.json"
                package.parent.mkdir(parents=True)
                package.write_text(json.dumps({"version": "1.0.0"}), encoding="utf-8")

            with patch.object(builder.shutil, "which", side_effect=lambda name: str(node) if name == "node" else None), patch.object(
                builder.subprocess, "run", side_effect=install,
            ):
                builder._build_youtubejs(root, args)
            self.assertTrue((root / "KeyTune-YouTubeJS-win-x64.zip").is_file())
            self.assertTrue((root / "KeyTune-YouTubeJS-win-x64.zip.sha256").is_file())

    def test_autodj_package_reuses_main_runtime_and_contains_only_optional_packages(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            args = SimpleNamespace(python_exe="python.exe", app_version="2.0.4", architecture="x64")

            def install(command, **_kwargs):
                target = Path(command[command.index("--target") + 1])
                for package in ("librosa", "numpy", "av"):
                    (target / package).mkdir(parents=True)
                    (target / package / "__init__.py").write_text("", encoding="utf-8")
                for distribution, version in (
                    ("librosa", "0.11.0"),
                    ("numpy", "2.3.5"),
                    ("scipy", "1.16.3"),
                    ("numba", "0.63.1"),
                    ("av", "18.1.0"),
                ):
                    metadata_dir = target / f"{distribution}-{version}.dist-info"
                    metadata_dir.mkdir()
                    (metadata_dir / "METADATA").write_text("", encoding="utf-8")

            with patch.object(builder.subprocess, "run", side_effect=install) as run:
                builder._build_autodj(root, args)

            archive_path = root / "KeyTune-AutoDJ-win-x64.zip"
            with zipfile.ZipFile(archive_path) as archive:
                names = set(archive.namelist())
            self.assertIn("site-packages/librosa-0.11.0.dist-info/METADATA", names)
            self.assertFalse(any("autodj-analyzer.exe" in name for name in names))
            self.assertFalse(any(name.endswith("python311.dll") for name in names))
            command = run.call_args.args[0]
            self.assertIn("--target", command)
            self.assertNotIn("PyInstaller", command)
