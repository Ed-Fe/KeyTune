import os

import wx

from ..i18n import _, ngettext
from ..library import folder_display_name, is_playlist_source, is_remote_media_path, playlist_display_name, scan_folder_contents
from ..playlists import PlaylistState, build_playlist_title


class FrameLibraryNavigationMixin:
    def _is_appendable_playlist_state(self, candidate):
        if not isinstance(candidate, PlaylistState):
            return False
        if candidate.is_folder_tab or candidate.is_loading:
            return False
        return True

    def _playlist_state_for_external_media(self):
        current_state = self._get_tab_state(self._get_current_tab_index())
        if self._is_appendable_playlist_state(current_state):
            return current_state

        active_state = self._get_active_playlist_state()
        if self._is_appendable_playlist_state(active_state) and not active_state.is_empty:
            return active_state

        for candidate in self.playlists:
            if self._is_appendable_playlist_state(candidate) and not candidate.is_empty:
                return candidate

        return None

    def _append_media_paths_to_playlist(self, paths, state):
        """Append *paths* to *state*, deduping against existing items.

        Returns a tuple ``(added_count, first_play_path)`` where
        ``first_play_path`` is the path that should be focused/played next
        (the first new path, or the first requested path when all were
        duplicates).  ``added_count`` is the number of brand-new items that
        were appended (zero when every path was already in the playlist).
        """
        normalized_paths = []
        normalized_labels = []
        for path in paths:
            normalized_path = str(path or "").strip()
            if not normalized_path:
                continue
            if is_remote_media_path(normalized_path):
                normalized_paths.append(normalized_path)
                normalized_labels.append(os.path.basename(normalized_path) or normalized_path)
                continue
            normalized_path = self._normalize_path(normalized_path)
            if normalized_path and os.path.isfile(normalized_path):
                normalized_paths.append(normalized_path)
                normalized_labels.append(os.path.basename(normalized_path) or normalized_path)

        added_count, first_item = self._append_prepared_items_to_playlist(
            normalized_paths,
            state,
            browser_item_labels=normalized_labels,
        )
        if added_count > 0:
            self._remember_directory(normalized_paths[0])
            self._add_recent_media_paths(normalized_paths)
        return added_count, first_item

    def _append_prepared_items_to_playlist(self, items, state, *, browser_item_labels=None):
        """Append prepared playlist items to *state* while preserving custom labels."""
        if not state or state.is_folder_tab or state.is_loading:
            return 0, None

        normalized_items = []
        normalized_labels = []
        raw_labels = list(browser_item_labels or [])
        for index, item in enumerate(items or []):
            normalized_item = str(item or "").strip()
            if not normalized_item:
                continue
            normalized_items.append(normalized_item)
            fallback_label = os.path.basename(normalized_item) or normalized_item
            normalized_labels.append(str(raw_labels[index] or "").strip() or fallback_label)

        if not normalized_items:
            return 0, None

        existing = set(state.items)
        new_items = []
        new_labels = []
        for item, label in zip(normalized_items, normalized_labels):
            if item in existing:
                continue
            existing.add(item)
            new_items.append(item)
            new_labels.append(label)

        first_requested = normalized_items[0]
        if not new_items:
            return 0, first_requested

        state.finish_library_load()
        state.clear_folder_location()
        state.items.extend(new_items)
        state.browser_item_labels.extend(new_labels)
        state.refresh_browser_item_labels()
        self._maybe_rename_playlist_after_append(state)
        return len(new_items), new_items[0]

    def _maybe_rename_playlist_after_append(self, state):
        """Refresh the playlist title to reflect its current contents.

        Skips playlists that came from a saved file (``source_path``) so we
        don't override a name the user explicitly chose.
        """
        if not isinstance(state, PlaylistState):
            return
        if getattr(state, "source_path", None):
            return
        if not state.items:
            return

        new_title = build_playlist_title(state.items)
        if not new_title or new_title == state.title:
            return

        state.title = new_title
        target_index = self._resolve_playlist_state_index(state)
        if target_index != wx.NOT_FOUND and hasattr(self, "notebook"):
            self.notebook.SetPageText(target_index, new_title)

    def _open_external_media_paths(self, paths):
        target_state = self._playlist_state_for_external_media()
        if target_state is None:
            opened = self._open_media_paths(paths)
            if opened:
                self._suppress_next_auto_advance = True
            return opened

        added_count, play_path = self._append_media_paths_to_playlist(paths, target_state)
        if not play_path:
            return False

        target_index = self._resolve_playlist_state_index(target_state)
        if target_index == wx.NOT_FOUND:
            return added_count > 0

        play_index = target_state.index_of_item(play_path)
        if play_index is None:
            return added_count > 0

        target_state.select_index(play_index)
        self.active_playlist_index = target_index
        self._select_tab(target_index, announce=False)
        self._refresh_playlist_browser()
        self._play_media(index=target_index)
        self._suppress_next_auto_advance = True

        if hasattr(self, "_set_status_message"):
            if added_count > 0:
                self._set_status_message(
                    ngettext(
                        "{count} item adicionado a {title}.",
                        "{count} itens adicionados a {title}.",
                        added_count,
                    ).format(count=added_count, title=target_state.title)
                )
            else:
                self._set_status_message(
                    _("Reproduzindo item já presente em {title}.").format(title=target_state.title)
                )

        return True

    def _show_loading_library_tab(self, target_index, state, announcement=None):
        self.notebook.SetPageText(target_index, state.title)
        self._select_tab(target_index, announce=False)
        self._unload_player()
        self._update_title()
        self._refresh_playlist_browser()
        if announcement:
            self._announce(announcement)

    def _open_media_paths(self, paths):
        normalized_paths = []
        for path in paths:
            normalized_path = str(path or "").strip()
            if not normalized_path:
                continue
            if is_remote_media_path(normalized_path):
                normalized_paths.append(normalized_path)
                continue
            normalized_path = self._normalize_path(normalized_path)
            if normalized_path and os.path.isfile(normalized_path):
                normalized_paths.append(normalized_path)

        if not normalized_paths:
            return False

        self._remember_directory(normalized_paths[0])

        title = build_playlist_title(normalized_paths)
        tab_index = self._prepare_playlist_tab(normalized_paths, title)
        self._play_media(index=tab_index)
        self._add_recent_media_paths(normalized_paths)
        return True

    def _prepare_folder_tab(self, folder_path):
        normalized_folder_path = self._normalize_path(folder_path)
        if not normalized_folder_path or not os.path.isdir(normalized_folder_path):
            return None

        state, target_index = self._prepare_library_target_tab()
        if not state:
            return None

        auto_index_folder = getattr(self, "_auto_index_opened_folder", None)
        if callable(auto_index_folder):
            auto_index_folder(normalized_folder_path)

        self._begin_folder_load(state, normalized_folder_path, root_path=normalized_folder_path)
        self._queue_library_request(
            {
                "kind": "folder",
                "state": state,
                "folder_path": normalized_folder_path,
                "sort_by": state.folder_sort_by,
                "sort_descending": state.folder_sort_descending,
                "recent_path": normalized_folder_path,
                "focus_items": True,
                "completion_announcement": _("Pasta aberta no navegador: {name}.").format(name=folder_display_name(normalized_folder_path)),
            }
        )
        self._show_loading_library_tab(target_index, state)
        return target_index

    def _enter_folder_directory(self, folder_path, selected_path=None, announce=True):
        state = self._get_playlist_state()
        if not state or not state.is_folder_tab:
            return False

        normalized_folder_path = self._normalize_path(folder_path)
        if not normalized_folder_path or not os.path.isdir(normalized_folder_path):
            return False

        self._begin_folder_load(
            state,
            normalized_folder_path,
            root_path=state.folder_root_path or normalized_folder_path,
            selected_path=selected_path,
        )
        self._queue_library_request(
            {
                "kind": "folder",
                "state": state,
                "folder_path": normalized_folder_path,
                "sort_by": state.folder_sort_by,
                "sort_descending": state.folder_sort_descending,
                "focus_items": True,
                "completion_announcement": (
                    f"Pasta atual: {folder_display_name(normalized_folder_path)}."
                    if announce
                    else None
                ),
            }
        )
        self._show_loading_library_tab(
            self._get_current_tab_index(),
            state,
            announcement=(f"Carregando pasta: {folder_display_name(normalized_folder_path)}." if announce else None),
        )

        return True

    def _preview_folder_file(self, media_path, announce=True):
        state = self._get_playlist_state()
        if not state or not state.is_folder_tab or not state.folder_current_path:
            return

        if state.is_loading:
            self._announce(_("A pasta ainda está sendo carregada."))
            return

        normalized_media_path = self._normalize_path(media_path)
        if not normalized_media_path or not os.path.isfile(normalized_media_path):
            self._announce(_("O arquivo selecionado não está mais disponível."))
            self._refresh_playlist_browser()
            return

        same_media_already_playing = (
            state.current_media_path == normalized_media_path
            and self.player.get_media() is not None
            and self.player.is_playing()
        )

        state.folder_selected_path = normalized_media_path

        if not state.contains_item(normalized_media_path):
            try:
                folder_entries, media_files = scan_folder_contents(
                    state.folder_current_path,
                    sort_by=state.folder_sort_by,
                    descending=state.folder_sort_descending,
                )
            except OSError:
                folder_entries = []
                media_files = []
            state.set_folder_entries(folder_entries)
            state.set_items(media_files, auto_select=False)

        media_index = state.index_of_item(normalized_media_path)
        if media_index is None:
            self._announce(_("O arquivo selecionado não pertence à pasta atual."))
            self._refresh_playlist_browser()
            return

        if same_media_already_playing:
            state.select_index(media_index)
            self._refresh_playlist_browser()
            return

        state.select_index(media_index)
        announce_message = ""
        self._play_media(index=self._get_current_tab_index(), announce_message=announce_message)

    def _go_back_folder(self):
        state = self._get_playlist_state()
        if not state or not state.is_folder_tab or not state.folder_current_path:
            return

        parent_path = os.path.dirname(state.folder_current_path)
        if not parent_path or parent_path == state.folder_current_path:
            self._announce(_("Você já está na pasta raiz."))
            return

        self._enter_folder_directory(
            parent_path,
            selected_path=state.folder_current_path,
            announce=True,
        )

    def _open_folder_path(self, folder_path):
        normalized_folder_path = self._normalize_path(folder_path)
        if not normalized_folder_path or not os.path.isdir(normalized_folder_path):
            return False

        self._remember_directory(normalized_folder_path)

        tab_index = self._prepare_folder_tab(normalized_folder_path)
        if tab_index is None:
            return False
        self._announce(_("Carregando pasta: {name}.").format(name=folder_display_name(normalized_folder_path)))
        return True

    def _open_folder_as_playlist(self, folder_path):
        normalized_folder_path = self._normalize_path(folder_path)
        if not normalized_folder_path or not os.path.isdir(normalized_folder_path):
            return False

        self._remember_directory(normalized_folder_path)

        state, target_index = self._prepare_library_target_tab()
        if not state:
            return False

        title = folder_display_name(normalized_folder_path)
        previous_title = state.title
        previous_source_path = state.source_path
        self._begin_playlist_load(state, title)
        self._queue_library_request(
            {
                "kind": "folder_playlist",
                "state": state,
                "folder_path": normalized_folder_path,
                "title": title,
                "previous_title": previous_title,
                "previous_source_path": previous_source_path,
            }
        )
        self._show_loading_library_tab(target_index, state, announcement=f"Carregando pasta como playlist: {title}.")
        return True

    def _open_playlist_source(self, playlist_source):
        normalized_playlist_source = str(playlist_source or "").strip()
        if not normalized_playlist_source or not is_playlist_source(normalized_playlist_source):
            return False

        if not is_remote_media_path(normalized_playlist_source):
            normalized_playlist_source = self._normalize_path(normalized_playlist_source)
            if not normalized_playlist_source or not os.path.isfile(normalized_playlist_source):
                return False

            self._remember_directory(normalized_playlist_source)

        state, target_index = self._prepare_library_target_tab()
        if not state:
            return False

        title = playlist_display_name(normalized_playlist_source)
        previous_title = state.title
        previous_source_path = state.source_path
        self._begin_playlist_load(state, title)
        self._queue_library_request(
            {
                "kind": "playlist",
                "state": state,
                "playlist_source": normalized_playlist_source,
                "title": title,
                "previous_title": previous_title,
                "previous_source_path": previous_source_path,
            }
        )
        self._show_loading_library_tab(target_index, state, announcement=f"Carregando playlist: {title}.")
        return True

    def _open_playlist_path(self, playlist_path):
        return self._open_playlist_source(playlist_path)

    def _focus_item_navigation(self, announce=True):
        browser = self._get_browser_panel()
        if not browser:
            return

        self._refresh_playlist_browser()
        browser.focus_current_item()
        if announce:
            self._announce(_("Modo navegação de itens."))

    def _focus_player_controls(self, announce=True):
        # Focus the wx video panel (a restorable child) rather than the frame,
        # so returning to the window/closing a dialog lands back on the player.
        self._focus_player_surface()
        if announce:
            self._announce(_("Modo controle do player."))

    def _toggle_navigation_mode(self):
        browser = self._get_browser_panel()
        if not browser:
            return

        if browser.is_item_navigation_active():
            self._focus_player_controls(announce=True)
            return

        self._focus_item_navigation(announce=True)

    def _refresh_playlist_browser(self):
        browser = self._get_browser_panel()
        if not browser:
            return

        current_state = self._get_playlist_state()
        if not current_state:
            return

        refresh_library_marks = getattr(self, "_refresh_library_marks", None)
        if callable(refresh_library_marks):
            refresh_library_marks(browser, current_state)
        refresh_autodj_ui = getattr(self, "_refresh_autodj_session_ui", None)
        if callable(refresh_autodj_ui):
            refresh_autodj_ui(current_state)

        if current_state.is_folder_tab and current_state.folder_current_path:
            browser.update_folder(
                title=current_state.title,
                current_path=current_state.folder_current_path,
                entries=self._get_folder_entries(current_state),
                selected_path=current_state.folder_selected_path,
                current_media_path=current_state.current_media_path,
                entries_revision=current_state.folder_entries_revision,
                loading=current_state.is_loading,
                loading_message=current_state.loading_message,
                entry_index_map=current_state.folder_entry_index_map,
            )
            return

        browser.update_playlist(current_state)
