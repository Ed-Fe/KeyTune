from __future__ import annotations

import atexit
from collections import deque
import json
import os
import queue
import subprocess
import threading
from pathlib import Path
from dataclasses import dataclass

from .auth import sanitize_sensitive_text
from .content_locale import youtubejs_locale
from .yt_dlp_runtime import find_all_available_javascript_runtimes
from ..i18n import _
from ..optional_resources import (
    get_optional_resource_dir,
    install_optional_resource,
    optional_resource_installed,
    read_optional_resource_manifest,
)


YOUTUBEJS_RESOLUTION_TIMEOUT_SECONDS = 30
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


def search_page(query, kind, *, start, count):
    """Uma página da busca do YouTube: entradas no formato da listagem do yt-dlp e se há mais."""
    response = _request_action("search", query=str(query or "").strip(), kind=str(kind or ""), start=start, count=count)
    return list(response.get("entries") or []), bool(response.get("has_more"))


def _account_fields(cookie_header, account_index):
    return {"cookie": str(cookie_header or "").strip(), "account_index": int(account_index or 0)}


def comments_page(media_url, *, start, count, cookie_header="", account_index=0, sort="", linked_comment=""):
    """Uma página dos comentários de um vídeo, se há mais e se a conta pode comentar ali.

    Com os cookies, os comentários vêm pela conta. *sort* ``"newest"`` traz os mais
    recentes primeiro, e *linked_comment* põe na frente a conversa desse comentário.
    """
    response = _request_action(
        "comments",
        media_url=str(media_url or "").strip(),
        start=start,
        count=count,
        sort=str(sort or ""),
        linked_comment=str(linked_comment or "").strip(),
        **_account_fields(cookie_header, account_index),
    )
    return list(response.get("entries") or []), bool(response.get("has_more")), bool(response.get("can_comment"))


def comment_replies_page(media_url, comment_id, *, start, count, cookie_header="", account_index=0):
    """Uma página das respostas a um comentário aberto por :func:`comments_page`."""
    response = _request_action(
        "comment_replies",
        media_url=str(media_url or "").strip(),
        comment_id=str(comment_id or "").strip(),
        start=start,
        count=count,
        **_account_fields(cookie_header, account_index),
    )
    return list(response.get("entries") or []), bool(response.get("has_more"))


def post_comments_page(post_id, channel_id, *, start, count, cookie_header="", account_index=0, sort=""):
    """Uma página dos comentários de um post de canal, se há mais e se a conta pode comentar ali."""
    response = _request_action(
        "post_comments",
        post_id=str(post_id or "").strip(),
        channel_id=str(channel_id or "").strip(),
        start=start,
        count=count,
        sort=str(sort or ""),
        **_account_fields(cookie_header, account_index),
    )
    return list(response.get("entries") or []), bool(response.get("has_more")), bool(response.get("can_comment"))


def create_comment(cookie_header, text, *, media_url="", post_id="", channel_id="", account_index=0):
    """Publica um comentário no vídeo *media_url* ou no post *post_id* de *channel_id*."""
    return _request_action(
        "create_comment",
        text=str(text or ""),
        media_url=str(media_url or "").strip(),
        post_id=str(post_id or "").strip(),
        channel_id=str(channel_id or "").strip(),
        **_account_fields(cookie_header, account_index),
    )


def comment_action(cookie_header, comment_id, operation, *, text="", account_index=0):
    """Responde, avalia, edita ou apaga um comentário que veio numa lista aberta com a conta."""
    return _request_action(
        "comment_action",
        comment_id=str(comment_id or "").strip(),
        operation=str(operation or ""),
        text=str(text or ""),
        **_account_fields(cookie_header, account_index),
    )


def notifications_page(cookie_header, *, start, count, account_index=0):
    """Uma página da caixa de notificações da conta e se há mais."""
    response = _request_action(
        "notifications", start=start, count=count, **_account_fields(cookie_header, account_index)
    )
    return list(response.get("entries") or []), bool(response.get("has_more"))


