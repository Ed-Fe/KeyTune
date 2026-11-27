"""Entrega o zip portátil ao KeyTuneUpdater, fora da pasta que será trocada.

O atualizador está dentro da pasta do programa. Ele é copiado para uma pasta
temporária e iniciado de lá, senão a troca de arquivos o apaga enquanto ele
ainda está em execução. O instalador do Windows não entra neste caminho.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from ..constants import WINDOWS_UPDATER_EXECUTABLE_NAME
from ..i18n import _
from ..log import get_logger
from ..portable import PORTABLE_DATA_DIR_NAME, PORTABLE_MARKER_NAME


_logger = get_logger(__name__)


def launch_portable_update(
    archive_path: str | os.PathLike[str],
    *,
    parent_pid: int | None = None,
    target_version: str = "",
) -> None:
    """Copia o atualizador para fora da pasta e pede a troca dos arquivos.

    Não roda o instalador. O hash do zip já foi conferido no download.
    """
    from .service import (
        UpdateError,
        can_self_update,
        clear_pending_update,
        record_pending_update,
        unsupported_install_message,
    )
    from ..portable import application_dir, is_portable, portable_storage_warning

    if not can_self_update():
        raise UpdateError(unsupported_install_message())
    if not is_portable():
        raise UpdateError(_("Não foi possível preparar a atualização portátil."))

    app_dir = application_dir()
    if app_dir is None or not app_dir.is_dir():
        raise UpdateError(_("Não foi possível encontrar a pasta da versão portátil."))

    updater = app_dir / WINDOWS_UPDATER_EXECUTABLE_NAME
    if not updater.is_file():
        raise UpdateError(_("Não foi possível encontrar o atualizador da versão portátil."))

    archive_file = Path(archive_path).resolve()
    if not archive_file.is_file():
        raise UpdateError(_("Não foi possível encontrar o arquivo baixado."))

    try:
        if portable_storage_warning() is not None:
            raise PermissionError("Portable data directory is not writable")
        with tempfile.NamedTemporaryFile(dir=app_dir, prefix="keytune-update-probe-") as probe:
            probe.write(b"\0")
            probe.flush()
    except OSError as exc:
        raise UpdateError(
            _(
                "Não foi possível gravar na pasta do KeyTune. "
                "A atualização portátil precisa de permissão de escrita nessa pasta."
            )
        ) from exc

    try:
        runner_directory = Path(tempfile.mkdtemp(prefix="keytune-updater-runner-"))
    except OSError as exc:
        raise UpdateError(_("Não foi possível preparar a atualização portátil.")) from exc
    runner_updater = runner_directory / updater.name
    runner_archive = runner_directory / archive_file.name
    try:
        shutil.copy2(updater, runner_updater)
        shutil.copy2(archive_file, runner_archive)
    except OSError as exc:
        shutil.rmtree(runner_directory, ignore_errors=True)
        raise UpdateError(_("Não foi possível preparar a atualização portátil.")) from exc

    pid = int(os.getpid() if parent_pid is None else parent_pid)
    command = [
        str(runner_updater),
        "--parent-pid",
        str(pid),
        "--app-dir",
        str(app_dir),
        "--package",
        str(runner_archive),
        "--restart-executable",
        Path(sys.executable).name,
    ]
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform.startswith("win") else 0

    record_pending_update(target_version)
    try:
        subprocess.Popen(
            command,
            cwd=str(runner_directory),
            close_fds=True,
            creationflags=creationflags,
        )
    except OSError as exc:
        _logger.error("Failed to launch the portable updater: %s", exc)
        clear_pending_update()
        shutil.rmtree(runner_directory, ignore_errors=True)
        raise UpdateError(_("Não foi possível preparar a atualização portátil.")) from exc
    _logger.info(
        "Portable updater launched for %s (preserve %s and %s)",
        app_dir,
        PORTABLE_MARKER_NAME,
        PORTABLE_DATA_DIR_NAME,
    )
