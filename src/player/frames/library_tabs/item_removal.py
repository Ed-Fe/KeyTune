from ...playlists import ScreenTabState


class PlaylistItemRemovalMixin:
    def _remove_item_from_current_playlist(self, item_index, announce_prefix="Item removido"):
        if self._block_sensitive_action_during_youtube_music("close-media"):
            return

        state = self._get_playlist_state()
        if state and state.is_folder_tab:
            self._announce("Use Ctrl+Shift+W para fechar a prévia atual ou Backspace para voltar de pasta.")
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

    def _remove_items_from_current_playlist(self, item_indexes, announce_prefix="Itens removidos"):
        normalized_indexes = sorted(
            {
                int(item_index)
                for item_index in (item_indexes or [])
                if isinstance(item_index, int) or str(item_index).isdigit()
            },
            reverse=True,
        )
        if not normalized_indexes:
            self._announce("Nenhum item válido selecionado.")
            return

        if len(normalized_indexes) == 1:
            self._remove_item_from_current_playlist(normalized_indexes[0], announce_prefix="Item removido")
            return

        state = self._get_playlist_state()
        if state and state.is_folder_tab:
            self._announce("Use Ctrl+Shift+W para fechar a prévia atual ou Backspace para voltar de pasta.")
            return
        if not state:
            self._announce("Nenhuma playlist ativa.")
            return

        valid_indexes = [index for index in normalized_indexes if 0 <= index < len(state.items)]
        if not valid_indexes:
            self._announce("Nenhum item válido selecionado.")
            return

        removed_current_item = state.current_index in valid_indexes
        removed_count = len(valid_indexes)
        if removed_current_item:
            self._cancel_crossfade_transition(stop_incoming=True, stop_outgoing=True, invalidate_requests=True)
            self._stop_all_players(unload=False)

        removed_names = [self._media_label(state.items[index]) for index in reversed(valid_indexes)]
        for index in valid_indexes:
            state.items.pop(index)
        state.refresh_browser_item_labels()

        if not state.items:
            state.clear()
            self._unload_player()
            self._update_title()
            self._refresh_playlist_browser()
            self._announce(f"{announce_prefix}: {removed_count} itens. Playlist vazia.")
            return

        if removed_current_item:
            next_index = min(valid_indexes[-1], len(state.items) - 1)
            state.select_index(next_index)
            self._play_media(
                index=self._get_active_playlist_index(),
                announce_message=f"{announce_prefix}: {removed_count} itens removidos. {self._describe_playlist_position(state)}",
            )
            return

        shift_count = sum(1 for index in valid_indexes if index < state.current_index)
        if shift_count:
            state.current_index = max(0, state.current_index - shift_count)
        state.current_media_path = state.items[state.current_index]
        state.reset_playback_order(preferred_index=state.current_index)
        self._refresh_playlist_browser()
        self._announce(
            f"{announce_prefix}: {removed_count} itens removidos. {state.item_count} itens na playlist."
        )

    def _close_current_media(self):
        if self._block_sensitive_action_during_youtube_music("close-media"):
            return

        current_tab = self._get_tab_state()
        if isinstance(current_tab, ScreenTabState):
            self._announce("Nenhuma mídia carregada.")
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
            self._announce("Nenhuma mídia carregada.")
            return

        self._remove_item_from_current_playlist(state.current_index, announce_prefix="Mídia fechada")