def notification_action(cookie_header, notification_id, operation, *, account_index=0):
    """Marca uma notificação como lida (``read``) ou a tira da caixa (``hide``)."""
    return _request_action(
        "notification_action",
        notification_id=str(notification_id or "").strip(),
        operation=str(operation or ""),
        **_account_fields(cookie_header, account_index),
    )


def channel_state(cookie_header, channel_id, *, account_index=0):
    """Se a conta está inscrita em *channel_id* e o que o sino dele avisa."""
    return _request_action(
        "channel_state", channel_id=str(channel_id or "").strip(), **_account_fields(cookie_header, account_index)
    )


def channel_action(cookie_header, channel_id, operation, *, account_index=0):
    """Inscreve, cancela a inscrição ou muda as notificações de *channel_id*."""
    return _request_action(
        "channel_action",
        channel_id=str(channel_id or "").strip(),
        operation=str(operation or ""),
        **_account_fields(cookie_header, account_index),
    )


def channel_posts_page(channel_id, *, start, count, cookie_header="", account_index=0):
    """Uma página dos posts de um canal e se há mais."""
    response = _request_action(
        "channel_posts",
        channel_id=str(channel_id or "").strip(),
        start=start,
        count=count,
        **_account_fields(cookie_header, account_index),
    )
    return list(response.get("entries") or []), bool(response.get("has_more"))


def channel_about(channel_id):
    """A página "Sobre" de um canal: descrição, inscritos, vídeos, visualizações, país e links."""
    return _request_action("channel_about", channel_id=str(channel_id or "").strip())


def channel_search_page(channel_id, query, *, start, count):
    """Uma página do que a busca de dentro de um canal acha nos vídeos dele, e se há mais."""
    response = _request_action(
        "channel_search",
        channel_id=str(channel_id or "").strip(),
        query=str(query or "").strip(),
        start=start,
        count=count,
    )
    return list(response.get("entries") or []), bool(response.get("has_more"))


def post_vote(cookie_header, post_id, choice, *, remove=False, account_index=0):
    """Vota na opção *choice* da enquete de um post, ou tira o voto dela com *remove*."""
    return _request_action(
        "post_vote",
        post_id=str(post_id or "").strip(),
        choice=int(choice),
        operation="unvote" if remove else "vote",
        **_account_fields(cookie_header, account_index),
    )


def watch_history_page(cookie_header, *, start, count, account_index=0):
    """Uma página do histórico do YouTube da conta e se há mais."""
    response = _request_action(
        "watch_history", start=start, count=count, **_account_fields(cookie_header, account_index)
    )
    return list(response.get("entries") or []), bool(response.get("has_more"))


def add_to_watch_history(cookie_header, media_url, *, account_index=0):
    """Põe o vídeo *media_url* no histórico do YouTube da conta; devolve se o YouTube aceitou."""
    response = _request_action(
        "add_to_history", media_url=str(media_url or "").strip(), **_account_fields(cookie_header, account_index)
    )
    return bool(response.get("ok"))


def live_chat(media_url, *, restart=False, cookie_header="", account_index=0):
    """O que chegou no chat ao vivo de *media_url* desde o último pedido.

    Devolve ``(mensagens, se a conta pode enviar, se a transmissão acabou, nome da
    conta no chat, por que a conta não pode enviar)``; *restart* recomeça das
    mensagens mais recentes.
    """
    response = _request_action(
        "live_chat",
        media_url=str(media_url or "").strip(),
        restart=bool(restart),
        **_account_fields(cookie_header, account_index),
    )
    return (
        list(response.get("entries") or []),
        bool(response.get("can_send")),
        bool(response.get("ended")),
        str(response.get("viewer") or "").strip(),
        str(response.get("restriction") or "").strip(),
    )


def live_chat_send(cookie_header, media_url, text, *, account_index=0):
    """Envia *text* ao chat ao vivo de *media_url* com a conta."""
    return _request_action(
        "live_chat_send",
        media_url=str(media_url or "").strip(),
        text=str(text or ""),
        **_account_fields(cookie_header, account_index),
    )


