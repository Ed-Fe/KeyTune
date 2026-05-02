from __future__ import annotations

from dataclasses import dataclass
import importlib
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

from ..session import get_app_storage_dir


YTDLP_IMPORT_NAME = "yt_dlp"
YTMUSICAPI_IMPORT_NAME = "ytmusicapi"
YOUTUBE_DEPENDENCY_PACKAGES = ("yt-dlp", "ytmusicapi")
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


_RUNTIME_CONFIG = _RuntimeDependencyConfig()
_RUNTIME_CONFIG_LOCK = threading.Lock()


def configure_youtube_dependency_management(*, managed_install_enabled: bool, auto_update_enabled: bool) -> None:
    with _RUNTIME_CONFIG_LOCK:
        _RUNTIME_CONFIG.managed_install_enabled = bool(managed_install_enabled)
        _RUNTIME_CONFIG.auto_update_enabled = bool(auto_update_enabled)


def youtube_dependency_management_enabled() -> bool:
    with _RUNTIME_CONFIG_LOCK:
        return bool(_RUNTIME_CONFIG.managed_install_enabled)


def youtube_dependency_auto_update_enabled() -> bool:
    with _RUNTIME_CONFIG_LOCK:
        return bool(_RUNTIME_CONFIG.auto_update_enabled)


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
    return _can_import_dependency(YTDLP_IMPORT_NAME) and _can_import_dependency(YTMUSICAPI_IMPORT_NAME)


def get_installed_youtube_dependency_versions() -> dict[str, str]:
    activate_youtube_dependency_target_dir()
    versions: dict[str, str] = {}
    for import_name, package_name in (
        ("yt_dlp", "yt-dlp"),
        ("ytmusicapi", "ytmusicapi"),
    ):
        try:
            module = importlib.import_module(import_name)
        except Exception:
            continue

        versions[package_name] = _resolve_module_version(module)

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
) -> YouTubeDependencyUpdateResult:
    target_dir = activate_youtube_dependency_target_dir()
    if not force and youtube_dependencies_available():
        return YouTubeDependencyUpdateResult(
            updated=False,
            versions=get_installed_youtube_dependency_versions(),
            command_output="Dependências já disponíveis.",
        )

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

    if completed_process.returncode != 0:
        raise RuntimeError(_format_install_failure(completed_process))

    importlib.invalidate_caches()
    if not youtube_dependencies_available():
        raise RuntimeError(
            "As dependências foram baixadas, mas não puderam ser carregadas nesta execução. "
            "Reinicie o aplicativo e tente novamente."
        )

    return YouTubeDependencyUpdateResult(
        updated=True,
        versions=get_installed_youtube_dependency_versions(),
        command_output=_trim_process_output(completed_process),
    )


def import_yt_dlp_module():
    return _import_dependency_module(
        import_name=YTDLP_IMPORT_NAME,
        display_name="yt-dlp",
    )


def import_ytmusicapi_module():
    return _import_dependency_module(
        import_name=YTMUSICAPI_IMPORT_NAME,
        display_name="ytmusicapi",
    )


def _import_dependency_module(*, import_name: str, display_name: str):
    activate_youtube_dependency_target_dir()

    try:
        return importlib.import_module(import_name)
    except Exception as initial_error:
        if not youtube_dependency_management_enabled():
            raise RuntimeError(
                f"A dependência {display_name} não está instalada. "
                "Ative os Recursos adicionais nas Preferências para baixar e atualizar automaticamente."
            ) from initial_error

        try:
            install_or_update_youtube_dependencies(force=False)
        except Exception as exc:
            raise RuntimeError(
                f"Não foi possível preparar a dependência {display_name} automaticamente. Detalhes: {exc}"
            ) from exc

        try:
            return importlib.import_module(import_name)
        except Exception as final_error:
            raise RuntimeError(
                f"A dependência {display_name} foi baixada, mas não pôde ser carregada. "
                "Reinicie o aplicativo e tente novamente."
            ) from final_error


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


def _resolve_module_version(module) -> str:
    for attribute_name in ("__version__", "VERSION", "version"):
        value = getattr(module, attribute_name, "")
        normalized_value = str(value or "").strip()
        if normalized_value:
            return normalized_value
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
