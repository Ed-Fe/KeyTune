from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import time
import zipfile
from urllib import error, request

from ..constants import APP_TITLE, APP_VERSION, UPDATE_DOWNLOAD_CHUNK_SIZE, UPDATE_HTTP_TIMEOUT_SECONDS
from ..session import get_app_storage_dir
from .yt_dlp_runtime import (
    get_managed_yt_dlp_executable_path,
    get_yt_dlp_version,
    install_or_update_yt_dlp_executable,
    yt_dlp_executable_available,
)


YTMUSICAPI_IMPORT_NAME = "ytmusicapi"
YTMUSICAPI_PACKAGE_NAME = "ytmusicapi"
YTMUSICAPI_PYPI_JSON_URL = f"https://pypi.org/pypi/{YTMUSICAPI_PACKAGE_NAME}/json"
YOUTUBE_DEPENDENCY_INSTALL_TIMEOUT_SECONDS = 240


@dataclass(frozen=True, slots=True)
class YouTubeDependencyUpdateResult:
    updated: bool
    versions: dict[str, str]
    command_output: str = ""


@dataclass(frozen=True, slots=True)
class _PyPIWheelInfo:
    version: str
    filename: str
    download_url: str
    sha256: str


@dataclass(slots=True)
class _RuntimeDependencyConfig:
    managed_install_enabled: bool = False
    auto_update_enabled: bool = True
    prefer_nightly_yt_dlp: bool = False


_RUNTIME_CONFIG = _RuntimeDependencyConfig()
_RUNTIME_CONFIG_LOCK = threading.Lock()


def configure_youtube_dependency_management(
    *,
    managed_install_enabled: bool,
    auto_update_enabled: bool,
    prefer_nightly_yt_dlp: bool = False,
) -> None:
    with _RUNTIME_CONFIG_LOCK:
        _RUNTIME_CONFIG.managed_install_enabled = bool(managed_install_enabled)
        _RUNTIME_CONFIG.auto_update_enabled = bool(auto_update_enabled)
        _RUNTIME_CONFIG.prefer_nightly_yt_dlp = bool(prefer_nightly_yt_dlp)


def youtube_dependency_management_enabled() -> bool:
    with _RUNTIME_CONFIG_LOCK:
        return bool(_RUNTIME_CONFIG.managed_install_enabled)


def youtube_dependency_auto_update_enabled() -> bool:
    with _RUNTIME_CONFIG_LOCK:
        return bool(_RUNTIME_CONFIG.auto_update_enabled)


def youtube_dependency_nightly_yt_dlp_enabled() -> bool:
    with _RUNTIME_CONFIG_LOCK:
        return bool(_RUNTIME_CONFIG.prefer_nightly_yt_dlp)


def get_youtube_dependency_target_dir() -> Path:
    return Path(get_app_storage_dir()) / "resources" / "youtube_music" / "site-packages"


def activate_youtube_dependency_target_dir() -> Path:
    target_dir = get_youtube_dependency_target_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    normalized_target_dir = str(target_dir)
    if normalized_target_dir not in sys.path:
        sys.path.insert(0, normalized_target_dir)
    return target_dir


def youtube_dependencies_available() -> bool:
    activate_youtube_dependency_target_dir()
    return _can_import_dependency(YTMUSICAPI_IMPORT_NAME) and yt_dlp_executable_available()


def ensure_yt_dlp_executable_available() -> None:
    if yt_dlp_executable_available():
        return

    if not youtube_dependency_management_enabled():
        raise RuntimeError(
            "O executável yt-dlp não está disponível. "
            "Ative os Recursos adicionais nas Preferências para baixar e atualizar automaticamente."
        )

    install_or_update_youtube_dependencies(
        force=False,
        include_prerelease=youtube_dependency_nightly_yt_dlp_enabled(),
    )
    if not yt_dlp_executable_available():
        raise RuntimeError("O executável yt-dlp foi baixado, mas não pôde ser preparado nesta execução.")


