import os
import time
import unicodedata

import wx


TYPEAHEAD_RESET_SECONDS = 1.0


class VirtualItemsListCtrl(wx.ListCtrl):
    def __init__(self, parent, text_provider):
        super().__init__(
            parent,
            style=wx.LC_REPORT | wx.LC_NO_HEADER | wx.LC_SINGLE_SEL | wx.LC_VIRTUAL,
        )
        self._text_provider = text_provider
        self.InsertColumn(0, "Itens")
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
    ):
        super().__init__(parent)

        self._on_activate_item = on_activate_item
        self._on_remove_item = on_remove_item
        self._on_preview_item = on_preview_item
        self._on_go_back = on_go_back
        self._on_toggle_navigation_mode = on_toggle_navigation_mode
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
        self._has_placeholder = False
        self._placeholder_label = ""
        self._typeahead_query = ""
        self._typeahead_timestamp = 0.0

        root_sizer = wx.BoxSizer(wx.VERTICAL)

        self.header_label = wx.StaticText(self, label="Playlist")
        self.items_list = VirtualItemsListCtrl(self, self._get_display_label)
        self.items_list.SetName("Lista de itens")
        self.items_list.SetHelpText(
            "Mostra a playlist atual ou os itens da pasta atual. Use setas para navegar e digite letras para localizar rapidamente."
        )
        self.hint_label = wx.StaticText(
            self,
            label="Enter toca o item selecionado. Delete remove. Digite letras para localizar. Tab volta ao player.",
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

    def update_playlist(self, playlist_state):
        self._mode = "playlist"
        self._suppress_selection_event = True
        previous_current_index = self._playlist_current_index

        if playlist_state.is_loading:
            self._items = []
            self._base_labels = []
            self._playlist_current_index = wx.NOT_FOUND
            self._show_placeholder(playlist_state.loading_message or "Carregando playlist...")
            self._set_list_selection(wx.NOT_FOUND, ensure_visible=False)
            self.header_label.SetLabel(f"{playlist_state.title} — carregando")
            self.hint_label.SetLabel("Aguarde o carregamento da playlist. Tab volta ao player.")
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
            else:
                self._update_playlist_current_marker(
                    previous_current_index,
                    playlist_state.current_index,
                )
            self._set_list_selection(selection, ensure_visible=False)
        else:
            self._show_placeholder("Nenhum item nesta playlist.")
            self._set_list_selection(wx.NOT_FOUND, ensure_visible=False)

        self.header_label.SetLabel(
            f"{playlist_state.title} — {len(playlist_state.items)} item(ns)"
        )
        self.hint_label.SetLabel(
            "Enter toca o item selecionado. Delete remove. Digite letras para localizar. Tab volta ao player."
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
            self._show_placeholder(loading_message or "Carregando itens da pasta...")
            self._set_list_selection(wx.NOT_FOUND, ensure_visible=False)
            self._folder_index_by_key = {}
            self.header_label.SetLabel(f"{title} — {current_path}")
            self.hint_label.SetLabel("Aguarde o carregamento da pasta. Tab volta ao player.")
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
            self._show_placeholder("Nenhuma pasta ou mídia nesta localização.")
            self._set_list_selection(wx.NOT_FOUND, ensure_visible=False)
            self._folder_index_by_key = {}

        self.header_label.SetLabel(f"{title} — {current_path}")
        self.hint_label.SetLabel(
            "Enter entra na pasta ou toca o arquivo. Backspace volta. Digite letras para localizar. Tab volta ao player."
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
        focused_window = self.FindFocus()
        return self.IsShown() and focused_window is not None and focused_window is self.items_list

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

    def _get_display_label(self, index):
        if self._has_placeholder:
            return self._placeholder_label if index == 0 else ""

        if not 0 <= index < len(self._items):
            return ""

        if self._mode == "playlist":
            if not 0 <= index < len(self._base_labels):
                return ""
            return self._format_label(index, self._base_labels[index], self._playlist_current_index)

        return self._format_folder_label(self._items[index], self._current_folder_media_path())

    def _format_label(self, index, item_label, current_index):
        prefix = "▶ " if index == current_index else "   "
        return f"{prefix}{index + 1}. {item_label}"

    def _format_folder_label(self, entry, current_media_path):
        if getattr(entry, "is_parent", False):
            return entry.label

        if getattr(entry, "is_directory", False):
            return entry.label

        return entry.label

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
        if not text:
            return ""

        normalized = unicodedata.normalize("NFKD", text)
        without_accents = "".join(character for character in normalized if not unicodedata.combining(character))
        return without_accents.casefold().strip()

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
        selection = self._get_selected_index()
        if selection == wx.NOT_FOUND or selection >= len(self._items):
            return
        self._on_activate_item(selection)

    def _remove_selected(self):
        selection = self._get_selected_index()
        if selection == wx.NOT_FOUND or selection >= len(self._items):
            return
        self._on_remove_item(selection)

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

        if key_code == wx.WXK_TAB:
            if self._on_toggle_navigation_mode:
                self._on_toggle_navigation_mode()
            return

        if key_code in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._activate_selected()
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
