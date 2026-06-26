from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from urllib import error, request

from ..constants import (
    APP_VERSION,
    GITHUB_REPOSITORY_NAME,
    GITHUB_REPOSITORY_OWNER,
    UPDATE_DOWNLOAD_CHUNK_SIZE,
    UPDATE_HTTP_TIMEOUT_SECONDS,
    WINDOWS_SETUP_CHECKSUM_NAME,
    WINDOWS_SETUP_EXECUTABLE_NAME,
)
from ..install_info import read_install_info
from ..log import get_logger


_logger = get_logger(__name__)


UPDATE_REPOSITORY_OWNER_ENV = "MEDIA_PLAYER_UPDATE_REPOSITORY_OWNER"
UPDATE_REPOSITORY_NAME_ENV = "MEDIA_PLAYER_UPDATE_REPOSITORY_NAME"


class UpdateError(RuntimeError):
    pass


class UpdateCancelledError(UpdateError):
    pass


@dataclass(frozen=True)
class UpdateInfo:
    current_version: str
    latest_version: str
    release_name: str
    release_page_url: str
    release_notes: str
    archive_name: str
    archive_url: str
    archive_size_bytes: int
    checksum_name: str | None = None
    checksum_url: str | None = None


def check_for_update() -> UpdateInfo | None:
    current_version = normalize_version(APP_VERSION)
    _logger.info("Checking for updates (current version: %s)", current_version)
    latest_release = fetch_latest_release()
    if not is_newer_version(latest_release.latest_version, current_version):
        _logger.info("No update available; already on latest version %s", latest_release.latest_version)
        return None
    _logger.info("Update available: %s -> %s", current_version, latest_release.latest_version)
    return latest_release


def fetch_latest_release() -> UpdateInfo:
    repository_owner, repository_name = _configured_update_repository()
    api_url = f"https://api.github.com/repos/{repository_owner}/{repository_name}/releases/latest"
    _logger.debug("Fetching latest release info from: %s", api_url)
    payload = _fetch_json(api_url)

    tag_name = normalize_version(payload.get("tag_name") or payload.get("name") or "")
    if not tag_name:
        raise UpdateError("Não foi possível ler a versão mais recente.")

    _logger.debug("Latest release tag: %s", tag_name)

    assets = payload.get("assets")
    if not isinstance(assets, list):
        raise UpdateError("Não foi possível ler os arquivos da atualização.")

    archive_asset = _select_archive_asset(assets)
    if archive_asset is None:
        raise UpdateError("Não foi encontrado o arquivo da atualização.")

    checksum_asset = _select_checksum_asset(assets)
    archive_name = str(archive_asset.get("name") or WINDOWS_SETUP_EXECUTABLE_NAME)
    archive_url = str(archive_asset.get("browser_download_url") or "").strip()
    if not archive_url:
        raise UpdateError("Não foi possível abrir o arquivo da atualização.")

    return UpdateInfo(
        current_version=normalize_version(APP_VERSION),
        latest_version=tag_name,
        release_name=str(payload.get("name") or payload.get("tag_name") or archive_name),
        release_page_url=str(payload.get("html_url") or "").strip(),
        release_notes=str(payload.get("body") or "").strip(),
        archive_name=archive_name,
        archive_url=archive_url,
        archive_size_bytes=_safe_int(archive_asset.get("size")),
        checksum_name=str(checksum_asset.get("name") or "").strip() or None if checksum_asset else None,
        checksum_url=str(checksum_asset.get("browser_download_url") or "").strip() or None if checksum_asset else None,
    )


def download_release_archive(
    update_info: UpdateInfo,
    *,
    progress_callback=None,
    cancel_event: Event | None = None,
) -> Path:
    download_dir = Path(tempfile.mkdtemp(prefix="keytune-update-"))
    target_path = download_dir / update_info.archive_name
    partial_path = target_path.with_suffix(f"{target_path.suffix}.part")

    try:
        downloaded_bytes, total_bytes = _download_file(
            update_info.archive_url,
            partial_path,
            expected_size=update_info.archive_size_bytes,
            progress_callback=progress_callback,
            cancel_event=cancel_event,
        )
        os.replace(partial_path, target_path)
        _logger.info(
            "Release archive downloaded: %s (%s)",
            update_info.archive_name,
            format_byte_count(update_info.archive_size_bytes),
        )

        if update_info.checksum_url:
            if progress_callback is not None:
                progress_callback(downloaded_bytes, total_bytes, "Validando integridade do pacote...")
            expected_checksum = _download_expected_checksum(update_info.checksum_url)
            actual_checksum = _calculate_sha256(target_path)
            if actual_checksum.lower() != expected_checksum.lower():
                raise UpdateError("O arquivo baixado não pôde ser validado.")

        _logger.info("Release archive integrity verified: %s", target_path)
        return target_path
    except Exception:
        shutil.rmtree(download_dir, ignore_errors=True)
        raise


