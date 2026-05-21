from dataclasses import replace
import sys

import wx

from ..audio_output import is_selectable_audio_output_device_id, normalize_audio_output_device_id
from ..constants import (
    MAX_CROSSFADE_SECONDS,
    MAX_YOUTUBE_MUSIC_HOME_DISCOVERY_LIMIT,
    MAX_YOUTUBE_MUSIC_LIBRARY_PAGE_SIZE,
    MIN_YOUTUBE_MUSIC_HOME_DISCOVERY_LIMIT,
    MIN_YOUTUBE_MUSIC_LIBRARY_PAGE_SIZE,
    REPEAT_MODE_LABELS,
    REPEAT_MODES,
)


class PreferencesDialog(wx.Dialog):
    def __init__(self, parent, settings, *, audio_output_devices=None):
        super().__init__(
            parent,
            title="Preferências",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self._settings = settings
        self._audio_output_devices = list(audio_output_devices or [])
        self._audio_output_choice_ids = []

        panel = wx.Panel(self)
        root_sizer = wx.BoxSizer(wx.VERTICAL)

        intro_label = wx.StaticText(
            panel,
            label="Ajuste como o player inicia, salva estado e responde aos atalhos. "
            "Use as guias para navegar entre as categorias. Pressione Esc para cancelar ou Enter em Salvar para confirmar.",
        )
        intro_label.Wrap(540)

        root_sizer.Add(intro_label, 0, wx.ALL | wx.EXPAND, 10)

        self.notebook = wx.Notebook(panel)
        self.notebook.SetName("Categorias de preferências")
        self.notebook.SetHelpText(
            "Use as guias Geral, Reprodução, Acessibilidade e Recursos adicionais para navegar pelas configurações."
        )

        self._build_general_tab()
        self._build_playback_tab()
        self._build_accessibility_tab()
        self._build_additional_resources_tab()

        root_sizer.Add(self.notebook, 1, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)

        button_sizer = wx.StdDialogButtonSizer()
        self.save_button = wx.Button(panel, wx.ID_OK, "&Salvar")
        self.cancel_button = wx.Button(panel, wx.ID_CANCEL, "&Cancelar")
        self.save_button.SetDefault()
        button_sizer.AddButton(self.save_button)
        button_sizer.AddButton(self.cancel_button)
        button_sizer.Realize()
        root_sizer.Add(button_sizer, 0, wx.ALL | wx.EXPAND, 10)

        panel.SetSizer(root_sizer)

        frame_sizer = wx.BoxSizer(wx.VERTICAL)
        frame_sizer.Add(panel, 1, wx.EXPAND)
        self.SetSizerAndFit(frame_sizer)
        self.SetMinSize((620, 480))
        self.SetEscapeId(wx.ID_CANCEL)

        self._populate_controls(settings)
        # ESC handling is provided by SetEscapeId(wx.ID_CANCEL) above;
        # an extra EVT_CHAR_HOOK would duplicate that behavior.

    def _build_general_tab(self):
        page, page_sizer = self._create_tab_page("Geral")

        info_label = wx.StaticText(
            page,
            label="Configurações relacionadas ao início do player, à sessão salva e ao comportamento ao sair.",
        )
        info_label.Wrap(520)

        general_box = wx.StaticBoxSizer(wx.StaticBox(page, label="Inicialização e sessão"), wx.VERTICAL)
        self.restore_session_checkbox = wx.CheckBox(page, label="&Restaurar sessão ao iniciar")
        self.remember_window_size_checkbox = wx.CheckBox(page, label="Lembrar tamanho da &janela")
        self.remember_last_folder_checkbox = wx.CheckBox(page, label="Lembrar última &pasta usada")
        self.confirm_on_exit_checkbox = wx.CheckBox(page, label="Con&firmar ao sair")

        self._configure_checkbox(
            self.restore_session_checkbox,
            "Restaurar sessão ao iniciar",
            "Reabre as abas e tenta retomar a última sessão salva ao iniciar o player.",
        )
        self._configure_checkbox(
            self.remember_window_size_checkbox,
            "Lembrar tamanho da janela",
            "Salva e restaura o tamanho da janela principal entre execuções.",
        )
        self._configure_checkbox(
            self.remember_last_folder_checkbox,
            "Lembrar última pasta usada",
            "Usa a última pasta aberta como diretório inicial nos diálogos de abrir e salvar.",
        )
        self._configure_checkbox(
            self.confirm_on_exit_checkbox,
            "Confirmar ao sair",
            "Pede confirmação antes de fechar o player.",
        )

        for control in (
            self.restore_session_checkbox,
            self.remember_window_size_checkbox,
            self.remember_last_folder_checkbox,
            self.confirm_on_exit_checkbox,
        ):
            general_box.Add(control, 0, wx.ALL | wx.EXPAND, 6)

        note_label = wx.StaticText(
            page,
            label="As mudanças de restauração de sessão e de tamanho da janela afetam principalmente as próximas aberturas do player.",
        )
        note_label.Wrap(520)

        if sys.platform == "win32":
            assoc_box = wx.StaticBoxSizer(wx.StaticBox(page, label="Associação de arquivos"), wx.VERTICAL)
            assoc_help = wx.StaticText(
                page,
                label=(
                    "Registra o player no menu Abrir Com do Windows para formatos de áudio, "
                    "vídeo e playlists. Depois, defina o player como padrão nas configurações do Windows."
                ),
            )
            assoc_help.Wrap(500)
            self._register_assoc_button = wx.Button(page, label="&Registrar como player padrão")
            self._register_assoc_button.SetName("Registrar como player padrão")
            self._register_assoc_button.SetHelpText(
                "Adiciona o player à lista Abrir Com do Windows para formatos de mídia e playlists."
            )
            self._unregister_assoc_button = wx.Button(page, label="&Desregistrar associações")
            self._unregister_assoc_button.SetName("Desregistrar associações")
            self._unregister_assoc_button.SetHelpText(
                "Remove o player da lista Abrir Com do Windows."
            )

            self._register_assoc_button.Bind(wx.EVT_BUTTON, self._on_register_associations)
            self._unregister_assoc_button.Bind(wx.EVT_BUTTON, self._on_unregister_associations)

            button_row = wx.BoxSizer(wx.HORIZONTAL)
            button_row.Add(self._register_assoc_button, 0, wx.RIGHT, 6)
            button_row.Add(self._unregister_assoc_button, 0, 0)

            assoc_box.Add(assoc_help, 0, wx.ALL | wx.EXPAND, 6)
            assoc_box.Add(button_row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)
        else:
            assoc_box = None

        page_sizer.Add(info_label, 0, wx.ALL | wx.EXPAND, 10)
        page_sizer.Add(general_box, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)
        page_sizer.Add(note_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)
        if assoc_box:
            page_sizer.Add(assoc_box, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)

        self.notebook.AddPage(page, "Geral", select=True)

    def _build_playback_tab(self):
        page, page_sizer = self._create_tab_page("Reprodução")

        info_label = wx.StaticText(
            page,
            label="Configurações ligadas ao volume, ao avanço na mídia e ao comportamento padrão de playlists novas.",
        )
        info_label.Wrap(520)

        playback_box = wx.StaticBoxSizer(wx.StaticBox(page, label="Controles de reprodução"), wx.VERTICAL)
        self.shuffle_new_playlists_checkbox = wx.CheckBox(page, label="Ativar e&mbaralhamento em novas playlists")
        self.disable_video_output_checkbox = wx.CheckBox(page, label="Desativar saída de &vídeo (tocar só o áudio)")
        self._configure_checkbox(
            self.shuffle_new_playlists_checkbox,
            "Ativar embaralhamento em novas playlists",
            "Ativa o modo aleatório automaticamente em playlists criadas depois de salvar as preferências.",
        )
        self._configure_checkbox(
            self.disable_video_output_checkbox,
            "Desativar saída de vídeo",
            (
                "Mantém a reprodução apenas em áudio, inclusive em arquivos de vídeo. "
                "Útil para evitar a abertura de janelas externas de vídeo no Windows."
            ),
        )

        volume_group, self.default_volume_ctrl = self._build_spin_control_group(
            page,
            label_text="Volume padrão",
            help_text="Define o volume inicial do player. 0 é mudo e 100 é o máximo.",
            min_value=0,
            max_value=100,
        )
        volume_step_group, self.volume_step_ctrl = self._build_spin_control_group(
            page,
            label_text="Passo de volume",
            help_text="Valor usado ao aumentar ou diminuir o volume com as setas para cima e para baixo.",
            min_value=1,
            max_value=25,
        )
        crossfade_group, self.crossfade_ctrl = self._build_spin_control_group(
            page,
            label_text="Crossfade (segundos, 0 desativa)",
            help_text=(
                "Define por quantos segundos duas faixas de áudio se sobrepõem na transição. "
                "Use 0 para desativar. O crossfade só é aplicado entre arquivos de áudio e "
                "acontece automaticamente no final de cada faixa."
            ),
            min_value=0,
            max_value=MAX_CROSSFADE_SECONDS,
        )
        self.crossfade_on_manual_change_checkbox = wx.CheckBox(
            page, label="Aplicar crossfade ao trocar de faixa &manualmente"
        )
        self._configure_checkbox(
            self.crossfade_on_manual_change_checkbox,
            "Aplicar crossfade ao trocar de faixa manualmente",
            (
                "Quando ligado, o crossfade também é usado ao avançar ou voltar com os controles. "
                "Por padrão, o crossfade só é aplicado no fim natural de cada faixa."
            ),
        )
        seek_step_group, self.seek_step_ctrl = self._build_spin_control_group(
            page,
            label_text="Passo de busca (segundos)",
            help_text="Valor usado para avançar ou retroceder na mídia com as setas esquerda e direita.",
            min_value=1,
            max_value=120,
        )
        repeat_group, self.repeat_mode_choice = self._build_choice_control_group(
            page,
            label_text="Repetição padrão",
            help_text="Modo de repetição aplicado automaticamente às playlists novas.",
            choices=[REPEAT_MODE_LABELS[mode] for mode in REPEAT_MODES],
        )
        audio_output_group, self.audio_output_choice = self._build_choice_control_group(
            page,
            label_text="Dispositivo de áudio",
            help_text=(
                "Escolhe a saída de áudio usada na reprodução. "
                "Use Padrão do sistema para seguir o dispositivo principal do Windows."
            ),
            choices=self._audio_output_choice_labels(),
        )

        for group in (
            volume_group,
            volume_step_group,
            crossfade_group,
            seek_step_group,
            repeat_group,
            audio_output_group,
        ):
            playback_box.Add(group, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 6)

        playback_box.Add(self.shuffle_new_playlists_checkbox, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 6)
        playback_box.Add(self.crossfade_on_manual_change_checkbox, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 6)
        playback_box.Add(self.disable_video_output_checkbox, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 6)

        page_sizer.Add(info_label, 0, wx.ALL | wx.EXPAND, 10)
        page_sizer.Add(playback_box, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)

        self.notebook.AddPage(page, "Reprodução")

    def _build_accessibility_tab(self):
        page, page_sizer = self._create_tab_page("Acessibilidade")

        info_label = wx.StaticText(
            page,
            label="Configurações ligadas aos anúncios enviados ao leitor de tela e à navegação das preferências.",
        )
        info_label.Wrap(520)

        accessibility_box = wx.StaticBoxSizer(wx.StaticBox(page, label="Leitor de tela"), wx.VERTICAL)
        self.announcements_enabled_checkbox = wx.CheckBox(page, label="Ativar a&núncios de acessibilidade")
        self._configure_checkbox(
            self.announcements_enabled_checkbox,
            "Ativar anúncios de acessibilidade",
            "Liga ou desliga os anúncios enviados ao leitor de tela.",
        )
        accessibility_box.Add(self.announcements_enabled_checkbox, 0, wx.ALL | wx.EXPAND, 6)

        help_label = wx.StaticText(
            page,
            label="Se essa opção estiver desligada, o player deixa de anunciar mudanças como tempo, volume e troca de abas.",
        )
        help_label.Wrap(520)

        page_sizer.Add(info_label, 0, wx.ALL | wx.EXPAND, 10)
        page_sizer.Add(accessibility_box, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)
        page_sizer.Add(help_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)

        self.notebook.AddPage(page, "Acessibilidade")

    def _build_additional_resources_tab(self):
        page, page_sizer = self._create_tab_page("Recursos adicionais")

        info_label = wx.StaticText(
            page,
            label=(
                "Configure os recursos adicionais do YouTube Music. "
                "Você pode controlar como as dependências são gerenciadas e como a biblioteca é carregada."
            ),
        )
        info_label.Wrap(520)

        resources_box = wx.StaticBoxSizer(wx.StaticBox(page, label="Dependências do YouTube Music"), wx.VERTICAL)
        self.youtube_music_manage_dependencies_checkbox = wx.CheckBox(
            page,
            label="Ativar &recursos adicionais do YouTube Music (yt-dlp e ytmusicapi)",
        )
        self.youtube_music_auto_update_dependencies_checkbox = wx.CheckBox(
            page,
            label="Atualizar automaticamente as dependências do YouTube Music",
        )
        self.youtube_music_use_nightly_yt_dlp_checkbox = wx.CheckBox(
            page,
            label="Usar versão &nightly do yt-dlp (recomendado)",
        )

        self._configure_checkbox(
            self.youtube_music_manage_dependencies_checkbox,
            "Ativar recursos adicionais do YouTube Music",
            (
                "Baixa e mantém um yt-dlp executável atualizado junto com os recursos Python do "
                "YouTube Music em uma pasta local de recursos adicionais."
            ),
        )
        self._configure_checkbox(
            self.youtube_music_auto_update_dependencies_checkbox,
            "Atualizar automaticamente dependências do YouTube Music",
            "Verifica e aplica atualização automática das dependências no intervalo definido abaixo.",
        )
        self._configure_checkbox(
            self.youtube_music_use_nightly_yt_dlp_checkbox,
            "Usar versão nightly do yt-dlp",
            (
                "Baixa builds nightly oficiais do yt-dlp. Recomendado porque o YouTube quebra "
                "extractors com frequência e o nightly costuma receber correções antes do canal estável."
            ),
        )

        interval_group, self.youtube_music_dependency_update_interval_ctrl = self._build_spin_control_group(
            page,
            label_text="Intervalo de atualização (horas)",
            help_text=(
                "Define de quanto em quanto tempo o player tenta atualizar o yt-dlp e os recursos Python "
                "quando a aba YouTube Music é aberta."
            ),
            min_value=1,
            max_value=720,
        )

        resources_box.Add(self.youtube_music_manage_dependencies_checkbox, 0, wx.ALL | wx.EXPAND, 6)
        resources_box.Add(self.youtube_music_auto_update_dependencies_checkbox, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 6)
        resources_box.Add(self.youtube_music_use_nightly_yt_dlp_checkbox, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 6)
        resources_box.Add(interval_group, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 6)

        dependencies_note_label = wx.StaticText(
            page,
            label=(
                "Na primeira execução, o download pode levar alguns minutos e exige internet. "
                "Se desativado, o player volta a depender apenas das bibliotecas já disponíveis no ambiente."
            ),
        )
        dependencies_note_label.Wrap(520)
        resources_box.Add(dependencies_note_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 6)

        library_box = wx.StaticBoxSizer(
            wx.StaticBox(page, label="Carregamento da biblioteca do YouTube Music"),
            wx.VERTICAL,
        )

        page_size_group, self.youtube_music_library_page_size_ctrl = self._build_spin_control_group(
            page,
            label_text="Playlists carregadas por vez",
            help_text=(
                "Define quantas playlists da sua biblioteca são trazidas em cada carregamento. "
                "Valores menores aceleram a abertura; ao chegar ao final da lista o player oferece carregar mais."
            ),
            min_value=MIN_YOUTUBE_MUSIC_LIBRARY_PAGE_SIZE,
            max_value=MAX_YOUTUBE_MUSIC_LIBRARY_PAGE_SIZE,
        )

        home_limit_group, self.youtube_music_home_discovery_limit_ctrl = self._build_spin_control_group(
            page,
            label_text="Mixes personalizadas para descobrir",
            help_text=(
                "Limite máximo de itens varridos na página inicial do YouTube Music para encontrar "
                "mixes personalizadas. Valores menores deixam a sincronização mais rápida."
            ),
            min_value=MIN_YOUTUBE_MUSIC_HOME_DISCOVERY_LIMIT,
            max_value=MAX_YOUTUBE_MUSIC_HOME_DISCOVERY_LIMIT,
        )

        library_box.Add(page_size_group, 0, wx.ALL | wx.EXPAND, 6)
        library_box.Add(home_limit_group, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 6)

        self.youtube_music_manage_dependencies_checkbox.Bind(
            wx.EVT_CHECKBOX,
            self._on_toggle_youtube_music_manage_dependencies,
        )
        self.youtube_music_auto_update_dependencies_checkbox.Bind(
            wx.EVT_CHECKBOX,
            self._on_toggle_youtube_music_auto_update_dependencies,
        )

        page_sizer.Add(info_label, 0, wx.ALL | wx.EXPAND, 10)
        page_sizer.Add(resources_box, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)
        page_sizer.Add(library_box, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)

        self.notebook.AddPage(page, "Recursos adicionais")

    def _create_tab_page(self, name):
        page = wx.Panel(self.notebook)
        page.SetName(name)
        page_sizer = wx.BoxSizer(wx.VERTICAL)
        page.SetSizer(page_sizer)
        return page, page_sizer

    def _configure_checkbox(self, checkbox, name, help_text):
        checkbox.SetName(name)
        checkbox.SetToolTip(help_text)
        checkbox.SetHelpText(help_text)

    def _configure_control(self, control, name, help_text):
        control.SetName(name)
        control.SetToolTip(help_text)
        control.SetHelpText(help_text)

    def _build_spin_control_group(self, parent, label_text, help_text, min_value, max_value):
        label = wx.StaticText(parent, label=f"{label_text}:")
        control = wx.SpinCtrl(parent, min=min_value, max=max_value, name=label_text)
        self._configure_control(control, label_text, help_text)
        return self._build_labeled_control_group(parent, label_text, label, control, help_text), control

    def _build_choice_control_group(self, parent, label_text, help_text, choices):
        label = wx.StaticText(parent, label=f"{label_text}:")
        control = wx.Choice(parent, choices=choices, name=label_text)
        self._configure_control(control, label_text, help_text)
        return self._build_labeled_control_group(parent, label_text, label, control, help_text), control

    def _build_labeled_control_group(self, parent, label_text, visible_label, control, help_text):
        box_sizer = wx.StaticBoxSizer(wx.StaticBox(parent, label=label_text), wx.VERTICAL)
        help_label = wx.StaticText(parent, label=help_text)
        visible_label.Wrap(500)
        help_label.Wrap(500)

        box_sizer.Add(visible_label, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 6)
        box_sizer.Add(control, 0, wx.ALL | wx.EXPAND, 6)
        box_sizer.Add(help_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 6)
        return box_sizer

    def _on_toggle_youtube_music_manage_dependencies(self, _event):
        self._refresh_additional_resources_controls()

    def _on_toggle_youtube_music_auto_update_dependencies(self, _event):
        self._refresh_additional_resources_controls()

    def _refresh_additional_resources_controls(self):
        managed_dependencies_enabled = self.youtube_music_manage_dependencies_checkbox.GetValue()
        auto_update_enabled = self.youtube_music_auto_update_dependencies_checkbox.GetValue()
        self.youtube_music_auto_update_dependencies_checkbox.Enable(managed_dependencies_enabled)
        self.youtube_music_use_nightly_yt_dlp_checkbox.Enable(managed_dependencies_enabled)
        self.youtube_music_dependency_update_interval_ctrl.Enable(managed_dependencies_enabled and auto_update_enabled)

    def _audio_output_choice_labels(self):
        self._audio_output_choice_ids = [""]
        labels = ["Padrão do sistema"]

        selected_device_id = normalize_audio_output_device_id(getattr(self._settings, "audio_output_device_id", ""))
        if not is_selectable_audio_output_device_id(selected_device_id):
            selected_device_id = ""
        seen_ids = {""}

        for device in self._audio_output_devices:
            device_id = normalize_audio_output_device_id(getattr(device, "device_id", ""))
            if not is_selectable_audio_output_device_id(device_id) or device_id in seen_ids:
                continue
            labels.append(getattr(device, "menu_label", device_id))
            self._audio_output_choice_ids.append(device_id)
            seen_ids.add(device_id)

        if selected_device_id and selected_device_id not in seen_ids:
            labels.append(f"Dispositivo salvo indisponível — {selected_device_id}")
            self._audio_output_choice_ids.append(selected_device_id)

        return labels

    def _populate_controls(self, settings):
        self.restore_session_checkbox.SetValue(settings.restore_session_on_startup)
        self.remember_window_size_checkbox.SetValue(settings.remember_window_size)
        self.remember_last_folder_checkbox.SetValue(settings.remember_last_folder)
        self.confirm_on_exit_checkbox.SetValue(settings.confirm_on_exit)
        self.announcements_enabled_checkbox.SetValue(settings.announcements_enabled)
        self.disable_video_output_checkbox.SetValue(settings.disable_video_output)
        self.default_volume_ctrl.SetValue(settings.default_volume)
        self.crossfade_ctrl.SetValue(settings.crossfade_seconds)
        self.crossfade_on_manual_change_checkbox.SetValue(settings.crossfade_on_manual_track_change)
        self.volume_step_ctrl.SetValue(settings.volume_step)
        self.seek_step_ctrl.SetValue(settings.seek_step_seconds)
        self.shuffle_new_playlists_checkbox.SetValue(settings.shuffle_new_playlists)
        self.youtube_music_manage_dependencies_checkbox.SetValue(settings.youtube_music_manage_dependencies)
        self.youtube_music_auto_update_dependencies_checkbox.SetValue(settings.youtube_music_auto_update_dependencies)
        self.youtube_music_use_nightly_yt_dlp_checkbox.SetValue(settings.youtube_music_use_nightly_yt_dlp)
        self.youtube_music_dependency_update_interval_ctrl.SetValue(settings.youtube_music_dependency_update_interval_hours)
        self.youtube_music_library_page_size_ctrl.SetValue(settings.youtube_music_library_page_size)
        self.youtube_music_home_discovery_limit_ctrl.SetValue(settings.youtube_music_home_discovery_limit)

        repeat_mode_index = REPEAT_MODES.index(settings.repeat_mode_new_playlists)
        self.repeat_mode_choice.SetSelection(repeat_mode_index)

        selected_audio_output_device_id = normalize_audio_output_device_id(settings.audio_output_device_id)
        if not is_selectable_audio_output_device_id(selected_audio_output_device_id):
            selected_audio_output_device_id = ""
        try:
            audio_output_index = self._audio_output_choice_ids.index(selected_audio_output_device_id)
        except ValueError:
            audio_output_index = 0
        self.audio_output_choice.SetSelection(audio_output_index)
        self._refresh_additional_resources_controls()

    def get_settings(self):
        settings = replace(self._settings)
        settings.restore_session_on_startup = self.restore_session_checkbox.GetValue()
        settings.remember_window_size = self.remember_window_size_checkbox.GetValue()
        settings.remember_last_folder = self.remember_last_folder_checkbox.GetValue()
        settings.confirm_on_exit = self.confirm_on_exit_checkbox.GetValue()
        settings.announcements_enabled = self.announcements_enabled_checkbox.GetValue()
        settings.disable_video_output = self.disable_video_output_checkbox.GetValue()
        settings.default_volume = int(self.default_volume_ctrl.GetValue())
        settings.crossfade_seconds = int(self.crossfade_ctrl.GetValue())
        settings.crossfade_on_manual_track_change = self.crossfade_on_manual_change_checkbox.GetValue()
        settings.volume_step = int(self.volume_step_ctrl.GetValue())
        settings.seek_step_seconds = int(self.seek_step_ctrl.GetValue())
        settings.shuffle_new_playlists = self.shuffle_new_playlists_checkbox.GetValue()
        settings.repeat_mode_new_playlists = REPEAT_MODES[self.repeat_mode_choice.GetSelection()]
        settings.youtube_music_manage_dependencies = self.youtube_music_manage_dependencies_checkbox.GetValue()
        settings.youtube_music_auto_update_dependencies = self.youtube_music_auto_update_dependencies_checkbox.GetValue()
        settings.youtube_music_use_nightly_yt_dlp = self.youtube_music_use_nightly_yt_dlp_checkbox.GetValue()
        settings.youtube_music_dependency_update_interval_hours = int(
            self.youtube_music_dependency_update_interval_ctrl.GetValue()
        )
        settings.youtube_music_library_page_size = int(self.youtube_music_library_page_size_ctrl.GetValue())
        settings.youtube_music_home_discovery_limit = int(self.youtube_music_home_discovery_limit_ctrl.GetValue())
        selected_audio_output_index = self.audio_output_choice.GetSelection()
        if 0 <= selected_audio_output_index < len(self._audio_output_choice_ids):
            settings.audio_output_device_id = self._audio_output_choice_ids[selected_audio_output_index]
        else:
            settings.audio_output_device_id = ""

        if not settings.remember_last_folder:
            settings.last_open_dir = ""

        return settings

    def _on_register_associations(self, _event):
        from ..file_associations import register_file_associations

        if register_file_associations():
            wx.MessageBox(
                "Associações registradas com sucesso.\n\n"
                "Para definir o player como padrão, vá nas configurações do Windows:\n"
                "Configurações > Aplicativos > Aplicativos padrão.",
                "Associação de arquivos",
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
        else:
            wx.MessageBox(
                "Não foi possível registrar as associações de arquivo.",
                "Associação de arquivos",
                wx.OK | wx.ICON_ERROR,
                self,
            )

    def _on_unregister_associations(self, _event):
        from ..file_associations import unregister_file_associations

        if unregister_file_associations():
            wx.MessageBox(
                "Associações removidas.",
                "Associação de arquivos",
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
        else:
            wx.MessageBox(
                "Não foi possível remover as associações de arquivo.",
                "Associação de arquivos",
                wx.OK | wx.ICON_ERROR,
                self,
            )
