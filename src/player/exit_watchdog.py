"""Garante que o processo termine mesmo se algum desligamento travar.

Um desligamento que trava (por exemplo ao liberar o mpv) deixa o KeyTune vivo
em segundo plano, sem janela: o ícone some, mas o processo segura os arquivos
da instalação e atende o pipe de instância única, e a próxima abertura não
mostra nada. O watchdog encerra o processo à força depois de um prazo.
"""

import os
import threading
import time

from .log import get_logger

_logger = get_logger(__name__)

SHUTDOWN_DEADLINE_SECONDS = 20.0
INTERPRETER_EXIT_DEADLINE_SECONDS = 10.0

_armed = False
_lock = threading.Lock()


def arm_exit_watchdog(seconds: float) -> None:
    """Força a saída do processo em *seconds*, se ele ainda estiver vivo."""
    global _armed
    with _lock:
        if _armed:
            return
        _armed = True

    def _force_exit():
        time.sleep(seconds)
        _logger.error("O encerramento do KeyTune excedeu %.0f s; forçando a saída.", seconds)
        os._exit(0)

    threading.Thread(target=_force_exit, name="keytune-exit-watchdog", daemon=True).start()
