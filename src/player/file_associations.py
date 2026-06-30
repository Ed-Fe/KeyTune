"""Windows file-type association helpers.

Registers and unregisters the app as an *Open With* handler for supported
media and playlist extensions via per-user registry keys (HKCU).
"""

import ctypes
import logging
import os
import sys
import winreg

from .i18n import _
from .constants import APP_TITLE, SUPPORTED_MEDIA_EXTENSIONS

logger = logging.getLogger(__name__)

_PROG_ID = f"{APP_TITLE}.MediaFile"
_PROG_ID_DESCRIPTION = _("Arquivo de mídia — {app}").format(app=APP_TITLE)
_PLAYLIST_EXTENSIONS = {".m3u", ".m3u8"}
_ALL_EXTENSIONS = SUPPORTED_MEDIA_EXTENSIONS | _PLAYLIST_EXTENSIONS

_SHCNE_ASSOCCHANGED = 0x08000000
_SHCNF_IDLIST = 0x0000


def _get_open_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" "%1"'
    main_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "main.py"))
    return f'"{sys.executable}" "{main_py}" "%1"'


def _notify_shell():
    try:
        ctypes.windll.shell32.SHChangeNotify(
            _SHCNE_ASSOCCHANGED, _SHCNF_IDLIST, None, None
        )
    except Exception:
        pass


def register_file_associations() -> bool:
    """Register the app as an Open With handler for media and playlist files.

    Returns ``True`` on success, ``False`` if a registry operation failed.
    """
    command = _get_open_command()
    try:
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER,
            rf"Software\Classes\{_PROG_ID}",
            0,
            winreg.KEY_WRITE,
        ) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, _PROG_ID_DESCRIPTION)

        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER,
            rf"Software\Classes\{_PROG_ID}\shell\open",
            0,
            winreg.KEY_WRITE,
        ) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, f"Abrir no {APP_TITLE}")

        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER,
            rf"Software\Classes\{_PROG_ID}\shell\open\command",
            0,
            winreg.KEY_WRITE,
        ) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, command)

        for ext in sorted(_ALL_EXTENSIONS):
            with winreg.CreateKeyEx(
                winreg.HKEY_CURRENT_USER,
                rf"Software\Classes\{ext}\OpenWithProgids",
                0,
                winreg.KEY_WRITE,
            ) as key:
                winreg.SetValueEx(key, _PROG_ID, 0, winreg.REG_NONE, b"")

        _notify_shell()
        return True
    except OSError:
        logger.exception("Falha ao registrar associações de arquivo.")
        return False


def unregister_file_associations() -> bool:
    """Remove all per-user registry entries created by :func:`register_file_associations`."""
    try:
        for ext in sorted(_ALL_EXTENSIONS):
            try:
                with winreg.OpenKeyEx(
                    winreg.HKEY_CURRENT_USER,
                    rf"Software\Classes\{ext}\OpenWithProgids",
                    0,
                    winreg.KEY_WRITE,
                ) as key:
                    winreg.DeleteValue(key, _PROG_ID)
            except FileNotFoundError:
                pass

        _delete_key_tree(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{_PROG_ID}")
        _notify_shell()
        return True
    except OSError:
        logger.exception("Falha ao remover associações de arquivo.")
        return False


def are_associations_registered() -> bool:
    """Return ``True`` if the ProgId entry exists under HKCU."""
    try:
        with winreg.OpenKeyEx(
            winreg.HKEY_CURRENT_USER,
            rf"Software\Classes\{_PROG_ID}\shell\open\command",
            0,
            winreg.KEY_READ,
        ):
            return True
    except FileNotFoundError:
        return False


def _delete_key_tree(root, subkey):
    """Recursively delete a registry key and all its children."""
    try:
        with winreg.OpenKeyEx(root, subkey, 0, winreg.KEY_READ) as key:
            children = []
            index = 0
            while True:
                try:
                    children.append(winreg.EnumKey(key, index))
                    index += 1
                except OSError:
                    break

        for child in children:
            _delete_key_tree(root, rf"{subkey}\{child}")

        winreg.DeleteKey(root, subkey)
    except FileNotFoundError:
        pass
