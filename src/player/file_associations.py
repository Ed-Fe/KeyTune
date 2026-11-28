"""Windows file-type and link association helpers.

Registers and unregisters the app as an *Open With* handler for supported
media and playlist extensions via per-user registry keys (HKCU). The same
ProgId carries the Explorer verb that appends the selection to the playlist.

``register_link_handler`` also lists the app as a web browser for ``http``
and ``https``, so it can become the default for links; ``link_router`` then
plays the YouTube ones and passes every other link on to a real browser.

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
from .link_router import BROWSERS_KEY, link_handler_names
from .portable import is_portable

logger = logging.getLogger(__name__)

_CLASSES = r"Software\Classes"
_PLAYLIST_EXTENSIONS = {".m3u", ".m3u8"}
_ALL_EXTENSIONS = SUPPORTED_MEDIA_EXTENSIONS | _PLAYLIST_EXTENSIONS

_SHCNE_ASSOCCHANGED = 0x08000000
_SHCNF_IDLIST = 0x0000


def _launch_lead() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    main_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "main.py"))
    return f'"{sys.executable}" "{main_py}"'


def _launch_command(*arguments: str) -> str:
    lead = _launch_lead()
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


_REGISTERED_APPLICATIONS = r"Software\RegisteredApplications"
_URL_SCHEMES = ("http", "https")


def _icon_value() -> str:
    return f"{sys.executable},0"


def _installed_capabilities() -> str:
    return rf"Software\{APP_TITLE}\Capabilities"


def _link_capabilities_paths(client: str) -> tuple[str, ...]:
    """Where the ``URLAssociations`` go; the first one is what RegisteredApplications points to.

    The installer points ``RegisteredApplications\\KeyTune`` at
    ``Software\\KeyTune\\Capabilities``. Rewriting that value would drop the file
    types from the Default apps page, so an installed copy adds the links there.
    """
    browser_capabilities = rf"{BROWSERS_KEY}\{client}\Capabilities"
    if is_portable():
        return (browser_capabilities,)
    return (_installed_capabilities(), browser_capabilities)


def register_link_handler() -> bool:
    """List the app as a browser for ``http``/``https`` links (HKCU).

    It only becomes the default when the user picks it in Settings > Default apps.
    """
    prog_id, client, registered_name = link_handler_names(portable=is_portable())
    capabilities_paths = _link_capabilities_paths(client)
    description = _("Abre links do YouTube e do YouTube Music no {app}.").format(app=APP_TITLE)
    try:
        _write_values(rf"{_CLASSES}\{prog_id}", _("Link da web — {app}").format(app=APP_TITLE), **{"URL Protocol": ""})
        _write_values(rf"{_CLASSES}\{prog_id}\DefaultIcon", _icon_value())
        _write_values(rf"{_CLASSES}\{prog_id}\shell\open\command", _get_open_command())

        client_key = rf"{BROWSERS_KEY}\{client}"
        _write_values(client_key, client)
        _write_values(rf"{client_key}\DefaultIcon", _icon_value())
        _write_values(rf"{client_key}\shell\open\command", _launch_lead())
        for capabilities in capabilities_paths:
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, capabilities, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, "ApplicationName", 0, winreg.REG_SZ, client)
                winreg.SetValueEx(key, "ApplicationDescription", 0, winreg.REG_SZ, description)
            with winreg.CreateKeyEx(
                winreg.HKEY_CURRENT_USER, rf"{capabilities}\URLAssociations", 0, winreg.KEY_WRITE
            ) as key:
                for scheme in _URL_SCHEMES:
                    winreg.SetValueEx(key, scheme, 0, winreg.REG_SZ, prog_id)

        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, _REGISTERED_APPLICATIONS, 0, winreg.KEY_WRITE) as key:
            winreg.SetValueEx(key, registered_name, 0, winreg.REG_SZ, capabilities_paths[0])
        _notify_shell()
        return True
    except OSError:
        logger.exception("Falha ao registrar o KeyTune como navegador para links.")
        return False


def unregister_link_handler() -> bool:
    """Remove the per-user link registration, if it points to this copy."""
    prog_id, client, registered_name = link_handler_names(portable=is_portable())
    prog_key = rf"{_CLASSES}\{prog_id}"
    try:
        if not _owns_command(rf"{prog_key}\shell\open", _get_open_command()):
            return True
        _delete_key_tree(winreg.HKEY_CURRENT_USER, prog_key)
        _delete_key_tree(winreg.HKEY_CURRENT_USER, rf"{BROWSERS_KEY}\{client}")
        if not is_portable():
            _delete_key_tree(winreg.HKEY_CURRENT_USER, rf"{_installed_capabilities()}\URLAssociations")
        # The installer owns RegisteredApplications for an installed copy.
        if is_portable() or not _has_user_install_marker():
            try:
                with winreg.OpenKeyEx(
                    winreg.HKEY_CURRENT_USER, _REGISTERED_APPLICATIONS, 0, winreg.KEY_WRITE
                ) as key:
                    winreg.DeleteValue(key, registered_name)
            except FileNotFoundError:
                pass
        _notify_shell()
        return True
    except OSError:
        logger.exception("Falha ao remover o registro de navegador para links.")
        return False


def is_link_handler_registered() -> bool:
    """Return whether this copy owns the per-user URL ProgID."""
    prog_id, _client, _registered_name = link_handler_names(portable=is_portable())
    return _owns_command(rf"{_CLASSES}\{prog_id}\shell\open", _get_open_command())


def _has_user_install_marker() -> bool:
    try:
        with winreg.OpenKeyEx(winreg.HKEY_CURRENT_USER, rf"Software\{APP_TITLE}", 0, winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, "InstallDir")
        return True
    except OSError:
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
