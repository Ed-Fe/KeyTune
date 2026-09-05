import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.constants import APP_VERSION
from player import optional_resources


class OptionalResourcesTests(unittest.TestCase):
    def test_installed_resource_requires_current_manifest_and_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            resource_dir = Path(temporary) / "youtubejs"
            resource_dir.mkdir()
            (resource_dir / "resolve.mjs").write_text("", encoding="utf-8")
            (resource_dir / optional_resources.RESOURCE_MANIFEST_NAME).write_text(
                json.dumps(
                    {
                        "resource": "youtubejs",
                        "app_version": APP_VERSION,
                        "required_paths": ["resolve.mjs"],
                    }
                ),
                encoding="utf-8",
            )

            with patch.object(optional_resources, "get_optional_resource_dir", return_value=resource_dir):
                self.assertTrue(optional_resources.optional_resource_installed("youtubejs"))
                (resource_dir / "resolve.mjs").unlink()
                self.assertFalse(optional_resources.optional_resource_installed("youtubejs"))

    def test_extract_archive_rejects_parent_traversal(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive_path = Path(temporary) / "resource.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("../outside.txt", "invalid")

            with self.assertRaisesRegex(optional_resources.OptionalResourceError, "caminhos inválidos"):
                optional_resources._extract_archive(archive_path, Path(temporary) / "content")

    def test_resource_asset_name_uses_current_windows_architecture(self):
        with patch("player.optional_resources.platform.machine", return_value="AMD64"):
            self.assertEqual(
                optional_resources.resource_asset_name("autodj"),
                "KeyTune-AutoDJ-win-x64.zip",
            )

    def test_download_workspace_is_created_under_the_resource_parent(self):
        with tempfile.TemporaryDirectory() as temporary:
            resource_parent = Path(temporary) / "resources"
            resource_parent.mkdir()

            with patch("player.optional_resources.uuid.uuid4") as generate_uuid:
                generate_uuid.return_value.hex = "workspace"
                download_dir = optional_resources._create_download_dir(resource_parent, "youtube")

            self.assertEqual(download_dir, resource_parent / ".keytune-youtube-workspace")
            self.assertTrue(download_dir.is_dir())

    def test_inaccessible_resource_uses_repaired_sibling_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            resource_dir = Path(temporary) / "resources" / "youtube_music" / "youtube"
            resource_dir.mkdir(parents=True)

            with patch.object(optional_resources, "get_app_storage_dir", return_value=temporary), patch.object(
                optional_resources.os, "scandir", side_effect=PermissionError
            ):
                resolved_dir = optional_resources.get_optional_resource_dir("youtube")

            self.assertEqual(resolved_dir, resource_dir.with_name("youtube.repaired"))

    def test_install_validates_checksum_and_replaces_resource_atomically(self):
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            source_archive = temporary_path / "source.zip"
            asset_name = "KeyTune-YouTubeJS-win-x64.zip"
            with zipfile.ZipFile(source_archive, "w") as archive:
                archive.writestr("resolve.mjs", "export {};\n")
                archive.writestr(
                    optional_resources.RESOURCE_MANIFEST_NAME,
                    json.dumps(
                        {
                            "resource": "youtubejs",
                            "app_version": APP_VERSION,
                            "required_paths": ["resolve.mjs"],
                        }
                    ),
                )
            checksum = hashlib.sha256(source_archive.read_bytes()).hexdigest()
            source_checksum = temporary_path / "source.sha256"
            source_checksum.write_text(f"{checksum}  {asset_name}\n", encoding="ascii")
            target_dir = temporary_path / "installed" / "youtubejs"
            target_dir.mkdir(parents=True)
            (target_dir / "old.txt").write_text("old", encoding="utf-8")

            release_payload = {
                "assets": [
                    {"name": asset_name, "size": 1, "browser_download_url": "archive"},
                    {"name": f"{asset_name}.sha256", "browser_download_url": "checksum"},
                ]
            }

            def copy_download(url, destination):
                destination.write_bytes(
                    source_archive.read_bytes() if url == "archive" else source_checksum.read_bytes()
                )

            with patch.object(optional_resources, "resource_asset_name", return_value=asset_name), patch.object(
                optional_resources, "get_optional_resource_dir", return_value=target_dir
            ), patch.object(optional_resources, "_fetch_release_payload", return_value=release_payload), patch.object(
                optional_resources, "_download_file", side_effect=copy_download
            ), patch.object(
                optional_resources.shutil,
                "disk_usage",
                return_value=Mock(free=1024 * 1024 * 1024),
            ):
                manifest = optional_resources.install_optional_resource("youtubejs")

            self.assertEqual(manifest["resource"], "youtubejs")
            self.assertTrue((target_dir / "resolve.mjs").is_file())
            self.assertFalse((target_dir / "old.txt").exists())


if __name__ == "__main__":
    unittest.main()
