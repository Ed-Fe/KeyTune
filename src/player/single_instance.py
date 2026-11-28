"""Single instance enforcement via named pipe IPC on Windows.

When the app starts, it forwards its launch to an already-running instance and
exits.  A launch carrying file paths (e.g. from Explorer) is delivered as an
``open`` message; ``--enqueue`` is delivered as an ``enqueue`` message so the
files join the playlist without interrupting playback.  A bare launch (Start
Menu, shortcut) is delivered as a ``focus`` message so the running window comes
to front.  If no pipe exists, a background listener is started so future
launches can forward here.
"""

import os
import signal
import threading
import time
from multiprocessing.connection import Client, Listener

from .constants import APP_TITLE
from .log import get_logger
from .portable import portable_copy_id

logger = get_logger(__name__)


def build_pipe_address(*, dev_mode=None):
    """Return the named-pipe address for this installed or portable copy."""
    if dev_mode is None:
        dev_mode = bool(os.environ.get("KEYTUNE_DEV_MODE"))
    pipe_suffix = "_Dev" if dev_mode else ""
    copy_id = portable_copy_id()
    if copy_id is not None:
        pipe_suffix += f"_Portable_{copy_id}"
    return rf"\\.\pipe\{APP_TITLE}_SingleInstance{pipe_suffix}"


_PIPE_ADDRESS = build_pipe_address()
_PIPE_AUTH_KEY = b"keytune-single-instance"

ACTION_OPEN = "open"
ACTION_ENQUEUE = "enqueue"
ACTION_FOCUS = "focus"


# Quanto esperar a confirmação da instância existente. A UI dela confirma em
# até ``UI_ACK_TIMEOUT_SECONDS``; o cliente espera um pouco mais que isso.
# O prazo é folgado de propósito: sem confirmação, a instância é encerrada à força, e uma
# janela só ocupada por alguns segundos (disco lento, lista grande) não pode cair nisso.
UI_ACK_TIMEOUT_SECONDS = 15.0
_CLIENT_REPLY_TIMEOUT_SECONDS = 18.0
_STALLED_EXIT_WAIT_SECONDS = 5.0


def build_instance_message(paths, *, enqueue=False):
    """Return the pipe message for this launch.

    ``enqueue`` with at least one path asks the running instance to append the
    files without playing them.  An enqueue launch with no paths falls back to
    ``focus``, same as a bare launch.
    """
    normalized_paths = list(paths or [])
    if enqueue and normalized_paths:
        return {"action": ACTION_ENQUEUE, "paths": normalized_paths}
    if normalized_paths:
        return {"action": ACTION_OPEN, "paths": normalized_paths}
    return {"action": ACTION_FOCUS}


def try_send_to_existing_instance(paths: list[str], *, enqueue: bool = False) -> bool:
    """Forward this launch to an already-running instance.

    A non-empty *paths* sends an ``open`` request (the running instance plays
    the files **without** stealing focus), unless *enqueue* is set, in which
    case the files are appended and playback is left alone.  An empty *paths*
    sends a ``focus`` request (the running window comes to front).

    Returns ``True`` if the running instance confirmed it handled the launch,
    meaning the caller should exit.  Returns ``False`` when no other instance is
    listening, or when the listening process is stalled (its pipe answers but
    its interface does not, e.g. a half-closed process left behind by an
    update); a stalled process is terminated and the caller starts normally.
    """
    message = build_instance_message(paths, enqueue=enqueue)
    try:
        conn = Client(_PIPE_ADDRESS, authkey=_PIPE_AUTH_KEY)
    except (ConnectionRefusedError, FileNotFoundError, OSError):
        return False

    reply = None
    try:
        conn.send(message)
        if conn.poll(_CLIENT_REPLY_TIMEOUT_SECONDS):
            reply = conn.recv()
        else:
            logger.warning("A instância em execução não respondeu ao pipe de instância única.")
    except EOFError:
        # Instâncias antigas fecham o pipe sem confirmar: tratam como entregue.
        return True
    except OSError:
        return False
    finally:
        try:
            conn.close()
        except OSError:
            pass

    if isinstance(reply, dict) and reply.get("handled") is not False:
        return True

    _terminate_stalled_instance(reply.get("pid") if isinstance(reply, dict) else None)
    return False


def dispatch_instance_message(target, message) -> bool:
    """Route a pipe message to the running window.

    Called on the UI thread (the pipe listener hops there with ``wx.CallAfter``
    before invoking this).  Returns ``False`` when there is no window or the
    action is unknown.
    """
    if target is None or not isinstance(message, dict):
        return False
    action = message.get("action")
    paths = list(message.get("paths") or [])
    if action == ACTION_OPEN:
        target.receive_external_files(paths)
        return True
    if action == ACTION_ENQUEUE:
        target.receive_external_enqueue(paths)
        return True
    if action == ACTION_FOCUS:
        target.focus_from_relaunch()
        return True
    return False


def _terminate_stalled_instance(pid) -> None:
    if not isinstance(pid, int) or pid <= 0 or pid == os.getpid():
        return
    logger.warning("Encerrando a instância travada do KeyTune (pid %s).", pid)
    try:
        os.kill(pid, signal.SIGTERM)  # TerminateProcess no Windows
    except OSError:
        return
    deadline = time.monotonic() + _STALLED_EXIT_WAIT_SECONDS
    while time.monotonic() < deadline:
        try:
            Client(_PIPE_ADDRESS, authkey=_PIPE_AUTH_KEY).close()
        except (ConnectionRefusedError, FileNotFoundError, OSError):
            return
        time.sleep(0.2)


class SingleInstanceServer:
    """Background named-pipe listener that receives launches from new instances.

    *on_message_received* is called **from a background thread** with a message
    dict (``{"action": "open", "paths": [...]}``, ``{"action": "enqueue",
    "paths": [...]}`` or ``{"action": "focus"}``).  Callers that need to touch
    the UI must bridge to the main thread (e.g. ``wx.CallAfter``).  It should
    return ``False`` when the interface did not handle the message in time, so
    the launching process knows this instance is stalled; any other return value
    counts as handled.
    """

    def __init__(self, on_message_received):
        self._callback = on_message_received
        self._running = True
        try:
            self._listener = Listener(_PIPE_ADDRESS, authkey=_PIPE_AUTH_KEY)
        except OSError:
            logger.warning("Não foi possível criar o pipe de instância única.")
            self._listener = None
            return
        self._thread = threading.Thread(target=self._listen, daemon=True)
        self._thread.start()

    def _listen(self):
        while self._running:
            try:
                conn = self._listener.accept()
                try:
                    message = conn.recv()
                    handled = True
                    if message and self._callback:
                        handled = self._callback(message) is not False
                    try:
                        conn.send({"handled": handled, "pid": os.getpid()})
                    except OSError:
                        pass
                finally:
                    conn.close()
            except OSError:
                if not self._running:
                    break
            except Exception:
                logger.exception("Erro ao receber dados no pipe de instância única.")

    def shutdown(self):
        self._running = False
        if self._listener:
            try:
                self._listener.close()
            except OSError:
                pass
