"""Windows file-type association helpers.

Registers and unregisters the app as an *Open With* handler for supported
media and playlist extensions via per-user registry keys (HKCU). The same
ProgId carries the Explorer verb that appends the selection to the playlist.

Nothing calls this at startup. In portable mode the preferences screen asks
before writing, because the keys belong to this computer's Windows, not to
the portable folder.
"""

import ctypes
import logging
import os
import sys
import winreg

from .i18n import _
from .constants import APP_TITLE, SUPPORTED_MEDIA_EXTENSIONS
from .portable import is_portable

logger = logging.getLogger(__name__)

_CLASSES = r"Software\Classes"
_PLAYLIST_EXTENSIONS = {".m3u", ".m3u8"}
_ALL_EXTENSIONS = SUPPORTED_MEDIA_EXTENSIONS | _PLAYLIST_EXTENSIONS

_SHCNE_ASSOCCHANGED = 0x08000000
_SHCNF_IDLIST = 0x0000


def _launch_command(*arguments: str) -> str:
    if getattr(sys, "frozen", False):
        lead = f'"{sys.executable}"'
    else:
        main_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "main.py"))
        lead = f'"{sys.executable}" "{main_py}"'
    tail = " ".join(arguments)
    if tail:
        return f'{lead} {tail} "%1"'
    return f'{lead} "%1"'


def _get_open_command() -> str:
    return _launch_command()


def _get_enqueue_command() -> str:
    return _launch_command("--enqueue")


def _association_names() -> tuple[str, str]:
    prefix = f"{APP_TITLE}.Portable" if is_portable() else APP_TITLE
    return f"{prefix}.MediaFile", f"{prefix}.enqueue"


def _extension_verb(ext: str, verb: str) -> str:
    return rf"{_CLASSES}\SystemFileAssociations\{ext}\shell\{verb}"


def _write_values(subkey: str, default: str, **values: str) -> None:
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, subkey, 0, winreg.KEY_WRITE) as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, default)
        for name, value in values.items():
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)


def _register_enqueue_verb(subkey: str, command: str) -> None:
    _write_values(subkey, _("Adicionar à playlist do {app}").format(app=APP_TITLE), MultiSelectModel="Player")
    _write_values(rf"{subkey}\command", command)


def _owns_command(verb_key: str, command: str) -> bool:
    try:
        with winreg.OpenKeyEx(
            winreg.HKEY_CURRENT_USER, rf"{verb_key}\command", 0, winreg.KEY_READ
        ) as key:
            registered, _kind = winreg.QueryValueEx(key, "")
        return isinstance(registered, str) and registered.casefold() == command.casefold()
    except FileNotFoundError:
        return False


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
    prog_id, verb = _association_names()
    prog_key = rf"{_CLASSES}\{prog_id}"
    enqueue_command = _get_enqueue_command()
    try:
        _write_values(prog_key, _("Arquivo de mídia — {app}").format(app=APP_TITLE))
        _write_values(rf"{prog_key}\shell\open", _("Abrir no {app}").format(app=APP_TITLE))
        _write_values(rf"{prog_key}\shell\open\command", _get_open_command())

        # Share the verb name across the two locations so it appears once.
        _delete_key_tree(winreg.HKEY_CURRENT_USER, rf"{prog_key}\shell\enqueue")
        _register_enqueue_verb(rf"{prog_key}\shell\{verb}", enqueue_command)

        for ext in sorted(_ALL_EXTENSIONS):
            with winreg.CreateKeyEx(
                winreg.HKEY_CURRENT_USER,
                rf"{_CLASSES}\{ext}\OpenWithProgids",
                0,
                winreg.KEY_WRITE,
            ) as key:
                winreg.SetValueEx(key, prog_id, 0, winreg.REG_NONE, b"")

        for ext in sorted(SUPPORTED_MEDIA_EXTENSIONS - _PLAYLIST_EXTENSIONS):
            _register_enqueue_verb(_extension_verb(ext, verb), enqueue_command)

        _notify_shell()
        return True
    except OSError:
        logger.exception("Falha ao registrar associações de arquivo.")
        return False


def unregister_file_associations() -> bool:
    """Remove only per-user entries whose command points to this executable."""
    prog_id, verb = _association_names()
    prog_key = rf"{_CLASSES}\{prog_id}"
    enqueue_command = _get_enqueue_command()
    try:
        if _owns_command(rf"{prog_key}\shell\open", _get_open_command()):
            for ext in sorted(_ALL_EXTENSIONS):
                try:
                    with winreg.OpenKeyEx(
                        winreg.HKEY_CURRENT_USER,
                        rf"{_CLASSES}\{ext}\OpenWithProgids",
                        0,
                        winreg.KEY_WRITE,
                    ) as key:
                        winreg.DeleteValue(key, prog_id)
                except FileNotFoundError:
                    pass
            _delete_key_tree(winreg.HKEY_CURRENT_USER, prog_key)

        for ext in sorted(SUPPORTED_MEDIA_EXTENSIONS - _PLAYLIST_EXTENSIONS):
            verb_key = _extension_verb(ext, verb)
            if _owns_command(verb_key, enqueue_command):
                _delete_key_tree(winreg.HKEY_CURRENT_USER, verb_key)
        _notify_shell()
        return True
    except OSError:
        logger.exception("Falha ao remover associações de arquivo.")
        return False


def are_associations_registered() -> bool:
    """Return whether this copy owns the per-user ProgID."""
    prog_id, _verb = _association_names()
    return _owns_command(rf"{_CLASSES}\{prog_id}\shell\open", _get_open_command())


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
