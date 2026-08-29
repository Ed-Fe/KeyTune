from __future__ import annotations

import atexit
import json
import os
import queue
import subprocess
import threading
from dataclasses import dataclass

from .auth import sanitize_sensitive_text
from .yt_dlp_runtime import find_all_available_javascript_runtimes


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
    resolver_dir = os.path.join(os.path.dirname(__file__), "youtubejs")
    resolver_script = os.path.join(resolver_dir, "resolve.mjs")
    youtubejs_package = os.path.join(resolver_dir, "node_modules", "youtubei.js")
    if not node_executable or not os.path.isfile(resolver_script) or not os.path.isdir(youtubejs_package):
        raise RuntimeError("O resolvedor experimental YouTube.js não está instalado.")

    creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    _worker_process = subprocess.Popen(
        [node_executable, resolver_script, _youtubejs_cache_dir()],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=resolver_dir,
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


atexit.register(_stop_worker)
