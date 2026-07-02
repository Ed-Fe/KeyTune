import wx

from ...about import AboutDialog
from ...i18n import _
from ...log import setup_logging
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

        self._begin_library_loader_shutdown()
        self._begin_player_backend_shutdown()
        self.announcer.request_close()

        self._save_session()

        self._finish_library_loader_shutdown()
        self._finish_player_backend_shutdown()
        self._shutdown_smtc_service()
        self.announcer.close()
        self.Destroy()

    def toggle_lyrics_panel(self):
        """
        Toggles the visibility of the lyrics panel and updates the UI checkbox.
        """
        if hasattr(self, 'lyrics_panel'):
            is_shown = self.lyrics_panel.IsShown()
            self.lyrics_panel.Show(not is_shown)
            
            if hasattr(self, 'lyrics_checkbox'):
                self.lyrics_checkbox.SetValue(not is_shown)
                
            self.Layout()
            
            if not is_shown and hasattr(self.lyrics_panel, 'lyrics_text_ctrl'):
                self.lyrics_panel.lyrics_text_ctrl.SetFocus()

    def on_key_down(self, event):
        """
        Global keyboard hook for shortcuts.
        Passes the event down the MRO chain to preserve playback controls.
        """
        keycode = event.GetKeyCode()
        modifiers = event.GetModifiers()

        # Check if the lyrics text control is focused
        focused_window = wx.Window.FindFocus()
        is_lyrics_focused = (
            hasattr(self, 'lyrics_panel') 
            and self.lyrics_panel.IsShown()
            and hasattr(self.lyrics_panel, 'lyrics_text_ctrl')
            and focused_window == self.lyrics_panel.lyrics_text_ctrl
        )

        # If lyrics are focused, prevent arrow keys/Home/End from affecting playback (volume/seek)
        if is_lyrics_focused and keycode in (wx.WXK_UP, wx.WXK_DOWN, wx.WXK_LEFT, wx.WXK_RIGHT, wx.WXK_HOME, wx.WXK_END, wx.WXK_PAGEUP, wx.WXK_PAGEDOWN):
            event.Skip()
            return

        # Shortcut: Esc closes the lyrics panel if it is open
        if keycode == wx.WXK_ESCAPE and modifiers == wx.MOD_NONE:
            if hasattr(self, 'lyrics_panel') and self.lyrics_panel.IsShown():
                self.toggle_lyrics_panel()
                
                # Restore focus to the main panel so the screen reader doesn't get lost
                if hasattr(self, 'notebook'):
                    self.notebook.SetFocus()
                return

        # Shortcut: Ctrl+L toggles the lyrics panel
        if keycode == ord('L') and modifiers == wx.MOD_CONTROL:
            self.toggle_lyrics_panel()
            return
            
        try:
            super().on_key_down(event)
        except AttributeError:
            event.Skip()