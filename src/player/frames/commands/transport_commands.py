from ...i18n import _


class TransportCommandsMixin:
    def on_new_playlist(self, _event):
        tab_index = self._create_empty_playlist_tab(select=False)
        self._select_tab(tab_index, announce=True)

    def on_previous_track(self, _event):
        self._play_adjacent_item(-1)

    def on_play_pause(self, _event):
        self._toggle_play_pause()

    def on_stop(self, _event):
        state = self._get_playlist_state()
        self._cancel_crossfade_transition(stop_incoming=True, stop_outgoing=True, invalidate_requests=True)
        active_player_key = getattr(self, "_active_player_key", None)

        def finish_stop():
            self._stop_all_players(unload=False)
            if active_player_key is not None:
                self._apply_volume_to_player(active_player_key, self.current_volume)
            clear_youtube_music_history_tracking = getattr(self, "_clear_youtube_music_history_tracking", None)
            if callable(clear_youtube_music_history_tracking):
                clear_youtube_music_history_tracking()
            if state:
                state.was_playing = False
                state.last_position_ms = 0
            self._update_time_bar()
            self._announce(_("Parado."))
            if hasattr(self, "_set_status_message"):
                self._set_status_message(_("Parado."), auto_clear_ms=0)
            refresh_smtc = getattr(self, "_refresh_smtc_state", None)
            if callable(refresh_smtc):
                refresh_smtc()

        if active_player_key is not None:
            self._perform_short_fade_out(active_player_key, finish_stop)
        else:
            finish_stop()

    def on_next_track(self, _event):
        self._play_adjacent_item(1)

    def on_toggle_shuffle(self, _event):
        self._toggle_shuffle()

    def on_cycle_repeat_mode(self, _event):
        self._cycle_repeat_mode()

    def on_toggle_related_autoplay(self, _event):
        self._toggle_related_autoplay()

    def on_announce_time(self, _event):
        self._announce_playback_time()

    def on_announce_volume(self, _event):
        self._announce_current_volume()

    def on_increase_playback_rate(self, _event):
        self._change_playback_rate(0.25)

    def on_decrease_playback_rate(self, _event):
        self._change_playback_rate(-0.25)

    def on_reset_playback_rate(self, _event):
        self._reset_playback_rate()

    def on_increase_pitch(self, _event):
        self._change_pitch_semitones(1)

    def on_decrease_pitch(self, _event):
        self._change_pitch_semitones(-1)

    def on_reset_pitch(self, _event):
        self._reset_pitch_semitones()

    def on_announce_status(self, _event):
        self._announce_player_status()

    def on_close_current_media(self, _event):
        self._close_current_media()

    def on_close_current_tab(self, _event):
        self._close_current_tab()

    def on_next_tab(self, _event):
        self._cycle_tabs(1)

    def on_previous_tab(self, _event):
        self._cycle_tabs(-1)