def get_installed_youtube_dependency_versions() -> dict[str, str]:
    activate_youtube_dependency_target_dir()
    versions: dict[str, str] = {}

    try:
        ytmusicapi_module = importlib.import_module(YTMUSICAPI_IMPORT_NAME)
    except Exception:
        ytmusicapi_module = None
    if ytmusicapi_module is not None:
        versions["ytmusicapi"] = _resolve_module_version(ytmusicapi_module)

    yt_dlp_version = get_yt_dlp_version()
    if yt_dlp_version:
        versions["yt-dlp"] = yt_dlp_version

    return versions


def is_youtube_dependency_auto_update_due(
    last_update_epoch_seconds: int,
    *,
    interval_hours: int,
    now_epoch_seconds: int | None = None,
) -> bool:
    normalized_interval_hours = _normalize_interval_hours(interval_hours)
    try:
        normalized_last_update_epoch_seconds = int(last_update_epoch_seconds)
    except (TypeError, ValueError):
        normalized_last_update_epoch_seconds = 0

    if normalized_last_update_epoch_seconds <= 0:
        return True

    current_epoch_seconds = int(now_epoch_seconds if now_epoch_seconds is not None else time.time())
    elapsed_seconds = current_epoch_seconds - normalized_last_update_epoch_seconds
    return elapsed_seconds >= (normalized_interval_hours * 3600)


def install_or_update_youtube_dependencies(
    *,
    force: bool = False,
    timeout_seconds: int = YOUTUBE_DEPENDENCY_INSTALL_TIMEOUT_SECONDS,
    include_prerelease: bool = False,
) -> YouTubeDependencyUpdateResult:
    output_parts: list[str] = []

    target_dir = activate_youtube_dependency_target_dir()
    ytmusicapi_was_available = _dependency_spec_available(YTMUSICAPI_IMPORT_NAME)
    yt_dlp_managed_exists = get_managed_yt_dlp_executable_path().is_file()

    versions_before = get_installed_youtube_dependency_versions()

    if force or not ytmusicapi_was_available:
        installed_version = _install_or_update_ytmusicapi(
            target_dir=target_dir,
            timeout_seconds=timeout_seconds,
        )
        if installed_version:
            output_parts.append(f"ytmusicapi {installed_version}")

    if force or not yt_dlp_managed_exists:
        yt_dlp_version = install_or_update_yt_dlp_executable(
            force=force,
            include_prerelease=include_prerelease,
            timeout_seconds=timeout_seconds,
        )
        if yt_dlp_version:
            output_parts.append(f"yt-dlp {yt_dlp_version}")

    if not youtube_dependencies_available():
        raise RuntimeError(
            "Os recursos adicionais do YouTube Music foram preparados, mas nem todos puderam ser carregados. "
            "Reinicie o aplicativo e tente novamente."
        )

    versions_after = get_installed_youtube_dependency_versions()
    updated = versions_after != versions_before

    return YouTubeDependencyUpdateResult(
        updated=updated,
        versions=versions_after,
        command_output="\n".join(part for part in output_parts if part).strip(),
    )


def import_ytmusicapi_module(*, reload: bool = False):
    activate_youtube_dependency_target_dir()
    if reload:
        _clear_dependency_modules((YTMUSICAPI_IMPORT_NAME,))
        importlib.invalidate_caches()

    try:
        return importlib.import_module(YTMUSICAPI_IMPORT_NAME)
    except Exception as initial_error:
        if not youtube_dependency_management_enabled():
            raise RuntimeError(
                "A dependência ytmusicapi não está instalada. "
                "Ative os Recursos adicionais nas Preferências para baixar e atualizar automaticamente."
            ) from initial_error

        try:
            install_or_update_youtube_dependencies(
                force=False,
                include_prerelease=youtube_dependency_nightly_yt_dlp_enabled(),
            )
        except Exception as exc:
            raise RuntimeError(
                f"Não foi possível preparar a dependência ytmusicapi automaticamente. Detalhes: {exc}"
            ) from exc

        try:
            return importlib.import_module(YTMUSICAPI_IMPORT_NAME)
        except Exception as final_error:
            raise RuntimeError(
                "A dependência ytmusicapi foi baixada, mas não pôde ser carregada. "
                "Reinicie o aplicativo e tente novamente."
            ) from final_error


