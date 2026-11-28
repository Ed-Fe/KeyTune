"""Troca os arquivos da versão portátil por um zip, com rollback.

O ``KeyTuneUpdater.exe`` chama :func:`apply_portable_update` depois que o
player fecha. ``portable.ini`` que já existe e a pasta ``data`` não são
substituídos. Se uma cópia falha, os arquivos já trocados voltam do backup e
o executável anterior é aberto de novo.
"""

from __future__ import annotations

import ntpath
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
import zlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .i18n import _
from .log import get_logger
from .portable import PORTABLE_DATA_DIR_NAME, PORTABLE_MARKER_NAME


PORTABLE_UPDATE_LOG_NAME = "portable-update.log"
_COPY_ATTEMPTS = 5
_RETRY_PAUSE_SECONDS = 0.4
_WAIT_TIMEOUT_SECONDS = 180
_METADATA_DIR = "__macosx"
_ARCHIVE_ERRORS = (zipfile.BadZipFile, EOFError, NotImplementedError, zlib.error)
_logger = get_logger(__name__)

StatusCallback = Callable[[str, str], None]


class PortableApplyError(RuntimeError):
    """A troca dos arquivos não pôde ser concluída."""


@dataclass(frozen=True)
class _Replacement:
    destination: Path
    backup: Path
    had_original: bool


def apply_portable_update(
    app_dir: str | Path,
    package: str | Path,
    *,
    restart_executable: str,
    parent_pid: int | None = None,
    relaunch: bool = True,
    copy_attempts: int = _COPY_ATTEMPTS,
    retry_pause_seconds: float = _RETRY_PAUSE_SECONDS,
    status_callback: StatusCallback | None = None,
) -> None:
    """Extrai *package* e substitui os arquivos de *app_dir*.

    Espera *parent_pid* encerrar antes de mexer na pasta. O log fica em
    ``data/portable-update.log``.
    """

    app_path = Path(app_dir).resolve()
    executable_name = ntpath.basename(restart_executable)
    log = _UpdateLog(app_path)

    def report(title: str, detail: str = "") -> None:
        log.write(title if not detail else f"{title} {detail}")
        if status_callback is not None:
            try:
                status_callback(title, detail)
            except Exception:
                _logger.exception("Could not show portable update progress")

    if not app_path.is_dir():
        raise PortableApplyError(_("A pasta do KeyTune não foi encontrada."))
    report(_("Preparando a atualização portátil."))
    if parent_pid:
        report(_("Aguardando o KeyTune fechar."))
        _wait_for_process_exit(int(parent_pid), timeout_seconds=_WAIT_TIMEOUT_SECONDS)

    work = None
    backup_dir = None
    preserve_backup = False
    replacements: list[_Replacement] = []
    retry = {"attempts": copy_attempts, "pause_seconds": retry_pause_seconds}
    executable = app_path / executable_name
    try:
        existing = {entry.name.casefold(): entry for entry in app_path.iterdir()}
        executable = existing.get(executable_name.casefold(), executable)
        package_path = Path(package).resolve()
        if not package_path.is_file():
            raise PortableApplyError(_("O pacote da atualização não foi encontrado."))
        work = Path(tempfile.mkdtemp(prefix="keytune-updater-job-"))
        extract_dir = work / "extract"
        report(_("Preparando os arquivos novos."))
        _extract_archive(package_path, extract_dir, executable_name)

        data_dir = existing.get(PORTABLE_DATA_DIR_NAME, app_path / PORTABLE_DATA_DIR_NAME)
        data_dir.mkdir(exist_ok=True)
        backup_dir = Path(tempfile.mkdtemp(
            prefix=f"portable-update-backup-{datetime.now():%Y%m%d-%H%M%S}-",
            dir=data_dir,
        ))
        report(_("Aplicando a atualização."))
        for entry in sorted(extract_dir.iterdir(), key=lambda entry: entry.name.casefold()):
            name = entry.name.casefold()
            original = existing.get(name)
            if name == PORTABLE_MARKER_NAME and original is not None:
                report(_("Mantendo o portable.ini que já está na pasta."))
                continue
            destination = original if original is not None else app_path / entry.name
            if original is None and os.path.lexists(destination):
                # Windows can resolve an 8.3 alias to a different directory entry.
                raise PortableApplyError(_("O pacote de atualização contém nomes de arquivo conflitantes."))
            replacement = _Replacement(destination, backup_dir / destination.name, original is not None)
            replacements.append(replacement)
            _replace_entry(entry, replacement, **retry)

        if relaunch:
            _relaunch(executable)
        report(_("Atualização concluída."), _("O KeyTune será aberto em instantes."))
    except Exception as exc:
        log.write(f"Portable update failed: {exc!r}")
        message = str(exc) if isinstance(exc, PortableApplyError) else _(
            "Não foi possível aplicar a atualização portátil."
        )
        failed_paths = []
        if replacements:
            report(_("Não foi possível aplicar a atualização. Restaurando a versão anterior."))
            failed_paths = _rollback(replacements, log=log, **retry)
            if failed_paths:
                preserve_backup = True
                message = _(
                    "Não foi possível restaurar todos os arquivos anteriores. "
                    "Os arquivos de backup foram preservados em {path}."
                ).format(path=backup_dir)
                log.write(message)
            else:
                report(_("A versão anterior foi restaurada."))
                message = _("Não foi possível aplicar a atualização portátil. A versão anterior foi restaurada.")
        if relaunch:
            try:
                if executable in failed_paths:
                    raise OSError(_("Não foi possível restaurar o executável anterior."))
                _relaunch(executable)
            except Exception as restart_error:
                restart_message = _("Não foi possível reabrir o KeyTune.")
                report(restart_message, str(restart_error))
                if restart_message not in message:
                    message += "\n\n" + restart_message
        raise PortableApplyError(message) from exc
    finally:
        if backup_dir is not None and not preserve_backup:
            shutil.rmtree(backup_dir, ignore_errors=True)
        if work is not None:
            shutil.rmtree(work, ignore_errors=True)


