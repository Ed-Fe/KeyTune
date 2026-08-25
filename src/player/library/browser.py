import os
import time

import wx

from ..i18n import _, ngettext
from .text import normalize_search_text


TYPEAHEAD_RESET_SECONDS = 1.0


class VirtualItemsListCtrl(wx.ListCtrl):
    def __init__(self, parent, text_provider):
        super().__init__(
            parent,
            style=wx.LC_REPORT | wx.LC_NO_HEADER | wx.LC_VIRTUAL,
        )
        self._text_provider = text_provider
        self.InsertColumn(0, _("Itens"))
        self.Bind(wx.EVT_SIZE, self._on_size)
        self._sync_column_width()

    def OnGetItemText(self, item, column):
        if column != 0:
            return ""
        return self._text_provider(item)

    def _on_size(self, event):
        self._sync_column_width()
        event.Skip()

    def _sync_column_width(self):
        client_width = self.GetClientSize().Width
        if client_width > 0:
            self.SetColumnWidth(0, max(120, client_width - 6))


class PlaylistBrowserPanel(wx.Panel):
    def __init__(
        self,
        parent,
        on_activate_item,
        on_remove_item,
        on_preview_item=None,
        on_go_back=None,
        on_toggle_navigation_mode=None,
        on_show_context_menu=None,
    ):
        super().__init__(parent)

        self._on_activate_item = on_activate_item
        self._on_remove_item = on_remove_item
        self._on_preview_item = on_preview_item
        self._on_go_back = on_go_back
        self._on_toggle_navigation_mode = on_toggle_navigation_mode
        self._on_show_context_menu = on_show_context_menu
        self._items = []
        self._mode = "playlist"
        self._suppress_selection_event = False
        self._render_mode = None
        self._playlist_items_revision = -1
        self._playlist_current_index = wx.NOT_FOUND
        self._folder_entries_revision = -1
        self._folder_current_media_key = None
        self._folder_index_by_key = {}
        self._base_labels = []
        # Sufixos de favorito/avaliação por caminho, alimentados pelo frame a
        # partir da biblioteca inteligente. Ficam só na exibição: a busca
        # (Ctrl+F) e a sessão continuam vendo o rótulo puro.
        self._library_marks = {}
        self._has_placeholder = False
        self._placeholder_label = ""
        self._typeahead_query = ""
        self._typeahead_timestamp = 0.0

        root_sizer = wx.BoxSizer(wx.VERTICAL)

        self.header_label = wx.StaticText(self, label=_("Playlist"))
        self.items_list = VirtualItemsListCtrl(self, self._get_display_label)
        self.items_list.SetName(_("Lista de itens"))
        self.hint_label = wx.StaticText(
            self,
            label=_("Enter ativa. Delete remove. Shift+F10 abre ações. Digite letras para localizar. Tab volta ao player."),
        )
        self.hint_label.Wrap(260)

        root_sizer.Add(self.header_label, 0, wx.ALL | wx.EXPAND, 10)
        root_sizer.Add(self.items_list, 1, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)
        root_sizer.Add(self.hint_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)

        self.SetSizer(root_sizer)
        self.SetMinSize((300, 320))

        self.items_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_selection_changed)
        self.items_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.on_activate)
        self.items_list.Bind(wx.EVT_CHAR_HOOK, self.on_key_down)
        self.items_list.Bind(wx.EVT_CONTEXT_MENU, self.on_context_menu)

    def update_playlist(self, playlist_state):
        self._mode = "playlist"
        self._suppress_selection_event = True
        previous_current_index = self._playlist_current_index

        if playlist_state.is_loading:
            self._items = []
            self._base_labels = []
            self._playlist_current_index = wx.NOT_FOUND
            self._show_placeholder(playlist_state.loading_message or _("Carregando playlist..."))
            self._set_list_selection(wx.NOT_FOUND, ensure_visible=False)
            self.header_label.SetLabel(_("{title} — carregando").format(title=playlist_state.title))
            self.hint_label.SetLabel(_("Aguarde o carregamento da playlist. Tab volta ao player."))
            self.hint_label.Wrap(260)
            self._render_mode = "playlist"
            self._playlist_items_revision = playlist_state.items_revision
            self._folder_entries_revision = -1
            self._folder_current_media_key = None
            self._folder_index_by_key = {}
            self._clear_typeahead()
            self._suppress_selection_event = False
            return

        self._items = playlist_state.items
        self._base_labels = playlist_state.browser_item_labels
        self._playlist_current_index = playlist_state.current_index

        if playlist_state.items:
            if len(self._base_labels) != len(playlist_state.items):
                playlist_state.refresh_browser_item_labels()
            self._base_labels = playlist_state.browser_item_labels
            selection = (
                playlist_state.current_index
                if 0 <= playlist_state.current_index < len(self._base_labels)
                else wx.NOT_FOUND
            )
            needs_full_rebuild = (
                self._render_mode != "playlist"
                or self._playlist_items_revision != playlist_state.items_revision
                or self.items_list.GetItemCount() != len(self._base_labels)
            )
            if needs_full_rebuild:
                self._show_items(len(self._base_labels))
                self._set_list_selection(selection, ensure_visible=False)
            else:
                self._update_playlist_current_marker(
                    previous_current_index,
                    playlist_state.current_index,
                )
                existing_selection = self._get_selected_index()
                if existing_selection == wx.NOT_FOUND or existing_selection >= len(self._base_labels):
                    self._set_list_selection(selection, ensure_visible=False)
        else:
            self._show_placeholder(_("Nenhum item nesta playlist."))
            self._set_list_selection(wx.NOT_FOUND, ensure_visible=False)

        self.header_label.SetLabel(
            ngettext(
                "{title} — {count} item",
                "{title} — {count} itens",
                len(playlist_state.items),
            ).format(title=playlist_state.title, count=len(playlist_state.items))
        )
        self.hint_label.SetLabel(
            _("Enter ativa. Delete remove. Shift+F10 abre ações. Digite letras para localizar. Tab volta ao player.")
        )
        self.hint_label.Wrap(260)
        self._render_mode = "playlist"
        self._playlist_items_revision = playlist_state.items_revision
        self._folder_entries_revision = -1
        self._folder_current_media_key = None
        self._folder_index_by_key = {}
        self._clear_typeahead()
        self._suppress_selection_event = False

    def update_folder(
        self,
        title,
        current_path,
        entries,
        selected_path,
        current_media_path,
        entries_revision=0,
        loading=False,
        loading_message=None,
        entry_index_map=None,
    ):
        self._mode = "folder"
        self._suppress_selection_event = True

        if loading:
            self._items = []
            self._base_labels = []
            self._folder_current_media_key = None
            self._show_placeholder(loading_message or _("Carregando itens da pasta..."))
            self._set_list_selection(wx.NOT_FOUND, ensure_visible=False)
            self._folder_index_by_key = {}
            self.header_label.SetLabel(_("{title} — {path}").format(title=title, path=current_path))
            self.hint_label.SetLabel(_("Aguarde o carregamento da pasta. Tab volta ao player."))
            self.hint_label.Wrap(260)
            self._render_mode = "folder"
            self._folder_entries_revision = entries_revision
            self._playlist_items_revision = -1
            self._playlist_current_index = wx.NOT_FOUND
            self._clear_typeahead()
            self._suppress_selection_event = False
            return

        self._items = entries
        self._base_labels = []
        current_media_key = self._normalize_path_key(current_media_path)
        previous_media_key = self._folder_current_media_key
        self._folder_current_media_key = current_media_key

        if entries:
            needs_full_rebuild = (
                self._render_mode != "folder"
                or self._folder_entries_revision != entries_revision
                or self.items_list.GetItemCount() != len(entries)
            )
            if needs_full_rebuild:
                self._show_items(len(entries))
                self._folder_index_by_key = dict(entry_index_map or self._build_folder_index(entries))
            else:
                self._update_folder_current_marker(
                    entries,
                    previous_media_key,
                    current_media_key,
                )
            selection = self._find_selection(selected_path, current_media_key)
            self._set_list_selection(selection, ensure_visible=False)
        else:
            self._show_placeholder(_("Nenhuma pasta ou mídia nesta localização."))
            self._set_list_selection(wx.NOT_FOUND, ensure_visible=False)
            self._folder_index_by_key = {}

        self.header_label.SetLabel(_("{title} — {path}").format(title=title, path=current_path))
        self.hint_label.SetLabel(
            _("Enter entra na pasta ou toca o arquivo. Backspace volta. Ctrl+Espaço classifica. Digite letras para localizar. Tab volta ao player.")
        )
        self.hint_label.Wrap(260)
        self._render_mode = "folder"
        self._folder_entries_revision = entries_revision
        self._playlist_items_revision = -1
        self._playlist_current_index = wx.NOT_FOUND
        self._clear_typeahead()
        self._suppress_selection_event = False

    def focus_current_item(self):
        self.items_list.SetFocus()
        selection = self._get_selected_index()
        if selection == wx.NOT_FOUND and self._items:
            selection = 0
            self._set_list_selection(selection, ensure_visible=True)
        if selection != wx.NOT_FOUND:
            self.items_list.Focus(selection)
            self.items_list.EnsureVisible(selection)

    def is_item_navigation_active(self):
        if not self.IsShown():
            return False

        focused_window = wx.Window.FindFocus()
        current_window = focused_window
        while isinstance(current_window, wx.Window):
            if current_window is self.items_list:
                return True
            current_window = current_window.GetParent()

        return False

    def get_selected_item_path(self):
        if self._has_placeholder:
            return None

        selection = self._get_selected_index()
        if selection == wx.NOT_FOUND or selection >= len(self._items):
            return None

        item = self._items[selection]
        if isinstance(item, str):
            return item or None

        if getattr(item, "is_parent", False):
            return None

        path = getattr(item, "path", None)
        return path or None

    def has_searchable_items(self):
        """Whether the list currently holds real items (not a placeholder)."""
        return bool(self._items) and not self._has_placeholder

    def search_labels(self):
        """Labels usados pela busca (Ctrl+F), na mesma ordem da lista."""
        if self._has_placeholder:
            return []
        return [self._item_search_label(index) for index in range(len(self._items))]

    def get_selected_index(self):
        return self._get_selected_index()

    def focus_search_result(self, index):
        """Seleciona um resultado de busca e devolve o foco para a lista."""
        if self._has_placeholder or not 0 <= index < len(self._items):
            return False

        self._clear_typeahead()
        self._set_list_selection(index, ensure_visible=True)
        self.items_list.SetFocus()
        return True

    def get_selected_indexes(self):
        selections = []
        selection = self.items_list.GetFirstSelected()
        while selection != -1:
            selections.append(selection)
            selection = self.items_list.GetNextSelected(selection)
        return selections

    def get_selected_item_paths(self):
        if self._has_placeholder:
            return []
        selected_paths = []
        for selection in self.get_selected_indexes():
            if not 0 <= selection < len(self._items):
                continue
            item = self._items[selection]
            if isinstance(item, str):
                if item:
                    selected_paths.append(item)
                continue
            if getattr(item, "is_parent", False):
                continue
            item_path = getattr(item, "path", None)
            if item_path:
                selected_paths.append(item_path)
        return selected_paths

    def restore_selected_item_paths(self, paths):
        """Restore multi-selection after folder entries have been reordered."""
        if self._mode != "folder" or self._has_placeholder:
            return False

        indexes = []
        for path in paths or ():
            index = self._folder_index_by_key.get(self._normalize_path_key(path))
            if index is not None:
                indexes.append(index)
        if not indexes:
            return False

        self._suppress_selection_event = True
        try:
            for index in indexes:
                self.items_list.Select(index, True)
            self.items_list.Focus(indexes[0])
            self.items_list.EnsureVisible(indexes[0])
        finally:
            self._suppress_selection_event = False
        return True

    def set_library_marks(self, marks_by_path):
        """Define os marcadores exibidos ao lado de cada item.

        Recebe um dicionário caminho -> texto já formatado (por exemplo
        "favorito, 4 estrelas"). Um dicionário vazio remove os marcadores.
        """
        normalized_marks = dict(marks_by_path or {})
        if normalized_marks == self._library_marks:
            return False

        self._library_marks = normalized_marks
        # A lista é virtual: basta repintar para os rótulos serem relidos.
        self.items_list.Refresh()
        return True

    def _library_mark_suffix(self, media_path):
        if not self._library_marks or not media_path:
            return ""

        marks = self._library_marks.get(media_path)
        return f" — {marks}" if marks else ""

    def _get_display_label(self, index):
        if self._has_placeholder:
            return self._placeholder_label if index == 0 else ""

        if not 0 <= index < len(self._items):
            return ""

        if self._mode == "playlist":
            if not 0 <= index < len(self._base_labels):
                return ""
            return self._format_label(
                index,
                self._base_labels[index],
                self._playlist_current_index,
                self._library_mark_suffix(self._items[index]),
            )

        return self._format_folder_label(self._items[index], self._current_folder_media_path())

    def _format_label(self, index, item_label, current_index, mark_suffix=""):
        prefix = "▶ " if index == current_index else "   "
        return f"{prefix}{index + 1}. {item_label}{mark_suffix}"

    def _format_folder_label(self, entry, current_media_path):
        if getattr(entry, "is_parent", False):
            return entry.label

        if getattr(entry, "is_directory", False):
            return entry.label

        return f"{entry.label}{self._library_mark_suffix(getattr(entry, 'path', ''))}"

    def _find_selection(self, selected_path, current_media_key):
        target_key = self._normalize_path_key(selected_path) or current_media_key
        if target_key and target_key in self._folder_index_by_key:
            return self._folder_index_by_key[target_key]

        for index, entry in enumerate(self._items):
            if not getattr(entry, "is_parent", False):
                return index

        return 0 if self._items else wx.NOT_FOUND

    def _normalize_path_key(self, path):
        if not path:
            return None
        return os.path.normcase(os.path.normpath(path))

    def _build_folder_index(self, entries):
        index_by_key = {}
        for index, entry in enumerate(entries):
            entry_path = getattr(entry, "path", None)
            entry_key = self._normalize_path_key(entry_path)
            if entry_key:
                index_by_key[entry_key] = index
        return index_by_key

    def _show_items(self, count):
        self._has_placeholder = False
        self._placeholder_label = ""
        self.items_list.SetItemCount(count)
        self.items_list.Refresh()

    def _show_placeholder(self, label):
        self._has_placeholder = True
        self._placeholder_label = label
        self.items_list.SetItemCount(1)
        self.items_list.RefreshItem(0)

    def _get_selected_index(self):
        selection = self.items_list.GetFirstSelected()
        return selection if selection != -1 else wx.NOT_FOUND

    def _get_focused_index(self):
        get_focused_item = getattr(self.items_list, "GetFocusedItem", None)
        if callable(get_focused_item):
            focused = get_focused_item()
        else:
            focused = self.items_list.GetNextItem(-1, wx.LIST_NEXT_ALL, wx.LIST_STATE_FOCUSED)
        return focused if focused != -1 else wx.NOT_FOUND

    def _get_activation_index(self):
        focused = self._get_focused_index()
        if focused != wx.NOT_FOUND and focused < len(self._items):
            self._set_list_selection(focused)
            return focused

        selection = self._get_selected_index()
        if selection == wx.NOT_FOUND or selection >= len(self._items):
            return wx.NOT_FOUND
        return selection

    def _clear_selection(self):
        selection = self._get_selected_index()
        while selection != wx.NOT_FOUND:
            self.items_list.Select(selection, on=False)
            selection = self.items_list.GetFirstSelected()

    def _set_list_selection(self, selection, ensure_visible=True):
        current_selection = self._get_selected_index()
        if selection == wx.NOT_FOUND:
            if current_selection != wx.NOT_FOUND:
                self._clear_selection()
            return

        if current_selection != selection:
            self._clear_selection()
            self.items_list.Select(selection)

        self.items_list.Focus(selection)
        if ensure_visible:
            self.items_list.EnsureVisible(selection)

    def _refresh_item(self, index):
        if 0 <= index < self.items_list.GetItemCount():
            self.items_list.RefreshItem(index)

    def _update_playlist_current_marker(self, previous_index, current_index):
        item_count = len(self._base_labels)
        indexes_to_refresh = set()
        if 0 <= previous_index < item_count:
            indexes_to_refresh.add(previous_index)
        if 0 <= current_index < item_count:
            indexes_to_refresh.add(current_index)

        for index in indexes_to_refresh:
            self._refresh_item(index)

    def _current_folder_media_path(self):
        if not self._folder_current_media_key:
            return None

        index = self._folder_index_by_key.get(self._folder_current_media_key)
        if index is None or not 0 <= index < len(self._items):
            return None

        return getattr(self._items[index], "path", None)

    def _update_folder_current_marker(self, entries, previous_media_key, current_media_key):
        return

    def _clear_typeahead(self):
        self._typeahead_query = ""
        self._typeahead_timestamp = 0.0

    def _normalize_search_text(self, text):
        return normalize_search_text(text)

    def _item_search_label(self, index):
        if not 0 <= index < len(self._items):
            return ""

        if self._mode == "playlist":
            if 0 <= index < len(self._base_labels):
                return self._base_labels[index]
            return ""

        return getattr(self._items[index], "label", "")

    def _move_selection_to_search_match(self, search_text):
        normalized_search = self._normalize_search_text(search_text)
        if not normalized_search or not self._items:
            return False

        current_selection = self._get_selected_index()
        start_index = current_selection if current_selection != wx.NOT_FOUND else -1
        item_count = len(self._items)

        for offset in range(1, item_count + 1):
            candidate_index = (start_index + offset) % item_count
            candidate_label = self._normalize_search_text(self._item_search_label(candidate_index))
            if candidate_label.startswith(normalized_search):
                self._set_list_selection(candidate_index, ensure_visible=True)
                return True

        return False

    def _handle_typeahead(self, character):
        if self._has_placeholder or not self._items:
            return False

        now = time.monotonic()
        if now - self._typeahead_timestamp > TYPEAHEAD_RESET_SECONDS:
            self._typeahead_query = ""

        self._typeahead_timestamp = now
        self._typeahead_query += character

        if self._move_selection_to_search_match(self._typeahead_query):
            return True

        self._typeahead_query = character
        return self._move_selection_to_search_match(self._typeahead_query)

    def _character_from_event(self, event):
        if event.ControlDown() or event.AltDown():
            return ""

        unicode_key = event.GetUnicodeKey()
        if unicode_key == wx.WXK_NONE:
            return ""

        if unicode_key < 32:
            return ""

        character = chr(unicode_key)
        if not character.isprintable() or character.isspace():
            return ""

        return character

    def _activate_selected(self):
        selection = self._get_activation_index()
        if selection == wx.NOT_FOUND or selection >= len(self._items):
            return
        self._on_activate_item(selection)

    def _remove_selected(self):
        selections = [selection for selection in self.get_selected_indexes() if 0 <= selection < len(self._items)]
        if not selections:
            return
        self._on_remove_item(selections)

    def _show_context_menu(self, anchor_window=None):
        if not callable(self._on_show_context_menu):
            return
        self._on_show_context_menu(self, anchor_window or self.items_list)

    def on_activate(self, _event):
        self._activate_selected()

    def on_selection_changed(self, _event):
        if self._mode != "folder" or self._suppress_selection_event:
            return

        selection = self._get_selected_index()
        if selection == wx.NOT_FOUND or selection >= len(self._items):
            return

        entry = self._items[selection]
        if not getattr(entry, "is_file", False) or not self._on_preview_item:
            return

        self._on_preview_item(selection)

    def on_key_down(self, event):
        key_code = event.GetKeyCode()
        character = self._character_from_event(event)

        if event.ControlDown() or event.AltDown():
            event.Skip()
            return

        if key_code == wx.WXK_TAB:
            if self._on_toggle_navigation_mode:
                self._on_toggle_navigation_mode()
            return

        if key_code in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._activate_selected()
            return

        if key_code == wx.WXK_F10 and event.ShiftDown():
            self._show_context_menu()
            return

        if self._mode == "folder" and key_code == wx.WXK_BACK:
            if self._on_go_back:
                self._on_go_back()
            return

        if self._mode == "playlist" and key_code in (wx.WXK_DELETE, wx.WXK_BACK):
            self._remove_selected()
            return

        if key_code == wx.WXK_ESCAPE:
            self._clear_typeahead()
            if self._on_toggle_navigation_mode:
                self._on_toggle_navigation_mode()
            return

        if character and self._handle_typeahead(character):
            return

        event.DoAllowNextEvent()

    def on_context_menu(self, event):
        self._show_context_menu(event.GetEventObject() if hasattr(event, "GetEventObject") else None)
