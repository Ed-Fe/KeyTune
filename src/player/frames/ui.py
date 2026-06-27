from pathlib import Path
import sys

import wx

from ..accessibility import attach_named_accessible
from ..constants import CROSSFADE_TIMER_INTERVAL_MS, PROGRESS_GAUGE_RANGE, PROGRESS_TIMER_INTERVAL_MS
from ..library import PlaylistBrowserPanel, is_audio_playback_media


class FrameUIMixin:
    def _manual_candidate_paths(self):
        candidates = []

        if getattr(sys, "frozen", False):
            executable_dir = Path(sys.executable).resolve().parent
            candidates.append(executable_dir / "docs" / "manual.html")

        repo_root = Path(__file__).resolve().parents[3]
        candidates.append(repo_root / "docs" / "manual.html")
        candidates.append(Path.cwd() / "docs" / "manual.html")
        candidates.append(repo_root / "docs" / "manual.md")
        candidates.append(Path.cwd() / "docs" / "manual.md")

        unique_candidates = []
        seen = set()
        for candidate in candidates:
            normalized_candidate = str(candidate)
            if normalized_candidate in seen:
                continue
            seen.add(normalized_candidate)
            unique_candidates.append(candidate)
        return unique_candidates

    def _open_manual_document(self):
        manual_path = next((path for path in self._manual_candidate_paths() if path.is_file()), None)
        if manual_path is None:
            wx.MessageBox(
                "Não foi possível localizar o manual do KeyTune. Gere a versão HTML da release ou verifique a pasta docs do projeto.",
                "Manual do KeyTune",
                wx.OK | wx.ICON_ERROR,
                self,
            )
            return False

        try:
            launched = wx.LaunchDefaultBrowser(manual_path.resolve().as_uri())
        except Exception:
            launched = False

        if not launched:
            wx.MessageBox(
                "Não foi possível abrir o manual do KeyTune no visualizador padrão do sistema.",
                "Manual do KeyTune",
                wx.OK | wx.ICON_ERROR,
                self,
            )
            return False

        self._set_status_message(f"Abrindo manual: {manual_path.name}")
        return True

    def _primary_shortcuts_hint_text(self):
        return (
            "Atalhos principais: Ctrl+Alt+O abrir mídia, playlist ou pasta · Ctrl+O abrir arquivos ou playlist · Ctrl+Shift+O abrir pasta · "
            "Espaço reproduzir/pausar · ←/→ buscar · ↑/↓ volume · Tab itens/player · Ctrl+Shift+Y central do YouTube Music (opcional) · F1 ajuda"
        )

    def _player_overlay_hint_text(self):
        return (
            "Sem mídia carregada\n\n"
            "Ctrl+Alt+O abre mídia, playlist ou pasta\n"
            "Ctrl+O abre arquivos ou playlist\n"
            "Ctrl+Shift+O abre uma pasta no navegador\n"
            "Espaço reproduz ou pausa\n"
            "Tab alterna entre itens e player\n"
            "Ctrl+Shift+Y abre a central do YouTube Music quando a integração opcional estiver ativada\n"
            "F1 mostra a ajuda rápida de atalhos"
        )

    def _player_audio_only_text(self):
        return (
            "Saída de vídeo desativada\n\n"
            "Esta mídia está tocando só o áudio.\n"
            "Abra Preferências > Reprodução para reativar o vídeo quando quiser."
        )

    def _player_overlay_text_for_state(self, state):
        if not state or not getattr(state, "current_media_path", None):
            return self._player_overlay_hint_text()

        if (
            getattr(self.settings, "disable_video_output", False)
            and not is_audio_playback_media(state.current_media_path)
        ):
            return self._player_audio_only_text()

        return ""

    def _keyboard_help_text(self):
        return (
            "Ajuda rápida de atalhos\n\n"
            "Arquivos e playlists\n"
            "Ctrl+Alt+O — Abrir mídia, playlist ou pasta\n"
            "Ctrl+O — Abrir arquivos de mídia ou uma playlist local\n"
            "Ctrl+Shift+O — Abrir pasta no navegador\n"
            "Ctrl+C — Copiar caminho ou link do item selecionado\n"
            "Ctrl+V — Colar e adicionar a mídia ou link na playlist atual quando possível\n"
            "Ctrl+Shift+V — Colar e abrir em uma nova playlist\n"
            "Ctrl+Shift+S — Salvar playlist atual\n"
            "Ctrl+T — Nova playlist\n"
            "Ctrl+W — Fechar aba ou playlist atual\n"
            "Ctrl+Shift+W — Fechar mídia atual\n\n"
            "Reprodução\n"
            "Espaço — Play/Pause\n"
            "Seta esquerda / direita — Voltar ou avançar no arquivo\n"
            "Shift+Seta esquerda / direita — Voltar ou avançar 1 minuto\n"
            "Home / End — Ir para o início ou para o fim\n"
            "Seta cima / baixo — Aumentar ou diminuir o volume\n"
            "Menu Reprodução > Dispositivo de áudio — Trocar a saída de som\n"
            "Ctrl+PageUp / Ctrl+PageDown — Faixa anterior ou próxima\n"
            "Alt+Seta esquerda / direita — Faixa anterior ou próxima na playlist\n"
            "Alt+Seta cima / baixo — Mover o item atual na playlist\n"
            "Alt+Home / End — Ir para o primeiro ou último item da playlist\n"
            "Ctrl+L — Curtir mídia atual no YouTube Music\n"
            "Ctrl+Shift+L — Marcar mídia atual como não gostei no YouTube Music\n"
            "Ctrl+Shift+A — Adicionar a mídia atual a uma playlist do YouTube Music\n"
            "E — Alternar modo aleatório\n"
            "R — Alternar modo de repetição\n"
            "T — Anunciar tempo\n"
            "V — Anunciar volume\n"
            "S — Anunciar status\n\n"
            "Navegação\n"
            "Tab — Alternar entre a lista de itens e o player\n"
            "Ctrl+B — Alternar foco entre a lista de itens e o player\n"
            "Ctrl+Shift+Y — Abrir a central do YouTube Music em uma aba, quando a integração estiver ativada\n"
            "Enter — Tocar ou abrir o item selecionado no navegador\n"
            "Delete — Remover item da playlist\n"
            "Backspace — Voltar de pasta no navegador\n"
            "Digite letras ou números — Ir rapidamente para itens com esse início\n"
            "Ctrl+Tab / Ctrl+Shift+Tab — Próxima ou aba anterior\n"
            "F1 — Mostrar esta ajuda"
        )

    def _refresh_shortcuts_hint_layout(self):
        if not hasattr(self, "shortcuts_hint_label") or not hasattr(self, "progress_panel"):
            return

        wrap_width = max(320, self.progress_panel.GetClientSize().Width - 24)
        self.shortcuts_hint_label.Wrap(wrap_width)
        self.progress_panel.Layout()

    def _refresh_player_visual_hints(self):
        if not hasattr(self, "notebook"):
            return

        for index in range(self.notebook.GetPageCount()):
            page = self.notebook.GetPage(index)
            video_panel = getattr(page, "video_panel", None)
            video_hint_overlay = getattr(page, "video_hint_overlay", None)
            if not video_panel or not video_hint_overlay:
                continue

            playlist_state = self._get_playlist_state(index)
            overlay_text = self._player_overlay_text_for_state(playlist_state)
            show_overlay = bool(overlay_text)
            if video_hint_overlay.GetLabel() != overlay_text:
                video_hint_overlay.SetLabel(overlay_text)
                page.video_hint_wrap_width = None
            if video_hint_overlay.IsShown() != show_overlay:
                video_hint_overlay.Show(show_overlay)

            if show_overlay:
                wrap_width = max(260, video_panel.GetClientSize().Width - 80)
                if getattr(page, "video_hint_wrap_width", None) != wrap_width:
                    video_hint_overlay.Wrap(wrap_width)
                    page.video_hint_wrap_width = wrap_width
            self._layout_video_page(page)

    def _layout_video_page(self, page):
        video_panel = getattr(page, "video_panel", None)
        video_surface = getattr(page, "video_surface", None)
        video_hint_overlay = getattr(page, "video_hint_overlay", None)
        if not video_panel:
            return

        if video_surface is not None:
            panel_size = video_panel.GetClientSize()
            video_surface.SetSize(0, 0, panel_size.Width, panel_size.Height)

        if video_hint_overlay is None or not video_hint_overlay.IsShown():
            return

        panel_size = video_panel.GetClientSize()
        overlay_size = video_hint_overlay.GetBestSize()
        position_x = max(24, (panel_size.Width - overlay_size.Width) // 2)
        position_y = max(24, (panel_size.Height - overlay_size.Height) // 2)
        video_hint_overlay.SetPosition((position_x, position_y))
        video_hint_overlay.Raise()

    def _on_progress_panel_size(self, event):
        self._refresh_shortcuts_hint_layout()
        event.Skip()

    def _show_keyboard_help_dialog(self):
        dialog = wx.Dialog(
            self,
            title="Ajuda rápida de atalhos",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        dialog.SetMinSize((520, 420))

        root_sizer = wx.BoxSizer(wx.VERTICAL)
        instructions = wx.TextCtrl(
            dialog,
            value=self._keyboard_help_text(),
            style=wx.TE_MULTILINE | wx.TE_READONLY,
        )
        instructions.SetName("Ajuda rápida de atalhos")
        instructions.SetHelpText("Lista os atalhos principais do player e do navegador de itens.")
        instructions.SetInsertionPoint(0)

        button_sizer = dialog.CreateStdDialogButtonSizer(wx.OK)
        if button_sizer is not None:
            ok_button = dialog.FindWindowById(wx.ID_OK)
            if ok_button is not None:
                ok_button.SetLabel("F&echar")

        root_sizer.Add(instructions, 1, wx.ALL | wx.EXPAND, 12)
        if button_sizer is not None:
            root_sizer.Add(button_sizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.ALIGN_RIGHT, 12)

        dialog.SetSizerAndFit(root_sizer)
        dialog.SetSize((560, 460))
        try:
            dialog.ShowModal()
        finally:
            dialog.Destroy()

    def on_open_manual(self, _event):
        self._open_manual_document()

    def _build_menu_bar(self):
        menu_bar = wx.MenuBar()

        file_menu = wx.Menu()
        self.file_menu = file_menu
        self.menu_new_playlist_id = wx.NewIdRef()
        self.menu_open_file_id = wx.ID_OPEN
        self.menu_open_folder_id = wx.NewIdRef()
        self.menu_open_source_id = wx.NewIdRef()
        self.menu_youtube_music_login_id = wx.NewIdRef()
        self.menu_youtube_music_disconnect_id = wx.NewIdRef()
        self.menu_youtube_music_refresh_library_id = wx.NewIdRef()
        self.menu_open_youtube_music_id = wx.NewIdRef()
        self.menu_save_playlist_id = wx.NewIdRef()
        self.menu_close_media_id = wx.NewIdRef()
        self.menu_close_tab_id = wx.NewIdRef()
        self.menu_copy_current_item_path_id = wx.NewIdRef()
        self.menu_paste_open_from_clipboard_id = wx.NewIdRef()
        self.menu_paste_open_from_clipboard_new_playlist_id = wx.NewIdRef()
        self.recent_menu = wx.Menu()
        self.recent_files_menu = wx.Menu()
        self.recent_folders_menu = wx.Menu()
        self.recent_playlists_menu = wx.Menu()
        file_menu.Append(self.menu_open_source_id, "Abrir &Mídia, Playlist ou Pasta...\tCtrl+Alt+O")
        file_menu.Append(self.menu_open_file_id, "Abrir &Arquivos ou Playlist...\tCtrl+O")
        file_menu.Append(self.menu_open_folder_id, "Abrir &Pasta...\tCtrl+Shift+O")
        file_menu.AppendSeparator()
        file_menu.Append(self.menu_copy_current_item_path_id, "&Copiar caminho do item (Ctrl+C)")
        file_menu.Append(self.menu_paste_open_from_clipboard_id, "Co&lar na playlist atual / abrir... (Ctrl+V)")
        file_menu.Append(
            self.menu_paste_open_from_clipboard_new_playlist_id,
            "Colar e abrir em &nova playlist... (Ctrl+Shift+V)",
        )
        file_menu.AppendSeparator()
        self.recent_menu.AppendSubMenu(self.recent_files_menu, "Arquivos recentes")
        self.recent_menu.AppendSubMenu(self.recent_folders_menu, "Pastas recentes")
        self.recent_menu.AppendSubMenu(self.recent_playlists_menu, "Playlists recentes")
        file_menu.AppendSubMenu(self.recent_menu, "&Recentes")
        file_menu.AppendSeparator()
        file_menu.Append(self.menu_save_playlist_id, "Salvar Playli&st\tCtrl+Shift+S")
        file_menu.Append(self.menu_close_media_id, "Fechar Mí&dia\tCtrl+Shift+W")
        file_menu.AppendSeparator()
        file_menu.Append(wx.ID_EXIT, "&Sair\tAlt+F4")

        playback_menu = wx.Menu()
        self.playback_menu = playback_menu
        self.menu_previous_track_id = wx.NewIdRef()
        self.menu_play_pause_id = wx.NewIdRef()
        self.menu_stop_id = wx.NewIdRef()
        self.menu_next_track_id = wx.NewIdRef()
        self.menu_add_to_youtube_playlist_id = wx.NewIdRef()
        self.menu_open_equalizer_id = wx.NewIdRef()
        self.menu_toggle_shuffle_id = wx.NewIdRef()
        self.menu_cycle_repeat_id = wx.NewIdRef()
        self.menu_announce_time_id = wx.NewIdRef()
        self.menu_announce_volume_id = wx.NewIdRef()
        self.menu_announce_status_id = wx.NewIdRef()
        self.menu_refresh_audio_output_devices_id = wx.NewIdRef()
        self.audio_output_menu = wx.Menu()
        self._audio_output_menu_actions = {}
        self._audio_output_menu_ids = []
        announce_menu = wx.Menu()
        playback_menu.Append(self.menu_previous_track_id, "Faixa &Anterior\tCtrl+PageUp")
        playback_menu.Append(self.menu_play_pause_id, "Reproduzir / Pa&usar\tEspaço")
        playback_menu.Append(self.menu_stop_id, "P&arar\tCtrl+.")
        playback_menu.Append(self.menu_next_track_id, "Próxima Fai&xa\tCtrl+PageDown")
        playback_menu.AppendSeparator()
        playback_menu.Append(self.menu_add_to_youtube_playlist_id, "Adicionar à Playlist do &YouTube Music\tCtrl+Shift+A")
        playback_menu.AppendSeparator()
        playback_menu.Append(self.menu_toggle_shuffle_id, "Em&baralhar (E)")
        playback_menu.Append(self.menu_cycle_repeat_id, "Modo de &Repetição (R)")
        playback_menu.AppendSubMenu(self.audio_output_menu, "Dispositivo de áu&dio")
        announce_menu.Append(self.menu_announce_time_id, "Anunciar &Tempo (T)")
        announce_menu.Append(self.menu_announce_volume_id, "Anunciar &Volume (V)")
        announce_menu.Append(self.menu_announce_status_id, "Anunciar &Status (S)")
        playback_menu.AppendSubMenu(announce_menu, "&Anunciar")

        view_menu = wx.Menu()
        self.view_menu = view_menu
        self.menu_playlist_browser_id = wx.NewIdRef()
        view_menu.Append(self.menu_playlist_browser_id, "Alternar foco entre &itens e player\tTab")
        view_menu.Append(self.menu_open_equalizer_id, "Eq&ualizador por aba\tCtrl+Shift+E")
        view_menu.Append(self.menu_open_youtube_music_id, "YouTube &Music por aba\tCtrl+Shift+Y")

        tabs_menu = wx.Menu()
        self.menu_next_tab_id = wx.NewIdRef()
        self.menu_previous_tab_id = wx.NewIdRef()
        tabs_menu.Append(self.menu_new_playlist_id, "&Nova playlist\tCtrl+T")
        tabs_menu.AppendSeparator()
        tabs_menu.Append(self.menu_next_tab_id, "Próxima A&ba\tCtrl+Tab")
        tabs_menu.Append(self.menu_previous_tab_id, "Aba A&nterior\tCtrl+Shift+Tab")
        tabs_menu.AppendSeparator()
        tabs_menu.Append(self.menu_close_tab_id, "Fechar A&ba / Playlist\tCtrl+W")

        settings_menu = wx.Menu()
        self.menu_check_updates_id = wx.NewIdRef()
        self.menu_preferences_id = wx.NewIdRef()
        settings_menu.Append(self.menu_preferences_id, "&Preferências\tCtrl+,")

        help_menu = wx.Menu()
        self.menu_open_manual_id = wx.NewIdRef()
        self.menu_keyboard_help_id = wx.NewIdRef()
        help_menu.Append(self.menu_open_manual_id, "Abrir &manual do usuário")
        help_menu.AppendSeparator()
        help_menu.Append(self.menu_keyboard_help_id, "Ajuda rápida de &atalhos\tF1")
        help_menu.AppendSeparator()
        help_menu.Append(self.menu_check_updates_id, "Verificar &atualizações")

        menu_bar.Append(file_menu, "&Arquivo")
        menu_bar.Append(playback_menu, "&Reprodução")
        menu_bar.Append(view_menu, "&Exibir")
        menu_bar.Append(tabs_menu, "A&bas")
        menu_bar.Append(settings_menu, "Con&figurações")
        menu_bar.Append(help_menu, "A&juda")
        self.SetMenuBar(menu_bar)
        self._refresh_recent_menus()
        self._refresh_audio_output_menu()

    def _refresh_audio_output_menu(self, announce=False):
        if not hasattr(self, "audio_output_menu"):
            return

        while self.audio_output_menu.GetMenuItemCount():
            self.audio_output_menu.Delete(self.audio_output_menu.FindItemByPosition(0))

        self._audio_output_menu_actions = {}
        self._audio_output_menu_ids = []

        default_item = self.audio_output_menu.AppendRadioItem(wx.NewIdRef(), "&Padrão do sistema")
        default_item_id = default_item.GetId()
        self._audio_output_menu_ids.append(default_item_id)
        self._audio_output_menu_actions[default_item_id] = ""
        self.Bind(wx.EVT_MENU, self.on_select_audio_output_device, id=default_item_id)

        devices = list(getattr(self, "_audio_output_devices", lambda: [])())
        current_device_id = getattr(self, "_current_audio_output_device_id", lambda: "")()
        default_item.Check(not current_device_id)

        if devices:
            self.audio_output_menu.AppendSeparator()
            for device in devices:
                item = self.audio_output_menu.AppendRadioItem(wx.NewIdRef(), device.menu_label)
                item_id = item.GetId()
                self._audio_output_menu_ids.append(item_id)
                self._audio_output_menu_actions[item_id] = device.device_id
                self.Bind(wx.EVT_MENU, self.on_select_audio_output_device, id=item_id)
                item.Check(device.device_id == current_device_id)
        else:
            unavailable_item = self.audio_output_menu.Append(wx.ID_ANY, "Nenhum dispositivo detectado agora")
            unavailable_item.Enable(False)

        self.audio_output_menu.AppendSeparator()
        self.audio_output_menu.Append(
            self.menu_refresh_audio_output_devices_id,
            "&Atualizar lista de dispositivos",
        )

        if announce:
            if devices:
                self._announce(f"Lista de dispositivos de áudio atualizada. {len(devices)} dispositivo(s) disponível(is).")
            else:
                self._announce("Lista de dispositivos de áudio atualizada, mas nenhum dispositivo foi detectado agora.")

    def _build_ui(self):
        panel = wx.Panel(self)
        root_sizer = wx.BoxSizer(wx.VERTICAL)

        self.notebook = wx.Notebook(panel)
        self.progress_panel = wx.Panel(panel)
        self.progress_label = wx.StaticText(self.progress_panel, label="Tempo: nenhuma mídia carregada.")
        self.progress_gauge = wx.Gauge(self.progress_panel, range=PROGRESS_GAUGE_RANGE, style=wx.GA_SMOOTH)
        self.shortcuts_hint_label = wx.StaticText(
            self.progress_panel,
            label=self._primary_shortcuts_hint_text(),
        )
        self.progress_timer = wx.Timer(self)
        self.crossfade_timer = wx.Timer(self)

        progress_sizer = wx.BoxSizer(wx.VERTICAL)
        progress_sizer.Add(self.progress_label, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 10)
        progress_sizer.Add(self.progress_gauge, 0, wx.ALL | wx.EXPAND, 10)
        progress_sizer.Add(self.shortcuts_hint_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)
        self.progress_panel.SetSizer(progress_sizer)

        self.progress_panel.SetName("Painel de tempo")
        self.progress_panel.SetHelpText(
            "Mostra o andamento da mídia atual com o tempo decorrido e a duração total quando disponível."
        )
        self.progress_label.SetName("Tempo da mídia")
        self.progress_label.SetHelpText(
            "Mostra o tempo decorrido e o tempo total da mídia atual."
        )
        self.progress_gauge.SetName("Barra de tempo")
        self.progress_gauge.SetHelpText(
            "Mostra visualmente o andamento da mídia atual sem alterar o foco do teclado."
        )
        self.shortcuts_hint_label.SetName("Dicas rápidas de atalhos")
        self.shortcuts_hint_label.SetHelpText(
            "Resume os atalhos mais usados para abrir mídia, controlar a reprodução e acessar a ajuda."
        )
        self.shortcuts_hint_label.SetForegroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT))
        attach_named_accessible(
            self.progress_label,
            name="Tempo da mídia",
            description="Mostra o tempo decorrido e a duração total da mídia atual.",
            value_provider=lambda: self.progress_label.GetLabel(),
        )
        attach_named_accessible(
            self.progress_gauge,
            name="Barra de tempo",
            description="Mostra o progresso da mídia atual.",
            value_provider=self._time_bar_accessible_value,
        )
        attach_named_accessible(
            self.shortcuts_hint_label,
            name="Dicas rápidas de atalhos",
            description="Resume os atalhos mais usados para controlar o player.",
            value_provider=lambda: self.shortcuts_hint_label.GetLabel(),
        )

        root_sizer.Add(self.notebook, 1, wx.EXPAND)
        root_sizer.Add(self.progress_panel, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 4)
        panel.SetSizer(root_sizer)

        self.status_bar = self.CreateStatusBar(1)
        self.status_bar.SetStatusText("")
        self._status_clear_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_status_clear_timer, self._status_clear_timer)

        self._create_empty_playlist_tab(select=True)
        self._apply_current_volume()
        self._update_time_bar()
        self._refresh_shortcuts_hint_layout()

    def _on_status_clear_timer(self, _event):
        if hasattr(self, "status_bar") and self.status_bar:
            self.status_bar.SetStatusText("")

    def _set_status_message(self, message, *, auto_clear_ms=6000):
        if not hasattr(self, "status_bar") or not self.status_bar:
            return
        self.status_bar.SetStatusText(message or "")
        timer = getattr(self, "_status_clear_timer", None)
        if timer:
            timer.Stop()
            if message and auto_clear_ms and auto_clear_ms > 0:
                timer.StartOnce(auto_clear_ms)

    def _bind_events(self):
        accelerators = wx.AcceleratorTable(
            [
                (wx.ACCEL_CTRL, ord("O"), self.menu_open_file_id),
                (wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord("O"), int(self.menu_open_folder_id)),
                (wx.ACCEL_CTRL | wx.ACCEL_ALT, ord("O"), int(self.menu_open_source_id)),
            ]
        )
        self.SetAcceleratorTable(accelerators)

        self.Bind(wx.EVT_MENU, self.on_new_playlist, id=self.menu_new_playlist_id)
        self.Bind(wx.EVT_MENU, self.on_open, id=self.menu_open_file_id)
        self.Bind(wx.EVT_MENU, self.on_open_folder, id=self.menu_open_folder_id)
        self.Bind(wx.EVT_MENU, self.on_open_source, id=self.menu_open_source_id)
        self.Bind(wx.EVT_MENU, self.on_copy_current_item_path, id=self.menu_copy_current_item_path_id)
        self.Bind(wx.EVT_MENU, self.on_paste_open_from_clipboard, id=self.menu_paste_open_from_clipboard_id)
        self.Bind(
            wx.EVT_MENU,
            self.on_paste_open_from_clipboard_new_playlist,
            id=self.menu_paste_open_from_clipboard_new_playlist_id,
        )
        self.Bind(wx.EVT_MENU, self.on_connect_youtube_music, id=self.menu_youtube_music_login_id)
        self.Bind(wx.EVT_MENU, self.on_disconnect_youtube_music, id=self.menu_youtube_music_disconnect_id)
        self.Bind(wx.EVT_MENU, self.on_refresh_youtube_music_library, id=self.menu_youtube_music_refresh_library_id)
        self.Bind(wx.EVT_MENU, self.on_open_youtube_music, id=self.menu_open_youtube_music_id)
        self.Bind(wx.EVT_MENU, self.on_save_playlist, id=self.menu_save_playlist_id)
        self.Bind(wx.EVT_MENU, self.on_previous_track, id=self.menu_previous_track_id)
        self.Bind(wx.EVT_MENU, self.on_play_pause, id=self.menu_play_pause_id)
        self.Bind(wx.EVT_MENU, self.on_stop, id=self.menu_stop_id)
        self.Bind(wx.EVT_MENU, self.on_next_track, id=self.menu_next_track_id)
        self.Bind(wx.EVT_MENU, self.on_add_to_youtube_playlist, id=self.menu_add_to_youtube_playlist_id)
        self.Bind(wx.EVT_MENU, self.on_open_equalizer, id=self.menu_open_equalizer_id)
        self.Bind(wx.EVT_MENU, self.on_toggle_shuffle, id=self.menu_toggle_shuffle_id)
        self.Bind(wx.EVT_MENU, self.on_cycle_repeat_mode, id=self.menu_cycle_repeat_id)
        self.Bind(wx.EVT_MENU, self.on_refresh_audio_output_devices, id=self.menu_refresh_audio_output_devices_id)
        self.Bind(wx.EVT_MENU, self.on_announce_time, id=self.menu_announce_time_id)
        self.Bind(wx.EVT_MENU, self.on_announce_volume, id=self.menu_announce_volume_id)
        self.Bind(wx.EVT_MENU, self.on_announce_status, id=self.menu_announce_status_id)
        self.Bind(wx.EVT_MENU, self.on_close_current_media, id=self.menu_close_media_id)
        self.Bind(wx.EVT_MENU, self.on_close_current_tab, id=self.menu_close_tab_id)
        self.Bind(wx.EVT_MENU, self.on_toggle_playlist_browser, id=self.menu_playlist_browser_id)
        self.Bind(wx.EVT_MENU, self.on_next_tab, id=self.menu_next_tab_id)
        self.Bind(wx.EVT_MENU, self.on_previous_tab, id=self.menu_previous_tab_id)
        self.Bind(wx.EVT_MENU, self.on_check_for_updates, id=self.menu_check_updates_id)
        self.Bind(wx.EVT_MENU, self.on_open_preferences, id=self.menu_preferences_id)
        self.Bind(wx.EVT_MENU, self.on_open_manual, id=self.menu_open_manual_id)
        self.Bind(wx.EVT_MENU, self.on_show_keyboard_help, id=self.menu_keyboard_help_id)
        self.Bind(wx.EVT_MENU, self.on_exit, id=wx.ID_EXIT)

        self.notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.on_tab_changed)
        self.progress_panel.Bind(wx.EVT_SIZE, self._on_progress_panel_size)
        self.Bind(wx.EVT_TIMER, self.on_progress_timer, self.progress_timer)
        self.Bind(wx.EVT_TIMER, self.on_crossfade_timer, self.crossfade_timer)
        self.Bind(wx.EVT_CHAR_HOOK, self.on_key_down)
        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.progress_timer.Start(PROGRESS_TIMER_INTERVAL_MS)
        self.crossfade_timer.Start(CROSSFADE_TIMER_INTERVAL_MS)

    def _create_playlist_page(self):
        page = wx.Panel(self.notebook)
        root_sizer = wx.BoxSizer(wx.HORIZONTAL)

        browser_panel = PlaylistBrowserPanel(
            page,
            on_activate_item=self.on_playlist_browser_activate_item,
            on_remove_item=self.on_playlist_browser_remove_item,
            on_preview_item=self.on_playlist_browser_preview_item,
            on_go_back=self.on_playlist_browser_go_back,
            on_toggle_navigation_mode=self.on_toggle_playlist_browser,
            on_show_context_menu=self.on_playlist_browser_show_context_menu,
        )

        video_panel = wx.Panel(page, style=wx.TAB_TRAVERSAL | wx.CLIP_CHILDREN)
        video_panel.SetName("Painel de vídeo")
        video_panel.SetBackgroundColour(wx.Colour(0, 0, 0))
        video_panel.Bind(wx.EVT_SIZE, self.on_video_panel_resize)
        video_panel.Bind(wx.EVT_SET_FOCUS, self.on_video_panel_focus)

        video_surface = wx.Window(video_panel, style=wx.NO_BORDER | wx.WANTS_CHARS)
        video_surface.SetName("Superfície de vídeo")
        video_surface.SetBackgroundColour(wx.Colour(0, 0, 0))
        video_surface.Bind(wx.EVT_SIZE, self.on_video_panel_resize)
        video_surface.Bind(wx.EVT_SET_FOCUS, self.on_video_panel_focus)

        video_hint_overlay = wx.StaticText(
            video_panel,
            label=self._player_overlay_hint_text(),
            style=wx.ALIGN_CENTER_HORIZONTAL,
        )
        video_hint_overlay.SetName("Ajuda visual do player")
        video_hint_overlay.SetHelpText(
            "Mostra os atalhos principais quando não há mídia carregada na aba atual."
        )
        video_hint_overlay.SetForegroundColour(wx.Colour(235, 235, 235))

        video_panel_sizer = wx.BoxSizer(wx.VERTICAL)
        video_panel_sizer.Add(video_surface, 1, wx.EXPAND)
        video_panel.SetSizer(video_panel_sizer)

        root_sizer.Add(browser_panel, 0, wx.EXPAND | wx.ALL, 4)
        root_sizer.Add(video_panel, 1, wx.EXPAND | wx.TOP | wx.RIGHT | wx.BOTTOM, 4)
        page.SetSizer(root_sizer)
        page.browser_panel = browser_panel
        page.video_panel = video_panel
        page.video_surface = video_surface
        page.video_hint_overlay = video_hint_overlay
        page.video_hint_wrap_width = None
        self._layout_video_page(page)
        return page

    def on_add_to_youtube_playlist(self, _event):
        if hasattr(self, "_add_current_media_to_youtube_playlist"):
            self._add_current_media_to_youtube_playlist()
        else:
            wx.MessageBox(
                "A integração com o YouTube Music não está pronta ou ativa no momento.",
                "YouTube Music",
                wx.OK | wx.ICON_WARNING,
                self,
            )