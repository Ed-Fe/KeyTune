import wx

from ...i18n import _
from ...library import is_remote_media_path


class BrowserCommandsMixin:
    def on_toggle_playlist_browser(self, _event=None):
        self._toggle_navigation_mode()

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

        copy_item = menu.Append(wx.ID_ANY, _("Copiar seleção"))
        paste_item = menu.Append(wx.ID_ANY, _("Colar na playlist atual"))
        paste_new_item = menu.Append(wx.ID_ANY, _("Colar em nova playlist"))
        menu.AppendSeparator()
        enqueue_item = menu.Append(wx.ID_ANY, _("Adicionar à &Fila\tCtrl+Shift+F"))
        menu.AppendSeparator()
        remove_item = menu.Append(wx.ID_ANY, _("Remover seleção"))
        menu.AppendSeparator()
        like_item = menu.Append(wx.ID_ANY, _("Curtir no YouTube Music"))
        dislike_item = menu.Append(wx.ID_ANY, _("Não gostei no YouTube Music"))
        add_to_playlist_item = menu.Append(wx.ID_ANY, _("Adicionar à playlist do YouTube Music..."))
        remove_from_youtube_playlist_item = menu.Append(wx.ID_ANY, _("Remover da playlist do YouTube Music"))

        current_state = self._get_playlist_state()
        can_edit_playlist = bool(current_state and not current_state.is_folder_tab and not current_state.is_loading)
        has_youtube_items = any(is_remote_media_path(path) and "youtube" in path.lower() for path in selected_paths)
        like_rateable_paths = self._selected_youtube_music_media_paths_to_rate(selected_paths, "LIKE")
        dislike_rateable_paths = self._selected_youtube_music_media_paths_to_rate(selected_paths, "DISLIKE")
        youtube_music_video_ids = self._youtube_music_video_ids_from_paths(selected_paths)
        on_editable_youtube_playlist = bool(self._current_tab_youtube_music_playlist_id())

        copy_item.Enable(selected_count > 0)
        enqueue_item.Enable(selected_count > 0)
        remove_item.Enable(selected_count > 0 and can_edit_playlist)
        like_item.Enable(has_youtube_items and bool(like_rateable_paths))
        dislike_item.Enable(has_youtube_items and bool(dislike_rateable_paths))
        add_to_playlist_item.Enable(bool(youtube_music_video_ids))
        remove_from_youtube_playlist_item.Enable(
            bool(youtube_music_video_ids) and on_editable_youtube_playlist
        )

        menu.Bind(wx.EVT_MENU, lambda _event: self.on_copy_current_item_path(None), id=copy_item.GetId())
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
        menu.Bind(
            wx.EVT_MENU,
            lambda _event: self._remove_items_from_current_playlist(browser_panel.get_selected_indexes()),
            id=remove_item.GetId(),
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