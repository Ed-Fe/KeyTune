from pathlib import Path
import sys

import wx

from ..accessibility import attach_named_accessible
from ..constants import PROGRESS_GAUGE_RANGE, PROGRESS_TIMER_INTERVAL_MS
from ..i18n import _, SOURCE_LANGUAGE, get_active_language
from ..library import PlaylistBrowserPanel, is_audio_playback_media
from ..welcome import WelcomeDialog


class FrameUIMixin:
    def _localized_doc_names(self, stem):
        # Prefer a translated document (e.g. manual.en.html) when a non-source
        # language is active, then fall back to the Portuguese base document.
        language = get_active_language()
        names = []
        if language and language != SOURCE_LANGUAGE:
            names.append(f"{stem}.{language}.html")
            names.append(f"{stem}.{language}.md")
        names.append(f"{stem}.html")
        names.append(f"{stem}.md")
        return names

    def _doc_candidate_paths(self, stem):
        candidates = []
        names = self._localized_doc_names(stem)
        repo_root = Path(__file__).resolve().parents[3]

        if getattr(sys, "frozen", False):
            executable_dir = Path(sys.executable).resolve().parent
            for name in names:
                candidates.append(executable_dir / "docs" / name)

        for name in names:
            candidates.append(repo_root / "docs" / name)
            candidates.append(Path.cwd() / "docs" / name)

        unique_candidates = []
        seen = set()
        for candidate in candidates:
            normalized_candidate = str(candidate)
            if normalized_candidate in seen:
                continue
            seen.add(normalized_candidate)
            unique_candidates.append(candidate)
        return unique_candidates

    def _manual_candidate_paths(self):
        return self._doc_candidate_paths("manual")

    def _open_manual_document(self):
        manual_path = next((path for path in self._manual_candidate_paths() if path.is_file()), None)
        if manual_path is None:
            wx.MessageBox(
                _("Não foi possível localizar o manual do KeyTune. Gere a versão HTML da release ou verifique a pasta docs do projeto."),
                _("Manual do KeyTune"),
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
                _("Não foi possível abrir o manual do KeyTune no visualizador padrão do sistema."),
                _("Manual do KeyTune"),
                wx.OK | wx.ICON_ERROR,
                self,
            )
            return False

        self._set_status_message(_("Abrindo manual: {name}").format(name=manual_path.name))
        return True

    def _credits_candidate_paths(self):
        return self._doc_candidate_paths("credits")

    def _open_credits_document(self):
        credits_path = next((path for path in self._credits_candidate_paths() if path.is_file()), None)
        if credits_path is None:
            wx.MessageBox(
                _("Não foi possível localizar os créditos do KeyTune. Gere a versão HTML da release ou verifique a pasta docs do projeto."),
                _("Créditos do KeyTune"),
                wx.OK | wx.ICON_ERROR,
                self,
            )
            return False

        try:
            launched = wx.LaunchDefaultBrowser(credits_path.resolve().as_uri())
        except Exception:
            launched = False

        if not launched:
            wx.MessageBox(
                _("Não foi possível abrir os créditos do KeyTune no visualizador padrão do sistema."),
                _("Créditos do KeyTune"),
                wx.OK | wx.ICON_ERROR,
                self,
            )
            return False

        self._set_status_message(_("Abrindo créditos: {name}").format(name=credits_path.name))
        return True

    def _primary_shortcuts_hint_text(self):
        return _(
            "Atalhos principais: Ctrl+Alt+O abrir mídia, playlist ou pasta · Ctrl+O abrir arquivos ou playlist · Ctrl+Shift+O abrir pasta · "
            "Espaço reproduzir/pausar · ←/→ buscar · ↑/↓ volume · Tab itens/player · Ctrl+Shift+Y central do YouTube Music (opcional) · F1 ajuda"
        )

    def _player_overlay_hint_text(self):
        return _(
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
        return _(
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
        return _(
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
            "] / [ — Aumentar ou diminuir a velocidade de reprodução\n"
            "\\ — Restaurar velocidade normal (1x)\n"
            "Shift+] / Shift+[ — Aumentar ou diminuir o tom (pitch), em semitons, sem alterar a velocidade\n"
            "Shift+\\ — Restaurar o tom original\n"
            "Menu Reprodução > Dispositivo de áudio — Trocar a saída de som\n"
            "Ctrl+PageUp / Ctrl+PageDown — Faixa anterior ou próxima\n"
            "Alt+Seta esquerda / direita — Faixa anterior ou próxima na playlist\n"
            "Alt+Seta cima / baixo — Mover o item atual na playlist\n"
            "Alt+Home / End — Ir para o primeiro ou último item da playlist\n"
            "Ctrl+L — Curtir mídia atual no YouTube Music\n"
            "Ctrl+Alt+L — Alternar painel de letras\n"
            "Ctrl+Shift+L — Marcar mídia atual como não gostei no YouTube Music\n"
            "Ctrl+Shift+A — Adicionar a mídia atual a uma playlist do YouTube Music\n"
            "Ctrl+Shift+F — Adicionar o item selecionado à fila de reprodução\n"
            "Ctrl+Shift+Q — Gerenciar a fila de reprodução (ver, remover, reordenar)\n"
            "E — Alternar modo aleatório\n"
            "R — Alternar modo de repetição\n"
            "A — Alternar conteúdo relacionado do YouTube Music (rádio automática ao fim da playlist)\n"
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
            surface_size = (panel_size.Width, panel_size.Height)
            # The progress timer lays out every video page twice per second.
            # Only touch the native surface when the size actually changed to
            # avoid pointless resize/repaint churn (and flicker) while idle.
            if getattr(page, "_video_surface_size", None) != surface_size:
                video_surface.SetSize(0, 0, panel_size.Width, panel_size.Height)
                page._video_surface_size = surface_size

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

    def _on_video_erase_background(self, _event):
        # Intentionally do nothing (and do not Skip): the native MPV surface
        # owns this area, so suppressing the default background erase avoids
        # flicker during resizes without touching focus or the video output.
        return

    def _show_keyboard_help_dialog(self):
        dialog = wx.Dialog(
            self,
            title=_("Ajuda rápida de atalhos"),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        dialog.SetMinSize((520, 420))

        root_sizer = wx.BoxSizer(wx.VERTICAL)
        instructions_label = wx.StaticText(dialog, label=_("Ajuda rápida de atalhos:"))
        instructions = wx.TextCtrl(
            dialog,
            value=self._keyboard_help_text(),
            style=wx.TE_MULTILINE | wx.TE_READONLY,
        )
        instructions.SetName(_("Ajuda rápida de atalhos"))
        instructions.SetInsertionPoint(0)

        button_sizer = dialog.CreateStdDialogButtonSizer(wx.OK)
        if button_sizer is not None:
            # Descendant-scoped FindWindow (not the global FindWindowById) so we
            # never rename a wx.ID_OK button in another open dialog.
            ok_button = dialog.FindWindow(wx.ID_OK)
            if ok_button is not None:
                ok_button.SetLabel(_("F&echar"))

        root_sizer.Add(instructions_label, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 12)
        root_sizer.Add(instructions, 1, wx.ALL | wx.EXPAND, 12)
        if button_sizer is not None:
            root_sizer.Add(button_sizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.ALIGN_RIGHT, 12)

        dialog.SetSizerAndFit(root_sizer)
        dialog.SetSize((560, 460))
        # Only an OK/"Fechar" button exists here, so ESC must map to it for the
        # keyboard-first close to work like every other dialog in the app.
        dialog.SetEscapeId(wx.ID_OK)
        dialog.CentreOnParent()
        try:
            dialog.ShowModal()
        finally:
            dialog.Destroy()

    def on_open_manual(self, _event):
        self._open_manual_document()

    def _show_welcome_screen_if_first_run(self):
        if self.settings.welcome_screen_completed:
            return
        self._show_welcome_dialog()

    def on_show_welcome_screen(self, _event):
        self._show_welcome_dialog()

    def _show_welcome_dialog(self):
        dialog = WelcomeDialog(
            self,
            on_open_manual=self._open_manual_document,
            on_show_shortcuts=self._show_keyboard_help_dialog,
        )
        try:
            dialog.ShowModal()
        finally:
            dialog.Destroy()
        self.settings.welcome_screen_completed = True
        self._save_settings()

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
        file_menu.Append(self.menu_open_source_id, _("Abrir &Mídia, Playlist ou Pasta...\tCtrl+Alt+O"))
        file_menu.Append(self.menu_open_file_id, _("Abrir &Arquivos ou Playlist...\tCtrl+O"))
        file_menu.Append(self.menu_open_folder_id, _("Abrir &Pasta...\tCtrl+Shift+O"))
        file_menu.AppendSeparator()
        file_menu.Append(self.menu_copy_current_item_path_id, _("&Copiar caminho do item (Ctrl+C)"))
        file_menu.Append(self.menu_paste_open_from_clipboard_id, _("Co&lar na playlist atual / abrir... (Ctrl+V)"))
        file_menu.Append(
            self.menu_paste_open_from_clipboard_new_playlist_id,
            _("Colar e abrir em &nova playlist... (Ctrl+Shift+V)"),
        )
        file_menu.AppendSeparator()
        self.recent_menu.AppendSubMenu(self.recent_files_menu, _("Arquivos recentes"))
        self.recent_menu.AppendSubMenu(self.recent_folders_menu, _("Pastas recentes"))
        self.recent_menu.AppendSubMenu(self.recent_playlists_menu, _("Playlists recentes"))
        file_menu.AppendSubMenu(self.recent_menu, _("&Recentes"))
        file_menu.AppendSeparator()
        file_menu.Append(self.menu_save_playlist_id, _("Salvar Playli&st\tCtrl+Shift+S"))
        file_menu.Append(self.menu_close_media_id, _("Fechar Mí&dia\tCtrl+Shift+W"))
        file_menu.AppendSeparator()
        file_menu.Append(wx.ID_EXIT, _("&Sair\tAlt+F4"))

        playback_menu = wx.Menu()
        self.playback_menu = playback_menu
        self.menu_previous_track_id = wx.NewIdRef()
        self.menu_play_pause_id = wx.NewIdRef()
        self.menu_stop_id = wx.NewIdRef()
        self.menu_next_track_id = wx.NewIdRef()
        self.menu_add_to_youtube_playlist_id = wx.NewIdRef()
        self.menu_enqueue_item_id = wx.NewIdRef()
        self.menu_manage_queue_id = wx.NewIdRef()
        self.menu_open_equalizer_id = wx.NewIdRef()
        self.menu_toggle_shuffle_id = wx.NewIdRef()
        self.menu_cycle_repeat_id = wx.NewIdRef()
        self.menu_toggle_related_autoplay_id = wx.NewIdRef()
        self.menu_increase_playback_rate_id = wx.NewIdRef()
        self.menu_decrease_playback_rate_id = wx.NewIdRef()
        self.menu_reset_playback_rate_id = wx.NewIdRef()
        self.menu_increase_pitch_id = wx.NewIdRef()
        self.menu_decrease_pitch_id = wx.NewIdRef()
        self.menu_reset_pitch_id = wx.NewIdRef()
        self.menu_announce_time_id = wx.NewIdRef()
        self.menu_announce_volume_id = wx.NewIdRef()
        self.menu_announce_status_id = wx.NewIdRef()
        self.menu_refresh_audio_output_devices_id = wx.NewIdRef()
        self.audio_output_menu = wx.Menu()
        self._audio_output_menu_actions = {}
        self._audio_output_menu_ids = []
        announce_menu = wx.Menu()
        playback_menu.Append(self.menu_previous_track_id, _("Faixa &Anterior\tCtrl+PageUp"))
        playback_menu.Append(self.menu_play_pause_id, _("Reproduzir / Pa&usar (Espaço)"))
        playback_menu.Append(self.menu_stop_id, _("P&arar\tCtrl+."))
        playback_menu.Append(self.menu_next_track_id, _("Próxima Fai&xa\tCtrl+PageDown"))
        playback_menu.AppendSeparator()
        playback_menu.Append(self.menu_add_to_youtube_playlist_id, _("Adicionar à Playlist do &YouTube Music\tCtrl+Shift+A"))
        playback_menu.Append(self.menu_enqueue_item_id, _("Adicionar à &Fila de Reprodução\tCtrl+Shift+F"))
        playback_menu.Append(self.menu_manage_queue_id, _("&Gerenciar Fila de Reprodução\tCtrl+Shift+Q"))
        playback_menu.AppendSeparator()
        playback_menu.Append(self.menu_toggle_shuffle_id, _("Em&baralhar (E)"))
        playback_menu.Append(self.menu_cycle_repeat_id, _("Modo de &Repetição (R)"))
        playback_menu.Append(self.menu_toggle_related_autoplay_id, _("&Conteúdo Relacionado do YouTube Music (A)"))
        playback_menu.Append(self.menu_increase_playback_rate_id, _("Aumentar &Velocidade (])"))
        playback_menu.Append(self.menu_decrease_playback_rate_id, _("Diminuir Ve&locidade ([)"))
        playback_menu.Append(self.menu_reset_playback_rate_id, _("Restaurar Velocidade &Normal (\\)"))
        playback_menu.Append(self.menu_increase_pitch_id, _("Aumentar &Tom (Shift+])"))
        playback_menu.Append(self.menu_decrease_pitch_id, _("Diminuir T&om (Shift+[)"))
        playback_menu.Append(self.menu_reset_pitch_id, _("Restaurar &Tom Original (Shift+\\)"))
        playback_menu.AppendSubMenu(self.audio_output_menu, _("Dispositivo de áu&dio"))
        announce_menu.Append(self.menu_announce_time_id, _("Anunciar &Tempo (T)"))
        announce_menu.Append(self.menu_announce_volume_id, _("Anunciar &Volume (V)"))
        announce_menu.Append(self.menu_announce_status_id, _("Anunciar &Status (S)"))
        playback_menu.AppendSubMenu(announce_menu, _("&Anunciar"))

        view_menu = wx.Menu()
        self.view_menu = view_menu
        self.menu_playlist_browser_id = wx.NewIdRef()
        view_menu.Append(self.menu_playlist_browser_id, _("Alternar foco entre &itens e player (Tab)"))
        view_menu.Append(self.menu_open_equalizer_id, _("Eq&ualizador por aba\tCtrl+Shift+E"))
        view_menu.Append(self.menu_open_youtube_music_id, _("YouTube &Music por aba\tCtrl+Shift+Y"))

        tabs_menu = wx.Menu()
        self.menu_next_tab_id = wx.NewIdRef()
        self.menu_previous_tab_id = wx.NewIdRef()
        tabs_menu.Append(self.menu_new_playlist_id, _("&Nova playlist\tCtrl+T"))
        tabs_menu.AppendSeparator()
        tabs_menu.Append(self.menu_next_tab_id, _("Próxima A&ba\tCtrl+Tab"))
        tabs_menu.Append(self.menu_previous_tab_id, _("Aba A&nterior\tCtrl+Shift+Tab"))
        tabs_menu.AppendSeparator()
        tabs_menu.Append(self.menu_close_tab_id, _("Fechar A&ba / Playlist\tCtrl+W"))

        settings_menu = wx.Menu()
        self.menu_check_updates_id = wx.NewIdRef()
        self.menu_preferences_id = wx.NewIdRef()
        settings_menu.Append(self.menu_preferences_id, _("&Preferências\tCtrl+,"))

        help_menu = wx.Menu()
        self.menu_open_manual_id = wx.NewIdRef()
        self.menu_keyboard_help_id = wx.NewIdRef()
        self.menu_show_welcome_screen_id = wx.NewIdRef()
        self.menu_about_id = wx.NewIdRef()
        help_menu.Append(self.menu_show_welcome_screen_id, _("Mostrar tela de &boas-vindas"))
        help_menu.Append(self.menu_open_manual_id, _("Abrir &manual do usuário"))
        help_menu.AppendSeparator()
        help_menu.Append(self.menu_keyboard_help_id, _("Ajuda rápida de &atalhos\tF1"))
        help_menu.AppendSeparator()
        help_menu.Append(self.menu_check_updates_id, _("Verificar &atualizações"))
        help_menu.AppendSeparator()
        help_menu.Append(self.menu_about_id, _("&Sobre o KeyTune"))

        menu_bar.Append(file_menu, _("&Arquivo"))
        menu_bar.Append(playback_menu, _("&Reprodução"))
        menu_bar.Append(view_menu, _("&Exibir"))
        menu_bar.Append(tabs_menu, _("A&bas"))
        menu_bar.Append(settings_menu, _("Con&figurações"))
        menu_bar.Append(help_menu, _("A&juda"))
        self.SetMenuBar(menu_bar)
        self._refresh_recent_menus()
        self._refresh_audio_output_menu()

    def _refresh_audio_output_menu(self, announce=False):
        if not hasattr(self, "audio_output_menu"):
            return

        while self.audio_output_menu.GetMenuItemCount():
            self.audio_output_menu.Delete(self.audio_output_menu.FindItemByPosition(0))

        # Same fix as the recent menus: unbind the handlers tied to the previous
        # item ids so repeated device-list refreshes don't leak frame bindings.
        for previous_item_id in getattr(self, "_audio_output_menu_ids", []):
            self.Unbind(wx.EVT_MENU, id=int(previous_item_id))
        self._audio_output_menu_actions = {}
        self._audio_output_menu_ids = []

        default_item = self.audio_output_menu.AppendRadioItem(wx.NewIdRef(), _("&Padrão do sistema"))
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
            unavailable_item = self.audio_output_menu.Append(wx.ID_ANY, _("Nenhum dispositivo detectado agora"))
            unavailable_item.Enable(False)

        self.audio_output_menu.AppendSeparator()
        self.audio_output_menu.Append(
            self.menu_refresh_audio_output_devices_id,
            _("&Atualizar lista de dispositivos"),
        )

        if announce:
            if devices:
                self._announce(
                    _("Lista de dispositivos de áudio atualizada. {count} dispositivo(s) disponível(is).").format(
                        count=len(devices)
                    )
                )
            else:
                self._announce(_("Lista de dispositivos de áudio atualizada, mas nenhum dispositivo foi detectado agora."))

    def _build_ui(self):
        panel = wx.Panel(self)
        root_sizer = wx.BoxSizer(wx.VERTICAL)

        self.notebook = wx.Notebook(panel)
        self.progress_panel = wx.Panel(panel)
        self.progress_label = wx.StaticText(self.progress_panel, label=_("Tempo: nenhuma mídia carregada."))
        
        # Lyrics panel toggle integrated alongside the progress label
        self.lyrics_checkbox = wx.CheckBox(self.progress_panel, label=_("Letras"))
        self.lyrics_checkbox.SetName(_("Painel de letras"))
        self.lyrics_checkbox.Bind(wx.EVT_CHECKBOX, self.on_toggle_lyrics)
        
        top_progress_sizer = wx.BoxSizer(wx.HORIZONTAL)
        top_progress_sizer.Add(self.progress_label, 1, wx.ALIGN_CENTER_VERTICAL)
        top_progress_sizer.Add(self.lyrics_checkbox, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 10)

        self.progress_gauge = wx.Gauge(self.progress_panel, range=PROGRESS_GAUGE_RANGE, style=wx.GA_SMOOTH)
        self.shortcuts_hint_label = wx.StaticText(
            self.progress_panel,
            label=self._primary_shortcuts_hint_text(),
        )
        self.progress_timer = wx.Timer(self)
        self.crossfade_timer = wx.Timer(self)

        progress_sizer = wx.BoxSizer(wx.VERTICAL)
        progress_sizer.Add(top_progress_sizer, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 10)
        progress_sizer.Add(self.progress_gauge, 0, wx.ALL | wx.EXPAND, 10)
        progress_sizer.Add(self.shortcuts_hint_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)
        self.progress_panel.SetSizer(progress_sizer)

        self.progress_panel.SetName(_("Painel de tempo"))
        self.progress_label.SetName(_("Tempo da mídia"))
        self.progress_gauge.SetName(_("Barra de tempo"))
        self.shortcuts_hint_label.SetName(_("Dicas rápidas de atalhos"))
        self.shortcuts_hint_label.SetForegroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT))
        attach_named_accessible(
            self.progress_label,
            name=_("Tempo da mídia"),
            description=_("Mostra o tempo decorrido e a duração total da mídia atual."),
            value_provider=lambda: self.progress_label.GetLabel(),
        )
        attach_named_accessible(
            self.lyrics_checkbox,
            name=_("Painel de letras"),
            description=_("Ativa ou desativa a exibição das letras da música."),
            value_provider=lambda: _("Ativado") if self.lyrics_checkbox.GetValue() else _("Desativado"),
        )
        attach_named_accessible(
            self.progress_gauge,
            name=_("Barra de tempo"),
            description=_("Mostra o progresso da mídia atual."),
            value_provider=self._time_bar_accessible_value,
        )
        attach_named_accessible(
            self.shortcuts_hint_label,
            name=_("Dicas rápidas de atalhos"),
            description=_("Resume os atalhos mais usados para controlar o player."),
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
                (wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord("F"), int(self.menu_enqueue_item_id)),
                (wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord("Q"), int(self.menu_manage_queue_id)),
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
        self.Bind(wx.EVT_MENU, self.on_enqueue_item, id=self.menu_enqueue_item_id)
        self.Bind(wx.EVT_MENU, self.on_manage_queue, id=self.menu_manage_queue_id)
        self.Bind(wx.EVT_MENU, self.on_open_equalizer, id=self.menu_open_equalizer_id)
        self.Bind(wx.EVT_MENU, self.on_toggle_shuffle, id=self.menu_toggle_shuffle_id)
        self.Bind(wx.EVT_MENU, self.on_cycle_repeat_mode, id=self.menu_cycle_repeat_id)
        self.Bind(wx.EVT_MENU, self.on_toggle_related_autoplay, id=self.menu_toggle_related_autoplay_id)
        self.Bind(wx.EVT_MENU, self.on_increase_playback_rate, id=self.menu_increase_playback_rate_id)
        self.Bind(wx.EVT_MENU, self.on_decrease_playback_rate, id=self.menu_decrease_playback_rate_id)
        self.Bind(wx.EVT_MENU, self.on_reset_playback_rate, id=self.menu_reset_playback_rate_id)
        self.Bind(wx.EVT_MENU, self.on_increase_pitch, id=self.menu_increase_pitch_id)
        self.Bind(wx.EVT_MENU, self.on_decrease_pitch, id=self.menu_decrease_pitch_id)
        self.Bind(wx.EVT_MENU, self.on_reset_pitch, id=self.menu_reset_pitch_id)
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
        self.Bind(wx.EVT_MENU, self.on_open_about, id=self.menu_about_id)
        self.Bind(wx.EVT_MENU, self.on_show_keyboard_help, id=self.menu_keyboard_help_id)
        self.Bind(wx.EVT_MENU, self.on_show_welcome_screen, id=self.menu_show_welcome_screen_id)
        self.Bind(wx.EVT_MENU, self.on_exit, id=wx.ID_EXIT)

        self.notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.on_tab_changed)
        self.progress_panel.Bind(wx.EVT_SIZE, self._on_progress_panel_size)
        self.Bind(wx.EVT_TIMER, self.on_progress_timer, self.progress_timer)
        self.Bind(wx.EVT_TIMER, self.on_crossfade_timer, self.crossfade_timer)
        self.Bind(wx.EVT_CHAR_HOOK, self.on_key_down)
        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.progress_timer.Start(PROGRESS_TIMER_INTERVAL_MS)
        # The crossfade timer is started on demand (only while a crossfade is
        # active) by CrossfadeMixin._ensure_crossfade_timer_running(); leaving
        # it stopped while idle avoids ~64 needless CPU wakeups per second.

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

        video_panel = wx.Panel(
            page,
            style=wx.TAB_TRAVERSAL | wx.CLIP_CHILDREN | wx.NO_FULL_REPAINT_ON_RESIZE,
        )
        video_panel.SetName(_("Área do player"))
        # A plain wx.Panel does not expose its SetName() to the screen reader
        # (it just reads the generic "panel" role), so register a real
        # accessible name/description — this is the control the player focus
        # lands on.
        attach_named_accessible(
            video_panel,
            name=_("Área do player"),
            description=_("Área de reprodução. Use Espaço para tocar ou pausar e as setas para navegar."),
        )
        video_panel.SetBackgroundColour(wx.Colour(0, 0, 0))
        video_panel.Bind(wx.EVT_SIZE, self.on_video_panel_resize)
        video_panel.Bind(wx.EVT_SET_FOCUS, lambda event, panel=video_panel: self.on_video_panel_focus(event, panel))
        # MPV paints the native child surface, so the wx-side background never
        # needs erasing. Swallowing EVT_ERASE_BACKGROUND removes the black
        # flash behind the video while the border is dragged (wxWiki
        # Flicker-Free Drawing).
        video_panel.Bind(wx.EVT_ERASE_BACKGROUND, self._on_video_erase_background)

        video_surface = wx.Window(
            video_panel,
            style=wx.NO_BORDER | wx.WANTS_CHARS | wx.NO_FULL_REPAINT_ON_RESIZE,
        )
        video_surface.SetName(_("Superfície de vídeo"))
        video_surface.SetBackgroundColour(wx.Colour(0, 0, 0))
        video_surface.Bind(wx.EVT_SIZE, self.on_video_panel_resize)
        video_surface.Bind(wx.EVT_SET_FOCUS, lambda event, panel=video_panel: self.on_video_panel_focus(event, panel))
        video_surface.Bind(wx.EVT_ERASE_BACKGROUND, self._on_video_erase_background)

        video_hint_overlay = wx.StaticText(
            video_panel,
            label=self._player_overlay_hint_text(),
            style=wx.ALIGN_CENTER_HORIZONTAL,
        )
        video_hint_overlay.SetName(_("Ajuda visual do player"))
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
        self._add_current_media_to_youtube_playlist()

    def on_enqueue_item(self, _event):
        self._enqueue_selected_item()

    def on_manage_queue(self, _event):
        self._open_queue_manager()

    def on_toggle_lyrics(self, _event):
        if hasattr(self, 'toggle_lyrics_panel'):
            self.toggle_lyrics_panel()
