import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest
import zipfile

from player.plugins.api import PermissionDeniedError, PluginAPI, PluginContext
from player.plugins.installer import InstallationError, install_archive
from player.plugins.host import PluginHostAdapter
from player.plugins.manifest import ManifestError, PluginManifest, PluginPermission
from player.plugins.marketplace import MarketplaceError, parse_catalog
from player.plugins.registry import PluginRegistry
from player.plugins.registry import InstalledPlugin
from player.plugins.service import PluginCompatibilityError, PluginService


def manifest(**changes):
    value = {"id": "org.test.plugin", "name": "Teste", "version": "1.0.0", "api_version": "2.0", "entrypoint": "plugin:Plugin", "author": "Testes", "permissions": ["network"]}
    value.update(changes); return value


class Bridge:
    def __init__(self): self.calls = []
    def invoke(self, method, arguments): self.calls.append((method, arguments)); return {"ok": True}
    def register_contribution(self, kind, value): self.calls.append((kind, value))


class PluginTests(unittest.TestCase):
    def test_manifest_is_strict_and_round_trips(self):
        parsed = PluginManifest.from_dict(manifest())
        self.assertEqual(parsed.id, "org.test.plugin")
        self.assertEqual(PluginManifest.from_dict(parsed.to_dict()), parsed)
        with self.assertRaises(ManifestError): PluginManifest.from_dict(manifest(id="Unsafe ID"))
        with self.assertRaises(ManifestError): PluginManifest.from_dict(manifest(permissions=["root"] ))

    def test_api_denies_missing_capability(self):
        api = PluginAPI(PluginContext("org.test.plugin", Path("."), frozenset()), Bridge())
        with self.assertRaises(PermissionDeniedError): api.request("https://example.com")
        bridge = Bridge(); api = PluginAPI(PluginContext("org.test.plugin", Path("."), frozenset({PluginPermission.NETWORK})), bridge)
        api.request("https://example.com")
        self.assertEqual(bridge.calls[0][0], "network.request")

        download_context = PluginContext(
            "org.test.plugin", Path("."), frozenset({PluginPermission.YT_DLP})
        )
        with self.assertRaises(PermissionDeniedError):
            PluginAPI(download_context, Bridge()).yt_dlp_download(
                "https://youtu.be/example", "/tmp"
            )
        download_bridge = Bridge()
        download_context = PluginContext(
            "org.test.plugin",
            Path("."),
            frozenset({PluginPermission.YT_DLP, PluginPermission.FILESYSTEM_WRITE}),
        )
        PluginAPI(download_context, download_bridge).yt_dlp_download(
            "https://youtu.be/example", "/tmp"
        )
        self.assertEqual(download_bridge.calls[0][0], "yt_dlp.download")

    def test_catalog_validation(self):
        entry = {"id":"org.test.plugin","name":"Teste","version":"1.0.0","author":"Teste","download_url":"https://example.com/p.ktplugin","sha256":"a"*64}
        self.assertEqual(parse_catalog(json.dumps({"schema_version":1,"plugins":[entry]}))[0].id, entry["id"])
        entry["download_url"] = "http://example.com/plugin"
        with self.assertRaises(MarketplaceError): parse_catalog(json.dumps({"schema_version":1,"plugins":[entry]}))

    def test_install_checksum_registry_and_zip_slip(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); package = root / "plugin.ktplugin"
            with zipfile.ZipFile(package, "w") as archive:
                archive.writestr("keytune-plugin.json", json.dumps(manifest()))
                archive.writestr("plugin.py", "class Plugin: pass")
            digest = hashlib.sha256(package.read_bytes()).hexdigest()
            parsed = install_archive(package, root / "plugins", expected_sha256=digest)
            registry = PluginRegistry(root / "plugins")
            self.assertFalse(registry.discover()[0].enabled)
            registry.update(parsed.id, enabled=True, granted_permissions=parsed.permissions)
            self.assertTrue(registry.discover()[0].enabled)
            updated_manifest = manifest(permissions=["network", "notifications"], version="1.1.0")
            (root / "plugins" / parsed.id / "keytune-plugin.json").write_text(json.dumps(updated_manifest), encoding="utf-8")
            self.assertFalse(registry.discover()[0].enabled)
            unsafe = root / "unsafe.ktplugin"
            with zipfile.ZipFile(unsafe, "w") as archive:
                archive.writestr("keytune-plugin.json", json.dumps(manifest()))
                archive.writestr("../escape.py", "bad")
            with self.assertRaises(InstallationError): install_archive(unsafe, root / "plugins")

    def test_isolated_worker_returns_rpc_values_and_registers_menu(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); plugin_dir = root / "org.test.worker"; plugin_dir.mkdir()
            worker_manifest = PluginManifest.from_dict(manifest(
                id="org.test.worker", isolation="process",
                permissions=["playback.read", "notifications", "ui.menu"],
            ))
            (plugin_dir / "plugin.py").write_text(
                "class Plugin:\n"
                " def __init__(self, api): self.api = api\n"
                " def on_start(self):\n"
                "  state = self.api.playback_state()\n"
                "  self.api.notify(state['media_path'])\n"
                "  self.api.add_menu_action('hello', 'Olá', self.hello)\n"
                " def hello(self): self.api.notify('callback executado')\n",
                encoding="utf-8",
            )
            calls = []
            def dispatch(method, arguments, _manifest):
                calls.append((method, arguments))
                if method == "playback.state": return {"media_path": "teste.mp3"}
                if method == "ui.register_menu": return arguments
                return None
            contributions = []
            service = PluginService(root / "plugins", host_dispatch=dispatch, contribution_handler=lambda *value: contributions.append(value))
            runtime = service.start(InstalledPlugin(worker_manifest, plugin_dir, True, worker_manifest.permissions))
            deadline = time.time() + 5
            while not contributions and time.time() < deadline: time.sleep(.02)
            contributions[0][2]["callback"]()
            while ("notifications.show", {"message": "callback executado"}) not in calls and time.time() < deadline:
                time.sleep(.02)
            service.stop_all()
            self.assertFalse(runtime.error)
            self.assertIn(("notifications.show", {"message": "teste.mp3"}), calls)
            self.assertIn(("notifications.show", {"message": "callback executado"}), calls)
            self.assertEqual(contributions[0][1], "menu")

    def test_host_exposes_loaded_playlists_without_internal_objects(self):
        class State:
            title = "Lista"; items = ["a.mp3"]; browser_item_labels = ["A"]
            current_index = 0; current_media_path = "a.mp3"; source_path = None
            is_folder_tab = False; is_screen_tab = False; shuffle_enabled = False; repeat_mode = "off"
        class Frame:
            playlists = [State()]
            def _get_active_playlist_state(self): return self.playlists[0]
            def _get_active_playlist_index(self): return 0
        adapter = PluginHostAdapter(Frame(), Path("."))
        allowed = PluginManifest.from_dict(manifest(permissions=["library.read"]))
        result = adapter.dispatch("library.playlists", {}, allowed)
        self.assertEqual(result[0]["items"], ["a.mp3"])
        self.assertIsInstance(result[0], dict)

    def test_rejects_newer_api_minor_and_keytune_version(self):
        with tempfile.TemporaryDirectory() as temporary:
            service = PluginService(Path(temporary) / "plugins")
            with self.assertRaises(PluginCompatibilityError):
                service._check_compatibility(PluginManifest.from_dict(manifest(api_version="2.9")))
            with self.assertRaises(PluginCompatibilityError):
                service._check_compatibility(PluginManifest.from_dict(manifest(minimum_keytune_version="9.0.0")))