def _install_or_update_ytmusicapi(
    *,
    target_dir: Path,
    timeout_seconds: int,
) -> str:
    wheel_info = _fetch_latest_ytmusicapi_wheel_info(timeout_seconds=timeout_seconds)

    download_dir = Path(tempfile.mkdtemp(prefix="keytune-ytmusicapi-"))
    wheel_path = download_dir / wheel_info.filename
    try:
        _download_binary_file(
            wheel_info.download_url,
            wheel_path,
            timeout_seconds=timeout_seconds,
        )

        actual_sha256 = _calculate_sha256(wheel_path)
        if actual_sha256.casefold() != wheel_info.sha256.casefold():
            raise RuntimeError("O wheel da ytmusicapi baixado não passou na validação de integridade.")

        _remove_previous_ytmusicapi_install(target_dir)
        _extract_wheel(wheel_path, target_dir)
    finally:
        shutil.rmtree(download_dir, ignore_errors=True)

    # Drop cached module entries so the next import picks up the new files.
    _clear_dependency_modules((YTMUSICAPI_IMPORT_NAME,))
    importlib.invalidate_caches()
    return wheel_info.version


def _fetch_latest_ytmusicapi_wheel_info(*, timeout_seconds: int) -> _PyPIWheelInfo:
    payload = _download_json(YTMUSICAPI_PYPI_JSON_URL, timeout_seconds=timeout_seconds)

    info_section = payload.get("info") if isinstance(payload, dict) else None
    if not isinstance(info_section, dict):
        raise RuntimeError("A resposta da PyPI para ytmusicapi veio em formato inválido.")
    version_text = str(info_section.get("version") or "").strip()
    if not version_text:
        raise RuntimeError("A PyPI não informou a versão mais recente da ytmusicapi.")

    releases_section = payload.get("releases") if isinstance(payload, dict) else None
    if not isinstance(releases_section, dict):
        raise RuntimeError("A PyPI não publicou a lista de releases da ytmusicapi.")
    assets = releases_section.get(version_text)
    if not isinstance(assets, list) or not assets:
        raise RuntimeError("A PyPI não publicou arquivos para a versão mais recente da ytmusicapi.")

    for asset in assets:
        if not isinstance(asset, dict):
            continue
        if str(asset.get("packagetype") or "").strip() != "bdist_wheel":
            continue
        filename = str(asset.get("filename") or "").strip()
        download_url = str(asset.get("url") or "").strip()
        digests = asset.get("digests") if isinstance(asset.get("digests"), dict) else {}
        sha256_digest = str(digests.get("sha256") or "").strip()
        if not filename or not download_url or len(sha256_digest) != 64:
            continue
        return _PyPIWheelInfo(
            version=version_text,
            filename=filename,
            download_url=download_url,
            sha256=sha256_digest,
        )

    raise RuntimeError("A release mais recente da ytmusicapi não publicou um wheel utilizável.")


