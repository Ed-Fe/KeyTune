"""Reads the install marker written by the Windows installer.

The Inno Setup installer (``installer/keytune.iss``) writes ``Software\\KeyTune``
under HKCU (per-user install) or HKLM (per-machine install). The updater uses
this to know the install scope so it can request elevation only when needed.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

from .constants import APP_TITLE
from .log import get_logger

_logger = get_logger(__name__)

_INSTALL_SUBKEY = rf"Software\{APP_TITLE}"


@dataclass(frozen=True)
class InstallInfo:
    install_dir: str
    mode: str  # "user" or "machine"


def read_install_info() -> InstallInfo | None:
    """Return install marker info, or ``None`` if not installed via the installer."""
    if not sys.platform.startswith("win"):
        return None

    try:
        import winreg
    except ImportError:
        return None

    for root, mode in (
        (winreg.HKEY_CURRENT_USER, "user"),
        (winreg.HKEY_LOCAL_MACHINE, "machine"),
    ):
        info = _read_from_root(winreg, root, mode)
        if info is not None:
            return info
    return None


def _read_from_root(winreg, root, default_mode: str) -> InstallInfo | None:
    try:
        with winreg.OpenKeyEx(root, _INSTALL_SUBKEY, 0, winreg.KEY_READ) as key:
            install_dir = _read_value(winreg, key, "InstallDir")
            if not install_dir:
                return None
            mode = _read_value(winreg, key, "InstallMode") or default_mode
            return InstallInfo(install_dir=install_dir, mode=mode)
    except FileNotFoundError:
        return None
    except OSError as exc:
        _logger.debug("Failed to read install info from registry: %s", exc)
        return None


def _read_value(winreg, key, name: str) -> str:
    try:
        value, _ = winreg.QueryValueEx(key, name)
        return str(value or "").strip()
    except FileNotFoundError:
        return ""
