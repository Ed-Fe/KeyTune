from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys

from ..optional_resources import (
    get_optional_resource_dir,
    install_optional_resource,
    optional_resource_installed,
    read_optional_resource_manifest,
)


_DLL_DIRECTORY_HANDLES = []
_AUTODJ_MODULES = ("librosa", "numpy", "av")


def get_autodj_site_packages_dir() -> Path:
    return get_optional_resource_dir("autodj") / "site-packages"


def get_autodj_worker_command() -> list[str]:
    main_script = Path(__file__).resolve().parents[2] / "main.py"
    if getattr(sys, "frozen", False):
        return [sys.executable, "--autodj-analyzer"]
    return [sys.executable, str(main_script), "--autodj-analyzer"]


def _autodj_modules_available() -> bool:
    return all(importlib.util.find_spec(name) is not None for name in _AUTODJ_MODULES)


def activate_autodj_dependencies() -> Path:
    target_dir = get_autodj_site_packages_dir()
    # Source-tree development installs the optional libraries in its virtual
    # environment. Keep it ahead of any resources left by a previously
    # installed KeyTune version in AppData.
    if not getattr(sys, "frozen", False) and _autodj_modules_available():
        return target_dir
    if target_dir.is_dir():
        normalized = str(target_dir)
        if normalized not in sys.path:
            sys.path.insert(0, normalized)
        if os.name == "nt" and hasattr(os, "add_dll_directory"):
            for candidate in (target_dir, *target_dir.glob("*.libs")):
                if candidate.is_dir():
                    try:
                        _DLL_DIRECTORY_HANDLES.append(os.add_dll_directory(str(candidate)))
                    except OSError:
                        pass
    return target_dir


def autodj_dependencies_available() -> bool:
    if optional_resource_installed("autodj"):
        activate_autodj_dependencies()
        return _autodj_modules_available()
    if getattr(sys, "frozen", False):
        return False
    activate_autodj_dependencies()
    return _autodj_modules_available()


def install_autodj_dependencies(*, progress_callback=None) -> dict:
    manifest = install_optional_resource("autodj", progress_callback=progress_callback)
    if not autodj_dependencies_available():
        raise RuntimeError("As bibliotecas do AutoDJ foram instaladas, mas não puderam ser carregadas.")
    return manifest


def autodj_dependency_versions() -> dict[str, str]:
    manifest = read_optional_resource_manifest("autodj")
    versions = manifest.get("versions") if isinstance(manifest, dict) else None
    return dict(versions) if isinstance(versions, dict) else {}


def managed_autodj_resource_installed() -> bool:
    return optional_resource_installed("autodj")
