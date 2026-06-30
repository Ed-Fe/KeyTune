import os

import wx

from ..constants import RECENT_ITEMS_LIMIT
from ..i18n import _


class FrameRecentsMixin:
    def _default_dialog_directory(self):
        if not self.settings.remember_last_folder:
            return ""

        last_open_dir = (self.settings.last_open_dir or "").strip()
        if last_open_dir and os.path.isdir(last_open_dir):
            return last_open_dir

        return ""

    def _remember_directory(self, path):
        if not self.settings.remember_last_folder or not path:
            return

        normalized_path = path
        if os.path.isfile(normalized_path):
            normalized_path = os.path.dirname(normalized_path)

        if not normalized_path or not os.path.isdir(normalized_path):
            return

        self.settings.last_open_dir = normalized_path
        self._save_settings()

    def _normalize_path(self, path):
        normalized_path = str(path or "").strip()
        if not normalized_path:
            return ""

        return os.path.abspath(os.path.normpath(normalized_path))

    def _recent_collections(self):
        return (
            ("recent_media_files", os.path.isfile),
            ("recent_folders", os.path.isdir),
            ("recent_playlists", os.path.isfile),
        )

    def _clean_recent_paths(self, paths, exists_checker):
        normalized_paths = []
        seen_paths = set()

        for path in paths:
            normalized_path = self._normalize_path(path)
            normalized_key = os.path.normcase(normalized_path)
            if not normalized_path or normalized_key in seen_paths or not exists_checker(normalized_path):
                continue

            seen_paths.add(normalized_key)
            normalized_paths.append(normalized_path)

            if len(normalized_paths) >= RECENT_ITEMS_LIMIT:
                break

        return normalized_paths

    def _prune_recent_items(self):
        changed = False

        for attribute_name, exists_checker in self._recent_collections():
            current_paths = getattr(self.settings, attribute_name, [])
            cleaned_paths = self._clean_recent_paths(current_paths, exists_checker)
            if cleaned_paths != current_paths:
                setattr(self.settings, attribute_name, cleaned_paths)
                changed = True

        return changed

    def _recent_entry_label(self, path):
        normalized_path = str(path).rstrip("\\/")
        entry_name = os.path.basename(normalized_path) or normalized_path
        parent_path = os.path.dirname(normalized_path)
        entry_name = entry_name.replace("&", "&&")
        parent_path = parent_path.replace("&", "&&")
        if parent_path and parent_path != normalized_path:
            return f"{entry_name} — {parent_path}"
        return entry_name

    def _refresh_recent_submenu(self, menu, attribute_name, empty_label, clear_label):
        while menu.GetMenuItemCount():
            menu.Delete(menu.FindItemByPosition(0))

        paths = getattr(self.settings, attribute_name, [])
        if not paths:
            placeholder = menu.Append(wx.ID_ANY, empty_label)
            placeholder.Enable(False)
            return

        for path in paths:
            item_id_ref = wx.NewIdRef()
            item_id = int(item_id_ref)
            self._recent_menu_ids.append(item_id_ref)
            menu.Append(item_id_ref, self._recent_entry_label(path))
            self.Bind(wx.EVT_MENU, self.on_recent_menu_action, id=item_id)
            self._recent_menu_actions[item_id] = ("open", attribute_name, path)

        menu.AppendSeparator()
        clear_item_id_ref = wx.NewIdRef()
        clear_item_id = int(clear_item_id_ref)
        self._recent_menu_ids.append(clear_item_id_ref)
        menu.Append(clear_item_id_ref, clear_label)
        self.Bind(wx.EVT_MENU, self.on_recent_menu_action, id=clear_item_id)
        self._recent_menu_actions[clear_item_id] = ("clear", attribute_name, None)

    def _refresh_recent_menus(self):
        # Drop the EVT_MENU handlers bound to the previous (now-deleted) item
        # ids before rebuilding. Without this, every rebuild leaks a frame-level
        # binding to a dead IdRef, accumulating handlers over a long session.
        for previous_id_ref in getattr(self, "_recent_menu_ids", []):
            self.Unbind(wx.EVT_MENU, id=int(previous_id_ref))
        self._recent_menu_actions = {}
        self._recent_menu_ids = []
        recent_paths_changed = self._prune_recent_items()

        self._refresh_recent_submenu(
            self.recent_files_menu,
            "recent_media_files",
            _("Nenhum arquivo recente."),
            _("Limpar arquivos recentes"),
        )
        self._refresh_recent_submenu(
            self.recent_folders_menu,
            "recent_folders",
            _("Nenhuma pasta recente."),
            _("Limpar pastas recentes"),
        )
        self._refresh_recent_submenu(
            self.recent_playlists_menu,
            "recent_playlists",
            _("Nenhuma playlist recente."),
            _("Limpar playlists recentes"),
        )

        if recent_paths_changed:
            self._save_settings()

    def _add_recent_path(self, attribute_name, path):
        normalized_path = self._normalize_path(path)
        if not normalized_path:
            return

        exists_checker = dict(self._recent_collections()).get(attribute_name)
        if not exists_checker or not exists_checker(normalized_path):
            return

        current_paths = getattr(self.settings, attribute_name, [])
        normalized_key = os.path.normcase(normalized_path)
        updated_paths = [normalized_path]
        for current_path in current_paths:
            current_normalized = self._normalize_path(current_path)
            if os.path.normcase(current_normalized) == normalized_key:
                continue
            updated_paths.append(current_normalized)

        setattr(self.settings, attribute_name, updated_paths[:RECENT_ITEMS_LIMIT])
        self._save_settings()
        self._refresh_recent_menus()

    def _add_recent_media_paths(self, paths):
        for path in reversed(list(paths)):
            self._add_recent_path("recent_media_files", path)

    def _remove_recent_path(self, attribute_name, path):
        normalized_path = self._normalize_path(path)
        normalized_key = os.path.normcase(normalized_path)
        current_paths = getattr(self.settings, attribute_name, [])
        updated_paths = []

        for current_path in current_paths:
            current_normalized = self._normalize_path(current_path)
            if os.path.normcase(current_normalized) == normalized_key:
                continue
            updated_paths.append(current_normalized)

        setattr(self.settings, attribute_name, updated_paths)
        self._save_settings()
        self._refresh_recent_menus()

    def _clear_recent_paths(self, attribute_name, announcement):
        setattr(self.settings, attribute_name, [])
        self._save_settings()
        self._refresh_recent_menus()
        self._announce(announcement)