def _download_json(url: str, *, timeout_seconds: int) -> dict:
    json_request = request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": f"{APP_TITLE}/{APP_VERSION}",
        },
    )
    try:
        with request.urlopen(
            json_request,
            timeout=max(5, int(timeout_seconds or 0) or UPDATE_HTTP_TIMEOUT_SECONDS),
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (error.HTTPError, error.URLError, json.JSONDecodeError) as exc:
        raise RuntimeError("Não foi possível consultar a release mais recente da ytmusicapi.") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("A resposta da PyPI veio em formato inválido.")
    return payload


def _download_binary_file(url: str, destination_path: Path, *, timeout_seconds: int) -> None:
    download_request = request.Request(
        url,
        headers={
            "Accept": "application/octet-stream",
            "User-Agent": f"{APP_TITLE}/{APP_VERSION}",
        },
    )
    try:
        with request.urlopen(
            download_request,
            timeout=max(10, int(timeout_seconds or 0)),
        ) as response:
            with open(destination_path, "wb") as target_file:
                shutil.copyfileobj(response, target_file, length=UPDATE_DOWNLOAD_CHUNK_SIZE)
    except (error.HTTPError, error.URLError, OSError) as exc:
        raise RuntimeError("Não foi possível baixar o wheel oficial da ytmusicapi.") from exc


def _calculate_sha256(file_path: Path) -> str:
    digest = hashlib.sha256()
    with open(file_path, "rb") as source_file:
        while True:
            chunk = source_file.read(UPDATE_DOWNLOAD_CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _remove_previous_ytmusicapi_install(target_dir: Path) -> None:
    package_dir = target_dir / YTMUSICAPI_IMPORT_NAME
    if package_dir.is_dir():
        shutil.rmtree(package_dir, ignore_errors=True)

    normalized_name = YTMUSICAPI_PACKAGE_NAME.replace("-", "_").lower()
    try:
        for entry in target_dir.iterdir():
            if not entry.is_dir():
                continue
            name_lower = entry.name.lower()
            if not name_lower.endswith(".dist-info"):
                continue
            stem = name_lower[: -len(".dist-info")]
            dash_pos = stem.rfind("-")
            if dash_pos < 0:
                continue
            dist_name = stem[:dash_pos].replace("-", "_")
            if dist_name == normalized_name:
                shutil.rmtree(entry, ignore_errors=True)
    except OSError:
        pass


def _extract_wheel(wheel_path: Path, target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(wheel_path) as wheel_archive:
            for member_name in wheel_archive.namelist():
                # zipfile.extract already rejects absolute paths and parent
                # traversal, but be explicit so a malicious wheel cannot escape
                # the target directory.
                normalized_member = member_name.replace("\\", "/")
                if normalized_member.startswith("/") or ".." in normalized_member.split("/"):
                    raise RuntimeError("O wheel da ytmusicapi contém caminhos inválidos.")
            wheel_archive.extractall(target_dir)
    except zipfile.BadZipFile as exc:
        raise RuntimeError("O wheel da ytmusicapi baixado está corrompido.") from exc
    except OSError as exc:
        raise RuntimeError("Não foi possível extrair o wheel da ytmusicapi.") from exc


def _clear_dependency_modules(module_names: tuple[str, ...]) -> None:
    normalized_module_names = [str(module_name or "").strip() for module_name in module_names]
    normalized_module_names = [module_name for module_name in normalized_module_names if module_name]
    if not normalized_module_names:
        return

    for loaded_module_name in list(sys.modules.keys()):
        if any(
            loaded_module_name == module_name or loaded_module_name.startswith(f"{module_name}.")
            for module_name in normalized_module_names
        ):
            sys.modules.pop(loaded_module_name, None)


def _can_import_dependency(import_name: str) -> bool:
    try:
        importlib.import_module(import_name)
        return True
    except Exception:
        return False


def _dependency_spec_available(import_name: str) -> bool:
    normalized_import_name = str(import_name or "").strip()
    if not normalized_import_name:
        return False

    try:
        return importlib.util.find_spec(normalized_import_name) is not None
    except Exception:
        return False


def _resolve_module_version(module) -> str:
    for attribute_name in ("__version__", "VERSION"):
        value = getattr(module, attribute_name, "")
        if isinstance(value, str):
            normalized_value = value.strip()
            if normalized_value:
                return normalized_value

    distribution_name = getattr(module, "__name__", "")
    if distribution_name:
        try:
            from importlib import metadata as importlib_metadata

            distribution_version = importlib_metadata.version(distribution_name)
            normalized_distribution_version = str(distribution_version or "").strip()
            if normalized_distribution_version:
                return normalized_distribution_version
        except Exception:
            pass

    return "desconhecida"


def _normalize_interval_hours(value: int) -> int:
    try:
        normalized_value = int(value)
    except (TypeError, ValueError):
        normalized_value = 24
    return max(1, min(720, normalized_value))