def _wait_for_process_exit(process_id: int, *, timeout_seconds: int) -> None:
    if process_id <= 0:
        return
    if sys.platform.startswith("win"):
        _wait_for_process_exit_windows(process_id, timeout_seconds=timeout_seconds)
        return

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            os.kill(process_id, 0)
        except OSError:
            return
        time.sleep(0.3)
    raise PortableApplyError(_("O tempo acabou esperando o KeyTune fechar."))


def _wait_for_process_exit_windows(process_id: int, *, timeout_seconds: int) -> None:
    import ctypes
    from ctypes import wintypes

    synchronize = 0x00100000
    error_invalid_parameter = 87
    wait_object_0 = 0x00000000
    wait_timeout = 0x00000102
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    handle = kernel32.OpenProcess(synchronize, False, int(process_id))
    if not handle:
        if ctypes.get_last_error() == error_invalid_parameter:
            return
        raise PortableApplyError(_("Não foi possível esperar o KeyTune fechar."))
    try:
        result = kernel32.WaitForSingleObject(handle, int(timeout_seconds * 1000))
    finally:
        kernel32.CloseHandle(handle)
    if result == wait_object_0:
        return
    if result == wait_timeout:
        raise PortableApplyError(_("O tempo acabou esperando o KeyTune fechar."))
    raise PortableApplyError(_("Não foi possível esperar o KeyTune fechar."))


def _archive_layout(archive: zipfile.ZipFile, executable_name: str):
    paths = {}
    members = {}
    for member in archive.infolist():
        if member.flag_bits & 1:
            raise zipfile.BadZipFile("Encrypted member")
        name = member.orig_filename.replace("\\", "/")
        is_dir = name.endswith("/")
        parts = tuple(name.removesuffix("/").split("/"))
        if any(not part or part in {".", ".."} or ntpath.isreserved(part) for part in parts):
            raise PortableApplyError(_("O pacote de atualização contém um caminho inválido."))

        # Index implicit directories as well as ZIP records, so A/x and a/y
        # cannot merge into the same directory when extracted on Windows.
        key = tuple(part.casefold() for part in parts)
        if key in members:
            raise PortableApplyError(_("O pacote de atualização contém nomes de arquivo conflitantes."))
        for depth in range(1, len(parts) + 1):
            prefix = key[:depth]
            entry = (parts[:depth], is_dir or depth < len(parts))
            if paths.setdefault(prefix, entry) != entry:
                raise PortableApplyError(_("O pacote de atualização contém nomes de arquivo conflitantes."))
        members[key] = member

    executable = executable_name.casefold()
    payload = ()
    if paths.get((executable,), ((), True))[1]:
        roots = [key for key in paths if len(key) == 1 and key[0] != _METADATA_DIR]
        if len(roots) != 1 or paths.get((*roots[0], executable), ((), True))[1]:
            raise PortableApplyError(_("O pacote de atualização não contém o programa."))
        payload = roots[0]

    if (PORTABLE_DATA_DIR_NAME,) in paths or (*payload, PORTABLE_DATA_DIR_NAME) in paths:
        raise PortableApplyError(_("O pacote de atualização contém a pasta de dados do KeyTune."))
    return payload, paths, members


