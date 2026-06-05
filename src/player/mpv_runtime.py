from __future__ import annotations

import locale
import os
import sys
from pathlib import Path


_RUNTIME_DLL_NAMES = (
    "mpv-2.dll",
    "libmpv-2.dll",
    "mpv-1.dll",
)
_RUNTIME_CACHE_FILE_NAME = "mpv-runtime-dir.txt"


def _runtime_cache_path() -> Path | None:
    try:
        from .session import get_app_storage_dir

        return Path(get_app_storage_dir()) / _RUNTIME_CACHE_FILE_NAME
    except Exception:
        return None


def _iter_cached_runtime_dirs() -> list[Path]:
    cache_path = _runtime_cache_path()
    if cache_path is None or not cache_path.is_file():
        return []

    try:
        cached_path = cache_path.read_text(encoding="utf-8").strip()
    except OSError:
        return []

    if not cached_path:
        return []
    return [Path(cached_path)]


def _cache_runtime_dir(runtime_dir: Path) -> None:
    cache_path = _runtime_cache_path()
    if cache_path is None:
        return

    try:
        cache_path.write_text(str(runtime_dir.resolve()), encoding="utf-8")
    except OSError:
        return


def _iter_chocolatey_runtime_dirs() -> list[Path]:
    chocolatey_root = Path(os.environ.get("ChocolateyInstall") or r"C:\ProgramData\chocolatey")
    lib_dir = chocolatey_root / "lib"
    if not lib_dir.is_dir():
        return []

    candidates = [
        lib_dir / "mpvio.install" / "tools",
        lib_dir / "mpvio" / "tools",
        lib_dir / "mpv.install" / "tools",
        lib_dir / "mpv" / "tools",
    ]

    try:
        for child in lib_dir.iterdir():
            if not child.is_dir() or "mpv" not in child.name.casefold():
                continue
            candidates.append(child / "tools")
            candidates.append(child)
    except OSError:
        pass

    return candidates


def _candidate_runtime_dirs() -> list[Path]:
    candidates: list[Path] = []

    for env_name in ("MPV_HOME", "MPV_DLL_DIR"):
        env_path = str(os.environ.get(env_name) or "").strip()
        if env_path:
            candidates.append(Path(env_path))

    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / "mpv")

    repo_root = Path(__file__).resolve().parents[2]
    candidates.append(repo_root / "mpv")
    candidates.append(Path.cwd() / "mpv")
    candidates.extend(_iter_cached_runtime_dirs())
    candidates.extend(_iter_chocolatey_runtime_dirs())

    unique_candidates: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        try:
            resolved = str(candidate.resolve())
        except OSError:
            resolved = str(candidate)
        if resolved in seen:
            continue
        seen.add(resolved)
        unique_candidates.append(candidate)
    return unique_candidates


def _is_valid_runtime_dir(directory: Path) -> bool:
    return any((directory / dll_name).is_file() for dll_name in _RUNTIME_DLL_NAMES)


def bootstrap_mpv_runtime() -> bool:
    try:
        locale.setlocale(locale.LC_NUMERIC, "C")
    except locale.Error:
        pass

    if not sys.platform.startswith("win"):
        return False

    for runtime_dir in _candidate_runtime_dirs():
        if not _is_valid_runtime_dir(runtime_dir):
            continue

        os.environ["PATH"] = f"{runtime_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        add_dll_directory = getattr(os, "add_dll_directory", None)
        if add_dll_directory is not None:
            add_dll_directory(str(runtime_dir))
        _cache_runtime_dir(runtime_dir)
        _get_logger().info("MPV runtime found: %s", runtime_dir)
        return True

    _get_logger().warning("MPV runtime not found on Windows; playback may not be available")
    return False


def _get_logger():
    from .log import get_logger
    return get_logger(__name__)
