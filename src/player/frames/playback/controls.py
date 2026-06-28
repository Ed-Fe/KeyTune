from ...constants import PROGRESS_GAUGE_RANGE
from ...library import folder_display_name


class PlaybackControlsMixin:
    def _format_time_ms(self, milliseconds):
        if milliseconds is None or milliseconds < 0:
            return "tempo desconhecido"

        total_seconds = int(milliseconds // 1000)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        if hours:
            return f"{hours}:{minutes:02}:{seconds:02}"
        return f"{minutes}:{seconds:02}"

    def _time_bar_accessible_value(self):
        return self.progress_label.GetLabel()

    def _set_progress_label(self, text):
        # The progress timer refreshes this label twice per second; skip the
        # SetLabel call (and the re-layout/repaint it triggers) when the text
        # has not changed since the last tick.
        if getattr(self, "_last_progress_label_text", None) == text:
            return
        self._last_progress_label_text = text
        self.progress_label.SetLabel(text)

    def _set_progress_gauge_value(self, value):
        bounded_value = max(0, min(PROGRESS_GAUGE_RANGE, int(value)))
        if getattr(self, "_last_progress_gauge_value", None) == bounded_value:
            return
        self._last_progress_gauge_value = bounded_value
        self.progress_gauge.SetValue(bounded_value)

    def _update_time_bar(self):
        if not hasattr(self, "progress_label") or not hasattr(self, "progress_gauge"):
            return

        media = self.player.get_media() if hasattr(self, "player") else None
        if media is None:
            self._set_progress_label("Tempo: nenhuma mídia carregada.")
            self._set_progress_gauge_value(0)
            self._refresh_player_visual_hints()
            return

        current_time = self.player.get_time()
        if current_time is None or current_time < 0:
            current_time = 0

        total_time = self.player.get_length()
        current_label = self._format_time_ms(current_time)

        if total_time is None or total_time <= 0:
            self._set_progress_label(f"Tempo: {current_label} / duração desconhecida")
            if self.player.is_playing():
                # Pulse() drives an indeterminate animation, so it must run every
                # tick; invalidate the cached value so a later real SetValue applies.
                self._last_progress_gauge_value = None
                self.progress_gauge.Pulse()
            else:
                self._set_progress_gauge_value(0)
            self._refresh_player_visual_hints()
            return

        bounded_current_time = max(0, min(current_time, total_time))
        percentage = int(round((bounded_current_time / total_time) * 100)) if total_time > 0 else 0
        gauge_value = int(round((bounded_current_time / total_time) * PROGRESS_GAUGE_RANGE)) if total_time > 0 else 0
        total_label = self._format_time_ms(total_time)

        self._set_progress_label(f"Tempo: {current_label} / {total_label} ({percentage}%)")
        self._set_progress_gauge_value(gauge_value)
        self._refresh_player_visual_hints()

    def _seek_relative(self, delta_ms):
        if self._crossfade_state:
            if self._crossfade_state.get("phase") == "running":
                self._finish_crossfade()
            else:
                self._cancel_crossfade_transition(stop_incoming=True, stop_outgoing=False, invalidate_requests=True)

        if self.player.get_media() is None:
            return

        current_time = self.player.get_time()
        if current_time is None or current_time < 0:
            current_time = 0

        target_time = max(0, current_time + delta_ms)
        self.player.set_time(target_time)
        self._update_time_bar()

    def _change_volume(self, delta):
        self.current_volume = max(0, min(100, self.current_volume + delta))
        self._apply_current_volume()

    def _seek_to_start(self):
        if self._crossfade_state:
            if self._crossfade_state.get("phase") == "running":
                self._finish_crossfade()
            else:
                self._cancel_crossfade_transition(stop_incoming=True, stop_outgoing=False, invalidate_requests=True)

        if self.player.get_media() is None:
            return

        self.player.set_time(0)
        self._update_time_bar()
        self._announce("Início do arquivo.")

    def _seek_to_end(self):
        if self._crossfade_state:
            if self._crossfade_state.get("phase") == "running":
                self._finish_crossfade()
            else:
                self._cancel_crossfade_transition(stop_incoming=True, stop_outgoing=False, invalidate_requests=True)

        if self.player.get_media() is None:
            return

        media_length = self.player.get_length()
        if media_length is None or media_length <= 0:
            self.player.set_position(0.99)
        else:
            self.player.set_time(max(0, media_length - 1000))

        self._update_time_bar()
        self._announce("Fim do arquivo.")

    def _toggle_play_pause(self):
        state = self._get_playlist_state()
        if not self.player.get_media():
            self.on_open(None)
            return

        if self._crossfade_state:
            if self._crossfade_state.get("phase") == "running":
                self._finish_crossfade()
            else:
                self._cancel_crossfade_transition(stop_incoming=True, stop_outgoing=False, invalidate_requests=True)

        if self.player.is_playing():
            active_player_key = self._active_player_key

            def finish_pause():
                player = self._managed_player(active_player_key)
                if player is not None:
                    try:
                        player.pause()
                    except Exception:
                        pass
                self._apply_volume_to_player(active_player_key, self.current_volume)
                if state:
                    state.was_playing = False
                self._update_time_bar()
                self._announce("Pausado.")
                if hasattr(self, "_set_status_message") and state and state.current_media_path:
                    self._set_status_message(
                        f"Pausado: {self._media_label(state.current_media_path)}",
                        auto_clear_ms=0,
                    )
                refresh_smtc = getattr(self, "_refresh_smtc_state", None)
                if callable(refresh_smtc):
                    refresh_smtc()

            self._perform_short_fade_out(active_player_key, finish_pause)
        else:
            self._bind_player_to_window()
            self.player.play()
            if state:
                state.was_playing = True
            self._update_time_bar()
            self._announce("Reprodução retomada.")
            if hasattr(self, "_set_status_message") and state and state.current_media_path:
                self._set_status_message(
                    f"Tocando: {self._media_label(state.current_media_path)}",
                    auto_clear_ms=0,
                )
            refresh_smtc = getattr(self, "_refresh_smtc_state", None)
            if callable(refresh_smtc):
                refresh_smtc()

    def _announce_playback_time(self):
        if not self.player.get_media():
            self._announce("Nenhuma mídia carregada.")
            return

        current_time = self.player.get_time()
        if current_time is None or current_time < 0:
            current_time = 0

        total_time = self.player.get_length()
        current_label = self._format_time_ms(current_time)

        if total_time is None or total_time <= 0:
            self._announce(f"Tempo atual: {current_label}.")
            return

        total_label = self._format_time_ms(total_time)
        percentage = int(max(0, min(100, round((max(0, current_time) / total_time) * 100)))) if total_time > 0 else 0
        self._announce(f"Tempo atual: {current_label} de {total_label}. {percentage}%.")

    def _announce_current_volume(self):
        self._announce(f"Volume atual: {self.current_volume}%.")

    def _announce_player_status(self):
        current_tab = self._get_tab_state()
        state = self._get_playlist_state()
        status_parts = []

        if current_tab:
            status_parts.append(f"Aba atual: {current_tab.title}.")

        if state and current_tab is not state:
            status_parts.append(f"Aba de mídia ativa: {state.title}.")

        if state:
            if state.is_folder_tab and state.folder_current_path:
                status_parts.append(f"Pasta atual: {folder_display_name(state.folder_current_path)}.")

        media_path = state.current_media_path if state else None
        if not media_path:
            status_parts.append("Nenhuma mídia tocando agora.")
            status_parts.append(f"Volume atual: {self.current_volume}%.")
            if state:
                shuffle_label = "ligado" if state.shuffle_enabled else "desligado"
                status_parts.append(f"Aleatório {shuffle_label}.")
                status_parts.append(self._repeat_mode_message(state.repeat_mode) + ".")
            self._announce(" ".join(status_parts))
            return

        media_name = self._media_label(media_path)
        playback_state = "tocando" if self.player.is_playing() else "pausado"
        status_parts.append(f"Mídia: {media_name}. Estado: {playback_state}.")

        if state and state.item_count > 0:
            status_parts.append(f"Item {state.current_index + 1} de {state.item_count}.")
            shuffle_label = "ligado" if state.shuffle_enabled else "desligado"
            status_parts.append(f"Aleatório {shuffle_label}.")
            status_parts.append(self._repeat_mode_message(state.repeat_mode) + ".")

        current_time = self.player.get_time()
        if current_time is None or current_time < 0:
            current_time = 0

        total_time = self.player.get_length()
        if total_time is not None and total_time > 0:
            percentage = int(max(0, min(100, round((current_time / total_time) * 100))))
            status_parts.append(
                f"Tempo {self._format_time_ms(current_time)} de {self._format_time_ms(total_time)}. {percentage}%."
            )
        else:
            status_parts.append(f"Tempo atual: {self._format_time_ms(current_time)}.")

        status_parts.append(f"Volume atual: {self.current_volume}%.")
        self._announce(" ".join(status_parts))
