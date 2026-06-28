import os

import wx

from ...library import folder_display_name
from ...playlists import PlaylistState, ScreenTabState, default_playlist_title


class TabManagementMixin:
    def _resolve_target_playlist_tab(self, current_index=None):
        if current_index is None:
            current_index = self.notebook.GetSelection()

        current_tab = self._get_tab_state(current_index)
        state = current_tab if isinstance(current_tab, PlaylistState) else self._get_active_playlist_state()

        if isinstance(current_tab, PlaylistState) and current_tab.is_empty:
            return current_tab, current_index

        if state and state.is_empty:
            return state, self._get_active_playlist_index()

        target_index = self._create_empty_playlist_tab(select=False)
        return self._get_playlist_state(target_index), target_index

    def _resolve_playlist_state_index(self, state):
        for index, candidate in enumerate(self.playlists):
            if candidate is state:
                return index
        return wx.NOT_FOUND

    def _is_current_playlist_state(self, state):
        current_index = self._get_current_tab_index()
        return self._get_tab_state(current_index) is state

    def _prepare_library_target_tab(self):
        return self._resolve_target_playlist_tab()

    def _insert_tab(self, state, page, select=False, index=None):
        if index is None:
            index = len(self.playlists)

        index = max(0, min(index, len(self.playlists)))
        self.playlists.insert(index, state)

        if index >= self.notebook.GetPageCount():
            self.notebook.AddPage(page, state.title, select=select)
        else:
            self.notebook.InsertPage(index, page, state.title, select=select)

        if isinstance(state, PlaylistState) and self.active_playlist_index is None:
            self.active_playlist_index = index

        return index

    def _get_tab_state(self, index=None):
        if not self.playlists:
            return None

        if index is None:
            index = self.notebook.GetSelection()

        if index == wx.NOT_FOUND or not 0 <= index < len(self.playlists):
            return None

        return self.playlists[index]

    def _get_active_playlist_index(self):
        if (
            self.active_playlist_index is not None
            and 0 <= self.active_playlist_index < len(self.playlists)
            and isinstance(self.playlists[self.active_playlist_index], PlaylistState)
        ):
            return self.active_playlist_index

        for index, state in enumerate(self.playlists):
            if isinstance(state, PlaylistState):
                self.active_playlist_index = index
                return index

        self.active_playlist_index = None
        return wx.NOT_FOUND

    def _get_active_playlist_state(self):
        active_index = self._get_active_playlist_index()
        if active_index == wx.NOT_FOUND:
            return None

        return self.playlists[active_index]

    def _open_screen_tab(
        self,
        screen_id,
        title,
        page_factory,
        *,
        select=True,
        activation_message=None,
        on_activate=None,
        on_close=None,
    ):
        for index, state in enumerate(self.playlists):
            if isinstance(state, ScreenTabState) and state.screen_id == screen_id:
                self._remember_screen_tab_return_context(state)
                state.title = title
                state.activation_message = activation_message
                state.on_activate = on_activate
                state.on_close = on_close
                self.notebook.SetPageText(index, title)
                if select:
                    self._select_tab(index, announce=True)
                return index

        page = page_factory(self.notebook)
        state = ScreenTabState(
            title=title,
            screen_id=screen_id,
            activation_message=activation_message,
            on_activate=on_activate,
            on_close=on_close,
        )
        self._remember_screen_tab_return_context(state)
        tab_index = self._insert_tab(state, page, select=select)
        if select:
            self._activate_tab(tab_index, announce=False)
        return tab_index

    def _create_empty_playlist_tab(self, select=False):
        tab_number = len(self.playlists) + 1
        title = default_playlist_title(tab_number)
        page = self._create_playlist_page()
        state = PlaylistState(
            title=title,
            shuffle_enabled=self.settings.shuffle_new_playlists,
            repeat_mode=self.settings.repeat_mode_new_playlists,
        )
        return self._insert_tab(state, page, select=select)

    def _playlist_focus_mode(self, index=None):
        browser = self._get_browser_panel(index)
        if browser and browser.is_item_navigation_active():
            return "items"

        return "player"

    def _screen_tab_return_context(self):
        current_index = self.notebook.GetSelection() if hasattr(self, "notebook") else wx.NOT_FOUND
        current_state = self._get_tab_state(current_index)
        if isinstance(current_state, PlaylistState):
            return current_index, self._playlist_focus_mode(current_index)

        active_index = self._get_active_playlist_index()
        if active_index == wx.NOT_FOUND:
            return None, None

        return active_index, None

    def _remember_screen_tab_return_context(self, screen_state):
        if not isinstance(screen_state, ScreenTabState):
            return

        return_index, return_focus_mode = self._screen_tab_return_context()
        if isinstance(return_index, int) and return_index >= 0:
            screen_state.return_to_tab_index = return_index
        if return_focus_mode is not None:
            screen_state.return_focus_mode = return_focus_mode

    def _resolve_screen_tab_close_target(self, current_index, total_tabs, screen_state):
        fallback_index = current_index if current_index < total_tabs - 1 else current_index - 1
        preferred_index = getattr(screen_state, "return_to_tab_index", None)
        if not isinstance(preferred_index, int):
            return fallback_index

        adjusted_index = preferred_index - 1 if preferred_index > current_index else preferred_index
        if 0 <= adjusted_index < total_tabs - 1:
            return adjusted_index

        return fallback_index

    def _restore_screen_tab_focus(self, screen_state, next_state):
        if not isinstance(screen_state, ScreenTabState) or not isinstance(next_state, PlaylistState):
            return

        if screen_state.return_focus_mode == "items":
            self._focus_item_navigation(announce=False)
            return

        if screen_state.return_focus_mode == "player":
            self._focus_player_controls(announce=False)

    def _reset_playlist_tabs(self):
        while self.notebook.GetPageCount():
            self.notebook.DeletePage(0)

        self.playlists = []
        self.active_playlist_index = None
        self._create_empty_playlist_tab(select=True)

    def _select_tab(self, index, announce=True):
        current_index = self.notebook.GetSelection()
        if index == current_index:
            if announce:
                self._activate_tab(index, announce=True)
            return

        if current_index != wx.NOT_FOUND and isinstance(self._get_tab_state(current_index), PlaylistState):
            self._capture_tab_state(current_index)

        self.notebook.ChangeSelection(index)
        self._activate_tab(index, announce=announce)

    def _get_playlist_state(self, index=None):
        if index is None:
            selected_state = self._get_tab_state()
            if isinstance(selected_state, PlaylistState):
                return selected_state

            return self._get_active_playlist_state()

        state = self._get_tab_state(index)
        return state if isinstance(state, PlaylistState) else None

    def _get_current_tab_index(self):
        index = self.notebook.GetSelection()
        return 0 if index == wx.NOT_FOUND else index

    def _get_video_panel(self, index=None):
        if index is None:
            selected_state = self._get_tab_state()
            if isinstance(selected_state, PlaylistState):
                index = self.notebook.GetSelection()
            else:
                index = self._get_active_playlist_index()

        if index == wx.NOT_FOUND or index is None:
            return None

        if not 0 <= index < self.notebook.GetPageCount():
            return None

        page = self.notebook.GetPage(index)
        if not page:
            return None

        return getattr(page, "video_surface", None) or getattr(page, "video_panel", None)

    def _get_browser_panel(self, index=None):
        if index is None:
            index = self.notebook.GetSelection()

        if index == wx.NOT_FOUND or index is None:
            return None

        if not 0 <= index < self.notebook.GetPageCount():
            return None

        page = self.notebook.GetPage(index)
        if not page:
            return None

        return getattr(page, "browser_panel", None)

    def _prepare_playlist_tab(self, items, title, source_path=None):
        state, target_index = self._resolve_target_playlist_tab()

        state.title = title
        state.set_items(items, start_index=0)
        state.source_path = source_path
        self.notebook.SetPageText(target_index, title)
        self._select_tab(target_index, announce=False)
        self._refresh_playlist_browser()
        return target_index

    def _open_prepared_media_playlist(
        self,
        items,
        title,
        *,
        browser_item_labels=None,
        source_path=None,
        announce_message=None,
    ):
        normalized_items = list(items or [])
        if not normalized_items:
            return wx.NOT_FOUND

        if browser_item_labels is None:
            normalized_browser_labels = [os.path.basename(path) or path for path in normalized_items]
        else:
            normalized_browser_labels = list(browser_item_labels)

        if len(normalized_browser_labels) != len(normalized_items):
            normalized_browser_labels = [os.path.basename(path) or path for path in normalized_items]

        state, target_index = self._resolve_target_playlist_tab()

        state.finish_library_load()
        state.clear_folder_location()
        state.title = title
        state.source_path = source_path
        state.set_items_prepared(
            normalized_items,
            {item: index for index, item in enumerate(normalized_items)},
            normalized_browser_labels,
            start_index=0,
        )

        self.notebook.SetPageText(target_index, title)
        self._select_tab(target_index, announce=False)
        self._refresh_playlist_browser()
        self._play_media(index=target_index, announce_message=announce_message)
        return target_index

    def _activate_tab(self, index, announce=True):
        tab_state = self._get_tab_state(index)
        if not tab_state:
            return

        if isinstance(tab_state, ScreenTabState):
            self._update_title()
            if callable(tab_state.on_activate):
                tab_state.on_activate()
            if announce:
                self._announce(tab_state.activation_message or f"Aba {index + 1}: {tab_state.title}.")
            return

        state = self._get_playlist_state(index)
        if not state:
            return

        # Switching tabs changes which video page is visible. Refresh its
        # overlay right away instead of waiting for the gated progress-timer
        # pass (see PlaybackControlsMixin._maybe_refresh_player_visual_hints).
        refresh_visual_hints = getattr(self, "_refresh_player_visual_hints", None)
        if callable(refresh_visual_hints):
            refresh_visual_hints()

        previous_active_playlist_index = self._get_active_playlist_index()
        self.active_playlist_index = index
        self._apply_equalizer_state(state)

        if state.is_loading:
            self._unload_player()
            self._update_title()
            self._refresh_playlist_browser()
            if announce:
                self._announce(state.loading_message or f"Carregando {state.title}.")
            return

        if not state.current_media_path:
            self._unload_player()
            self._update_title()
            self._refresh_playlist_browser()
            if announce:
                if state.is_folder_tab and state.folder_current_path:
                    self._announce(
                        f"Aba {index + 1}: {state.title}. Pasta atual: {folder_display_name(state.folder_current_path)}."
                    )
                else:
                    self._announce(f"{state.title}. Nenhuma mídia tocando agora.")
            return

        if previous_active_playlist_index == index and self._player_has_loaded_media(state.current_media_path):
            self._bind_player_to_window()
            self._update_title()
            self._update_time_bar()
            self._refresh_playlist_browser()
            if announce:
                self._announce(f"Aba {index + 1}: {state.title}. {self._describe_playlist_position(state)}")
            return

        pause_after_restore = not state.was_playing
        self._update_title()
        self._refresh_playlist_browser()
        announce_message = (
            f"Aba {index + 1}: {state.title}. {self._describe_playlist_position(state)}"
            if announce
            else None
        )
        self._queue_media_start(
            state.current_media_path,
            tab_index=index,
            announce_message=announce_message,
            restore_position_ms=state.last_position_ms,
            pause_after_start=pause_after_restore,
        )

    def _close_current_tab(self):
        current_index = self._get_current_tab_index()
        current_state = self._get_tab_state(current_index)
        total_tabs = self.notebook.GetPageCount()

        if total_tabs <= 1:
            # Última aba: não dá para deixar a janela sem nenhuma aba, então
            # paramos a reprodução e substituímos por uma playlist vazia nova.
            if isinstance(current_state, PlaylistState):
                active_index = self._get_active_playlist_index()
                if active_index == current_index:
                    self._unload_player()
                self._reset_playlist_tabs()
                self._refresh_playlist_browser()
                self._announce(f"Aba fechada: {current_state.title}. Nova playlist vazia criada.")
                return True

            self._announce("Não é possível fechar a última aba.")
            return False

        if isinstance(current_state, ScreenTabState):
            self._capture_active_playlist_state()

        next_index = (
            self._resolve_screen_tab_close_target(current_index, total_tabs, current_state)
            if isinstance(current_state, ScreenTabState)
            else (current_index if current_index < total_tabs - 1 else current_index - 1)
        )
        active_playlist_index = self._get_active_playlist_index()
        closing_active_playback = (
            isinstance(current_state, PlaylistState)
            and active_playlist_index != wx.NOT_FOUND
            and current_index == active_playlist_index
        )

        self._suppress_tab_change_event = True
        try:
            if isinstance(current_state, ScreenTabState) and callable(current_state.on_close):
                current_state.on_close()

            self.playlists.pop(current_index)
            self.notebook.DeletePage(current_index)

            if active_playlist_index != wx.NOT_FOUND:
                if current_index == active_playlist_index:
                    self.active_playlist_index = None
                elif current_index < active_playlist_index:
                    self.active_playlist_index = active_playlist_index - 1

            self.notebook.ChangeSelection(next_index)
        finally:
            self._suppress_tab_change_event = False

        if closing_active_playback:
            self._unload_player()

        self._activate_tab(next_index, announce=False)
        self._refresh_playlist_browser()

        next_state = self._get_tab_state(next_index)
        if isinstance(current_state, ScreenTabState):
            self._restore_screen_tab_focus(current_state, next_state)

        if next_state:
            self._announce(
                f"Aba fechada: {current_state.title if current_state else 'sem nome'}. "
                + (
                    f"Agora em {next_state.title}. {self._describe_playlist_position(next_state)}"
                    if isinstance(next_state, PlaylistState)
                    else f"Agora em {next_state.title}."
                )
            )
        else:
            self._announce("Aba fechada.")

        return True

    def _cycle_tabs(self, step):
        total_tabs = self.notebook.GetPageCount()
        if total_tabs <= 1:
            return

        current_index = self.notebook.GetSelection()
        next_index = (current_index + step) % total_tabs
        if next_index == current_index:
            return

        self._select_tab(next_index, announce=True)
