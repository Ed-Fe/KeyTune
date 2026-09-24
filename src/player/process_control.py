"""Controle de processos externos de longa duração (yt-dlp, FFmpeg).

Usado pelo download e pela conversão para cancelar, de outra thread, um
processo que já está rodando.
"""

from __future__ import annotations

import subprocess
import sys
import threading


def terminate_process_tree(process) -> None:
    if process.poll() is not None:
        return
    try:
        if sys.platform.startswith("win"):
            # O yt-dlp.exe empacotado lança um processo filho (e o FFmpeg,
            # outro): terminate() sozinho deixaria os dois órfãos.
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                check=False,
                capture_output=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        else:
            process.kill()
    except OSError:
        pass


class CancelToken:
    """Permite cancelar, de outra thread, uma tarefa que já está rodando."""

    def __init__(self):
        self._event = threading.Event()
        self._lock = threading.Lock()
        self._process: subprocess.Popen | None = None

    @property
    def cancelled(self):
        return self._event.is_set()

    @property
    def event(self):
        return self._event

    def attach(self, process):
        with self._lock:
            self._process = process
        if self._event.is_set():
            terminate_process_tree(process)

    def cancel(self):
        self._event.set()
        with self._lock:
            process = self._process
        if process is not None:
            terminate_process_tree(process)
