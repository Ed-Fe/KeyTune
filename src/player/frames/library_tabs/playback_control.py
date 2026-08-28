from ...constants import (
    APP_TITLE,
    PLAYBACK_RESTART_THRESHOLD_MS,
    REPEAT_ALL,
    REPEAT_MODE_LABELS,
    REPEAT_MODES,
    REPEAT_OFF,
    REPEAT_ONE,
)
from ...i18n import _
from ...library import folder_display_name
from ...log import get_logger
from ...playlists import ScreenTabState
from ...youtube_music.playlists import is_youtube_music_media


_logger = get_logger(__name__)


class PlaylistPlaybackMixin:
    def _repeat_mode_message(self, repeat_mode):
        return REPEAT_MODE_LABELS.get(repeat_mode, REPEAT_MODE_LABELS[REPEAT_OFF])

    def _describe_playlist_position(self, state):
        if not state.current_media_path:
            if state.is_folder_tab and state.folder_current_path:
                return _("Pasta atual: {name}.").format(name=folder_display_name(state.folder_current_path))
            return _("Nenhuma mídia tocando agora.")

        media_name = self._media_label(state.current_media_path)
        if state.is_folder_tab:
            return _("Pasta atual: {name}.").format(name=folder_display_name(state.folder_current_path))

        if state.item_count <= 1 or not 0 <= state.current_index < state.item_count:
            return _("Item atual: {name}.").format(name=media_name)

        return _("Item atual: {name}. Item {current} de {total}.").format(name=media_name, current=state.current_index + 1, total=state.item_count)

    def _play_media(
        self,
        media_path=None,
        index=None,
        announce_message=None,
        allow_crossfade=False,
        autodj_transition=None,
    ):
        self._suppress_next_auto_advance = False
        state = self._get_playlist_state(index)
        if not state:
            return
        state.autodj_waiting_for_next = False

        if media_path is not None and state.current_media_path != media_path:
            media_index = state.index_of_item(media_path)
            if media_index is not None:
                state.select_index(media_index)
            else:
                state.current_media_path = media_path

        if not state.current_media_path:
            return

        if self._youtube_music_media_is_disliked(state.current_media_path):
            skipped_media_name = self._media_label(state.current_media_path)
            if not self._select_next_allowed_youtube_music_media(state):
                state.was_playing = False
                self._announce(_("Nenhuma faixa disponível: as músicas restantes estão marcadas como não gostei."))
                self._refresh_playlist_browser()
                return
            self._announce(
                _("Faixa marcada como não gostei ignorada: {name}.").format(name=skipped_media_name)
            )

        crossfade_state = getattr(self, "_crossfade_state", None)
        self._cancel_crossfade_transition(
            stop_incoming=True,
            stop_outgoing=bool(crossfade_state and crossfade_state.get("phase") == "running"),
            invalidate_requests=bool(crossfade_state),
        )

        # A faixa que estava tocando ainda tem a posição na memória do backend;
        # grava-a antes de o player ser reaproveitado pela nova mídia.
        flush_library_state = getattr(self, "_flush_smart_library_playback_state", None)
        if callable(flush_library_state):
            flush_library_state()

        state.was_playing = True
        state.last_position_ms = 0
        if autodj_transition is None:
            state.playback_gain_db = 0.0
        target_index = self._get_active_playlist_index() if index is None else index
        transition_duration_ms = (
            self._autodj_transition_duration_ms(autodj_transition)
            if autodj_transition is not None
            else None
        )
        if allow_crossfade and self._can_crossfade_to_media(
            state.current_media_path,
            duration_override_ms=transition_duration_ms,
        ):
            if self._start_crossfade(
                state.current_media_path,
                tab_index=target_index,
                announce_message=announce_message,
                autodj_transition=autodj_transition,
            ):
                return

        # Mídias longas (podcasts, audiolivros, vídeos) voltam de onde pararam.
        resume_position_ms = 0
        library_resume_position = getattr(self, "_library_resume_position_ms", None)
        if callable(library_resume_position):
            resume_position_ms = library_resume_position(state.current_media_path)
            if resume_position_ms > 0:
                state.last_position_ms = resume_position_ms
                self._announce_resume_position(state.current_media_path, resume_position_ms)

        self._update_title()
        self._update_time_bar()
        self._refresh_playlist_browser()

        self._queue_media_start(
            state.current_media_path,
            tab_index=target_index,
            announce_message=announce_message,
            restore_position_ms=resume_position_ms,
        )

    def _youtube_music_media_is_disliked(self, media_path):
        if not is_youtube_music_media(media_path):
            return False

        youtube_music_service = self._youtube_music_service_for_playback()
        if youtube_music_service is None:
            return False
        if not getattr(youtube_music_service, "has_saved_browser_auth", lambda: False)():
            return False

        try:
            return bool(youtube_music_service.is_media_disliked(media_path))
        except Exception:
            return False

    def _select_next_allowed_youtube_music_media(self, state):
        should_wrap = state.repeat_mode == REPEAT_ALL
        for _attempt in range(max(0, state.item_count - 1)):
            target = state.move_in_playback_order(1, wrap=should_wrap)
            if not target:
                return False
            if not self._youtube_music_media_is_disliked(target):
                return True
        return False

    def _maybe_start_automatic_crossfade(self):
        if getattr(self, "_crossfade_state", None) is not None:
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

        prepared_autodj = getattr(self, "_prepared_autodj_transition", lambda _state: None)(state)
        if prepared_autodj is not None:
            plan = prepared_autodj["plan"]
            transition_start_ms = plan.outgoing_start_ms
            preload_lead_ms = self._autodj_preload_lead_ms(prepared_autodj["pair"][1])
            if transition_start_ms is None or current_time < max(0, transition_start_ms - preload_lead_ms):
                return False
            crossfade_window_ms = self._autodj_transition_duration_ms(prepared_autodj)
        else:
            configured_crossfade_ms = self._crossfade_duration_ms()
            if configured_crossfade_ms <= 0:
                return False
            startup_headroom_ms = self._crossfade_startup_headroom_ms()
            crossfade_window_ms = configured_crossfade_ms + startup_headroom_ms

        remaining_time = total_time - max(0, current_time)
        if prepared_autodj is None and remaining_time > crossfade_window_ms:
            return False
        if remaining_time <= 0:
            return False

        should_wrap = state.repeat_mode == REPEAT_ALL
        next_media_path = state.peek_in_playback_order(1, wrap=should_wrap)
        expected_autodj_path = prepared_autodj["pair"][1] if prepared_autodj is not None else None
        if expected_autodj_path is not None and next_media_path != expected_autodj_path:
            return False
        transition_duration_ms = (
            self._autodj_transition_duration_ms(prepared_autodj)
            if prepared_autodj is not None
            else None
        )
        if not next_media_path or not self._can_crossfade_to_media(
            next_media_path,
            duration_override_ms=transition_duration_ms,
        ):
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

        loop_prefix = _("Nova volta da playlist. ") if wrapped_cycle else ""
        self._play_media(
            index=self._get_active_playlist_index(),
            announce_message=f"{loop_prefix}{self._describe_playlist_position(state)}",
            allow_crossfade=True,
            autodj_transition=prepared_autodj,
        )
        return True

    def _update_title(self):
        current_tab = self._get_tab_state()
        if isinstance(current_tab, ScreenTabState):
            active_state = self._get_active_playlist_state()
            if active_state and active_state.current_media_path:
                media_name = self._media_label(active_state.current_media_path)
                self.SetTitle(f"{APP_TITLE} — {media_name}")
            else:
                self.SetTitle(f"{APP_TITLE} — {current_tab.title}")
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
        self.SetTitle(f"{APP_TITLE} — {media_name}")
        refresh_smtc = getattr(self, "_refresh_smtc_state", None)
        if callable(refresh_smtc):
            refresh_smtc()

    def _play_adjacent_item(self, direction):
        if self._block_sensitive_action_during_youtube_music("track-navigation"):
            return

        state = self._get_playlist_state()
        if not state or not state.items:
            self._announce(_("Nenhuma playlist carregada."))
            return

        if direction < 0 and self.player.get_media() is not None:
            current_time = self.player.get_time()
            if current_time is not None and current_time > PLAYBACK_RESTART_THRESHOLD_MS:
                self.player.set_time(0)
                self._update_time_bar()
                self._announce(_("Início do item atual."))
                return

        should_wrap = state.repeat_mode == REPEAT_ALL
        target = state.move_in_playback_order(-1 if direction < 0 else 1, wrap=should_wrap)
        if not target:
            defer_autodj_advance = getattr(self, "_defer_autodj_advance", None)
            if direction > 0 and callable(defer_autodj_advance) and defer_autodj_advance(state):
                return
            if direction > 0 and self._try_autoplay_related_youtube_music(state):
                return
            boundary_message = _("Você já está no primeiro item.") if direction < 0 else _("Você já está no último item.")
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
            self._announce(_("Nenhuma playlist carregada."))
            return

        target_index = len(state.items) - 1 if to_last else 0
        if state.current_index == target_index:
            boundary_message = _("Você já está no último item.") if to_last else _("Você já está no primeiro item.")
            self._announce(boundary_message)
            return

        state.select_index(target_index)
        self._play_media(index=self._get_active_playlist_index())

    def _move_current_item(self, direction):
        if self._block_sensitive_action_during_youtube_music("playback-order"):
            return

        state = self._get_playlist_state()
        if not state or not state.items:
            self._announce(_("Nenhuma playlist carregada."))
            return

        if state.is_folder_tab:
            self._announce(_("Não é possível reordenar arquivos no navegador de pastas."))
            return

        if len(state.items) < 2:
            self._announce(_("A playlist precisa de pelo menos dois itens para reordenar."))
            return

        current_index = state.current_index
        if current_index < 0 or current_index >= len(state.items):
            media_index = state.index_of_item(state.current_media_path)
            if media_index is not None:
                current_index = media_index
                state.current_index = current_index
            else:
                self._announce(_("Nenhum item atual para reordenar."))
                return

        target_index = current_index + direction
        if not 0 <= target_index < len(state.items):
            boundary_message = _("O item já está no topo da playlist.") if direction < 0 else _("O item já está no final da playlist.")
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
            _("Item movido para a posição {pos} de {total}: {name}.").format(pos=target_index + 1, total=state.item_count, name=self._media_label(moved_item))
        )

    def _toggle_shuffle(self):
        if self._block_sensitive_action_during_youtube_music("playback-order"):
            return

        state = self._get_playlist_state()
        if not state:
            self._announce(_("Nenhuma playlist ativa."))
            return

        state.shuffle_enabled = not state.shuffle_enabled
        preferred_index = state.current_index if state.current_index >= 0 else 0
        state.reset_playback_order(preferred_index=preferred_index)
        status = _("ativado") if state.shuffle_enabled else _("desativado")
        self._announce(_("Modo aleatório {status}.").format(status=status))
        if hasattr(self, "_set_status_message"):
            self._set_status_message(_("Aleatório: {status}.").format(status=status))
        self._refresh_playlist_browser()

    def _cycle_repeat_mode(self):
        if self._block_sensitive_action_during_youtube_music("playback-order"):
            return

        state = self._get_playlist_state()
        if not state:
            self._announce(_("Nenhuma playlist ativa."))
            return

        current_mode_index = REPEAT_MODES.index(state.repeat_mode)
        state.repeat_mode = REPEAT_MODES[(current_mode_index + 1) % len(REPEAT_MODES)]
        self._announce(self._repeat_mode_message(state.repeat_mode) + ".")
        if hasattr(self, "_set_status_message"):
            mode_label = REPEAT_MODE_LABELS.get(state.repeat_mode, state.repeat_mode)
            self._set_status_message(_("Repetir: {mode}.").format(mode=mode_label))
        self._refresh_playlist_browser()

    def _toggle_related_autoplay(self):
        self.settings.youtube_music_autoplay_related = not self.settings.youtube_music_autoplay_related
        status = _("ativado") if self.settings.youtube_music_autoplay_related else _("desativado")
        self._announce(_("Conteúdo relacionado do YouTube Music {status}.").format(status=status))
        if hasattr(self, "_set_status_message"):
            self._set_status_message(_("Conteúdo relacionado: {status}.").format(status=status))
        self._save_settings()

    def _handle_media_end(self):
        # O temporizador "fim da faixa" tem prioridade sobre repetição, fila e
        # avanço automático: a sessão termina aqui, com a posição preservada.
        if self._sleep_timer_should_stop_at_media_end():
            _logger.debug("Media end: sleep timer armed for end of track; stopping playback.")
            end_state = self._get_playlist_state()
            if end_state:
                end_state.was_playing = False
                end_state.last_position_ms = 0
            self._handle_sleep_timer_media_end()
            self._update_time_bar()
            self._refresh_playlist_browser()
            return

        state = self._get_playlist_state()
        if not state:
            _logger.debug("Media end: no active playlist state.")
            self._announce(_("Mídia finalizada."))
            return

        # Chegou ao fim: a marca de retomada dessa mídia deixa de fazer sentido.
        forget_resume_position = getattr(self, "_forget_resume_position", None)
        if callable(forget_resume_position) and state.current_media_path:
            forget_resume_position(state.current_media_path)

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
                announce_message=_("Repetindo faixa atual. {position}").format(position=self._describe_playlist_position(state)),
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
            loop_prefix = _("Nova volta da playlist. ") if wrapped_cycle else ""
            self._play_media(
                index=self._get_active_playlist_index(),
                announce_message=f"{loop_prefix}{self._describe_playlist_position(state)}",
            )
            return

        defer_autodj_advance = getattr(self, "_defer_autodj_advance", None)
        if callable(defer_autodj_advance) and defer_autodj_advance(state):
            return

        _logger.debug("Media end: no next track; attempting related autoplay.")
        if self._try_autoplay_related_youtube_music(state):
            return

        self._announce(_("Playlist {title} finalizada.").format(title=state.title))
