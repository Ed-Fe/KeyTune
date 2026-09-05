from __future__ import annotations

import atexit
import json
import os
import queue
import subprocess
import threading
from pathlib import Path
from dataclasses import dataclass

from .auth import sanitize_sensitive_text
from .yt_dlp_runtime import find_all_available_javascript_runtimes
from ..optional_resources import (
    get_optional_resource_dir,
    install_optional_resource,
    optional_resource_installed,
    read_optional_resource_manifest,
)


YOUTUBEJS_RESOLUTION_TIMEOUT_SECONDS = 10
_RESULT_PREFIX = "KEYTUNE_YOUTUBEJS_RESULT="
_worker_process = None
_worker_lock = threading.RLock()


@dataclass(slots=True)
class YouTubeJSStreamInfo:
    stream_url: str
    display_title: str = ""
    display_artist: str = ""


def warm_up():
    def start_worker():
        try:
            with _worker_lock:
                _ensure_worker()
        except Exception:
            pass

    threading.Thread(target=start_worker, daemon=True).start()


def youtubejs_dependencies_available():
    resolver_dir = _youtubejs_resolver_dir()
    source_dir = Path(__file__).resolve().parent / "youtubejs"
    package_available = (resolver_dir / "node_modules" / "youtubei.js").is_dir()
    if resolver_dir != source_dir and not optional_resource_installed("youtubejs"):
        package_available = False
    return bool(find_all_available_javascript_runtimes().get("node")) and package_available


def install_nodejs_dependency(*, force=False, progress_callback=None):
    node_path = find_all_available_javascript_runtimes().get("node")
    managed_node_path = get_optional_resource_dir("node") / "node.exe"
    if not node_path or (Path(node_path) == managed_node_path and not optional_resource_installed("node")):
        _stop_worker()
        install_optional_resource("node", progress_callback=progress_callback)
    return youtubejs_dependency_versions()


def install_youtubejs_dependencies(*, force=False, progress_callback=None):
    install_nodejs_dependency(force=force, progress_callback=progress_callback)
    if not optional_resource_installed("youtubejs"):
        _stop_worker()
        install_optional_resource("youtubejs", progress_callback=progress_callback)
    if not youtubejs_dependencies_available():
        raise RuntimeError("O Node.js ou o pacote YouTube.js não pôde ser preparado.")
    return youtubejs_dependency_versions()


def youtubejs_dependency_versions():
    versions = {}
    for resource_name in ("node", "youtubejs"):
        manifest = read_optional_resource_manifest(resource_name)
        resource_versions = manifest.get("versions") if isinstance(manifest, dict) else None
        if isinstance(resource_versions, dict):
            versions.update(resource_versions)
    return versions


def resolve_stream(media_url, *, cookie_header="", user_agent=""):
    response = _request_worker(
        {
            "media_url": str(media_url or "").strip(),
            "cookie": str(cookie_header or "").strip(),
            "user_agent": str(user_agent or "").strip(),
        }
    )
    if response.get("error"):
        raise RuntimeError(sanitize_sensitive_text(response["error"]))

    stream_url = str(response.get("stream_url") or "").strip()
    if not stream_url:
        raise RuntimeError("O YouTube.js não retornou uma URL direta de áudio.")

    return YouTubeJSStreamInfo(
        stream_url=stream_url,
        display_title=str(response.get("title") or "").strip(),
        display_artist=str(response.get("artist") or "").strip(),
    )


def _request_worker(request):
    with _worker_lock:
        for attempt in range(2):
            worker = _ensure_worker()
            try:
                worker.stdin.write(json.dumps(request) + "\n")
                worker.stdin.flush()
                return _read_worker_response(worker)
            except (BrokenPipeError, OSError, RuntimeError):
                _discard_worker(worker)
                if attempt:
                    raise
    raise RuntimeError("O processo do YouTube.js não respondeu.")


def _ensure_worker():
    global _worker_process

    if _worker_process is not None and _worker_process.poll() is None:
        return _worker_process

    node_executable = find_all_available_javascript_runtimes().get("node", "")
    resolver_dir = _youtubejs_resolver_dir()
    resolver_script = resolver_dir / "resolve.mjs"
    youtubejs_package = _youtubejs_package_dir()
    if not node_executable or not os.path.isfile(resolver_script) or not os.path.isdir(youtubejs_package):
        raise RuntimeError("O resolvedor experimental YouTube.js não está instalado.")

    creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    _worker_process = subprocess.Popen(
        [node_executable, str(resolver_script), _youtubejs_cache_dir()],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(resolver_dir),
        creationflags=creation_flags,
    )
    return _worker_process


def _read_worker_response(worker):
    result_queue = queue.Queue(maxsize=1)

    def read_result():
        try:
            while line := worker.stdout.readline():
                if line.startswith(_RESULT_PREFIX):
                    result_queue.put((line, None))
                    return
            result_queue.put(("", RuntimeError("O processo do YouTube.js foi encerrado.")))
        except Exception as exc:
            result_queue.put(("", exc))

    reader = threading.Thread(target=read_result, daemon=True)
    reader.start()
    reader.join(YOUTUBEJS_RESOLUTION_TIMEOUT_SECONDS)
    if reader.is_alive():
        raise RuntimeError("O YouTube.js demorou demais para responder.")

    response_line, error = result_queue.get_nowait()
    if error is not None:
        raise RuntimeError(str(error)) from error
    return _parse_response(response_line)


def _parse_response(response_line):
    try:
        response = json.loads(str(response_line or "")[len(_RESULT_PREFIX):])
    except json.JSONDecodeError as exc:
        raise RuntimeError("O YouTube.js retornou uma resposta inválida.") from exc
    if not isinstance(response, dict):
        raise RuntimeError("O YouTube.js retornou uma resposta inválida.")
    return response


def _discard_worker(worker):
    global _worker_process

    if _worker_process is worker:
        _worker_process = None
    if worker.poll() is None:
        worker.kill()
    try:
        worker.wait(timeout=2)
    except subprocess.TimeoutExpired:
        pass


def _stop_worker():
    with _worker_lock:
        if _worker_process is not None:
            _discard_worker(_worker_process)


def _youtubejs_cache_dir():
    if os.name == "nt":
        base_dir = os.environ.get("APPDATA") or os.path.expanduser("~")
    else:
        base_dir = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    cache_dir = os.path.join(base_dir, "KeyTune", "youtubejs-cache")
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir


def _youtubejs_resolver_dir() -> Path:
    source_dir = Path(__file__).resolve().parent / "youtubejs"
    if os.path.isdir(source_dir / "node_modules" / "youtubei.js"):
        return source_dir
    try:
        managed_dir = get_optional_resource_dir("youtubejs")
    except OSError:
        return source_dir
    if os.path.isfile(managed_dir / "resolve.mjs"):
        return managed_dir
    return source_dir


def _youtubejs_package_dir() -> Path:
    return _youtubejs_resolver_dir() / "node_modules" / "youtubei.js"


atexit.register(_stop_worker)
