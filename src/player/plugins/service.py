"""Plugin lifecycle coordinator with failure isolation and diagnostics."""

from __future__ import annotations

from dataclasses import dataclass, field
import importlib.util
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import threading
from typing import Any, Callable

from ..session import get_app_storage_dir
from ..constants import APP_VERSION
from .api import API_VERSION, PluginAPI, PluginContext
from .manifest import PluginManifest
from .host import METHOD_PERMISSIONS
from .registry import InstalledPlugin, PluginRegistry


class PluginCompatibilityError(RuntimeError):
    pass


@dataclass
class PluginRuntime:
    installed: InstalledPlugin
    instance: Any = None
    process: subprocess.Popen | None = None
    contributions: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    error: str = ""
    ready: threading.Event = field(default_factory=threading.Event)


class _Bridge:
    def __init__(self, service: "PluginService", runtime: PluginRuntime):
        self.service, self.runtime = service, runtime

    def invoke(self, method, arguments):
        return self.service.host_dispatch(method, arguments, self.runtime.installed.manifest)

    def register_contribution(self, kind, contribution):
        self.runtime.contributions.append((kind, contribution))
        if self.service.contribution_handler:
            self.service.contribution_handler(self.runtime.installed.manifest, kind, contribution)


class PluginService:
    """Loads opted-in plugins; disabled and broken plugins never block startup."""

    def __init__(self, plugins_dir: str | Path | None = None, *, host_dispatch=None, contribution_handler=None):
        storage = Path(get_app_storage_dir())
        self.plugins_dir = Path(plugins_dir) if plugins_dir else storage / "plugins"
        self.data_dir = storage / "plugin-data"
        self.logs_dir = storage / "plugin-logs"
        self.registry = PluginRegistry(self.plugins_dir)
        self.host_dispatch: Callable = host_dispatch or self._unsupported_dispatch
        self.contribution_handler = contribution_handler
        self.runtimes: dict[str, PluginRuntime] = {}

    @staticmethod
    def _unsupported_dispatch(method, _arguments, _manifest):
        raise NotImplementedError(f"O host não implementa {method}.")

    def discover(self):
        return self.registry.discover()

    def start_enabled(self):
        for installed in self.discover():
            if installed.enabled:
                self.start(installed)

    def start(self, installed: InstalledPlugin) -> PluginRuntime:
        runtime = PluginRuntime(installed)
        self.runtimes[installed.manifest.id] = runtime
        try:
            self._check_compatibility(installed.manifest)
            if installed.granted_permissions != installed.manifest.permissions:
                raise PermissionError("As permissões solicitadas ainda não foram integralmente aprovadas.")
            if installed.manifest.isolation == "process":
                self._start_process(runtime)
            else:
                self._start_in_process(runtime)
        except Exception as exc:
            runtime.error = str(exc)
            self._write_diagnostic(runtime, exc)
        return runtime

    def _check_compatibility(self, manifest):
        requested_api = _version_tuple(manifest.api_version, parts=2)
        host_api = _version_tuple(API_VERSION, parts=2)
        if requested_api[0] != host_api[0] or requested_api > host_api:
            raise PluginCompatibilityError(
                f"Plugin requer API {manifest.api_version}; o KeyTune oferece {API_VERSION}."
            )
        if _version_tuple(manifest.minimum_keytune_version) > _version_tuple(APP_VERSION):
            raise PluginCompatibilityError(
                f"Plugin requer KeyTune {manifest.minimum_keytune_version} ou posterior; esta versão é {APP_VERSION}."
            )

    def _start_in_process(self, runtime):
        manifest = runtime.installed.manifest
        module_name, object_name = manifest.entrypoint.split(":", 1)
        module_path = runtime.installed.path.joinpath(*module_name.split(".")).with_suffix(".py")
        if not module_path.is_file():
            module_path = runtime.installed.path / module_name.replace(".", "/") / "__init__.py"
        spec = importlib.util.spec_from_file_location(f"keytune_plugin_{manifest.id}", module_path)
        if not spec or not spec.loader:
            raise ImportError(f"Não foi possível importar {module_name}.")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        factory = getattr(module, object_name)
        context = PluginContext(manifest.id, self.data_dir / manifest.id, runtime.installed.granted_permissions)
        context.data_directory.mkdir(parents=True, exist_ok=True)
        runtime.instance = factory(PluginAPI(context, _Bridge(self, runtime)))
        callback = getattr(runtime.instance, "on_start", None)
        if callback:
            callback()

    def _start_process(self, runtime):
        installed = runtime.installed
        context = {
            "plugin_id": installed.manifest.id,
            "plugin_path": str(installed.path),
            "data_directory": str(self.data_dir / installed.manifest.id),
            "entrypoint": installed.manifest.entrypoint,
            "permissions": sorted(item.value for item in installed.granted_permissions),
        }
        (self.data_dir / installed.manifest.id).mkdir(parents=True, exist_ok=True)
        command = (
            [sys.executable, "--plugin-worker"]
            if getattr(sys, "frozen", False)
            else [sys.executable, "-I", str(Path(__file__).with_name("worker.py"))]
        )
        runtime.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONPATH": ""},
        )
        runtime.process.stdin.write(json.dumps({"type": "start", "context": context}) + "\n")
        runtime.process.stdin.flush()
        threading.Thread(target=self._serve_process_requests, args=(runtime,), daemon=True).start()
        threading.Thread(target=self._drain_process_errors, args=(runtime,), daemon=True).start()

    def _serve_process_requests(self, runtime):
        process = runtime.process
        try:
            for line in process.stdout:
                message = json.loads(line)
                if message.get("type") == "ready":
                    runtime.ready.set()
                    continue
                if message.get("type") != "request":
                    continue
                method = message.get("method", "")
                raw_required = METHOD_PERMISSIONS.get(method)
                required = (
                    raw_required
                    if isinstance(raw_required, frozenset)
                    else frozenset({raw_required}) if raw_required is not None else frozenset()
                )
                if not required or not required.issubset(runtime.installed.granted_permissions):
                    raise PermissionError(f"Operação não autorizada: {method}")
                request_id = message.get("id")
                try:
                    result = self.host_dispatch(method, message.get("arguments", {}), runtime.installed.manifest)
                    if method == "ui.register_menu":
                        contribution = dict(result)
                        contribution["callback"] = lambda plugin_runtime=runtime, action_id=result["id"]: self.send_event(
                            plugin_runtime, "ui.action", {"id": action_id}
                        )
                        runtime.contributions.append(("menu", contribution))
                        if self.contribution_handler:
                            self.contribution_handler(runtime.installed.manifest, "menu", contribution)
                    response = {"type": "response", "id": request_id, "result": result}
                except Exception as exc:
                    response = {"type": "response", "id": request_id, "error": f"{type(exc).__name__}: {exc}"}
                process.stdin.write(json.dumps(response, ensure_ascii=False) + "\n")
                process.stdin.flush()
        except Exception as exc:
            if process.poll() is None:
                runtime.error = str(exc)
                self._write_diagnostic(runtime, exc)

    def _drain_process_errors(self, runtime):
        process = runtime.process
        for line in process.stderr:
            message = line.rstrip()
            if message:
                self._write_diagnostic_message(runtime, message)

    def send_event(self, runtime, event, payload=None):
        if runtime.process and runtime.process.poll() is None:
            runtime.process.stdin.write(json.dumps({"type": "event", "event": event, "payload": payload or {}}) + "\n")
            runtime.process.stdin.flush()

    def emit(self, event: str, payload: dict[str, Any] | None = None):
        for runtime in tuple(self.runtimes.values()):
            try:
                if runtime.instance:
                    callback = getattr(runtime.instance, "on_event", None)
                    if callback:
                        callback(event, payload or {})
                elif runtime.process and runtime.process.poll() is None:
                    self.send_event(runtime, event, payload)
            except Exception as exc:
                runtime.error = str(exc)
                self._write_diagnostic(runtime, exc)

    def invoke_callback(self, plugin_id, callback):
        runtime = self.runtimes.get(plugin_id)
        if runtime is None:
            return None
        try:
            return callback()
        except Exception as exc:
            runtime.error = str(exc)
            self._write_diagnostic(runtime, exc)
            return None

    def stop_all(self):
        for runtime in tuple(self.runtimes.values()):
            self._stop_runtime(runtime)
        self.runtimes.clear()

    def stop(self, plugin_id):
        runtime = self.runtimes.pop(str(plugin_id), None)
        if runtime is not None:
            self._stop_runtime(runtime)

    def _stop_runtime(self, runtime):
        try:
            callback = getattr(runtime.instance, "on_stop", None) if runtime.instance else None
            if callback:
                callback()
            if runtime.process and runtime.process.poll() is None:
                runtime.process.terminate()
                runtime.process.wait(timeout=2)
        except Exception as exc:
            self._write_diagnostic(runtime, exc)
            if runtime.process:
                runtime.process.kill()
        finally:
            process = runtime.process
            if process is not None:
                for stream in (process.stdin, process.stdout, process.stderr):
                    if stream is not None:
                        try:
                            stream.close()
                        except OSError:
                            pass

    def _write_diagnostic(self, runtime, exc):
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        logger = logging.getLogger(f"keytune.plugin.{runtime.installed.manifest.id}")
        logger.exception("Plugin failure", exc_info=exc)
        with (self.logs_dir / f"{runtime.installed.manifest.id}.log").open("a", encoding="utf-8") as stream:
            stream.write(f"{type(exc).__name__}: {exc}\n")

    def _write_diagnostic_message(self, runtime, message):
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        with (self.logs_dir / f"{runtime.installed.manifest.id}.log").open("a", encoding="utf-8") as stream:
            stream.write(f"worker: {message}\n")


def _version_tuple(value, parts=3):
    core = str(value or "0").split("-", 1)[0].split("+", 1)[0]
    values = []
    for item in core.split(".")[:parts]:
        try:
            values.append(int(item))
        except ValueError:
            values.append(0)
    return tuple((values + [0] * parts)[:parts])
