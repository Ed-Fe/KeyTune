import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


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
