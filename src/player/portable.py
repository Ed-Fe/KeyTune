"""Modo portátil: um arquivo marcador ao lado do executável guarda os dados junto dele.

O marcador é ``portable.ini`` (pode estar vazio) na pasta de ``sys.executable``
quando o app está empacotado (``sys.frozen``). Em desenvolvimento o marcador é
ignorado. A variável ``KEYTUNE_PORTABLE_DIR``, quando aponta para uma pasta,
faz o papel da pasta do executável e liga o modo portátil — é o que permite
testar sem um executável empacotado.

A pasta de dados é ``data`` dentro dessa pasta. Fora do modo portátil nada
aqui é consultado pelos caminhos normais.
"""

from __future__ import annotations

import hashlib
import ntpath
import os
import sys
import tempfile
from functools import cache
from pathlib import Path

from .log import get_logger


PORTABLE_MARKER_NAME = "portable.ini"
PORTABLE_DATA_DIR_NAME = "data"
PORTABLE_DIR_ENV = "KEYTUNE_PORTABLE_DIR"


def _env_portable_dir() -> Path | None:
    raw = os.environ.get(PORTABLE_DIR_ENV, "").strip()
    if not raw:
        return None
    path = Path(raw)
    try:
        if path.is_dir():
            return path.resolve()
    except OSError:
        return None
    return None


def application_dir() -> Path | None:
    """Pasta do executável empacotado, ou a pasta de ``KEYTUNE_PORTABLE_DIR``.

    A variável de ambiente, quando aponta para uma pasta, vem na frente: é a
    pasta que em desenvolvimento ocupa o lugar da pasta do executável.
    """
    override = _env_portable_dir()
    if override is not None:
        return override
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return None


def is_portable() -> bool:
    """Verdadeiro quando o KeyTune deve guardar tudo ao lado do executável."""
    if _env_portable_dir() is not None:
        return True
    if not getattr(sys, "frozen", False):
        return False
    app_dir = Path(sys.executable).resolve().parent
    try:
        return (app_dir / PORTABLE_MARKER_NAME).is_file()
    except OSError:
        return False


def portable_copy_id() -> str | None:
    """Return a stable identity for the portable directory."""
    app_dir = application_dir() if is_portable() else None
    if app_dir is None:
        return None
    normalized = ntpath.normcase(str(app_dir.resolve()))
    return hashlib.sha256(os.fsencode(normalized)).hexdigest()[:16]


def _data_path() -> Path:
    app_dir = application_dir() if is_portable() else None
    if app_dir is None:
        raise RuntimeError("portable_data_dir() called outside portable mode")
    return app_dir / PORTABLE_DATA_DIR_NAME


@cache
def _data_write_error(data_dir: Path) -> str | None:
    # Keep the choice of storage stable throughout the process.
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=data_dir, prefix="keytune-probe-") as probe:
            probe.write(b"\0")
            probe.flush()
    except OSError as exc:
        get_logger(__name__).warning("Cannot write to portable data directory %s: %s", data_dir, exc)
        return str(exc)
    return None


def portable_storage_warning() -> tuple[Path, str] | None:
    """Return the unwritable path and its error for this portable launch."""
    if is_portable():
        data_dir = _data_path()
        error = _data_write_error(data_dir)
        if error is not None:
            return data_dir, error
    return None


def portable_data_dir() -> str:
    """Use writable storage next to the executable or on this computer."""
    data_dir = _data_path()
    if _data_write_error(data_dir) is not None:
        from .session import _get_local_storage_dir

        return _get_local_storage_dir(allow_legacy=False)
    return str(data_dir)