def can_self_update() -> bool:
    return sys.platform.startswith("win") and getattr(sys, "frozen", False)


def unsupported_install_message() -> str:
    return (
        "A instalação automática só está disponível na versão do Windows empacotada."
    )


# Silent install flags for the Inno Setup installer. The installer's [Run]
# section relaunches KeyTune automatically when invoked silently.
_SILENT_INSTALL_FLAGS = (
    "/VERYSILENT",
    "/SP-",
    "/SUPPRESSMSGBOXES",
    "/NORESTART",
    "/NOCANCEL",
)


def launch_installer_update(installer_path: str | os.PathLike[str], *, parent_pid: int | None = None) -> None:
    """Run the downloaded setup .exe silently to upgrade in place.

    The installer closes the running KeyTune (``CloseApplications=yes``),
    replaces the files, and relaunches the app. Per-machine installs require
    elevation, so we re-launch the installer via ``runas`` in that case.
    """
    if not can_self_update():
        raise UpdateError(unsupported_install_message())

    installer_file = Path(installer_path).resolve()
    if not installer_file.exists():
        raise UpdateError("Não foi possível encontrar o arquivo baixado.")

    # Copy out of the temp download dir so it isn't cleaned while the installer runs.
    runner_directory = Path(tempfile.mkdtemp(prefix="keytune-setup-runner-"))
    runner_installer = runner_directory / installer_file.name
    shutil.copy2(installer_file, runner_installer)

    install_info = read_install_info()
    needs_elevation = install_info is not None and install_info.mode == "machine"

    try:
        if needs_elevation:
            _launch_elevated(runner_installer)
        else:
            subprocess.Popen(
                [str(runner_installer), *_SILENT_INSTALL_FLAGS],
                cwd=str(runner_directory),
                close_fds=True,
            )
        _logger.info("Installer update launched (elevated=%s): %s", needs_elevation, runner_installer)
    except OSError as exc:
        _logger.error("Failed to launch installer update: %s", exc)
        raise UpdateError("Não foi possível abrir o instalador da atualização.") from exc


def _launch_elevated(installer: Path) -> None:
    import ctypes

    parameters = " ".join(_SILENT_INSTALL_FLAGS)
    # SW_SHOWNORMAL = 1. ShellExecuteW returns > 32 on success.
    result = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", str(installer), parameters, str(installer.parent), 1
    )
    if int(result) <= 32:
        raise OSError(f"ShellExecuteW failed with code {result}")


def normalize_version(value: str) -> str:
    text = str(value or "").strip()
    if text.lower().startswith("v"):
        text = text[1:]
    match = re.search(r"\d+(?:\.\d+)*", text)
    return match.group(0) if match else text


def is_newer_version(candidate: str, current: str) -> bool:
    return _version_key(candidate) > _version_key(current)


def format_byte_count(byte_count: int) -> str:
    size = max(0, int(byte_count or 0))
    units = ["B", "KB", "MB", "GB", "TB"]
    numeric_size = float(size)
    for unit in units:
        if numeric_size < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(numeric_size)} {unit}"
            return f"{numeric_size:.1f} {unit}".replace(".", ",")
        numeric_size /= 1024.0
    return f"{size} B"


def _version_key(version: str) -> tuple[int, ...]:
    parts = [int(part) for part in re.findall(r"\d+", normalize_version(version))]
    return tuple(parts or [0])


def _select_archive_asset(assets: list[dict]) -> dict | None:
    preferred_name = WINDOWS_SETUP_EXECUTABLE_NAME.casefold()
    for asset in assets:
        name = str(asset.get("name") or "").casefold()
        if name == preferred_name:
            return asset

    for asset in assets:
        name = str(asset.get("name") or "").casefold()
        if name.endswith("setup.exe"):
            return asset

    return None


