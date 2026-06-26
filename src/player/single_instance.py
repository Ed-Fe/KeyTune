"""Single instance enforcement via named pipe IPC on Windows.

When the app starts, it forwards its launch to an already-running instance and
exits.  A launch carrying file paths (e.g. from Explorer) is delivered as an
``open`` message; a bare launch (Start Menu, shortcut) is delivered as a
``focus`` message so the running window comes to front.  If no pipe exists, a
background listener is started so future launches can forward here.
"""

import threading
from multiprocessing.connection import Client, Listener

from .constants import APP_TITLE
from .log import get_logger

logger = get_logger(__name__)

_PIPE_ADDRESS = rf"\\.\pipe\{APP_TITLE}_SingleInstance"
_PIPE_AUTH_KEY = b"keytune-single-instance"

ACTION_OPEN = "open"
ACTION_FOCUS = "focus"


def try_send_to_existing_instance(paths: list[str]) -> bool:
    """Forward this launch to an already-running instance.

    A non-empty *paths* sends an ``open`` request (the running instance plays
    the files **without** stealing focus); an empty *paths* sends a ``focus``
    request (the running window comes to front).

    Returns ``True`` if the message was delivered, meaning the caller should
    exit.  Returns ``False`` when no other instance is listening and the
    caller should continue with normal startup.
    """
    if paths:
        message = {"action": ACTION_OPEN, "paths": list(paths)}
    else:
        message = {"action": ACTION_FOCUS}
    try:
        conn = Client(_PIPE_ADDRESS, authkey=_PIPE_AUTH_KEY)
        conn.send(message)
        conn.close()
        return True
    except (ConnectionRefusedError, FileNotFoundError, OSError):
        return False


class SingleInstanceServer:
    """Background named-pipe listener that receives launches from new instances.

    *on_message_received* is called **from a background thread** with a message
    dict (``{"action": "open", "paths": [...]}`` or ``{"action": "focus"}``).
    Callers that need to touch the UI must bridge to the main thread (e.g.
    ``wx.CallAfter``).
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
                finally:
                    conn.close()
                if message and self._callback:
                    self._callback(message)
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
