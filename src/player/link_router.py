"""Links abertos por outros programas enquanto o KeyTune é o navegador padrão.

O Windows não deixa um programa abrir só os links de um site: ou ele recebe
todos os ``http``/``https``, ou nenhum. Por isso o KeyTune se registra como
navegador (ver ``file_associations.register_link_handler`` e o instalador) e,
quando a pessoa o escolhe como padrão, cada link passa por aqui:

- vídeo ou playlist do YouTube e do YouTube Music segue para o player, pelo
  mesmo caminho de um arquivo aberto pelo Explorador;
- qualquer outro link vai para o navegador escolhido nas preferências ou, sem
  escolha, para o que era o padrão antes do KeyTune. O processo sai logo, sem
  carregar a interface nem o MPV.

Só o Windows tem esse roteamento; nos outros sistemas ``route_launch`` não faz
nada. Os módulos ``winreg`` e ``ctypes.windll`` só são importados ao usar.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from urllib.parse import quote

from .constants import APP_TITLE
from .log import get_logger
from .youtube_links import is_youtube_link

_logger = get_logger(__name__)

MAX_URL_LENGTH = 2048
STATE_FILE_NAME = "link_router.json"
SETTINGS_FILE_NAME = "settings.json"
BROWSER_SETTING_KEY = "link_browser"
_URL_START = re.compile(r"^https?://", re.IGNORECASE)
_URL_PLACEHOLDER = re.compile(r"%[1lL]")
_OTHER_PLACEHOLDERS = re.compile(r"\s*%\*")
_USER_CHOICE = r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\{scheme}\UserChoice"
BROWSERS_KEY = r"Software\Clients\StartMenuInternet"
_DETACHED = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
_FORBIDDEN_BROWSER_EXECUTABLES = {"iexplore.exe", "accessible reels.exe"}
# Outros apps que também se registram como navegador para rotear links. Repassar a
# eles pode fazer o link ficar indo e voltando entre os dois, então nunca entram.
_OTHER_LINK_ROUTER_MARKERS = ("accessible reels", "accessible-reels", "accessiblereels")
_OTHER_LINK_ROUTER_PROG_IDS = {"accessiblereelsurl"}
_OWN_EXECUTABLES = {f"{APP_TITLE}.exe".casefold()}


def link_handler_names(*, portable=None):
    """``(ProgId da URL, nome em StartMenuInternet, nome em RegisteredApplications)``.

    A cópia portátil usa nomes próprios, para não apagar nem sobrescrever o
    registro de uma cópia instalada no mesmo Windows.
    """
    if portable is None:
        from .portable import is_portable

        portable = is_portable()
    if portable:
        return f"{APP_TITLE}.PortableURL", f"{APP_TITLE} Portable", f"{APP_TITLE} Portable"
    return f"{APP_TITLE}URL", APP_TITLE, APP_TITLE


def _own_prog_ids():
    """ProgIds que nunca contam como navegador: os do KeyTune e os de outros roteadores de links."""
    own = {link_handler_names(portable=portable)[0].casefold() for portable in (False, True)}
    return own | _OTHER_LINK_ROUTER_PROG_IDS


def link_from_arguments(arguments):
    """O primeiro endereço ``http(s)`` em *arguments* (sem o nome do programa), ou ``None``."""
    for argument in arguments or ():
        text = str(argument or "").strip().strip('"')
        if _URL_START.match(text) and len(text) <= MAX_URL_LENGTH:
            return text
    return None


def build_command(template, url):
    """Preenche o comando ``open`` do registro com o *url*.

    O comando roda sem shell, mas navegadores como o Firefox põem ``%1`` entre
    aspas: tudo o que fecharia a aspa ou separaria argumentos é codificado.
    """
    safe = quote(str(url), safe="!#$&'()*+,/:;=?@[]~%-._")
    template = _OTHER_PLACEHOLDERS.sub("", str(template or "").strip())
    if _URL_PLACEHOLDER.search(template):
        return _URL_PLACEHOLDER.sub(lambda _match: safe, template)
    return f'{template} "{safe}"'


def executable_of(command):
    """O executável de um comando do registro, com ou sem aspas."""
    command = str(command or "").strip()
    if command.startswith('"'):
        return command[1:].split('"', 1)[0]
    match = re.match(r"^(.*?\.exe)(?:\s|$)", command, re.IGNORECASE)
    if match:
        return match.group(1)
    return command.split(" ", 1)[0]


def _normalized_executable(path):
    try:
        return os.path.normcase(os.path.abspath(path))
    except (TypeError, ValueError):
        return ""


def is_own_command(command):
    executable = executable_of(command)
    if not executable:
        return False
    if os.path.basename(executable).casefold() in _OWN_EXECUTABLES:
        return True
    return _normalized_executable(executable) == _normalized_executable(sys.executable)


def is_forbidden_browser(command):
    """Comandos que nunca recebem um link repassado: vazios, o KeyTune, outros roteadores de links, o Internet Explorer."""
    if not command or not str(command).strip():
        return True
    if is_own_command(command):
        return True
    if any(marker in str(command).casefold() for marker in _OTHER_LINK_ROUTER_MARKERS):
        return True
    return os.path.basename(executable_of(command)).casefold() in _FORBIDDEN_BROWSER_EXECUTABLES


def _registry_value(root, path, name=""):
    import winreg

    try:
        with winreg.OpenKey(root, path) as key:
            value, _kind = winreg.QueryValueEx(key, name)
    except OSError:
        return None
    return value if isinstance(value, str) and value else None


def current_default_prog_id(scheme="https"):
    import winreg

    return _registry_value(winreg.HKEY_CURRENT_USER, _USER_CHOICE.format(scheme=scheme), "ProgId")


def _prog_id_command(prog_id):
    import winreg

    return _registry_value(winreg.HKEY_CLASSES_ROOT, rf"{prog_id}\shell\open\command")


def registered_browsers():
    """``{nome visível: comando}`` dos navegadores instalados, sem o KeyTune nem o Internet Explorer."""
    import winreg

    browsers = {}
    for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(root, BROWSERS_KEY) as key:
                names = [winreg.EnumKey(key, index) for index in range(winreg.QueryInfoKey(key)[0])]
        except OSError:
            continue
        for name in names:
            command = _registry_value(root, rf"{BROWSERS_KEY}\{name}\shell\open\command")
            if is_forbidden_browser(command):
                continue
            display = _registry_value(root, rf"{BROWSERS_KEY}\{name}") or name
            browsers.setdefault(display, command)
    return browsers


def _storage_path(file_name):
    from .session import get_app_storage_dir

    return os.path.join(get_app_storage_dir(), file_name)


def _read_json(file_name):
    try:
        with open(_storage_path(file_name), "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def preferred_browser():
    """O navegador escolhido em Preferências para os outros links, ou ``""`` (o padrão anterior)."""
    value = _read_json(SETTINGS_FILE_NAME).get(BROWSER_SETTING_KEY)
    return value.strip() if isinstance(value, str) else ""


def remembered_prog_id():
    value = _read_json(STATE_FILE_NAME).get("prog_id")
    return value if isinstance(value, str) and value else None


def remember_default_browser():
    """Guarda o navegador padrão atual, a menos que seja o próprio KeyTune."""
    prog_id = current_default_prog_id()
    if not prog_id or prog_id.casefold() in _own_prog_ids() or prog_id == remembered_prog_id():
        return
    state = _read_json(STATE_FILE_NAME)
    state["prog_id"] = prog_id
    try:
        with open(_storage_path(STATE_FILE_NAME), "w", encoding="utf-8") as handle:
            json.dump(state, handle, ensure_ascii=False, indent=2)
    except OSError:
        _logger.warning("Não foi possível guardar o navegador padrão anterior.")


def browser_commands():
    """Comandos candidatos, sem repetir executável: o preferido, o padrão atual ou o anterior, os registrados."""
    seen = set()
    registered = None

    def accept(command):
        if is_forbidden_browser(command):
            return False
        executable = _normalized_executable(executable_of(command))
        if executable in seen:
            return False
        seen.add(executable)
        return True

    preferred = preferred_browser()
    if preferred:
        registered = registered_browsers()
        for name, command in registered.items():
            if name.casefold() == preferred.casefold() and accept(command):
                yield command
                break

    for prog_id in (current_default_prog_id(), remembered_prog_id()):
        if prog_id and prog_id.casefold() not in _own_prog_ids():
            command = _prog_id_command(prog_id)
            if accept(command):
                yield command

    for command in (registered if registered is not None else registered_browsers()).values():
        if accept(command):
            yield command


def open_in_browser(url):
    """Abre *url* num navegador de verdade; devolve se algum aceitou."""
    for template in browser_commands():
        try:
            subprocess.Popen(build_command(template, url), close_fds=True, creationflags=_DETACHED)
            return True
        except OSError:
            _logger.exception("Falha ao abrir o navegador para um link repassado.")
    return False


def _show_no_browser_message():
    from .i18n import _

    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(
            None,
            _(
                "O KeyTune só abre links do YouTube e não encontrou um navegador para este link. "
                "Escolha outro navegador padrão nas configurações do Windows ou em Preferências do KeyTune."
            ),
            APP_TITLE,
            0x10,
        )
    except Exception:
        pass


def default_apps_uri():
    """A página do KeyTune em Configurações > Aplicativos padrão."""
    _prog_id, _client, registered_name = link_handler_names()
    parameter = "registeredAppUser"
    from .portable import is_portable

    if not is_portable():
        from .install_info import read_install_info

        info = read_install_info()
        if info is not None and info.mode == "machine":
            parameter = "registeredAppMachine"
    return f"ms-settings:defaultapps?{parameter}={quote(registered_name)}"


def route_launch(arguments):
    """Decide o que esta abertura faz com um link.

    Devolve ``True`` quando o link já foi entregue ao navegador e o processo
    deve sair; ``False`` quando o KeyTune segue a abertura normal (sem link, ou
    com um link do YouTube, que vira um caminho para tocar).
    """
    if sys.platform != "win32":
        return False
    url = link_from_arguments(arguments)
    try:
        remember_default_browser()
    except Exception:
        _logger.exception("Falha ao ler o navegador padrão.")
    if not url or is_youtube_link(url):
        return False
    try:
        opened = open_in_browser(url)
    except Exception:
        _logger.exception("Falha ao repassar um link ao navegador.")
        opened = False
    if not opened:
        _logger.error("Nenhum navegador aceitou um link que não é do YouTube.")
        _show_no_browser_message()
    return True