def validate_portable_archive(
    package_path: Path,
    executable_name: str,
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> None:
    """Check the paths, executable and file CRCs while the player is still open."""
    try:
        with zipfile.ZipFile(package_path) as archive:
            _archive_layout(archive, executable_name)
            for member in archive.infolist():
                with archive.open(member) as source:
                    while source.read(1024 * 1024):
                        if check_cancelled is not None:
                            check_cancelled()
    except (OSError, *_ARCHIVE_ERRORS) as exc:
        raise PortableApplyError(_("O pacote de atualização está corrompido ou não pôde ser lido.")) from exc


def _extract_archive(package_path: Path, extract_directory: Path, executable_name: str) -> None:
    try:
        with zipfile.ZipFile(package_path) as archive:
            payload, paths, members = _archive_layout(archive, executable_name)
            for key, member in members.items():
                relative = key[len(payload):]
                if key[:len(payload)] != payload or not relative or relative[0] == _METADATA_DIR:
                    continue
                parts, is_dir = paths[key]
                target = extract_directory.joinpath(*parts[len(payload):])
                if is_dir:
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(member) as source, target.open("xb") as destination:
                        shutil.copyfileobj(source, destination)
    except _ARCHIVE_ERRORS as exc:
        raise PortableApplyError(_("O pacote de atualização está corrompido ou não pôde ser lido.")) from exc


def _replace_entry(
    source: Path,
    replacement: _Replacement,
    *,
    attempts: int,
    pause_seconds: float,
) -> None:
    if replacement.had_original:
        _call_with_retries(
            lambda: os.replace(replacement.destination, replacement.backup),
            attempts=attempts,
            pause_seconds=pause_seconds,
        )
    _call_with_retries(
        lambda: _copy_replacing(source, replacement.destination),
        attempts=attempts,
        pause_seconds=pause_seconds,
    )


def _rollback(
    replacements: list[_Replacement],
    *,
    log: _UpdateLog,
    attempts: int,
    pause_seconds: float,
) -> list[Path]:
    failed = []
    for replacement in reversed(replacements):
        destination, backup = replacement.destination, replacement.backup
        try:
            if replacement.had_original:
                # An absent backup means the initial atomic move failed and
                # the original is still in place.
                if os.path.lexists(backup):
                    _call_with_retries(
                        lambda: _restore_entry(backup, destination),
                        attempts=attempts,
                        pause_seconds=pause_seconds,
                    )
            else:
                _call_with_retries(
                    lambda: _remove_path_if_present(destination),
                    attempts=attempts,
                    pause_seconds=pause_seconds,
                )
        except Exception as exc:
            failed.append(destination)
            log.write(f"Could not restore {destination}: {exc!r}")
    return failed


def _restore_entry(backup: Path, destination: Path) -> None:
    _remove_path_if_present(destination)
    os.replace(backup, destination)


def _copy_replacing(source: Path, destination: Path) -> None:
    _remove_path_if_present(destination)
    if source.is_dir():
        shutil.copytree(source, destination)
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _remove_path(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
        return
    path.unlink()


def _remove_path_if_present(path: Path) -> None:
    if os.path.lexists(path):
        _remove_path(path)


def _call_with_retries(action: Callable[[], None], *, attempts: int, pause_seconds: float) -> None:
    last_error: Exception | None = None
    total = max(1, attempts)
    for attempt in range(total):
        try:
            action()
            return
        except OSError as exc:
            last_error = exc
            if attempt + 1 >= total:
                raise
            if pause_seconds > 0:
                time.sleep(pause_seconds)
    if last_error is not None:
        raise last_error


def _relaunch(executable: Path) -> None:
    if not executable.is_file():
        raise PortableApplyError(_("Não foi possível reabrir o KeyTune."))
    flags = 0
    if sys.platform.startswith("win"):
        flags = (
            getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
    subprocess.Popen(
        [str(executable)],
        cwd=str(executable.parent),
        close_fds=True,
        creationflags=flags,
    )


class _UpdateLog:
    def __init__(self, app_dir: Path):
        self.path = app_dir / PORTABLE_DATA_DIR_NAME / PORTABLE_UPDATE_LOG_NAME

    def write(self, message: str) -> None:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8", errors="backslashreplace") as handle:
                handle.write(f"[{stamp}] {message}\n")
        except OSError as exc:
            _logger.warning("Could not write %s: %s. %s", self.path, exc, message)
