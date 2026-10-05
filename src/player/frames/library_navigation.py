import os

import wx

from ..i18n import _, ngettext
from ..library import folder_display_name, is_playlist_source, is_remote_media_path, playlist_display_name
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

    def _append_media_paths_to_playlist(self, paths, state, *, verified=False):
        """Append *paths* to *state*, deduping against existing items.

        ``verified`` means the caller already confirmed, off the UI thread,
        that the local files exist, so the disk is not consulted again here.

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
            if normalized_path and (verified or os.path.isfile(normalized_path)):
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

    def _open_external_media_paths(self, paths, *, verified=False):
        target_state = self._playlist_state_for_external_media()
        if target_state is None:
            opened = self._open_media_paths(paths, verified=verified)
            if opened:
                self._suppress_next_auto_advance = True
            return opened

        added_count, play_path = self._append_media_paths_to_playlist(paths, target_state, verified=verified)
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

    def _add_media_paths_without_playing(self, paths, *, verified=False):
        """Põe *paths* no fim da playlist sem mexer no que está tocando."""
        target_state = self._playlist_state_for_external_media()
        if target_state is None:
            target_state = self._get_playlist_state(self._create_empty_playlist_tab(select=False))
        if target_state is None:
            return False

        if target_state.autodj_session and target_state is self._get_playlist_state():
            return self._add_media_to_autodj_session(paths)

        added_count, first_path = self._append_media_paths_to_playlist(paths, target_state, verified=verified)
        if not first_path:
            self._announce(_("Nenhuma mídia compatível para adicionar."))
            return False

        target_state.sync_playback_order()
        if self._is_current_playlist_state(target_state):
            self._refresh_playlist_browser()

        if added_count:
            message = ngettext(
                "{count} item adicionado a {title}, sem tocar.",
                "{count} itens adicionados a {title}, sem tocar.",
                added_count,
            ).format(count=added_count, title=target_state.title)
        else:
            message = _("Os itens já estavam em {title}.").format(title=target_state.title)
        self._announce(message)
        if hasattr(self, "_set_status_message"):
            self._set_status_message(message)
        return added_count > 0

    def _show_loading_library_tab(self, target_index, state, announcement=None):
        self.notebook.SetPageText(target_index, state.title)
        self._select_tab(target_index, announce=False)
        self._unload_player()
        self._update_title()
        self._refresh_playlist_browser()
        if announcement:
            self._announce(announcement)

    def _open_media_paths(self, paths, *, verified=False):
        normalized_paths = []
        for path in paths:
            normalized_path = str(path or "").strip()
            if not normalized_path:
                continue
            if is_remote_media_path(normalized_path):
                normalized_paths.append(normalized_path)
                continue
            normalized_path = self._normalize_path(normalized_path)
            if normalized_path and (verified or os.path.isfile(normalized_path)):
                normalized_paths.append(normalized_path)

        if not normalized_paths:
            return False

        self._remember_directory(normalized_paths[0])

        title = build_playlist_title(normalized_paths)
        tab_index = self._prepare_playlist_tab(normalized_paths, title)
        self._play_media(index=tab_index)
        self._add_recent_media_paths(normalized_paths)
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

        browser.update_playlist(current_state)
