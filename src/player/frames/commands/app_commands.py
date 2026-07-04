import wx

from ...about import AboutDialog
from ...i18n import _
from ...log import setup_logging
from ...playlists.queue_dialog import QueueManagerDialog
from ...preferences import PreferencesDialog


class AppCommandsMixin:
    def on_open_about(self, _event):
        dialog = AboutDialog(self, on_open_credits=self._open_credits_document)
        try:
            dialog.ShowModal()
        finally:
            dialog.Destroy()

    def on_open_preferences(self, _event):
        previous_settings = self.settings
        dialog = PreferencesDialog(
            self,
            self.settings,
            audio_output_devices=self._audio_output_devices(),
        )
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return
            self.settings = dialog.get_settings()
        finally:
            dialog.Destroy()

        setup_logging(self.settings.logging_enabled, self.settings.logging_level)

        if not self.settings.remember_last_folder:
            self.settings.last_open_dir = ""

        if self.current_volume == previous_settings.default_volume:
            self.current_volume = self.settings.default_volume
            self._apply_current_volume()

        if self.settings.disable_video_output != previous_settings.disable_video_output:
            self._refresh_player_backend_for_video_output_setting()

        audio_output_updated = True
        if self.settings.audio_output_device_id != previous_settings.audio_output_device_id:
            audio_output_updated = self._set_audio_output_device(
                self.settings.audio_output_device_id,
                announce=True,
                previous_device_id=previous_settings.audio_output_device_id,
            )
            if not audio_output_updated:
                self._save_settings()
        else:
            self._save_settings()

        handle_youtube_music_preferences_change = getattr(self, "_handle_youtube_music_preferences_change", None)
        if callable(handle_youtube_music_preferences_change):
            handle_youtube_music_preferences_change(previous_settings)

        if audio_output_updated:
            self._announce(_("Preferências salvas."))
        else:
            self._announce(_("Preferências salvas, mas o dispositivo de áudio anterior foi mantido."))

    def on_select_audio_output_device(self, event):
        selected_device_id = self._audio_output_menu_actions.get(event.GetId())
        if selected_device_id is None:
            event.Skip()
            return

        self._set_audio_output_device(selected_device_id)

    def on_refresh_audio_output_devices(self, _event):
        self._refresh_audio_output_menu(announce=True)

    def on_show_keyboard_help(self, _event):
        self._show_keyboard_help_dialog()

    def on_tab_changed(self, event):
        if self._suppress_tab_change_event:
            event.Skip()
            return

        old_index = event.GetOldSelection()
        if old_index != wx.NOT_FOUND:
            if self._get_playlist_state(old_index):
                self._capture_tab_state(old_index)
            else:
                self._capture_active_playlist_state()

        new_index = event.GetSelection()
        if new_index != wx.NOT_FOUND:
            self._activate_tab(new_index, announce=True)

        event.Skip()

    def on_progress_timer(self, _event):
        self._update_time_bar()
        record_snapshot = getattr(self, "_record_playback_state_snapshot", None)
        if callable(record_snapshot):
            record_snapshot()
        refresh_runtime_stream_title = getattr(self, "_refresh_active_runtime_stream_title", None)
        if callable(refresh_runtime_stream_title):
            refresh_runtime_stream_title()
        maybe_report_youtube_music_history = getattr(self, "_maybe_report_youtube_music_history", None)
        if callable(maybe_report_youtube_music_history):
            maybe_report_youtube_music_history()
        maybe_prefetch_related = getattr(self, "_maybe_prefetch_related_youtube_music", None)
        if callable(maybe_prefetch_related):
            maybe_prefetch_related()
        maybe_keepalive_smtc = getattr(self, "_maybe_keepalive_smtc", None)
        if callable(maybe_keepalive_smtc):
            maybe_keepalive_smtc()
        # Poll for the automatic crossfade start window here, on the slower
        # progress timer, instead of on the high-frequency crossfade timer.
        # The crossfade window already includes startup headroom, so 500 ms
        # granularity is plenty to decide when to begin the transition — and
        # the 15 ms timer can stay idle until a crossfade is actually running.
        maybe_start_crossfade = getattr(self, "_maybe_start_automatic_crossfade", None)
        if callable(maybe_start_crossfade) and getattr(self, "_crossfade_state", None) is None:
            maybe_start_crossfade()

    def on_crossfade_timer(self, _event):
        self._handle_playback_timer_tick()

    def on_video_panel_resize(self, _event):
        self._bind_player_to_window()
        self._refresh_player_visual_hints()

    def on_video_panel_focus(self, _event):
        wx.CallAfter(self.SetFocus)

    def on_exit(self, _event):
        self.Close()

    def on_close(self, event):
        if not getattr(self, "_update_restart_pending", False) and self.settings.confirm_on_exit and event.CanVeto():
            with wx.MessageDialog(
                self,
                _("Deseja realmente sair do KeyTune?"),
                _("Confirmar saída"),
                wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
            ) as dialog:
                if dialog.ShowModal() != wx.ID_YES:
                    event.Veto()
                    return

        if hasattr(self, "progress_timer") and self.progress_timer.IsRunning():
            self.progress_timer.Stop()
        if hasattr(self, "crossfade_timer") and self.crossfade_timer.IsRunning():
            self.crossfade_timer.Stop()
        self._dispose_equalizer_ui_cache()

        # Signal every background worker to stop up front so their shutdown
        # waits overlap instead of stacking. The session save (disk I/O) then
        # runs while those workers wind down, and the joins happen afterwards.
        self._begin_library_loader_shutdown()
        self._begin_player_backend_shutdown()
        self.announcer.request_close()

        self._save_session()

        self._finish_library_loader_shutdown()
        self._finish_player_backend_shutdown()
        self._shutdown_smtc_service()
        self.announcer.close()
        self.Destroy()

    def _enqueue_selected_item(self):
        # A fila pertence sempre à playlist que está tocando (opção a): assim
        # "adicionar à fila" afeta o que toca a seguir, não a aba navegada.
        state = self._get_active_playlist_state()
        if not state:
            self._announce(_("Nenhuma playlist ativa."))
            return

        browser = self._get_browser_panel()
        paths = []

        # Tenta pegar as músicas que estão selecionadas na lista, ignorando o foco
        if browser:
            paths = browser.get_selected_item_paths()

        # Se nada foi selecionado na lista, usa a música que está tocando agora
        if not paths and state.current_media_path:
            paths = [state.current_media_path]

        if not paths:
            self._announce(_("Nenhum item selecionado para adicionar à fila."))
            return

        added = 0
        removed = 0
        last_added_label = ""
        last_removed_label = ""

        # Alterna cada caminho: se já está na fila, remove; caso contrário, enfileira.
        for path in paths:
            label = self._queue_entry_label(state, path)
            if state.is_queued(path):
                if state.dequeue_item(path):
                    removed += 1
                    last_removed_label = label
            elif state.enqueue_item(path, label):
                added += 1
                last_added_label = label

        self._announce_queue_toggle(added, removed, last_added_label, last_removed_label)

    def _announce_queue_toggle(self, added, removed, added_label, removed_label):
        if added and removed:
            self._announce(
                _("{added} itens adicionados e {removed} removidos da fila de reprodução.").format(
                    added=added, removed=removed
                )
            )
        elif added == 1:
            self._announce(_("{item} adicionado à fila de reprodução.").format(item=added_label))
        elif added > 1:
            self._announce(_("{count} itens adicionados à fila de reprodução.").format(count=added))
        elif removed == 1:
            self._announce(_("{item} removido da fila de reprodução.").format(item=removed_label))
        elif removed > 1:
            self._announce(_("{count} itens removidos da fila de reprodução.").format(count=removed))
        else:
            self._announce(_("Nenhum item pôde ser adicionado à fila."))

    def _queue_entry_label(self, state, path):
        label = self._media_label_from_playlist_state(state, path)
        return label or self._media_label(path)

    def _open_queue_manager(self):
        state = self._get_active_playlist_state()
        if not state:
            self._announce(_("Nenhuma playlist ativa."))
            return

        if not state.queue_paths():
            self._announce(_("A fila de reprodução está vazia. Use Ctrl+Shift+F para adicionar itens."))
            return

        dialog = QueueManagerDialog(
            self,
            get_entries=lambda: [(path, self._queue_entry_label(state, path)) for path in state.queue_paths()],
            on_remove=state.remove_queue_entry,
            on_move=state.move_queue_entry,
            on_clear=state.clear_queue,
            announce=self._announce,
        )
        try:
            dialog.ShowModal()
        finally:
            dialog.Destroy()

    def toggle_lyrics_panel(self):
        """Toggle the lyrics panel visibility and sync the UI checkbox.

        When the panel becomes visible its text control receives focus so a
        screen-reader user lands directly on the lyrics.
        """
        lyrics_panel = getattr(self, "lyrics_panel", None)
        if lyrics_panel is None:
            return

        is_shown = lyrics_panel.IsShown()
        lyrics_panel.Show(not is_shown)

        lyrics_checkbox = getattr(self, "lyrics_checkbox", None)
        if lyrics_checkbox is not None:
            lyrics_checkbox.SetValue(not is_shown)

        self.Layout()

        if not is_shown:
            text_ctrl = getattr(lyrics_panel, "lyrics_text_ctrl", None)
            if text_ctrl is not None:
                text_ctrl.SetFocus()
