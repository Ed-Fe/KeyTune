import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.plugins.api import PermissionDeniedError, PluginAPI, PluginContext
from player.plugins.dialog import installation_summary
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
        with self.assertRaises(ManifestError): PluginManifest.from_dict(manifest(api_version="dois"))
        with self.assertRaises(ManifestError): PluginManifest.from_dict(manifest(minimum_keytune_version="2"))

    def test_installation_summary_shows_manifest_details_and_permissions(self):
        parsed = PluginManifest.from_dict(manifest(
            description="Plugin de teste",
            license="MIT",
            homepage="https://example.com/plugin",
            isolation="in_process",
            permissions=["network", "ui.tab"],
        ))
        summary = installation_summary(parsed, "Pacote local selecionado")
        self.assertIn("Nome: Teste", summary)
        self.assertIn("Versão: 1.0.0", summary)
        self.assertIn("Autor: Testes", summary)
        self.assertIn("Plugin de teste", summary)
        self.assertIn("Licença: MIT", summary)
        self.assertIn("Página: https://example.com/plugin", summary)
        self.assertIn("Adicionar abas ao player", summary)
        self.assertIn("Acessar a internet", summary)
        self.assertIn("mesmo acesso do aplicativo", summary)

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
        with self.assertRaises(PermissionDeniedError):
            PluginAPI(download_context, Bridge()).yt_dlp_info(
                "https://youtu.be/example", use_account_auth=True
            )
        analysis_context = PluginContext(
            "org.test.plugin", Path("."), frozenset({PluginPermission.AUTODJ_ANALYZE})
        )
        with self.assertRaises(PermissionDeniedError):
            PluginAPI(analysis_context, Bridge()).analyze_media(
                "https://music.youtube.com/watch?v=example", use_account_auth=True
            )
        file_bridge = Bridge()
        file_context = PluginContext(
            "org.test.plugin",
            Path("."),
            frozenset({PluginPermission.FILESYSTEM_READ, PluginPermission.FILESYSTEM_WRITE}),
        )
        file_api = PluginAPI(file_context, file_bridge)
        file_api.read_text("entrada.txt")
        file_api.write_text("saida.txt", "conteúdo")
        self.assertEqual([call[0] for call in file_bridge.calls], ["filesystem.read_text", "filesystem.write_text"])

    def test_catalog_validation(self):
        entry = {"id":"org.test.plugin","name":"Teste","version":"1.0.0","author":"Teste","download_url":"https://example.com/p.ktplugin","sha256":"a"*64}
        self.assertEqual(parse_catalog(json.dumps({"schema_version":1,"plugins":[entry]}))[0].id, entry["id"])
        entry["download_url"] = "http://example.com/plugin"
        with self.assertRaises(MarketplaceError): parse_catalog(json.dumps({"schema_version":1,"plugins":[entry]}))
        entry["download_url"] = "https://example.com/plugin"
        entry["verified"] = "sim"
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
            reserved = root / "reserved.ktplugin"
            with zipfile.ZipFile(reserved, "w") as archive:
                archive.writestr("keytune-plugin.json", json.dumps(manifest()))
                archive.writestr("plugin.py", "class Plugin: pass")
                archive.writestr("CON.txt", "bad")
            with self.assertRaises(InstallationError): install_archive(reserved, root / "plugins")
            with self.assertRaises(InstallationError):
                install_archive(package, root / "plugins", expected_plugin_id="org.outro.plugin")
            with self.assertRaises(InstallationError):
                install_archive(package, root / "plugins", expected_version="9.0.0")
            collision = root / "collision.ktplugin"
            with zipfile.ZipFile(collision, "w") as archive:
                archive.writestr("keytune-plugin.json", json.dumps(manifest()))
                archive.writestr("plugin.py", "class Plugin: pass")
                archive.writestr("Plugin.py", "class Plugin: pass")
            with self.assertRaises(InstallationError): install_archive(collision, root / "plugins")

    def test_isolated_worker_returns_rpc_values_and_registers_menu(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); plugin_dir = root / "org.test.worker"; plugin_dir.mkdir()
            worker_manifest = PluginManifest.from_dict(manifest(
                id="org.test.worker", isolation="process",
                permissions=["playback.read", "notifications", "ui.menu", "yt_dlp"],
            ))
            (plugin_dir / "plugin.py").write_text(
                "class Plugin:\n"
                " import os\n"
                " def __init__(self, api): self.api = api\n"
                " def on_start(self):\n"
                "  print('saída comum do plugin')\n"
                "  state = self.api.playback_state()\n"
                "  self.api.notify(state['media_path'])\n"
                "  self.api.notify(str(self.os.environ.get('KEYTUNE_PLUGIN_TEST_SECRET')))\n"
                "  try:\n"
                "   self.api.yt_dlp_info('https://example.invalid', use_account_auth=True)\n"
                "  except PermissionError:\n"
                "   self.api.notify('auth bloqueada')\n"
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
            removals = []
            service = PluginService(
                root / "plugins",
                host_dispatch=dispatch,
                contribution_handler=lambda *value: contributions.append(value),
                contribution_removal_handler=lambda *value: removals.append(value),
            )
            previous_secret = os.environ.get("KEYTUNE_PLUGIN_TEST_SECRET")
            os.environ["KEYTUNE_PLUGIN_TEST_SECRET"] = "não deve vazar"
            try:
                runtime = service.start(InstalledPlugin(worker_manifest, plugin_dir, True, worker_manifest.permissions))
            finally:
                if previous_secret is None:
                    os.environ.pop("KEYTUNE_PLUGIN_TEST_SECRET", None)
                else:
                    os.environ["KEYTUNE_PLUGIN_TEST_SECRET"] = previous_secret
            deadline = time.time() + 5
            while not contributions and time.time() < deadline: time.sleep(.02)
            contributions[0][2]["callback"]()
            while ("notifications.show", {"message": "callback executado"}) not in calls and time.time() < deadline:
                time.sleep(.02)
            service.stop_all()
            self.assertFalse(runtime.error)
            self.assertIn(("notifications.show", {"message": "teste.mp3"}), calls)
            self.assertIn(("notifications.show", {"message": "callback executado"}), calls)
            self.assertIn(("notifications.show", {"message": "None"}), calls)
            self.assertIn(("notifications.show", {"message": "auth bloqueada"}), calls)
            self.assertEqual(contributions[0][1], "menu")
            self.assertEqual(removals[0][1][0][0], "menu")

    def test_isolated_worker_keeps_normal_python_and_host_conveniences(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plugin_dir = root / "plugins" / "org.test.sandbox"
            plugin_dir.mkdir(parents=True)
            external_file = root / "external.txt"
            external_file.write_text("conteudo autorizado", encoding="utf-8")
            sandbox_manifest = PluginManifest.from_dict(manifest(
                id="org.test.sandbox",
                isolation="process",
                permissions=["filesystem.read", "notifications"],
            ))
            (plugin_dir / "plugin.py").write_text(
                "from pathlib import Path\n"
                "import socket\n"
                "class Plugin:\n"
                " def __init__(self, api): self.api = api\n"
                " def on_start(self):\n"
                f"  path = {str(external_file)!r}\n"
                "  self.api.notify('direto: ' + Path(path).read_text(encoding='utf-8'))\n"
                "  connection = socket.socket()\n"
                "  connection.close()\n"
                "  self.api.notify('socket direto permitido')\n"
                "  self.api.notify(self.api.read_text(path))\n"
                "  (self.api.data_directory / 'state.txt').write_text('ok', encoding='utf-8')\n",
                encoding="utf-8",
            )
            calls = []

            def dispatch(method, arguments, _manifest):
                calls.append((method, arguments))
                if method == "filesystem.read_text":
                    return Path(arguments["path"]).read_text(encoding="utf-8")
                return None

            service = PluginService(root / "plugins", host_dispatch=dispatch)
            runtime = service.start(InstalledPlugin(
                sandbox_manifest, plugin_dir, True, sandbox_manifest.permissions
            ))
            self.assertTrue(runtime.ready.wait(timeout=5), runtime.error)
            deadline = time.time() + 5
            expected = ("notifications.show", {"message": "conteudo autorizado"})
            while expected not in calls and time.time() < deadline:
                time.sleep(.02)
            service.stop_all()
            self.assertFalse(runtime.error)
            self.assertIn(("notifications.show", {"message": "direto: conteudo autorizado"}), calls)
            self.assertIn(("notifications.show", {"message": "socket direto permitido"}), calls)
            self.assertIn(expected, calls)
            self.assertEqual((root / "plugin-data" / sandbox_manifest.id / "state.txt").read_text(encoding="utf-8"), "ok")

    def test_in_process_failure_disables_plugin_and_removes_contributions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plugin_dir = root / "plugins" / "org.test.failure"
            plugin_dir.mkdir(parents=True)
            failed_manifest = PluginManifest.from_dict(manifest(
                id="org.test.failure", isolation="in_process", permissions=["ui.menu"]
            ))
            (plugin_dir / "keytune-plugin.json").write_text(
                json.dumps(failed_manifest.to_dict()), encoding="utf-8"
            )
            (plugin_dir / "plugin.py").write_text(
                "class Plugin:\n"
                " def __init__(self, api): self.api = api\n"
                " def on_start(self): self.api.add_menu_action('action', 'Ação', lambda: None)\n"
                " def on_event(self, event, payload): raise RuntimeError('falha controlada')\n",
                encoding="utf-8",
            )
            removals = []
            service = PluginService(
                root / "plugins",
                contribution_removal_handler=lambda *value: removals.append(value),
            )
            service.registry.update(
                failed_manifest.id, enabled=True, granted_permissions=failed_manifest.permissions
            )
            installed = service.discover()[0]
            runtime = service.start(installed)
            self.assertEqual(len(runtime.contributions), 1)
            with self.assertLogs("keytune.plugin.org.test.failure", level="ERROR"):
                service.emit("test.event")
            self.assertTrue(runtime.error)
            self.assertTrue(runtime.stopping)
            self.assertFalse(service.discover()[0].enabled)
            self.assertEqual(removals[0][1][0][0], "menu")

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

    def test_yt_dlp_is_anonymous_unless_account_permission_is_explicit(self):
        adapter = PluginHostAdapter(object(), Path("."))
        anonymous_manifest = PluginManifest.from_dict(manifest(permissions=["yt_dlp"]))
        with (
            patch("player.youtube_music.auth.load_saved_playback_auth") as load_auth,
            patch("player.youtube_music.yt_dlp_runtime.find_all_available_javascript_runtimes", return_value={}),
            patch(
                "player.youtube_music.yt_dlp_runtime.extract_info",
                return_value=SimpleNamespace(data={"title": "Teste"}),
            ) as extract_info,
        ):
            result = adapter.dispatch(
                "yt_dlp.info", {"media_path": "https://example.com/audio", "use_account_auth": False},
                anonymous_manifest,
            )
            self.assertEqual(result["title"], "Teste")
            load_auth.assert_not_called()
            self.assertEqual(extract_info.call_args.kwargs["cookie_file_path"], "")
            with self.assertRaises(PermissionError):
                adapter.dispatch(
                    "yt_dlp.info", {"media_path": "https://example.com/audio", "use_account_auth": True},
                    anonymous_manifest,
                )

        account_manifest = PluginManifest.from_dict(manifest(
            permissions=["yt_dlp", "youtube_music.read"]
        ))
        authentication = SimpleNamespace(cookie_file_path="cookies.txt", yt_dlp_http_headers={"X-Test": "1"})
        with (
            patch("player.youtube_music.auth.load_saved_playback_auth", return_value=authentication) as load_auth,
            patch("player.youtube_music.yt_dlp_runtime.find_all_available_javascript_runtimes", return_value={}),
            patch(
                "player.youtube_music.yt_dlp_runtime.extract_info",
                return_value=SimpleNamespace(data={}),
            ) as extract_info,
        ):
            adapter.dispatch(
                "yt_dlp.info", {"media_path": "https://example.com/audio", "use_account_auth": True},
                account_manifest,
            )
            load_auth.assert_called_once()
            self.assertEqual(extract_info.call_args.kwargs["cookie_file_path"], "cookies.txt")

    def test_rejects_newer_api_minor_and_keytune_version(self):
        with tempfile.TemporaryDirectory() as temporary:
            service = PluginService(Path(temporary) / "plugins")
            with self.assertRaises(PluginCompatibilityError):
                service._check_compatibility(PluginManifest.from_dict(manifest(api_version="2.9")))
            with self.assertRaises(PluginCompatibilityError):
                service._check_compatibility(PluginManifest.from_dict(manifest(minimum_keytune_version="9.0.0")))
