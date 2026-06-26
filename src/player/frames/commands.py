import os

import wx

from ..constants import LARGE_SEEK_STEP_MS, PLAYLIST_WILDCARD
from ..log import setup_logging
from ..library import (
    OPEN_MODE_FOLDER_BROWSER,
    OPEN_MODE_PLAYLIST,
    OPEN_SOURCE_DIALOG_TITLE,
    OpenSourceDialog,
    build_supported_media_wildcard,
    is_playlist_source,
    is_remote_media_path,
    is_supported_media,
    playlist_display_name,
    save_playlist,
)
from ..playlists import ScreenTabState
from ..preferences import PreferencesDialog


class FrameCommandMixin:
    def _split_selected_files(self, paths):
        media_paths = []
        playlist_paths = []

        for path in paths:
            normalized_path = self._normalize_path(path)
            if not normalized_path or not os.path.isfile(normalized_path):
                continue

            if is_playlist_source(normalized_path):
                playlist_paths.append(normalized_path)
                continue

            if is_supported_media(normalized_path):
                media_paths.append(normalized_path)

        return media_paths, playlist_paths

    def on_open(self, _event):
        with wx.FileDialog(
            self,
            "Escolha um ou mais arquivos de mídia ou uma playlist",
            defaultDir=self._default_dialog_directory(),
            wildcard=build_supported_media_wildcard(include_playlists=True),
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST | wx.FD_MULTIPLE,
        ) as dialog:
            if dialog.ShowModal() == wx.ID_CANCEL:
                return
            paths = dialog.GetPaths()

        if not paths:
            return

        self._open_selected_files(paths, dialog_title="Abrir arquivos")

    def on_open_folder(self, _event):
        with wx.DirDialog(
            self,
            "Escolha uma pasta para navegar",
            defaultPath=self._default_dialog_directory(),
            style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST,
        ) as dialog:
            if dialog.ShowModal() == wx.ID_CANCEL:
                return
            folder_path = dialog.GetPath()

        self._open_folder_path(folder_path)

    def on_open_source(self, _event):
        self._show_open_source_dialog(initial_mode=OPEN_MODE_PLAYLIST)

    def on_copy_current_item_path(self, _event):
        if isinstance(self._get_tab_state(), ScreenTabState):
            return

        browser = self._get_browser_panel()
        selected_items = browser.get_selected_item_paths() if browser else []
        if not selected_items:
            self._announce("Nenhum item selecionado para copiar.")
            return

        if not self._copy_text_to_clipboard("\n".join(selected_items)):
            self._announce("Não foi possível acessar a área de transferência.")
            return

        if len(selected_items) == 1 and is_remote_media_path(selected_items[0]):
            self._announce("Link copiado.")
        elif len(selected_items) == 1:
            self._announce("Caminho copiado.")
        else:
            self._announce(f"{len(selected_items)} itens copiados.")

    def on_paste_open_from_clipboard(self, _event):
        if isinstance(self._get_tab_state(), ScreenTabState):
            return

        text = self._read_text_from_clipboard()
        if not text:
            self._announce("A área de transferência está vazia.")
            return

        self._open_from_clipboard_text(text, force_new_playlist=False)

    def on_paste_open_from_clipboard_new_playlist(self, _event):
        if isinstance(self._get_tab_state(), ScreenTabState):
            return

        text = self._read_text_from_clipboard()
        if not text:
            self._announce("A área de transferência está vazia.")
            return

        self._open_from_clipboard_text(text, force_new_playlist=True)

    def _copy_text_to_clipboard(self, text):
        if not text or not wx.TheClipboard.Open():
            return False
        try:
            wx.TheClipboard.SetData(wx.TextDataObject(text))
        finally:
            wx.TheClipboard.Close()
        return True

    def _read_text_from_clipboard(self):
        if not wx.TheClipboard.Open():
            return ""
        try:
            data = wx.TextDataObject()
            if not wx.TheClipboard.GetData(data):
                return ""
            return (data.GetText() or "").strip()
        finally:
            wx.TheClipboard.Close()

    def _open_from_clipboard_text(self, text, *, force_new_playlist=False):
        normalized_lines = [
            str(line or "").strip().strip('"').strip("'")
            for line in str(text or "").replace("\r", "\n").split("\n")
        ]
        normalized_sources = [line for line in normalized_lines if line]
        if not normalized_sources:
            self._announce("A área de transferência está vazia.")
            return

        if len(normalized_sources) > 1:
            media_sources = []
            for source in normalized_sources:
                if is_remote_media_path(source):
                    if is_playlist_source(source):
                        self._announce("A área de transferência contém playlists misturadas com múltiplos itens. Use apenas mídias ou links.")
                        return
                    media_sources.append(source)
                    continue

                normalized_local = self._normalize_path(source)
                if normalized_local and os.path.isfile(normalized_local):
                    if is_playlist_source(normalized_local):
                        self._announce("A área de transferência contém playlists misturadas com múltiplos itens. Use apenas mídias ou links.")
                        return
                    media_sources.append(normalized_local)
                    continue

                self._announce("A área de transferência contém itens não suportados para colagem em lote.")
                return

            open_media = self._open_media_paths if force_new_playlist else self._open_external_media_paths
            if not open_media(media_sources):
                self._announce("Não foi possível abrir a mídia da área de transferência.")
            return

        normalized_source = normalized_sources[0]

        if is_remote_media_path(normalized_source):
            if is_playlist_source(normalized_source):
                if not self._open_playlist_source(normalized_source):
                    self._announce("Não foi possível abrir a playlist da área de transferência.")
                return

            open_media = self._open_media_paths if force_new_playlist else self._open_external_media_paths
            if not open_media([normalized_source]):
                self._announce("Não foi possível abrir a mídia da área de transferência.")
            return

        normalized_local = self._normalize_path(normalized_source)
        if normalized_local:
            if os.path.isdir(normalized_local):
                if not self._open_folder_path(normalized_local):
                    self._announce("Não foi possível abrir a pasta da área de transferência.")
                return

            if os.path.isfile(normalized_local):
                if is_playlist_source(normalized_local):
                    if not self._open_playlist_source(normalized_local):
                        self._announce("Não foi possível abrir a playlist da área de transferência.")
                    return

                open_media = self._open_media_paths if force_new_playlist else self._open_external_media_paths
                if not open_media([normalized_local]):
                    self._announce("Não foi possível abrir a mídia da área de transferência.")
                return

        self._announce("Conteúdo da área de transferência não suportado.")

    def _show_open_source_dialog(self, initial_source="", initial_mode=OPEN_MODE_PLAYLIST):
        source_value = initial_source
        open_mode = initial_mode

        while True:
            dialog = OpenSourceDialog(
                self,
                default_dir=self._default_dialog_directory(),
                initial_source=source_value,
                initial_mode=open_mode,
            )
            try:
                if dialog.ShowModal() == wx.ID_CANCEL:
                    return
                source_value = dialog.get_source()
                open_mode = dialog.get_open_mode()
            finally:
                dialog.Destroy()

            if self._open_source_from_dialog(source_value, open_mode):
                return

    def _open_selected_files(self, paths, dialog_title="Abrir arquivos"):
        media_paths, playlist_paths = self._split_selected_files(paths)

        if playlist_paths and media_paths:
            wx.MessageBox(
                "Selecione uma única playlist ou apenas arquivos de mídia.",
                dialog_title,
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            return False

        if len(playlist_paths) > 1:
            wx.MessageBox(
                "Selecione apenas uma playlist por vez.",
                dialog_title,
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            return False

        if playlist_paths:
            return self._open_playlist_source(playlist_paths[0])

        if media_paths:
            return self._open_media_paths(media_paths)

        wx.MessageBox(
            "Nenhum arquivo de mídia ou playlist compatível foi selecionado.",
            dialog_title,
            wx.OK | wx.ICON_WARNING,
            self,
        )
        return False

    def _open_external_files(self, paths):
        media_paths, playlist_paths = self._split_selected_files(paths)

        if playlist_paths and media_paths:
            self._announce("Arquivos externos mistos não foram abertos. Use apenas mídias ou uma playlist.")
            return False

        if len(playlist_paths) > 1:
            self._announce("A abertura externa aceita apenas uma playlist por vez.")
            return False

        if media_paths:
            return self._open_external_media_paths(media_paths)

        if playlist_paths:
            return self._open_playlist_source(playlist_paths[0])

        self._announce("Nenhum arquivo compatível foi recebido do Explorador.")
        return False

    def _open_source_from_dialog(self, source_value, open_mode):
        normalized_source = str(source_value or "").strip()
        if not normalized_source:
            wx.MessageBox(
                "Informe um caminho local, uma pasta ou um link de mídia.",
                OPEN_SOURCE_DIALOG_TITLE,
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            return False

        normalized_local_source = ""
        if not is_remote_media_path(normalized_source):
            normalized_local_source = self._normalize_path(normalized_source)

        if open_mode == OPEN_MODE_FOLDER_BROWSER:
            if normalized_local_source and self._open_folder_path(normalized_local_source):
                return True

            wx.MessageBox(
                "Para abrir no navegador, informe uma pasta local válida.",
                OPEN_SOURCE_DIALOG_TITLE,
                wx.OK | wx.ICON_WARNING,
                self,
            )
            return False

        if normalized_local_source and os.path.isdir(normalized_local_source):
            if self._open_folder_as_playlist(normalized_local_source):
                return True

            wx.MessageBox(
                "Não foi possível abrir a pasta selecionada como playlist.",
                OPEN_SOURCE_DIALOG_TITLE,
                wx.OK | wx.ICON_ERROR,
                self,
            )
            return False

        if is_playlist_source(normalized_source):
            if self._open_playlist_source(normalized_source):
                return True

            wx.MessageBox(
                "Não foi possível abrir a playlist ou link informado.",
                OPEN_SOURCE_DIALOG_TITLE,
                wx.OK | wx.ICON_ERROR,
                self,
            )
            return False

        if (normalized_local_source and os.path.isfile(normalized_local_source)) or is_remote_media_path(normalized_source):
            if self._open_media_paths([normalized_source if is_remote_media_path(normalized_source) else normalized_local_source]):
                return True

            wx.MessageBox(
                "Não foi possível abrir a mídia informada.",
                OPEN_SOURCE_DIALOG_TITLE,
                wx.OK | wx.ICON_ERROR,
                self,
            )
            return False

        message = (
            "Não foi possível interpretar o link informado como mídia ou playlist."
            if is_remote_media_path(normalized_source)
            else "Informe uma pasta local, um arquivo existente, uma playlist .m3u/.m3u8 ou um link de mídia."
        )
        wx.MessageBox(message, OPEN_SOURCE_DIALOG_TITLE, wx.OK | wx.ICON_WARNING, self)
        return False

    def on_save_playlist(self, _event):
        state = self._get_playlist_state()
        if not state or not state.items:
            self._announce("A playlist atual está vazia.")
            return

        default_name = os.path.basename(state.source_path) if state.source_path else f"{state.title}.m3u8"
        default_dir = os.path.dirname(state.source_path) if state.source_path else self._default_dialog_directory()

        with wx.FileDialog(
            self,
            "Salvar playlist",
            wildcard=PLAYLIST_WILDCARD,
            defaultDir=default_dir,
            defaultFile=default_name,
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        ) as dialog:
            if dialog.ShowModal() == wx.ID_CANCEL:
                return
            playlist_path = dialog.GetPath()

        if not os.path.splitext(playlist_path)[1]:
            playlist_path += ".m3u8"

        save_playlist(playlist_path, state.items)
        self._remember_directory(playlist_path)
        state.source_path = playlist_path
        state.title = playlist_display_name(playlist_path)
        active_index = self._get_active_playlist_index()
        if active_index != wx.NOT_FOUND:
            self.notebook.SetPageText(active_index, state.title)
        self._update_title()
        self._refresh_playlist_browser()
        self._add_recent_path("recent_playlists", playlist_path)
        self._announce(f"Playlist salva: {state.title}.")
        if hasattr(self, "_set_status_message"):
            self._set_status_message(f"Playlist salva em {playlist_path}")

    def on_recent_menu_action(self, event):
        action = self._recent_menu_actions.get(event.GetId())
        if not action:
            event.Skip()
            return

        action_kind, attribute_name, path = action
        if action_kind == "clear":
            announcements = {
                "recent_media_files": "Arquivos recentes limpos.",
                "recent_folders": "Pastas recentes limpas.",
                "recent_playlists": "Playlists recentes limpas.",
            }
            self._clear_recent_paths(attribute_name, announcements.get(attribute_name, "Itens recentes limpos."))
            return

        if path and attribute_name == "recent_media_files":
            if self._open_media_paths([path]):
                return
        elif path and attribute_name == "recent_folders":
            if self._open_folder_path(path):
                return
        elif path and attribute_name == "recent_playlists":
            if self._open_playlist_path(path):
                return

        if path:
            self._remove_recent_path(attribute_name, path)
        self._announce("O item recente selecionado não está mais disponível.")

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
            self._announce("Parado.")
            if hasattr(self, "_set_status_message"):
                self._set_status_message("Parado.", auto_clear_ms=0)
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

    def on_announce_status(self, _event):
        self._announce_player_status()

    def on_close_current_media(self, _event):
        self._close_current_media()

    def on_close_current_tab(self, _event):
        self._close_current_tab()

    def on_toggle_playlist_browser(self, _event=None):
        self._toggle_navigation_mode()

    def on_playlist_browser_activate_item(self, item_index):
        state = self._get_playlist_state()
        if not state:
            return

        if state.is_folder_tab:
            entries = self._get_folder_entries(state)
            if not 0 <= item_index < len(entries):
                return

            target_entry = entries[item_index]
            previous_path = state.folder_current_path
            state.folder_selected_path = target_entry.path
            if target_entry.is_directory:
                selected_path = previous_path if target_entry.is_parent else None
                self._enter_folder_directory(target_entry.path, selected_path=selected_path, announce=True)
            else:
                if self._block_sensitive_action_during_youtube_music("track-selection"):
                    return
                self._preview_folder_file(target_entry.path, announce=True)
            return

        if not 0 <= item_index < len(state.items):
            return

        if self._block_sensitive_action_during_youtube_music("track-selection"):
            return

        state.select_index(item_index)
        self._play_media(index=self._get_active_playlist_index(), allow_crossfade=False)

    def on_playlist_browser_remove_item(self, item_indexes):
        self._remove_items_from_current_playlist(item_indexes)

    def on_playlist_browser_show_context_menu(self, browser_panel, anchor_window=None):
        if browser_panel is None:
            return False

        selected_paths = list(browser_panel.get_selected_item_paths())
        selected_count = len(selected_paths)
        menu = wx.Menu()

        copy_item = menu.Append(wx.ID_ANY, "Copiar seleção")
        paste_item = menu.Append(wx.ID_ANY, "Colar na playlist atual")
        paste_new_item = menu.Append(wx.ID_ANY, "Colar em nova playlist")
        menu.AppendSeparator()
        remove_item = menu.Append(wx.ID_ANY, "Remover seleção")
        menu.AppendSeparator()
        like_item = menu.Append(wx.ID_ANY, "Curtir no YouTube Music")
        dislike_item = menu.Append(wx.ID_ANY, "Não gostei no YouTube Music")

        current_state = self._get_playlist_state()
        can_edit_playlist = bool(current_state and not current_state.is_folder_tab and not current_state.is_loading)
        has_youtube_items = any(is_remote_media_path(path) and "youtube" in path.lower() for path in selected_paths)
        like_rateable_paths = self._selected_youtube_music_media_paths_to_rate(selected_paths, "LIKE")
        dislike_rateable_paths = self._selected_youtube_music_media_paths_to_rate(selected_paths, "DISLIKE")

        copy_item.Enable(selected_count > 0)
        remove_item.Enable(selected_count > 0 and can_edit_playlist)
        like_item.Enable(has_youtube_items and bool(like_rateable_paths))
        dislike_item.Enable(has_youtube_items and bool(dislike_rateable_paths))

        menu.Bind(wx.EVT_MENU, lambda _event: self.on_copy_current_item_path(None), id=copy_item.GetId())
        menu.Bind(wx.EVT_MENU, lambda _event: self.on_paste_open_from_clipboard(None), id=paste_item.GetId())
        menu.Bind(
            wx.EVT_MENU,
            lambda _event: self.on_paste_open_from_clipboard_new_playlist(None),
            id=paste_new_item.GetId(),
        )
        menu.Bind(
            wx.EVT_MENU,
            lambda _event: self._remove_items_from_current_playlist(browser_panel.get_selected_indexes()),
            id=remove_item.GetId(),
        )
        rate_selected = getattr(self, "_rate_selected_playlist_items", None)
        if callable(rate_selected):
            menu.Bind(
                wx.EVT_MENU,
                lambda _event, media_paths=tuple(selected_paths): rate_selected(media_paths, "LIKE"),
                id=like_item.GetId(),
            )
            menu.Bind(
                wx.EVT_MENU,
                lambda _event, media_paths=tuple(selected_paths): rate_selected(media_paths, "DISLIKE"),
                id=dislike_item.GetId(),
            )

        popup_parent = anchor_window or browser_panel
        try:
            popup_parent.PopupMenu(menu)
        finally:
            menu.Destroy()
        return True

    def on_playlist_browser_preview_item(self, item_index):
        state = self._get_playlist_state()
        if not state or not state.is_folder_tab:
            return

        entries = self._get_folder_entries(state)
        if not 0 <= item_index < len(entries):
            return

        target_entry = entries[item_index]
        state.folder_selected_path = target_entry.path
        if target_entry.is_file:
            self._preview_folder_file(target_entry.path, announce=False)
            return

        self._refresh_playlist_browser()

    def on_playlist_browser_go_back(self):
        self._go_back_folder()

    def on_next_tab(self, _event):
        self._cycle_tabs(1)

    def on_previous_tab(self, _event):
        self._cycle_tabs(-1)

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
            self._announce("Preferências salvas.")
        else:
            self._announce("Preferências salvas, mas o dispositivo de áudio anterior foi mantido.")

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

    def on_crossfade_timer(self, _event):
        self._handle_playback_timer_tick()

    def on_video_panel_resize(self, _event):
        self._bind_player_to_window()
        self._refresh_player_visual_hints()

    def on_video_panel_focus(self, _event):
        wx.CallAfter(self.SetFocus)

    def _window_is_descendant_of(self, window, ancestor):
        current_window = window
        while isinstance(current_window, wx.Window):
            if current_window == ancestor:
                return True
            current_window = current_window.GetParent()

        return False

    def _screen_tab_focusable_windows(self, root_window):
        focusable_windows = []

        def collect(window):
            if not isinstance(window, wx.Window):
                return

            for child in window.GetChildren():
                collect(child)

            if window is root_window:
                return

            if not window.IsShownOnScreen() or not window.IsEnabled():
                return

            accepts_focus = False
            try:
                if not isinstance(window, (wx.Panel, wx.StaticBox, wx.CollapsiblePane)):
                    accepts_focus = bool(window.CanAcceptFocusFromKeyboard() or window.CanAcceptFocus())
            except Exception:
                accepts_focus = False

            if accepts_focus:
                focusable_windows.append(window)

        collect(root_window)
        return focusable_windows

    def _focus_screen_tab_edge_control(self, current_page, *, backward=False):
        focusable_windows = self._screen_tab_focusable_windows(current_page)
        if not focusable_windows:
            return False

        target_window = focusable_windows[-1] if backward else focusable_windows[0]
        try:
            target_window.SetFocus()
            return True
        except Exception:
            return False

    def _navigate_screen_tab_controls(self, *, backward=False):
        current_page = self.notebook.GetCurrentPage() if hasattr(self, "notebook") else None
        if not isinstance(current_page, wx.Window):
            return False

        focusable = self._screen_tab_focusable_windows(current_page)
        if not focusable:
            return False

        focused_window = wx.Window.FindFocus()
        focused_idx = -1
        for i, w in enumerate(focusable):
            if w == focused_window or self._window_is_descendant_of(focused_window, w):
                focused_idx = i
                break

        if focused_idx != -1:
            if backward:
                if focused_idx == 0:
                    try:
                        self.notebook.SetFocus()
                        return True
                    except Exception:
                        return False
                target = focusable[focused_idx - 1]
            else:
                if focused_idx == len(focusable) - 1:
                    try:
                        self.notebook.SetFocus()
                        return True
                    except Exception:
                        return False
                target = focusable[focused_idx + 1]
            try:
                target.SetFocus()
                return True
            except Exception:
                return False
        else:
            return self._focus_screen_tab_edge_control(current_page, backward=backward)

    def _handle_screen_tab_key_down(self, event, current_tab):
        if not isinstance(current_tab, ScreenTabState):
            return False

        key_code = event.GetKeyCode()

        if key_code == wx.WXK_ESCAPE:
            self._close_current_tab()
            return True

        if key_code == wx.WXK_TAB and not event.ControlDown() and not event.AltDown():
            if self._navigate_screen_tab_controls(backward=event.ShiftDown()):
                return True
            event.Skip()
            return True

        event.Skip()
        return True

    def on_key_down(self, event):
        key_code = event.GetKeyCode()
        browser = self._get_browser_panel()
        current_tab = self._get_tab_state()

        if key_code == wx.WXK_F1:
            self.on_show_keyboard_help(None)
            return

        if event.ControlDown() and event.ShiftDown() and key_code in (ord("Y"), ord("y")):
            self.on_open_youtube_music(None)
            return

        if key_code == wx.WXK_ESCAPE and isinstance(current_tab, ScreenTabState):
            self._close_current_tab()
            return

        if event.ControlDown() and key_code == wx.WXK_TAB:
            self._cycle_tabs(-1 if event.ShiftDown() else 1)
            return

        if self._handle_screen_tab_key_down(event, current_tab):
            return

        if event.ControlDown() and not event.AltDown() and key_code in (ord("C"), ord("c")):
            if not event.ShiftDown():
                self.on_copy_current_item_path(None)
                return

        if event.ControlDown() and not event.ShiftDown() and not event.AltDown() and key_code in (ord("V"), ord("v")):
            self.on_paste_open_from_clipboard(None)
            return

        if event.ControlDown() and event.ShiftDown() and not event.AltDown() and key_code in (ord("V"), ord("v")):
            self.on_paste_open_from_clipboard_new_playlist(None)
            return

        if browser and browser.is_item_navigation_active():
            if key_code == wx.WXK_TAB and not event.ControlDown() and not event.AltDown():
                self._toggle_navigation_mode()
                return
            event.Skip()
            return

        if not event.ControlDown() and not event.AltDown() and key_code in (ord("E"), ord("e")):
            self._toggle_shuffle()
            return

        if not event.ControlDown() and not event.AltDown() and key_code in (ord("R"), ord("r")):
            self._cycle_repeat_mode()
            return

        if not event.ControlDown() and not event.AltDown() and key_code in (ord("A"), ord("a")):
            self._toggle_related_autoplay()
            return

        if event.AltDown() and not event.ControlDown() and key_code == wx.WXK_UP:
            self._move_current_item(-1)
            return

        if event.AltDown() and not event.ControlDown() and key_code == wx.WXK_DOWN:
            self._move_current_item(1)
            return

        if event.AltDown() and not event.ControlDown() and key_code == wx.WXK_LEFT:
            self._play_adjacent_item(-1)
            return

        if event.AltDown() and not event.ControlDown() and key_code == wx.WXK_RIGHT:
            self._play_adjacent_item(1)
            return

        if event.AltDown() and not event.ControlDown() and key_code == wx.WXK_HOME:
            self._jump_to_playlist_boundary(to_last=False)
            return

        if event.AltDown() and not event.ControlDown() and key_code == wx.WXK_END:
            self._jump_to_playlist_boundary(to_last=True)
            return

        if event.ControlDown() and key_code == wx.WXK_PAGEUP:
            self._play_adjacent_item(-1)
            return

        if event.ControlDown() and key_code == wx.WXK_PAGEDOWN:
            self._play_adjacent_item(1)
            return

        if event.ControlDown() and key_code in (ord("T"), ord("t")):
            self.on_new_playlist(None)
            return

        if event.ControlDown() and event.AltDown() and not event.ShiftDown() and key_code in (ord("O"), ord("o")):
            self.on_open_source(None)
            return

        if event.ControlDown() and event.ShiftDown() and key_code in (ord("E"), ord("e")):
            self.on_open_equalizer(None)
            return

        if event.ControlDown() and event.ShiftDown() and key_code in (ord("S"), ord("s")):
            self.on_save_playlist(None)
            return

        if event.ControlDown() and key_code in (ord("L"), ord("l")):
            if event.ShiftDown():
                rate_current_youtube_music_media = getattr(self, "_rate_current_youtube_music_media", None)
                if callable(rate_current_youtube_music_media):
                    rate_current_youtube_music_media("DISLIKE")
                    return
            else:
                rate_current_youtube_music_media = getattr(self, "_rate_current_youtube_music_media", None)
                if callable(rate_current_youtube_music_media):
                    rate_current_youtube_music_media("LIKE")
                    return

        if event.ControlDown() and key_code in (ord("B"), ord("b")):
            self.on_toggle_playlist_browser(None)
            return

        if event.ControlDown() and key_code == ord(","):
            self.on_open_preferences(None)
            return

        if event.ControlDown() and event.ShiftDown() and key_code in (ord("W"), ord("w")):
            self._close_current_media()
            return

        if event.ControlDown() and key_code in (ord("W"), ord("w")):
            self.on_close_current_tab(None)
            return

        if not event.ControlDown() and not event.AltDown() and key_code in (ord("T"), ord("t")):
            self._announce_playback_time()
            return

        if not event.ControlDown() and not event.AltDown() and key_code in (ord("V"), ord("v")):
            self._announce_current_volume()
            return

        if not event.ControlDown() and not event.AltDown() and key_code in (ord("S"), ord("s")):
            self._announce_player_status()
            return

        if key_code == wx.WXK_TAB:
            self._toggle_navigation_mode()
            return

        if key_code == wx.WXK_SPACE:
            self._toggle_play_pause()
            return

        if key_code == wx.WXK_HOME:
            self._seek_to_start()
            return

        if key_code == wx.WXK_END:
            self._seek_to_end()
            return

        if not event.ControlDown() and event.ShiftDown() and key_code == wx.WXK_LEFT:
            self._seek_relative(-LARGE_SEEK_STEP_MS)
            return

        if not event.ControlDown() and event.ShiftDown() and key_code == wx.WXK_RIGHT:
            self._seek_relative(LARGE_SEEK_STEP_MS)
            return

        if key_code == wx.WXK_LEFT:
            self._seek_relative(-self.settings.seek_step_ms)
            return

        if key_code == wx.WXK_RIGHT:
            self._seek_relative(self.settings.seek_step_ms)
            return

        if key_code == wx.WXK_UP:
            self._change_volume(self.settings.volume_step)
            return

        if key_code == wx.WXK_DOWN:
            self._change_volume(-self.settings.volume_step)
            return

        event.Skip()

    def on_exit(self, _event):
        self.Close()

    def on_close(self, event):
        if not getattr(self, "_update_restart_pending", False) and self.settings.confirm_on_exit and event.CanVeto():
            with wx.MessageDialog(
                self,
                "Deseja realmente sair do KeyTune?",
                "Confirmar saída",
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
