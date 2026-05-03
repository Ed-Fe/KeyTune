import os

import wx

from ..constants import APP_TITLE, PLAYBACK_RESTART_THRESHOLD_MS, REPEAT_ALL, REPEAT_MODE_LABELS, REPEAT_MODES, REPEAT_OFF, REPEAT_ONE
from ..library import folder_display_name
from ..playlists import PlaylistState, ScreenTabState, build_playlist_title, default_playlist_title


class FrameLibraryTabsMixin:
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

    def _repeat_mode_message(self, repeat_mode):
        return REPEAT_MODE_LABELS.get(repeat_mode, REPEAT_MODE_LABELS[REPEAT_OFF])

    def _describe_playlist_position(self, state):
        if not state.current_media_path:
            if state.is_folder_tab and state.folder_current_path:
                return f"Pasta atual: {folder_display_name(state.folder_current_path)}."
            return "Nenhuma mídia tocando agora."

        media_name = self._media_label(state.current_media_path)
        if state.is_folder_tab:
            return f"Pasta atual: {folder_display_name(state.folder_current_path)}."

        if state.item_count <= 1 or not 0 <= state.current_index < state.item_count:
            return f"Item atual: {media_name}."

        return f"Item atual: {media_name}. Item {state.current_index + 1} de {state.item_count}."

    def _play_media(self, media_path=None, index=None, announce_message=None, allow_crossfade=False):
        state = self._get_playlist_state(index)
        if not state:
            return

        if media_path is not None and state.current_media_path != media_path:
            media_index = state.index_of_item(media_path)
            if media_index is not None:
                state.select_index(media_index)
            else:
                state.current_media_path = media_path

        if not state.current_media_path:
            return

        crossfade_state = getattr(self, "_crossfade_state", None)
        self._cancel_crossfade_transition(
            stop_incoming=True,
            stop_outgoing=bool(crossfade_state and crossfade_state.get("phase") == "running"),
            invalidate_requests=bool(crossfade_state),
        )

        state.was_playing = True
        state.last_position_ms = 0
        target_index = self._get_active_playlist_index() if index is None else index
        if allow_crossfade and self._can_crossfade_to_media(state.current_media_path):
            if self._start_crossfade(
                state.current_media_path,
                tab_index=target_index,
                announce_message=announce_message,
            ):
                return

        self._update_title()
        self._update_time_bar()
        self._refresh_playlist_browser()

        self._queue_media_start(
            state.current_media_path,
            tab_index=target_index,
            announce_message=announce_message,
        )

    def _maybe_start_automatic_crossfade(self):
        if getattr(self, "_crossfade_state", None) is not None:
            return False

        configured_crossfade_ms = self._crossfade_duration_ms()
        if configured_crossfade_ms <= 0:
            return False

        state = self._get_playlist_state()
        if not state or state.is_folder_tab or not state.current_media_path or state.repeat_mode == REPEAT_ONE:
            return False

        if self.player.get_media() is None or not self.player.is_playing():
            return False

        current_time = self.player.get_time()
        total_time = self.player.get_length()
        if current_time is None or current_time < 0 or total_time is None or total_time <= 0:
            return False

        startup_headroom_ms = self._crossfade_startup_headroom_ms()
        crossfade_window_ms = configured_crossfade_ms + startup_headroom_ms
        remaining_time = total_time - max(0, current_time)
        if remaining_time > crossfade_window_ms or remaining_time <= 0:
            return False

        should_wrap = state.repeat_mode == REPEAT_ALL
        next_media_path = state.peek_in_playback_order(1, wrap=should_wrap)
        if not next_media_path or not self._can_crossfade_to_media(next_media_path):
            return False

        wrapped_cycle = False
        if should_wrap:
            state.sync_playback_order()
            if state.shuffle_enabled:
                wrapped_cycle = state.playback_order_position == len(state.playback_order) - 1
            else:
                wrapped_cycle = state.current_index == state.item_count - 1

        target = state.move_in_playback_order(1, wrap=should_wrap)
        if not target:
            return False

        loop_prefix = "Nova volta da playlist. " if wrapped_cycle else ""
        self._play_media(
            index=self._get_active_playlist_index(),
            announce_message=f"{loop_prefix}{self._describe_playlist_position(state)}",
            allow_crossfade=True,
        )
        return True

    def _update_title(self):
        current_tab = self._get_tab_state()
        if isinstance(current_tab, ScreenTabState):
            title_parts = [APP_TITLE, current_tab.title]
            active_state = self._get_active_playlist_state()
            if active_state and active_state.current_media_path:
                title_parts.append(self._media_label(active_state.current_media_path))
            self.SetTitle(" — ".join(title_parts))
            return

        state = self._get_playlist_state()
        if not state:
            self.SetTitle(APP_TITLE)
            return

        if state.is_loading:
            self.SetTitle(f"{APP_TITLE} — {state.title}")
            return

        if not state.current_media_path:
            if state.is_folder_tab and state.folder_current_path:
                self.SetTitle(f"{APP_TITLE} — {state.title}")
                return

            self.SetTitle(APP_TITLE)
            return

        media_name = self._media_label(state.current_media_path)
        self.SetTitle(f"{APP_TITLE} — {state.title} — {media_name}")
        refresh_smtc = getattr(self, "_refresh_smtc_state", None)
        if callable(refresh_smtc):
            refresh_smtc()

    def _play_adjacent_item(self, direction):
        if self._block_sensitive_action_during_youtube_music("track-navigation"):
            return

        state = self._get_playlist_state()
        if not state or not state.items:
            self._announce("Nenhuma playlist carregada.")
            return

        if direction < 0 and self.player.get_media() is not None:
            current_time = self.player.get_time()
            if current_time is not None and current_time > PLAYBACK_RESTART_THRESHOLD_MS:
                self.player.set_time(0)
                self._update_time_bar()
                self._announce("Início do item atual.")
                return

        should_wrap = state.repeat_mode == REPEAT_ALL
        target = state.move_in_playback_order(-1 if direction < 0 else 1, wrap=should_wrap)
        if not target:
            boundary_message = "Você já está no primeiro item." if direction < 0 else "Você já está no último item."
            self._announce(boundary_message)
            return

        allow_manual_crossfade = bool(getattr(self.settings, "crossfade_on_manual_track_change", False))
        self._play_media(
            index=self._get_active_playlist_index(),
            allow_crossfade=allow_manual_crossfade,
        )

    def _jump_to_playlist_boundary(self, to_last=False):
        if self._block_sensitive_action_during_youtube_music("track-selection"):
            return

        state = self._get_playlist_state()
        if not state or not state.items:
            self._announce("Nenhuma playlist carregada.")
            return

        target_index = len(state.items) - 1 if to_last else 0
        if state.current_index == target_index:
            boundary_message = "Você já está no último item." if to_last else "Você já está no primeiro item."
            self._announce(boundary_message)
            return

        state.select_index(target_index)
        self._play_media(index=self._get_active_playlist_index())

    def _move_current_item(self, direction):
        if self._block_sensitive_action_during_youtube_music("playback-order"):
            return

        state = self._get_playlist_state()
        if not state or not state.items:
            self._announce("Nenhuma playlist carregada.")
            return

        if state.is_folder_tab:
            self._announce("Não é possível reordenar arquivos no navegador de pastas.")
            return

        if len(state.items) < 2:
            self._announce("A playlist precisa de pelo menos dois itens para reordenar.")
            return

        current_index = state.current_index
        if current_index < 0 or current_index >= len(state.items):
            media_index = state.index_of_item(state.current_media_path)
            if media_index is not None:
                current_index = media_index
                state.current_index = current_index
            else:
                self._announce("Nenhum item atual para reordenar.")
                return

        target_index = current_index + direction
        if not 0 <= target_index < len(state.items):
            boundary_message = "O item já está no topo da playlist." if direction < 0 else "O item já está no final da playlist."
            self._announce(boundary_message)
            return

        moved_item = state.items.pop(current_index)
        state.items.insert(target_index, moved_item)
        state.refresh_browser_item_labels()
        state.current_index = target_index
        state.current_media_path = moved_item
        state.reset_playback_order(preferred_index=target_index)
        self._refresh_playlist_browser()
        self._announce(
            f"Item movido para a posição {target_index + 1} de {state.item_count}: {self._media_label(moved_item)}."
        )

    def _toggle_shuffle(self):
        if self._block_sensitive_action_during_youtube_music("playback-order"):
            return

        state = self._get_playlist_state()
        if not state:
            self._announce("Nenhuma playlist ativa.")
            return

        state.shuffle_enabled = not state.shuffle_enabled
        preferred_index = state.current_index if state.current_index >= 0 else 0
        state.reset_playback_order(preferred_index=preferred_index)
        status = "ativado" if state.shuffle_enabled else "desativado"
        self._announce(f"Modo aleatório {status}.")
        if hasattr(self, "_set_status_message"):
            self._set_status_message(f"Aleatório: {status}.")
        self._refresh_playlist_browser()

    def _cycle_repeat_mode(self):
        if self._block_sensitive_action_during_youtube_music("playback-order"):
            return

        state = self._get_playlist_state()
        if not state:
            self._announce("Nenhuma playlist ativa.")
            return

        current_mode_index = REPEAT_MODES.index(state.repeat_mode)
        state.repeat_mode = REPEAT_MODES[(current_mode_index + 1) % len(REPEAT_MODES)]
        self._announce(self._repeat_mode_message(state.repeat_mode) + ".")
        if hasattr(self, "_set_status_message"):
            mode_label = REPEAT_MODE_LABELS.get(state.repeat_mode, state.repeat_mode)
            self._set_status_message(f"Repetir: {mode_label}.")
        self._refresh_playlist_browser()

    def _remove_item_from_current_playlist(self, item_index, announce_prefix="Item removido"):
        if self._block_sensitive_action_during_youtube_music("close-media"):
            return

        state = self._get_playlist_state()
        if state and state.is_folder_tab:
            self._announce("Use Ctrl+W para fechar a prévia atual ou Backspace para voltar de pasta.")
            return

        if not state or not 0 <= item_index < len(state.items):
            self._announce("Nenhum item válido selecionado.")
            return

        removed_path = state.items[item_index]
        removed_name = self._media_label(removed_path)
        removed_current_item = item_index == state.current_index

        if removed_current_item:
            self._cancel_crossfade_transition(stop_incoming=True, stop_outgoing=True, invalidate_requests=True)
            self._stop_all_players(unload=False)

        state.items.pop(item_index)
        state.refresh_browser_item_labels()

        if not state.items:
            state.clear()
            self._unload_player()
            self._update_title()
            self._refresh_playlist_browser()
            self._announce(f"{announce_prefix}: {removed_name}. Playlist vazia.")
            return

        if removed_current_item:
            next_index = min(item_index, len(state.items) - 1)
            state.select_index(next_index)
            self._play_media(
                index=self._get_active_playlist_index(),
                announce_message=f"{announce_prefix}: {removed_name}. {self._describe_playlist_position(state)}",
            )
            return

        if item_index < state.current_index:
            state.current_index -= 1

        state.current_media_path = state.items[state.current_index]
        state.reset_playback_order(preferred_index=state.current_index)
        self._refresh_playlist_browser()
        self._announce(f"{announce_prefix}: {removed_name}. {state.item_count} itens na playlist.")

    def _close_current_media(self):
        if self._block_sensitive_action_during_youtube_music("close-media"):
            return

        current_tab = self._get_tab_state()
        if isinstance(current_tab, ScreenTabState):
            self._close_current_tab()
            return

        state = self._get_playlist_state()
        if state and state.is_folder_tab and state.current_media_path:
            state.current_index = -1
            state.current_media_path = None
            state.last_position_ms = 0
            state.was_playing = False
            self._unload_player()
            self._update_title()
            self._refresh_playlist_browser()
            self._announce("Prévia fechada.")
            return

        if not state or not state.current_media_path:
            self._close_current_tab()
            return

        self._remove_item_from_current_playlist(state.current_index, announce_prefix="Mídia fechada")

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

    def _handle_media_end(self):
        state = self._get_playlist_state()
        if not state:
            self._announce("Mídia finalizada.")
            return

        state.was_playing = False
        state.last_position_ms = 0

        if state.is_folder_tab:
            self._update_time_bar()
            self._refresh_playlist_browser()
            return

        if state.repeat_mode == REPEAT_ONE and state.current_media_path:
            self._play_media(
                index=self._get_active_playlist_index(),
                announce_message=f"Repetindo faixa atual. {self._describe_playlist_position(state)}",
            )
            return

        should_wrap = state.repeat_mode == REPEAT_ALL
        wrapped_cycle = False
        if should_wrap:
            state.sync_playback_order()
            if state.shuffle_enabled:
                wrapped_cycle = state.playback_order_position == len(state.playback_order) - 1
            else:
                wrapped_cycle = state.current_index == state.item_count - 1

        target = state.move_in_playback_order(1, wrap=should_wrap)
        if target:
            loop_prefix = "Nova volta da playlist. " if wrapped_cycle else ""
            self._play_media(
                index=self._get_active_playlist_index(),
                announce_message=f"{loop_prefix}{self._describe_playlist_position(state)}",
            )
            return

        self._announce(f"Playlist {state.title} finalizada.")

    def _cycle_tabs(self, step):
        total_tabs = self.notebook.GetPageCount()
        if total_tabs <= 1:
            return

        current_index = self.notebook.GetSelection()
        next_index = (current_index + step) % total_tabs
        if next_index == current_index:
            return

        self._select_tab(next_index, announce=True)
