from __future__ import annotations

from dataclasses import dataclass
import importlib
from pathlib import Path
import sys
import threading
import time

from ..i18n import _
from ..optional_resources import (
    get_optional_resource_dir,
    install_optional_resource,
    optional_resource_installed,
)
from .yt_dlp_runtime import (
    get_managed_yt_dlp_executable_path,
    get_yt_dlp_version,
    install_or_update_yt_dlp_executable,
    yt_dlp_executable_available,
)


YTMUSICAPI_IMPORT_NAME = "ytmusicapi"
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
    youtubejs_enabled: bool = True


_RUNTIME_CONFIG = _RuntimeDependencyConfig()
_RUNTIME_CONFIG_LOCK = threading.Lock()


def configure_youtube_dependency_management(
    *,
    managed_install_enabled: bool,
    auto_update_enabled: bool,
    prefer_nightly_yt_dlp: bool = False,
    youtubejs_enabled: bool | None = None,
) -> None:
    with _RUNTIME_CONFIG_LOCK:
        _RUNTIME_CONFIG.managed_install_enabled = bool(managed_install_enabled)
        _RUNTIME_CONFIG.auto_update_enabled = bool(auto_update_enabled)
        _RUNTIME_CONFIG.prefer_nightly_yt_dlp = bool(prefer_nightly_yt_dlp)
        if youtubejs_enabled is not None:
            _RUNTIME_CONFIG.youtubejs_enabled = bool(youtubejs_enabled)


def youtube_dependency_management_enabled() -> bool:
    with _RUNTIME_CONFIG_LOCK:
        return bool(_RUNTIME_CONFIG.managed_install_enabled)


def youtube_dependency_auto_update_enabled() -> bool:
    with _RUNTIME_CONFIG_LOCK:
        return bool(_RUNTIME_CONFIG.auto_update_enabled)


def youtube_dependency_nightly_yt_dlp_enabled() -> bool:
    with _RUNTIME_CONFIG_LOCK:
        return bool(_RUNTIME_CONFIG.prefer_nightly_yt_dlp)


def youtubejs_resolver_enabled() -> bool:
    with _RUNTIME_CONFIG_LOCK:
        return bool(_RUNTIME_CONFIG.youtubejs_enabled)


def get_youtube_dependency_target_dir() -> Path:
    return get_optional_resource_dir("youtube") / "site-packages"


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
            _("O executável yt-dlp não está disponível. "
              "Ative os Recursos adicionais nas Preferências para baixar e atualizar automaticamente.")
        )

    install_or_update_youtube_dependencies(
        force=False,
        include_prerelease=youtube_dependency_nightly_yt_dlp_enabled(),
    )
    if not yt_dlp_executable_available():
        raise RuntimeError(_("O executável yt-dlp foi baixado, mas não pôde ser preparado nesta execução."))


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

    if youtubejs_resolver_enabled():
        from .youtubejs_runtime import youtubejs_dependency_versions

        versions.update(youtubejs_dependency_versions())

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
    progress_callback=None,
) -> YouTubeDependencyUpdateResult:
    # Release resources are versioned with KeyTune; force refreshes yt-dlp only.
    output_parts: list[str] = []

    activate_youtube_dependency_target_dir()
    yt_dlp_managed_exists = get_managed_yt_dlp_executable_path().is_file()

    versions_before = get_installed_youtube_dependency_versions()

    if not optional_resource_installed("youtube"):
        _report_progress(progress_callback, _("Instalando ytmusicapi..."))
        manifest = install_optional_resource("youtube", progress_callback=progress_callback)
        _clear_dependency_modules((YTMUSICAPI_IMPORT_NAME, "requests"))
        importlib.invalidate_caches()
        resource_versions = manifest.get("versions") if isinstance(manifest, dict) else None
        installed_version = (
            str(resource_versions.get("ytmusicapi") or "")
            if isinstance(resource_versions, dict)
            else ""
        )
        if installed_version:
            output_parts.append(f"ytmusicapi {installed_version}")

    if force or not yt_dlp_managed_exists:
        _report_progress(progress_callback, _("Baixando yt-dlp..."))
        yt_dlp_version = install_or_update_yt_dlp_executable(
            force=force,
            include_prerelease=include_prerelease,
            timeout_seconds=timeout_seconds,
        )
        if yt_dlp_version:
            output_parts.append(f"yt-dlp {yt_dlp_version}")

    if youtube_dependency_management_enabled():
        from .youtubejs_runtime import (
            install_nodejs_dependency,
            install_youtubejs_dependencies,
            youtubejs_dependencies_available,
        )

        if youtubejs_resolver_enabled() and (force or not youtubejs_dependencies_available()):
            youtubejs_versions = install_youtubejs_dependencies(
                force=force,
                progress_callback=progress_callback,
            )
            output_parts.extend(f"{name} {version}" for name, version in youtubejs_versions.items())
        else:
            install_nodejs_dependency(force=force, progress_callback=progress_callback)

    if not youtube_dependencies_available():
        raise RuntimeError(
            _("Os recursos adicionais do YouTube Music foram preparados, mas nem todos puderam ser carregados. "
              "Reinicie o aplicativo e tente novamente.")
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
                _("A dependência ytmusicapi não está instalada. "
                  "Ative os Recursos adicionais nas Preferências para baixar e atualizar automaticamente.")
            ) from initial_error

        try:
            install_or_update_youtube_dependencies(
                force=False,
                include_prerelease=youtube_dependency_nightly_yt_dlp_enabled(),
            )
        except Exception as exc:
            raise RuntimeError(
                _("Não foi possível preparar a dependência ytmusicapi automaticamente. Detalhes: {detail}").format(detail=exc)
            ) from exc

        try:
            return importlib.import_module(YTMUSICAPI_IMPORT_NAME)
        except Exception as final_error:
            raise RuntimeError(
                _("A dependência ytmusicapi foi baixada, mas não pôde ser carregada. "
                  "Reinicie o aplicativo e tente novamente.")
            ) from final_error


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

    return _("desconhecida")


def _normalize_interval_hours(value: int) -> int:
    try:
        normalized_value = int(value)
    except (TypeError, ValueError):
        normalized_value = 24
    return max(1, min(720, normalized_value))


def _report_progress(callback, message: str) -> None:
    if callable(callback):
        callback(message)
