from ...constants import PROGRESS_GAUGE_RANGE
from ...i18n import _
from ...library import folder_display_name

PLAYBACK_RATE_STEP = 0.25
PLAYBACK_RATE_MIN = 0.25
PLAYBACK_RATE_MAX = 3.0

PITCH_SEMITONES_MIN = -12
PITCH_SEMITONES_MAX = 12


class PlaybackControlsMixin:
    def _format_time_ms(self, milliseconds):
        if milliseconds is None or milliseconds < 0:
            return _("tempo desconhecido")

        total_seconds = int(milliseconds // 1000)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        if hours:
            return f"{hours}:{minutes:02}:{seconds:02}"
        return f"{minutes}:{seconds:02}"

    def _time_bar_accessible_value(self):
        return self.progress_label.GetLabel()

    def _maybe_refresh_player_visual_hints(self):
        # The video overlay hints only depend on the active tab's current media
        # and the video-output setting. Gate the (per-tab, string-building)
        # refresh on a cheap signature so the 500 ms progress timer does not
        # rebuild every page's overlay twice per second while nothing relevant
        # changed. A tab switch refreshes the now-visible page unconditionally
        # (see TabManagementMixin._activate_tab).
        active_state = (
            self._get_active_playlist_state() if hasattr(self, "_get_active_playlist_state") else None
        )
        signature = (
            getattr(active_state, "current_media_path", None),
            bool(getattr(self.settings, "disable_video_output", False)),
        )
        if getattr(self, "_last_visual_hints_signature", "__unset__") == signature:
            return
        self._last_visual_hints_signature = signature
        self._refresh_player_visual_hints()

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
            self._set_progress_label(_("Tempo: nenhuma mídia carregada."))
            self._set_progress_gauge_value(0)
            self._maybe_refresh_player_visual_hints()
            return

        current_time = self.player.get_time()
        if current_time is None or current_time < 0:
            current_time = 0

        total_time = self.player.get_length()
        current_label = self._format_time_ms(current_time)

        if total_time is None or total_time <= 0:
            self._set_progress_label(_("Tempo: {current} / duração desconhecida").format(current=current_label))
            if self.player.is_playing():
                # Pulse() drives an indeterminate animation, so it must run every
                # tick; invalidate the cached value so a later real SetValue applies.
                self._last_progress_gauge_value = None
                self.progress_gauge.Pulse()
            else:
                self._set_progress_gauge_value(0)
            self._maybe_refresh_player_visual_hints()
            return

        bounded_current_time = max(0, min(current_time, total_time))
        percentage = int(round((bounded_current_time / total_time) * 100)) if total_time > 0 else 0
        gauge_value = int(round((bounded_current_time / total_time) * PROGRESS_GAUGE_RANGE)) if total_time > 0 else 0
        total_label = self._format_time_ms(total_time)

        self._set_progress_label(f"Tempo: {current_label} / {total_label} ({percentage}%)")
        self._set_progress_gauge_value(gauge_value)
        self._maybe_refresh_player_visual_hints()

    def _seek_relative(self, delta_ms):
        if self._crossfade_state:
            if self._crossfade_state.get("phase") == "running":
                self._finish_crossfade()
            else:
                self._cancel_crossfade_transition(
                    stop_incoming=True, stop_outgoing=False, invalidate_requests=True, restore_selection=True,
                )

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

    def _format_playback_rate(self, rate):
        return f"{rate:g}x"

    def _change_playback_rate(self, delta):
        new_rate = round(self.current_playback_rate + delta, 2)
        self.current_playback_rate = max(PLAYBACK_RATE_MIN, min(PLAYBACK_RATE_MAX, new_rate))
        self._apply_current_playback_rate()
        self._announce_current_playback_rate()

    def _reset_playback_rate(self):
        self.current_playback_rate = 1.0
        self._apply_current_playback_rate()
        self._announce_current_playback_rate()

    def _announce_current_playback_rate(self):
        self._announce(
            _("Velocidade de reprodução: {rate}.").format(rate=self._format_playback_rate(self.current_playback_rate))
        )

    def _format_pitch_label(self, semitones):
        if semitones == 0:
            return _("tom original")
        return _("{semitones:+d} semitons").format(semitones=semitones)

    def _change_pitch_semitones(self, delta):
        new_semitones = self.current_pitch_semitones + delta
        self.current_pitch_semitones = max(PITCH_SEMITONES_MIN, min(PITCH_SEMITONES_MAX, new_semitones))
        self._apply_equalizer_state_to_current_playback()
        self._announce_current_pitch()

    def _reset_pitch_semitones(self):
        self.current_pitch_semitones = 0
        self._apply_equalizer_state_to_current_playback()
        self._announce_current_pitch()

    def _announce_current_pitch(self):
        self._announce(_("Tom: {pitch}.").format(pitch=self._format_pitch_label(self.current_pitch_semitones)))

    def _seek_to_start(self):
        if self._crossfade_state:
            if self._crossfade_state.get("phase") == "running":
                self._finish_crossfade()
            else:
                self._cancel_crossfade_transition(
                    stop_incoming=True, stop_outgoing=False, invalidate_requests=True, restore_selection=True,
                )

        if self.player.get_media() is None:
            return

        self.player.set_time(0)
        self._update_time_bar()
        self._announce(_("Início do arquivo."))

    def _seek_to_end(self):
        if self._crossfade_state:
            if self._crossfade_state.get("phase") == "running":
                self._finish_crossfade()
            else:
                self._cancel_crossfade_transition(
                    stop_incoming=True, stop_outgoing=False, invalidate_requests=True, restore_selection=True,
                )

        if self.player.get_media() is None:
            return

        media_length = self.player.get_length()
        if media_length is None or media_length <= 0:
            self.player.set_position(0.99)
        else:
            self.player.set_time(max(0, media_length - 1000))

        self._update_time_bar()
        self._announce(_("Fim do arquivo."))

    def _toggle_play_pause(self):
        state = self._get_playlist_state()
        if not self.player.get_media():
            media_start_is_pending = getattr(self, "_media_start_is_pending", None)
            if callable(media_start_is_pending) and media_start_is_pending():
                self._announce(_("A mídia ainda está carregando."))
                return
            self.on_open(None)
            return

        if self._crossfade_state:
            if self._crossfade_state.get("phase") == "running":
                self._finish_crossfade()
            else:
                self._cancel_crossfade_transition(
                    stop_incoming=True, stop_outgoing=False, invalidate_requests=True, restore_selection=True,
                )

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
                self._announce(_("Pausado."))
                if hasattr(self, "_set_status_message") and state and state.current_media_path:
                    self._set_status_message(
                        _("Pausado: {name}").format(name=self._media_label(state.current_media_path)),
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
            self._announce(_("Reprodução retomada."))
            if hasattr(self, "_set_status_message") and state and state.current_media_path:
                self._set_status_message(
                    _("Tocando: {name}").format(name=self._media_label(state.current_media_path)),
                    auto_clear_ms=0,
                )
            refresh_smtc = getattr(self, "_refresh_smtc_state", None)
            if callable(refresh_smtc):
                refresh_smtc()

    def _announce_playback_time(self):
        if not self.player.get_media():
            self._announce(_("Nenhuma mídia carregada."))
            return

        current_time = self.player.get_time()
        if current_time is None or current_time < 0:
            current_time = 0

        total_time = self.player.get_length()
        current_label = self._format_time_ms(current_time)

        if total_time is None or total_time <= 0:
            self._announce(_("Tempo atual: {time}.").format(time=current_label))
            return

        total_label = self._format_time_ms(total_time)
        percentage = int(max(0, min(100, round((max(0, current_time) / total_time) * 100)))) if total_time > 0 else 0
        self._announce(_("Tempo atual: {current} de {total}. {percent}%.").format(current=current_label, total=total_label, percent=percentage))

    def _announce_current_volume(self):
        self._announce(_("Volume atual: {volume}%.").format(volume=self.current_volume))

    def _append_sleep_timer_status(self, status_parts):
        sleep_timer_sentence = getattr(self, "_sleep_timer_status_sentence", None)
        if not callable(sleep_timer_sentence):
            return
        sentence = sleep_timer_sentence()
        if sentence:
            status_parts.append(sentence)

    def _announce_player_status(self):
        current_tab = self._get_tab_state()
        state = self._get_playlist_state()
        status_parts = []

        if current_tab:
            status_parts.append(_("Aba atual: {title}.").format(title=current_tab.title))

        if state and current_tab is not state:
            status_parts.append(_("Aba de mídia ativa: {title}.").format(title=state.title))

        if state:
            if state.is_folder_tab and state.folder_current_path:
                status_parts.append(_("Pasta atual: {name}.").format(name=folder_display_name(state.folder_current_path)))

        media_path = state.current_media_path if state else None
        if not media_path:
            status_parts.append(_("Nenhuma mídia tocando agora."))
            status_parts.append(_("Volume atual: {volume}%.").format(volume=self.current_volume))
            status_parts.append(
                _("Velocidade atual: {rate}.").format(rate=self._format_playback_rate(self.current_playback_rate))
            )
            status_parts.append(_("Tom: {pitch}.").format(pitch=self._format_pitch_label(self.current_pitch_semitones)))
            if state:
                shuffle_label = _("ligado") if state.shuffle_enabled else _("desligado")
                status_parts.append(_("Aleatório {state}.").format(state=shuffle_label))
                status_parts.append(self._repeat_mode_message(state.repeat_mode) + ".")
            self._append_sleep_timer_status(status_parts)
            self._announce(" ".join(status_parts))
            return

        media_name = self._media_label(media_path)
        playback_state = _("tocando") if self.player.is_playing() else _("pausado")
        status_parts.append(_("Mídia: {name}. Estado: {state}.").format(name=media_name, state=playback_state))
        status_parts.append(
            _("Velocidade atual: {rate}.").format(rate=self._format_playback_rate(self.current_playback_rate))
        )
        status_parts.append(_("Tom: {pitch}.").format(pitch=self._format_pitch_label(self.current_pitch_semitones)))

        if state and state.item_count > 0:
            status_parts.append(_("Item {current} de {total}.").format(current=state.current_index + 1, total=state.item_count))
            shuffle_label = _("ligado") if state.shuffle_enabled else _("desligado")
            status_parts.append(_("Aleatório {state}.").format(state=shuffle_label))
            status_parts.append(self._repeat_mode_message(state.repeat_mode) + ".")

        current_time = self.player.get_time()
        if current_time is None or current_time < 0:
            current_time = 0

        total_time = self.player.get_length()
        if total_time is not None and total_time > 0:
            percentage = int(max(0, min(100, round((current_time / total_time) * 100))))
            status_parts.append(
                _("Tempo {current} de {total}. {percent}%.").format(current=self._format_time_ms(current_time), total=self._format_time_ms(total_time), percent=percentage)
            )
        else:
            status_parts.append(_("Tempo atual: {time}.").format(time=self._format_time_ms(current_time)))

        status_parts.append(_("Volume atual: {volume}%.").format(volume=self.current_volume))
        self._append_sleep_timer_status(status_parts)
        self._announce(" ".join(status_parts))
