"""Reabrir o KeyTune sozinho, depois de uma mudança que só vale com o player aberto de novo.

A janela pede o reinício e fecha como sempre (a sessão é gravada); quando o
programa já soltou tudo, ``relaunch`` abre o processo novo.
"""

import os
import subprocess
import sys
from pathlib import Path

from .log import get_logger


_logger = get_logger(__name__)

# Com isto no ambiente, o processo novo não procura outro KeyTune aberto: o que
# pediu o reinício ainda pode estar terminando.
RESTART_ENVIRONMENT_VARIABLE = "KEYTUNE_RESTARTED"

_requested = False


def request_restart():
    global _requested
    _requested = True


def restart_requested():
    return _requested


def restart_command():
    """O comando que abre o KeyTune como este foi aberto, sem arquivos para tocar."""
    if getattr(sys, "frozen", False):
        return [sys.executable]
    return [sys.executable, str(Path(__file__).resolve().parents[1] / "main.py")]


def started_by_restart(environment=None):
    """Se este processo veio de um reinício; o aviso é consumido, para não passar aos processos filhos."""
    environment = os.environ if environment is None else environment
    return bool(environment.pop(RESTART_ENVIRONMENT_VARIABLE, ""))


def relaunch():
    """Abre o KeyTune de novo; devolve se conseguiu."""
    environment = dict(os.environ)
    environment[RESTART_ENVIRONMENT_VARIABLE] = "1"
    try:
        subprocess.Popen(restart_command(), env=environment, close_fds=True)
    except OSError as exc:
        _logger.warning("KeyTune could not be reopened: %s", exc)
        return False
    return True
