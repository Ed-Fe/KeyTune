from ...constants import (
    APP_TITLE,
    PLAYBACK_RESTART_THRESHOLD_MS,
    REPEAT_ALL,
    REPEAT_MODE_LABELS,
    REPEAT_MODES,
    REPEAT_OFF,
    REPEAT_ONE,
)
from ...library import folder_display_name
from ...log import get_logger
from ...playlists import ScreenTabState


_logger = get_logger(__name__)


class PlaylistPlaybackMixin:
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
        self._suppress_next_auto_advance = False
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
            if direction > 0 and self._try_autoplay_related_youtube_music(state):
                return
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

    def _toggle_related_autoplay(self):
        self.settings.youtube_music_autoplay_related = not self.settings.youtube_music_autoplay_related
        status = "ativado" if self.settings.youtube_music_autoplay_related else "desativado"
        self._announce(f"Conteúdo relacionado do YouTube Music {status}.")
        if hasattr(self, "_set_status_message"):
            self._set_status_message(f"Conteúdo relacionado: {status}.")
        self._save_settings()

    def _handle_media_end(self):
        state = self._get_playlist_state()
        if not state:
            _logger.debug("Media end: no active playlist state.")
            self._announce("Mídia finalizada.")
            return

        state.was_playing = False
        state.last_position_ms = 0

        if state.is_folder_tab:
            _logger.debug("Media end: folder tab, no auto-advance.")
            self._update_time_bar()
            self._refresh_playlist_browser()
            return

        if state.repeat_mode == REPEAT_ONE and state.current_media_path:
            _logger.debug("Media end: repeat-one, replaying current track.")
            self._play_media(
                index=self._get_active_playlist_index(),
                announce_message=f"Repetindo faixa atual. {self._describe_playlist_position(state)}",
            )
            return

        if getattr(self, "_suppress_next_auto_advance", False):
            _logger.debug("Media end: auto-advance suppressed for this end event.")
            self._suppress_next_auto_advance = False
            self._update_time_bar()
            self._refresh_playlist_browser()
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
            _logger.debug("Media end: advancing to next track in playback order.")
            loop_prefix = "Nova volta da playlist. " if wrapped_cycle else ""
            self._play_media(
                index=self._get_active_playlist_index(),
                announce_message=f"{loop_prefix}{self._describe_playlist_position(state)}",
            )
            return

        _logger.debug("Media end: no next track; attempting related autoplay.")
        if self._try_autoplay_related_youtube_music(state):
            return

        self._announce(f"Playlist {state.title} finalizada.")
