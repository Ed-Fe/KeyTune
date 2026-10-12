"""O YouTube.js dentro do KeyTune: os componentes, os processos Node e como falar com eles.

Dois processos Node, cada um com o seu trabalho, para que um nunca atrapalhe o outro:

- **reprodução** (``resolve.mjs``): resolve o vídeo e serve a faixa ao MPV por um proxy
  local. Fica de pé enquanto a música toca;
- **ações** (``actions.mjs``): busca, detalhes, conta, comentários, notificações, canais
  e chat ao vivo. Se uma ação demora ou o processo morre, a música não sente.

Este módulo também instala e valida os componentes (Node.js e o pacote YouTube.js).
As funções de cada ação ficam em ``youtubejs_actions`` e também valem por aqui.
"""

from __future__ import annotations

import atexit
import os
import subprocess
import threading
from pathlib import Path
from dataclasses import dataclass

from .auth import sanitize_sensitive_text
from .content_locale import youtubejs_locale
from .yt_dlp_runtime import find_all_available_javascript_runtimes
from .youtubejs_worker import NodeWorker
from ..i18n import _
from ..optional_resources import (
    get_optional_resource_dir,
    install_optional_resource,
    optional_resource_installed,
    read_optional_resource_manifest,
)


YOUTUBEJS_RESOLUTION_TIMEOUT_SECONDS = 30
# O processo da reprodução recebe só isto; todo o resto vai ao processo das ações.
_PLAYBACK_ACTIONS = frozenset({"resolve"})
# Ações que mudam algo no YouTube: nunca são reenviadas se o processo morrer depois de
# recebê-las, porque o YouTube pode já tê-las feito (um comentário ou uma mensagem duplicada).
_WRITE_ACTIONS = frozenset(
    {
        "add_to_history",
        "channel_action",
        "comment_action",
        "create_comment",
        "live_chat_send",
        "notification_action",
        "playlist_add_video",
        "playlist_remove_video",
        "post_vote",
    }
)
_PLAYBACK_SCRIPT = "resolve.mjs"
_ACTIONS_SCRIPT = "actions.mjs"


@dataclass(slots=True)
class YouTubeJSStreamInfo:
    stream_url: str
    display_title: str = ""
    display_artist: str = ""


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
    validate_youtubejs_dependencies()
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


def request_action(action, **fields):
    """Pede uma ação ao processo das ações, com o idioma e a região do conteúdo."""
    response = _request_worker({"action": action, **youtubejs_locale(), **fields})
    if response.get("error"):
        raise RuntimeError(sanitize_sensitive_text(response["error"]))
    return response


def _worker_scripts(resolver_dir):
    """Todos os módulos do worker (sem os pacotes de terceiros), para conferir um a um."""
    scripts = []
    for folder, subfolders, filenames in os.walk(resolver_dir):
        subfolders[:] = [name for name in subfolders if name != "node_modules"]
        scripts.extend(Path(folder) / name for name in filenames if name.endswith(".mjs"))
    return sorted(scripts)


def validate_youtubejs_dependencies() -> None:
    """Validate the managed Node.js resolver without making a network request."""
    node_executable = find_all_available_javascript_runtimes().get("node", "")
    resolver_dir = _youtubejs_resolver_dir()
    package_dir = _youtubejs_package_dir()
    entry_scripts = [resolver_dir / _PLAYBACK_SCRIPT, resolver_dir / _ACTIONS_SCRIPT]
    if not node_executable or not all(script.is_file() for script in entry_scripts) or not package_dir.is_dir():
        raise RuntimeError(_("O Node.js ou o pacote YouTube.js não pôde ser preparado."))

    commands = [[node_executable, "--check", str(script)] for script in _worker_scripts(resolver_dir)]
    commands.append([node_executable, "--input-type=module", "--eval", "await import('youtubei.js')"])
    for command in commands:
        try:
            completed = subprocess.run(
                command,
                cwd=str(resolver_dir),
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError(_("Não foi possível validar o processo do YouTube.js.")) from exc
        if completed.returncode != 0:
            detail = " ".join(str(completed.stderr or completed.stdout or "").split())[-2000:]
            raise RuntimeError(
                _("O processo do YouTube.js não passou na validação: {detail}").format(
                    detail=detail or _("erro desconhecido")
                )
            )


def _spawn_worker(script_name):
    """Um ``spawn`` para o ``NodeWorker`` que sobe *script_name* com o Node do KeyTune."""

    def spawn():
        node_executable = find_all_available_javascript_runtimes().get("node", "")
        resolver_dir = _youtubejs_resolver_dir()
        resolver_script = resolver_dir / script_name
        youtubejs_package = _youtubejs_package_dir()
        if not node_executable or not os.path.isfile(resolver_script) or not os.path.isdir(youtubejs_package):
            raise RuntimeError("O resolvedor experimental YouTube.js não está instalado.")

        creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        return subprocess.Popen(
            [node_executable, str(resolver_script), _youtubejs_cache_dir()],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(resolver_dir),
            creationflags=creation_flags,
        )

    return spawn


_playback_worker = NodeWorker("playback", _spawn_worker(_PLAYBACK_SCRIPT), sanitize=sanitize_sensitive_text)
_actions_worker = NodeWorker("actions", _spawn_worker(_ACTIONS_SCRIPT), sanitize=sanitize_sensitive_text)


def warm_up():
    """Sobe o processo da reprodução em segundo plano, para a primeira faixa não esperar por ele."""

    def start_worker():
        try:
            _playback_worker.ensure_started()
        except Exception:
            pass

    threading.Thread(target=start_worker, daemon=True).start()


def _request_worker(request):
    """Manda *request* ao processo certo; o tempo e as repetições dependem da ação."""
    action = str(request.get("action") or "resolve")
    worker = _playback_worker if action in _PLAYBACK_ACTIONS else _actions_worker
    return worker.request(
        request,
        timeout=YOUTUBEJS_RESOLUTION_TIMEOUT_SECONDS,
        replay_safe=action not in _WRITE_ACTIONS,
    )


def _stop_worker():
    """Encerra os dois processos (os componentes vão ser trocados, por exemplo)."""
    _playback_worker.stop()
    _actions_worker.stop()


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

# As ações viram funções deste módulo (``youtubejs_runtime.comments_page(...)``).
from .youtubejs_actions import *  # noqa: E402,F401,F403