def _select_checksum_asset(assets: list[dict]) -> dict | None:
    preferred_name = WINDOWS_SETUP_CHECKSUM_NAME.casefold()
    for asset in assets:
        name = str(asset.get("name") or "").casefold()
        if name == preferred_name:
            return asset

    for asset in assets:
        name = str(asset.get("name") or "").casefold()
        if name.endswith(".sha256"):
            return asset

    return None


def _fetch_json(url: str) -> dict:
    try:
        response_text = _download_text(url, accept_header="application/vnd.github+json")
        payload = json.loads(response_text)
    except error.URLError as exc:
        _logger.warning("Network error while fetching release info: %s", exc)
        raise UpdateError("Não foi possível verificar as atualizações.") from exc
    except json.JSONDecodeError as exc:
        _logger.warning("Failed to parse release info response: %s", exc)
        raise UpdateError("Não foi possível verificar as atualizações.") from exc

    if not isinstance(payload, dict):
        raise UpdateError("Não foi possível verificar as atualizações.")
    return payload


def _download_expected_checksum(url: str) -> str:
    checksum_text = _download_text(url)
    match = re.search(r"\b[a-fA-F0-9]{64}\b", checksum_text)
    if not match:
        raise UpdateError("Não foi possível validar a integridade do arquivo.")
    return match.group(0)


def _download_text(url: str, *, accept_header: str = "text/plain") -> str:
    request_headers = _request_headers(accept_header)
    release_request = request.Request(url, headers=request_headers)
    try:
        with request.urlopen(release_request, timeout=UPDATE_HTTP_TIMEOUT_SECONDS) as response:
            return response.read().decode("utf-8")
    except error.HTTPError as exc:
        raise UpdateError("Não foi possível acessar as atualizações.") from exc
    except error.URLError as exc:
        raise UpdateError("Não foi possível acessar as atualizações.") from exc


def _download_file(url: str, target_path: Path, *, expected_size: int, progress_callback=None, cancel_event: Event | None = None):
    download_request = request.Request(url, headers=_request_headers("application/octet-stream"))
    downloaded_bytes = 0
    total_bytes = max(0, int(expected_size or 0))

    try:
        with request.urlopen(download_request, timeout=UPDATE_HTTP_TIMEOUT_SECONDS) as response:
            content_length = _safe_int(response.headers.get("Content-Length"))
            if content_length > 0:
                total_bytes = content_length

            if progress_callback is not None:
                progress_callback(0, total_bytes, "Baixando atualização...")

            with open(target_path, "wb") as target_file:
                while True:
                    if cancel_event is not None and cancel_event.is_set():
                        raise UpdateCancelledError("Download cancelado pelo usuário.")

                    chunk = response.read(UPDATE_DOWNLOAD_CHUNK_SIZE)
                    if not chunk:
                        break

                    target_file.write(chunk)
                    downloaded_bytes += len(chunk)
                    if progress_callback is not None:
                        progress_callback(downloaded_bytes, total_bytes, "Baixando atualização...")
    except error.HTTPError as exc:
        raise UpdateError("Não foi possível baixar a atualização.") from exc
    except error.URLError as exc:
        raise UpdateError("Não foi possível baixar a atualização.") from exc
    finally:
        if cancel_event is not None and cancel_event.is_set() and target_path.exists():
            try:
                target_path.unlink()
            except OSError:
                pass

    return downloaded_bytes, total_bytes


def _calculate_sha256(file_path: Path) -> str:
    digest = hashlib.sha256()
    with open(file_path, "rb") as source_file:
        while True:
            chunk = source_file.read(UPDATE_DOWNLOAD_CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _request_headers(accept_header: str) -> dict[str, str]:
    return {
        "Accept": accept_header,
        "User-Agent": f"KeyTune/{APP_VERSION}",
    }


def _configured_update_repository() -> tuple[str, str]:
    repository_owner = str(os.environ.get(UPDATE_REPOSITORY_OWNER_ENV) or GITHUB_REPOSITORY_OWNER).strip()
    repository_name = str(os.environ.get(UPDATE_REPOSITORY_NAME_ENV) or GITHUB_REPOSITORY_NAME).strip()

    if not repository_owner or not repository_name:
        raise UpdateError("Não foi possível verificar as atualizações.")

    return repository_owner, repository_name


def _safe_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
