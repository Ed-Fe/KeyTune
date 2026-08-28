import os

import wx

from ...i18n import _
from ...library import (
    FOLDER_SORT_CREATED,
    FOLDER_SORT_MODIFIED,
    FOLDER_SORT_NAME,
    FOLDER_SORT_SIZE,
    FOLDER_SORT_TYPE,
    is_remote_media_path,
    sort_folder_entries,
)


class BrowserCommandsMixin:
    _FOLDER_SORT_LABELS = {
        FOLDER_SORT_NAME: _("Nome"),
        FOLDER_SORT_MODIFIED: _("Data de modificação"),
        FOLDER_SORT_CREATED: _("Data de criação"),
        FOLDER_SORT_TYPE: _("Tipo"),
        FOLDER_SORT_SIZE: _("Tamanho"),
    }

    def on_toggle_playlist_browser(self, _event=None):
        self._toggle_navigation_mode()

    def on_playlist_browser_tab(self, *, backward=False):
        return self._focus_autodj_controls_from_list(backward=backward)

    def on_playlist_browser_activate_item(self, item_index):
        state = self._get_playlist_state()
        if not state:
            return

        if state.is_folder_tab:
            entries = self._get_folder_entries(state)
            if not 0 <= item_index < len(entries):
                return

            target_entry = entries[item_index]
            previous_path = state.folder_current_path
            state.folder_selected_path = target_entry.path
            if target_entry.is_directory:
                selected_path = previous_path if target_entry.is_parent else None
                self._enter_folder_directory(target_entry.path, selected_path=selected_path, announce=True)
            else:
                if self._block_sensitive_action_during_youtube_music("track-selection"):
                    return
                self._preview_folder_file(target_entry.path, announce=True)
            return

        if not 0 <= item_index < len(state.items):
            return

        if self._block_sensitive_action_during_youtube_music("track-selection"):
            return

        state.select_index(item_index)
        self._play_media(index=self._get_active_playlist_index(), allow_crossfade=False)

    def on_playlist_browser_remove_item(self, item_indexes):
        self._remove_items_from_current_playlist(item_indexes)

    def on_playlist_browser_show_context_menu(self, browser_panel, anchor_window=None):
        if browser_panel is None:
            return False

        selected_paths = list(browser_panel.get_selected_item_paths())
        selected_count = len(selected_paths)
        menu = wx.Menu()

        current_state = self._get_playlist_state()
        is_folder_tab = bool(current_state and current_state.is_folder_tab)
        copy_item = menu.Append(wx.ID_ANY, _("Copiar seleção"))
        copy_path_item = menu.Append(wx.ID_ANY, _("Copiar caminho da seleção")) if is_folder_tab else None
        paste_item = menu.Append(wx.ID_ANY, _("Colar na playlist atual"))
        paste_new_item = menu.Append(wx.ID_ANY, _("Colar em nova playlist"))
        menu.AppendSeparator()
        enqueue_item = menu.Append(wx.ID_ANY, _("Adicionar à &Fila\tCtrl+Shift+F"))
        start_autodj_item = menu.Append(wx.ID_ANY, _("Reproduzir playlist com AutoDJ"))
        menu.AppendSeparator()
        remove_item = menu.Append(wx.ID_ANY, _("Remover seleção"))
        menu.AppendSeparator()
        favorite_item = menu.Append(wx.ID_ANY, _("Favoritar ou desfavoritar (Ctrl+D)"))
        rating_menu = wx.Menu()
        rating_items = [
            (rating, rating_menu.Append(wx.ID_ANY, label))
            for rating, label in (
                (0, _("Sem avaliação")),
                (1, _("1 estrela")),
                (2, _("2 estrelas")),
                (3, _("3 estrelas")),
                (4, _("4 estrelas")),
                (5, _("5 estrelas")),
            )
        ]
        menu.AppendSubMenu(rating_menu, _("Avaliação"))
        menu.AppendSeparator()
        like_item = menu.Append(wx.ID_ANY, _("Curtir no YouTube Music"))
        dislike_item = menu.Append(wx.ID_ANY, _("Não gostei no YouTube Music"))
        add_to_playlist_item = menu.Append(wx.ID_ANY, _("Adicionar à playlist do YouTube Music..."))
        remove_from_youtube_playlist_item = menu.Append(wx.ID_ANY, _("Remover da playlist do YouTube Music"))

        can_edit_playlist = bool(current_state and not current_state.is_folder_tab and not current_state.is_loading)
        has_youtube_items = any(is_remote_media_path(path) and "youtube" in path.lower() for path in selected_paths)
        like_rateable_paths = self._selected_youtube_music_media_paths_to_rate(selected_paths, "LIKE")
        dislike_rateable_paths = self._selected_youtube_music_media_paths_to_rate(selected_paths, "DISLIKE")
        youtube_music_video_ids = self._youtube_music_video_ids_from_paths(selected_paths)
        on_editable_youtube_playlist = bool(self._current_tab_youtube_music_playlist_id())

        copy_item.Enable(selected_count > 0)
        if copy_path_item is not None:
            copy_path_item.Enable(selected_count > 0)
        enqueue_item.Enable(selected_count > 0)
        start_autodj_item.Enable(bool(current_state and len(current_state.items) > 1 and not current_state.autodj_session))
        remove_item.Enable(selected_count > 0 and can_edit_playlist)
        like_item.Enable(has_youtube_items and bool(like_rateable_paths))
        dislike_item.Enable(has_youtube_items and bool(dislike_rateable_paths))
        add_to_playlist_item.Enable(bool(youtube_music_video_ids))
        remove_from_youtube_playlist_item.Enable(
            bool(youtube_music_video_ids) and on_editable_youtube_playlist
        )

        if current_state and current_state.autodj_session:
            menu.AppendSeparator()
            autodj_menu = wx.Menu()
            replace_next_item = autodj_menu.Append(wx.ID_ANY, _("Trocar próxima faixa"))
            recalculate_item = autodj_menu.Append(wx.ID_ANY, _("Recalcular sequência"))
            add_media_item = autodj_menu.Append(wx.ID_ANY, _("Adicionar músicas à sessão"))
            toggle_preparation_label = (
                _("Retomar preparação")
                if current_state.autodj_preparation_paused
                else _("Pausar preparação")
            )
            toggle_preparation_item = autodj_menu.Append(wx.ID_ANY, toggle_preparation_label)
            stop_autodj_item = autodj_menu.Append(wx.ID_ANY, _("Encerrar AutoDJ e manter sequência"))
            menu.AppendSubMenu(autodj_menu, _("Ações do AutoDJ"))
            next_path = current_state.peek_in_playback_order(1, wrap=False)
            replace_next_item.Enable(
                bool(next_path and any(path != next_path for path in current_state.autodj_remaining_items))
            )
            recalculate_item.Enable(
                bool(
                    current_state.autodj_remaining_items
                    or current_state.current_index + 1 < len(current_state.items)
                )
            )
            menu.Bind(wx.EVT_MENU, self.on_replace_autodj_next, id=replace_next_item.GetId())
            menu.Bind(wx.EVT_MENU, self.on_recalculate_autodj_session, id=recalculate_item.GetId())
            menu.Bind(wx.EVT_MENU, self.on_add_media_to_autodj_session, id=add_media_item.GetId())
            menu.Bind(wx.EVT_MENU, self.on_toggle_autodj_preparation, id=toggle_preparation_item.GetId())
            menu.Bind(wx.EVT_MENU, self.on_stop_autodj_session, id=stop_autodj_item.GetId())

        menu.Bind(wx.EVT_MENU, lambda _event: self.on_copy_current_item(None), id=copy_item.GetId())
        if copy_path_item is not None:
            menu.Bind(
                wx.EVT_MENU,
                lambda _event: self.on_copy_current_item_path(None),
                id=copy_path_item.GetId(),
            )
        menu.Bind(wx.EVT_MENU, lambda _event: self.on_paste_open_from_clipboard(None), id=paste_item.GetId())
        menu.Bind(
            wx.EVT_MENU,
            lambda _event: self.on_paste_open_from_clipboard_new_playlist(None),
            id=paste_new_item.GetId(),
        )
        menu.Bind(
            wx.EVT_MENU,
            lambda _event: self._enqueue_selected_item(),
            id=enqueue_item.GetId(),
        )
        menu.Bind(wx.EVT_MENU, self.on_start_autodj_session, id=start_autodj_item.GetId())
        menu.Bind(
            wx.EVT_MENU,
            lambda _event: self._remove_items_from_current_playlist(browser_panel.get_selected_indexes()),
            id=remove_item.GetId(),
        )
        smart_library_ready = bool(selected_count) and getattr(self, "_smart_library", lambda: None)() is not None
        favorite_item.Enable(smart_library_ready)
        for _rating, rating_item in rating_items:
            rating_item.Enable(smart_library_ready)

        menu.Bind(
            wx.EVT_MENU,
            lambda _event: self._toggle_favorite_for_selection(),
            id=favorite_item.GetId(),
        )
        for rating, rating_item in rating_items:
            menu.Bind(
                wx.EVT_MENU,
                lambda _event, value=rating: self._rate_selection(value),
                id=rating_item.GetId(),
            )

        rate_selected = getattr(self, "_rate_selected_playlist_items", None)
        if callable(rate_selected):
            menu.Bind(
                wx.EVT_MENU,
                lambda _event, media_paths=tuple(selected_paths): rate_selected(media_paths, "LIKE"),
                id=like_item.GetId(),
            )
            menu.Bind(
                wx.EVT_MENU,
                lambda _event, media_paths=tuple(selected_paths): rate_selected(media_paths, "DISLIKE"),
                id=dislike_item.GetId(),
            )

        menu.Bind(
            wx.EVT_MENU,
            lambda _event, media_paths=tuple(selected_paths): self._add_selected_media_to_youtube_playlist(media_paths),
            id=add_to_playlist_item.GetId(),
        )
        menu.Bind(
            wx.EVT_MENU,
            lambda _event, media_paths=tuple(selected_paths), item_indexes=tuple(
                browser_panel.get_selected_indexes()
            ): self._remove_selected_media_from_youtube_playlist(media_paths, item_indexes),
            id=remove_from_youtube_playlist_item.GetId(),
        )

        popup_parent = anchor_window or browser_panel
        try:
            popup_parent.PopupMenu(menu)
        finally:
            menu.Destroy()
        return True

    def on_show_folder_sort_menu(self, browser_panel=None, anchor_window=None):
        state = self._get_playlist_state()
        if not state or not state.is_folder_tab or state.is_loading:
            return False

        browser_panel = browser_panel or self._get_browser_panel()
        if browser_panel is None:
            return False

        selected_paths = tuple(browser_panel.get_selected_item_paths())
        menu = wx.Menu()
        criterion_menu = wx.Menu()
        direction_menu = wx.Menu()

        for sort_by, label in self._FOLDER_SORT_LABELS.items():
            item = criterion_menu.AppendRadioItem(wx.ID_ANY, label)
            item.Check(sort_by == state.folder_sort_by)
            criterion_menu.Bind(
                wx.EVT_MENU,
                lambda _event, value=sort_by: self._apply_folder_sort(
                    value,
                    state.folder_sort_descending,
                    browser_panel,
                    selected_paths,
                ),
                id=item.GetId(),
            )

        for descending, label in ((False, _("Crescente")), (True, _("Decrescente"))):
            item = direction_menu.AppendRadioItem(wx.ID_ANY, label)
            item.Check(descending == state.folder_sort_descending)
            direction_menu.Bind(
                wx.EVT_MENU,
                lambda _event, value=descending: self._apply_folder_sort(
                    state.folder_sort_by,
                    value,
                    browser_panel,
                    selected_paths,
                ),
                id=item.GetId(),
            )

        menu.AppendSubMenu(criterion_menu, _("Classificar por"))
        menu.AppendSubMenu(direction_menu, _("Ordem"))
        popup_parent = anchor_window or browser_panel.items_list
        try:
            popup_parent.PopupMenu(menu)
        finally:
            menu.Destroy()
        return True

    def _apply_folder_sort(self, sort_by, descending, browser_panel, selected_paths=()):
        state = self._get_playlist_state()
        if not state or not state.is_folder_tab:
            return False

        state.folder_sort_by = sort_by
        state.folder_sort_descending = bool(descending)
        sorted_entries = sort_folder_entries(
            state.folder_entries,
            sort_by=state.folder_sort_by,
            descending=state.folder_sort_descending,
        )
        entry_index_map = {
            os.path.normcase(os.path.normpath(entry.path)): index
            for index, entry in enumerate(sorted_entries)
            if getattr(entry, "path", None)
        }
        state.set_folder_entries(sorted_entries, entry_index_map=entry_index_map)

        media_files = [entry.path for entry in sorted_entries if getattr(entry, "is_file", False)]
        state.reorder_items(
            media_files,
            [os.path.basename(path) or path for path in media_files],
        )
        self._refresh_playlist_browser()
        browser_panel.restore_selected_item_paths(selected_paths)

        criterion_label = self._FOLDER_SORT_LABELS.get(sort_by, self._FOLDER_SORT_LABELS[FOLDER_SORT_NAME])
        direction_label = _("decrescente") if descending else _("crescente")
        self._announce(
            _("Pasta classificada por {criterion}, em ordem {direction}.").format(
                criterion=criterion_label,
                direction=direction_label,
            )
        )
        return True

    def on_playlist_browser_preview_item(self, item_index):
        state = self._get_playlist_state()
        if not state or not state.is_folder_tab:
            return

        entries = self._get_folder_entries(state)
        if not 0 <= item_index < len(entries):
            return

        target_entry = entries[item_index]
        state.folder_selected_path = target_entry.path
        if target_entry.is_file:
            self._preview_folder_file(target_entry.path, announce=False)
            return

        self._refresh_playlist_browser()

    def on_playlist_browser_go_back(self):
        self._go_back_folder()
