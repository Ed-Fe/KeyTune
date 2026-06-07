from __future__ import annotations

from dataclasses import dataclass
import importlib
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

from ..session import get_app_storage_dir
from .yt_dlp_runtime import (
    get_managed_yt_dlp_executable_path,
    get_yt_dlp_version,
    install_or_update_yt_dlp_executable,
    yt_dlp_executable_available,
)


YTMUSICAPI_IMPORT_NAME = "ytmusicapi"
YOUTUBE_DEPENDENCY_PACKAGES = ("ytmusicapi",)
YOUTUBE_DEPENDENCY_INSTALL_TIMEOUT_SECONDS = 240


@dataclass(frozen=True, slots=True)
class YouTubeDependencyUpdateResult:
    updated: bool
    versions: dict[str, str]
    command_output: str = ""


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
        completed_process = _install_or_update_ytmusicapi(target_dir=target_dir, timeout_seconds=timeout_seconds)
        output_parts.append(_trim_process_output(completed_process))

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
) -> subprocess.CompletedProcess:
    command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--no-input",
        "--upgrade",
        "--target",
        str(target_dir),
        *YOUTUBE_DEPENDENCY_PACKAGES,
    ]

    completed_process = _run_pip_install(command, timeout_seconds=timeout_seconds)
    if completed_process.returncode != 0 and _pip_missing_in_output(completed_process):
        _try_bootstrap_pip(timeout_seconds=timeout_seconds)
        completed_process = _run_pip_install(command, timeout_seconds=timeout_seconds)

    if completed_process.returncode != 0 and not _is_pyd_lock_error(completed_process):
        raise RuntimeError(_format_install_failure(completed_process))

    # Clear the cached module so the next import picks up the newly installed
    # version from disk rather than the stale entry left in sys.modules from
    # before pip ran. In the pyd-lock case the old .pyd stays as an orphaned
    # file (it cannot be deleted while loaded), but the new version's .pyd has
    # a different hash-based name and loads correctly without a restart.
    _clear_dependency_modules((YTMUSICAPI_IMPORT_NAME,))
    importlib.invalidate_caches()
    # Remove any stale dist-info directories left behind when pip could not
    # complete cleanup (e.g. pyd-lock on Windows). With two dist-infos present
    # importlib.metadata.version() may resolve to the older one.
    _cleanup_stale_dist_infos(target_dir, YTMUSICAPI_IMPORT_NAME)
    return completed_process


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


def _run_pip_install(command: list[str], *, timeout_seconds: int) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.setdefault("PYTHONUTF8", "1")
    try:
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=max(15, int(timeout_seconds or 0)),
            env=env,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("Não foi possível iniciar o instalador das dependências do Python.") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("A atualização das dependências demorou demais e foi interrompida.") from exc


def _try_bootstrap_pip(*, timeout_seconds: int) -> None:
    ensurepip_command = [sys.executable, "-m", "ensurepip", "--upgrade"]
    completed_process = _run_pip_install(ensurepip_command, timeout_seconds=timeout_seconds)
    if completed_process.returncode != 0:
        raise RuntimeError(
            "Não foi possível preparar o pip automaticamente para baixar as dependências do YouTube Music."
        )


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


def _trim_process_output(completed_process: subprocess.CompletedProcess, *, limit: int = 2000) -> str:
    output_parts = []
    if completed_process.stdout:
        output_parts.append(str(completed_process.stdout).strip())
    if completed_process.stderr:
        output_parts.append(str(completed_process.stderr).strip())

    combined_output = "\n".join(part for part in output_parts if part).strip()
    if len(combined_output) <= limit:
        return combined_output

    return combined_output[-limit:]


def _format_install_failure(completed_process: subprocess.CompletedProcess) -> str:
    details = _trim_process_output(completed_process, limit=1600)
    if details:
        return (
            "Não foi possível atualizar as dependências do YouTube Music automaticamente. "
            f"Detalhes: {details}"
        )

    return "Não foi possível atualizar as dependências do YouTube Music automaticamente."


def _cleanup_stale_dist_infos(target_dir: Path, package_name: str) -> None:
    """Remove dist-info directories for older versions of a package.

    When pip fails mid-cleanup (e.g. due to a locked .pyd on Windows), both the
    old and new dist-info directories can coexist. importlib.metadata then
    resolves the version non-deterministically. This function keeps only the
    dist-info with the highest version number.
    """
    import shutil

    normalized_name = package_name.replace("-", "_").lower()
    candidates: list[tuple[tuple[int, ...], Path]] = []
    try:
        for entry in target_dir.iterdir():
            if not entry.is_dir():
                continue
            name_lower = entry.name.lower()
            if not name_lower.endswith(".dist-info"):
                continue
            stem = name_lower[: -len(".dist-info")]
            # dist-info dirs are named  <package>-<version>.dist-info
            dash_pos = stem.rfind("-")
            if dash_pos < 0:
                continue
            dist_name = stem[:dash_pos].replace("-", "_")
            if dist_name != normalized_name:
                continue
            version_str = stem[dash_pos + 1 :]
            try:
                version_tuple = tuple(int(x) for x in version_str.split("."))
            except ValueError:
                continue
            candidates.append((version_tuple, entry))
    except OSError:
        return

    if len(candidates) <= 1:
        return

    candidates.sort(key=lambda c: c[0])
    # Keep the last (highest version); remove all earlier ones.
    for _, stale_path in candidates[:-1]:
        try:
            shutil.rmtree(stale_path)
        except OSError:
            pass


def _is_pyd_lock_error(completed_process: subprocess.CompletedProcess) -> bool:
    """Return True when pip failed only because it could not remove a locked .pyd file
    on Windows but the packages were actually installed successfully.

    On Windows, compiled extension modules (.pyd files) that are already loaded in the
    current process cannot be deleted. Pip reports a PermissionError when it tries to
    clean up the old file after installing the new version, causing a non-zero exit code
    even though all package files were written correctly.
    """
    combined_output = "\n".join(
        part
        for part in (
            str(completed_process.stdout or ""),
            str(completed_process.stderr or ""),
        )
        if part
    )
    has_pyd_permission_error = (
        "PermissionError" in combined_output
        and ".pyd" in combined_output
        and "WinError 5" in combined_output
    )
    packages_were_installed = "Successfully installed" in combined_output
    return has_pyd_permission_error and packages_were_installed


def _pip_missing_in_output(completed_process: subprocess.CompletedProcess) -> bool:
    output = "\n".join(
        part
        for part in (
            str(completed_process.stdout or ""),
            str(completed_process.stderr or ""),
        )
        if part
    )
    normalized_output = output.casefold()
    return "no module named pip" in normalized_output or "no module named 'pip'" in normalized_output


def _normalize_interval_hours(value: int) -> int:
    try:
        normalized_value = int(value)
    except (TypeError, ValueError):
        normalized_value = 24
    return max(1, min(720, normalized_value))
