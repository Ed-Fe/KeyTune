"""Explorador de pastas da janela principal: estado, raiz e coleta de mídias.

Este módulo não depende do wxPython, para poder ser testado sem interface. O
painel fica em ``library/browser.py`` (modo pasta) e o comportamento da janela
em ``frames/explorer.py``.
"""

import os
import sys
from dataclasses import dataclass, field

from ..folder_sort import FOLDER_SORT_NAME, FOLDER_SORT_OPTIONS
from ..i18n import _
from .media_scan import is_supported_media, scan_folder_contents
from .models import FOLDER_ENTRY_DIRECTORY, FOLDER_ENTRY_PARENT, FolderBrowserEntry


# Caminho vazio representa a raiz do explorador: unidades e pastas do usuário.
EXPLORER_ROOT = ""

def _user_folders():
    return (
        ("Music", _("Músicas")),
        ("Videos", _("Vídeos")),
        ("Downloads", _("Downloads")),
        ("Desktop", _("Área de trabalho")),
        ("Documents", _("Documentos")),
    )


@dataclass
class ExplorerState:
    current_path: str = EXPLORER_ROOT
    selected_path: str | None = None
    entries: list = field(default_factory=list)
    entry_index_map: dict = field(default_factory=dict)
    entries_revision: int = 0
    sort_by: str = FOLDER_SORT_NAME
    sort_descending: bool = False
    is_loading: bool = False
    request_serial: int = 0

    def set_entries(self, entries):
        self.entries = list(entries)
        self.entry_index_map = build_entry_index_map(self.entries)
        self.entries_revision += 1

    def entry_for(self, path):
        index = self.entry_index_map.get(path_key(path))
        return self.entries[index] if index is not None and index < len(self.entries) else None

    def to_dict(self, *, visible=False):
        return {
            "visible": bool(visible),
            "path": self.current_path,
            "sort_by": self.sort_by,
            "sort_descending": self.sort_descending,
        }

    def restore(self, data):
        """Aplica o que foi salvo na sessão; devolve se o painel estava visível."""
        if not isinstance(data, dict):
            return False

        # A pasta só é conferida ao ser carregada, fora da thread da interface:
        # uma unidade de rede fora do ar não pode segurar a abertura da janela.
        self.current_path = str(data.get("path") or "").strip() or EXPLORER_ROOT
        sort_by = str(data.get("sort_by") or FOLDER_SORT_NAME)
        self.sort_by = sort_by if sort_by in FOLDER_SORT_OPTIONS else FOLDER_SORT_NAME
        self.sort_descending = bool(data.get("sort_descending", False))
        return bool(data.get("visible", False))


def path_key(path):
    return os.path.normcase(os.path.normpath(str(path))) if path else None


def build_entry_index_map(entries):
    return {
        path_key(entry.path): index
        for index, entry in enumerate(entries)
        if getattr(entry, "path", None)
    }


def explorer_display_name(folder_path):
    if not folder_path:
        return _("Este computador")

    normalized_path = os.path.abspath(os.path.normpath(str(folder_path)))
    return os.path.basename(normalized_path.rstrip("\\/")) or normalized_path


def explorer_parent_path(folder_path):
    """Pasta acima de *folder_path*; ``None`` quando já se está na raiz."""
    if not folder_path:
        return None

    normalized_path = os.path.abspath(os.path.normpath(str(folder_path)))
    parent_path = os.path.dirname(normalized_path)
    if not parent_path or parent_path == normalized_path:
        return EXPLORER_ROOT
    return parent_path


def _drive_paths():
    if not sys.platform.startswith("win"):
        return ["/"]

    list_drives = getattr(os, "listdrives", None)
    if callable(list_drives):
        try:
            return list(list_drives())
        except OSError:
            pass
    return [f"{letter}:\\" for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if os.path.exists(f"{letter}:\\")]


def list_explorer_root():
    """Entradas da raiz: pastas habituais do usuário e depois as unidades."""
    entries = []
    seen = set()
    home_path = os.path.expanduser("~")

    for folder_name, label in _user_folders():
        folder_path = os.path.join(home_path, folder_name)
        key = path_key(folder_path)
        if key in seen or not os.path.isdir(folder_path):
            continue
        seen.add(key)
        entries.append(FolderBrowserEntry(path=folder_path, label=label, entry_type=FOLDER_ENTRY_DIRECTORY))

    for drive_path in _drive_paths():
        key = path_key(drive_path)
        if key in seen:
            continue
        seen.add(key)
        entries.append(
            FolderBrowserEntry(path=drive_path, label=drive_path, entry_type=FOLDER_ENTRY_DIRECTORY)
        )

    return entries


def scan_explorer_folder(folder_path, *, sort_by=FOLDER_SORT_NAME, descending=False):
    """Entradas de *folder_path*, sempre com um caminho de volta até a raiz."""
    if not folder_path:
        return list_explorer_root()
    if not os.path.isdir(folder_path):
        raise FileNotFoundError(folder_path)

    entries, _media_files = scan_folder_contents(folder_path, sort_by=sort_by, descending=descending)
    if not any(entry.is_parent for entry in entries):
        # Raiz de uma unidade: a pasta acima é a lista de unidades.
        entries.insert(
            0,
            FolderBrowserEntry(path=EXPLORER_ROOT, label="[..] Pasta acima", entry_type=FOLDER_ENTRY_PARENT),
        )
    return entries


def collect_media_paths(paths):
    """Arquivos de mídia de *paths*, descendo pelas subpastas em ordem de nome."""
    media_paths = []
    seen = set()

    def add(media_path):
        key = path_key(media_path)
        if key not in seen:
            seen.add(key)
            media_paths.append(media_path)

    for path in paths or ():
        raw_path = str(path or "").strip()
        if not raw_path:
            continue
        normalized_path = os.path.abspath(os.path.normpath(raw_path))
        if os.path.isfile(normalized_path):
            if is_supported_media(normalized_path):
                add(normalized_path)
            continue
        if not os.path.isdir(normalized_path):
            continue
        for folder_path, folder_names, file_names in os.walk(normalized_path):
            folder_names.sort(key=str.lower)
            for file_name in sorted(file_names, key=str.lower):
                if is_supported_media(file_name):
                    add(os.path.join(folder_path, file_name))

    return media_paths
