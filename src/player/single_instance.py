"""Single instance enforcement via named pipe IPC on Windows.

When the app starts, it checks whether another instance is already listening
on a named pipe.  If so, the new process sends its command-line paths to the
running instance and exits.  If no pipe exists, a background listener is
started so future launches can forward their paths here.
"""

import threading
from multiprocessing.connection import Client, Listener

from .constants import APP_TITLE
from .log import get_logger

logger = get_logger(__name__)

_PIPE_ADDRESS = rf"\\.\pipe\{APP_TITLE}_SingleInstance"
_PIPE_AUTH_KEY = b"keytune-single-instance"


def try_send_to_existing_instance(paths: list[str]) -> bool:
    """Try to send *paths* to an already-running instance.

    Returns ``True`` if the paths were delivered successfully, meaning the
    caller should exit.  Returns ``False`` when no other instance is
    listening and the caller should continue with normal startup.
    """
    try:
        conn = Client(_PIPE_ADDRESS, authkey=_PIPE_AUTH_KEY)
        conn.send(paths)
        conn.close()
        return True
    except (ConnectionRefusedError, FileNotFoundError, OSError):
        return False


class SingleInstanceServer:
    """Background named-pipe listener that receives paths from new instances.

    *on_paths_received* is called **from a background thread** with a list of
    file-path strings.  Callers that need to touch the UI must bridge to the
    main thread (e.g. ``wx.CallAfter``).
    """

    def __init__(self, on_paths_received):
        self._callback = on_paths_received
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
                    paths = conn.recv()
                finally:
                    conn.close()
                if paths and self._callback:
                    self._callback(paths)
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