def audio_tracks(media_url, *, names=True):
    """As faixas de áudio de um vídeo dublado; com *names*, os nomes vêm no idioma do conteúdo."""
    response = _request_action("audio_tracks", media_url=str(media_url or "").strip(), names=bool(names))
    return list(response.get("tracks") or [])


def media_details(media_url):
    """Os detalhes de um vídeo ou música: descrição, canal, visualizações, curtidas e data."""
    return _request_action("details", media_url=str(media_url or "").strip())


def subscription_videos_page(cookie_header, *, start, count, account_index=0):
    """Uma página dos vídeos novos das inscrições da conta *account_index* de *cookie_header*."""
    response = _request_action(
        "subscription_videos",
        cookie=str(cookie_header or "").strip(),
        account_index=int(account_index or 0),
        start=start,
        count=count,
    )
    return list(response.get("entries") or []), bool(response.get("has_more"))


def subscribed_channels_page(cookie_header, *, start, count, account_index=0):
    """Uma página dos canais em que a conta *account_index* de *cookie_header* está inscrita."""
    response = _request_action(
        "subscribed_channels",
        cookie=str(cookie_header or "").strip(),
        account_index=int(account_index or 0),
        start=start,
        count=count,
    )
    return list(response.get("entries") or []), bool(response.get("has_more"))


def _request_action(action, **fields):
    """Pede uma ação ao processo do YouTube.js, com o idioma e a região do conteúdo."""
    response = _request_worker({"action": action, **youtubejs_locale(), **fields})
    if response.get("error"):
        raise RuntimeError(sanitize_sensitive_text(response["error"]))
    return response


def validate_youtubejs_dependencies() -> None:
    """Validate the managed Node.js resolver without making a network request."""
    node_executable = find_all_available_javascript_runtimes().get("node", "")
    resolver_dir = _youtubejs_resolver_dir()
    resolver_script = resolver_dir / "resolve.mjs"
    package_dir = _youtubejs_package_dir()
    if not node_executable or not resolver_script.is_file() or not package_dir.is_dir():
        raise RuntimeError(_("O Node.js ou o pacote YouTube.js não pôde ser preparado."))

    commands = (
        [node_executable, "--check", str(resolver_script)],
        [node_executable, "--input-type=module", "--eval", "await import('youtubei.js')"],
    )
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
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(resolver_dir),
        creationflags=creation_flags,
    )
    return _worker_process


def _read_worker_response(worker):
    result_queue = queue.Queue(maxsize=1)
    diagnostics = deque(maxlen=20)
    diagnostics_lock = threading.Lock()

    def diagnostic_text() -> str:
        with diagnostics_lock:
            return " | ".join(diagnostics)[-2000:]

    def read_result():
        try:
            while line := worker.stdout.readline():
                if line.startswith(_RESULT_PREFIX):
                    result_queue.put((line, None))
                    return
                normalized_line = " ".join(str(line or "").split())
                if normalized_line:
                    with diagnostics_lock:
                        diagnostics.append(sanitize_sensitive_text(normalized_line))
            result_queue.put(("", RuntimeError("O processo do YouTube.js foi encerrado.")))
        except Exception as exc:
            result_queue.put(("", exc))

    reader = threading.Thread(target=read_result, daemon=True)
    reader.start()
    reader.join(YOUTUBEJS_RESOLUTION_TIMEOUT_SECONDS)
    if reader.is_alive():
        message = _("O YouTube.js demorou demais para responder.")
        detail = diagnostic_text()
        if detail:
            message += " " + _("Detalhes: {detail}").format(detail=detail)
        raise RuntimeError(message)

    response_line, error = result_queue.get_nowait()
    if error is not None:
        message = str(error)
        detail = diagnostic_text()
        if detail:
            message += " " + _("Detalhes: {detail}").format(detail=detail)
        raise RuntimeError(message) from error
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
