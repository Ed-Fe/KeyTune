from dataclasses import replace
import wx

from ..audio_output import is_selectable_audio_output_device_id, normalize_audio_output_device_id
import os
import subprocess
import sys

from ..constants import (
    LOGGING_LEVEL_LABELS,
    LOGGING_LEVELS,
    MAX_CROSSFADE_SECONDS,
    MAX_YOUTUBE_MUSIC_HOME_DISCOVERY_LIMIT,
    MAX_YOUTUBE_MUSIC_LIBRARY_PAGE_SIZE,
    MIN_YOUTUBE_MUSIC_HOME_DISCOVERY_LIMIT,
    MIN_YOUTUBE_MUSIC_LIBRARY_PAGE_SIZE,
    REPEAT_MODE_LABELS,
    REPEAT_MODES,
)
from ..i18n import _, available_languages, language_display_name
from ..log import get_log_dir


class PreferencesDialog(wx.Dialog):
    def __init__(self, parent, settings, *, audio_output_devices=None):
        super().__init__(
            parent,
            title=_("Preferências"),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self._settings = settings
        self._audio_output_devices = list(audio_output_devices or [])
        self._audio_output_choice_ids = []

        panel = wx.Panel(self)
        root_sizer = wx.BoxSizer(wx.VERTICAL)

        intro_label = wx.StaticText(
            panel,
            label=_(
                "Ajuste como o player inicia, salva estado e responde aos atalhos. "
                "Use as guias para navegar entre as categorias. Pressione Esc para cancelar ou Enter em Salvar para confirmar."
            ),
        )
        intro_label.Wrap(540)

        root_sizer.Add(intro_label, 0, wx.ALL | wx.EXPAND, 10)

        self.notebook = wx.Notebook(panel)
        self.notebook.SetName(_("Categorias de preferências"))

        self._build_general_tab()
        self._build_playback_tab()
        self._build_accessibility_tab()
        self._build_additional_resources_tab()

        root_sizer.Add(self.notebook, 1, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)

        button_sizer = wx.StdDialogButtonSizer()
        self.save_button = wx.Button(panel, wx.ID_OK, _("&Salvar"))
        self.cancel_button = wx.Button(panel, wx.ID_CANCEL, _("&Cancelar"))
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
        self.CentreOnParent()

        self._populate_controls(settings)
        # ESC handling is provided by SetEscapeId(wx.ID_CANCEL) above;
        # an extra EVT_CHAR_HOOK would duplicate that behavior.

    def _build_general_tab(self):
        page, page_sizer = self._create_tab_page(_("Geral"))

        info_label = wx.StaticText(
            page,
            label=_("Configurações relacionadas ao idioma, ao início do player, à sessão salva, ao comportamento ao sair e ao registro de logs."),
        )
        info_label.Wrap(520)

        language_box = wx.StaticBoxSizer(wx.StaticBox(page, label=_("Idioma")), wx.VERTICAL)
        self._language_choice_codes = [""]
        language_labels = [_("Automático (seguir o sistema)")]
        for code in available_languages():
            self._language_choice_codes.append(code)
            language_labels.append(language_display_name(code))

        language_group, self.language_choice = self._build_choice_control_group(
            page,
            label_text=_("Idioma da interface"),
            help_text=_(
                "Define o idioma de menus, diálogos e anúncios do leitor de tela. "
                "Use Automático para seguir o idioma do sistema operacional."
            ),
            choices=language_labels,
        )
        language_box.Add(language_group, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 6)

        language_note = wx.StaticText(
            page,
            label=_("A mudança de idioma é aplicada na próxima vez que o KeyTune for aberto."),
        )
        language_note.Wrap(520)
        language_box.Add(language_note, 0, wx.ALL | wx.EXPAND, 6)

        general_box = wx.StaticBoxSizer(wx.StaticBox(page, label=_("Inicialização e sessão")), wx.VERTICAL)
        self.restore_session_checkbox = wx.CheckBox(page, label=_("&Restaurar sessão ao iniciar"))
        self.remember_window_size_checkbox = wx.CheckBox(page, label=_("Lembrar tamanho da &janela"))
        self.remember_last_folder_checkbox = wx.CheckBox(page, label=_("Lembrar última &pasta usada"))
        self.confirm_on_exit_checkbox = wx.CheckBox(page, label=_("Con&firmar ao sair"))

        self._configure_checkbox(
            self.restore_session_checkbox,
            _("Restaurar sessão ao iniciar"),
            _("Reabre as abas e tenta retomar a última sessão salva ao iniciar o player."),
        )
        self._configure_checkbox(
            self.remember_window_size_checkbox,
            _("Lembrar tamanho da janela"),
            _("Salva e restaura o tamanho da janela principal entre execuções."),
        )
        self._configure_checkbox(
            self.remember_last_folder_checkbox,
            _("Lembrar última pasta usada"),
            _("Usa a última pasta aberta como diretório inicial nos diálogos de abrir e salvar."),
        )
        self._configure_checkbox(
            self.confirm_on_exit_checkbox,
            _("Confirmar ao sair"),
            _("Pede confirmação antes de fechar o player."),
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
            label=_("As mudanças de restauração de sessão e de tamanho da janela afetam principalmente as próximas aberturas do player."),
        )
        note_label.Wrap(520)

        if sys.platform == "win32":
            assoc_box = wx.StaticBoxSizer(wx.StaticBox(page, label=_("Associação de arquivos")), wx.VERTICAL)
            assoc_help = wx.StaticText(
                page,
                label=_(
                    "Registra o player no menu Abrir Com do Windows para formatos de áudio, "
                    "vídeo e playlists. Depois, defina o player como padrão nas configurações do Windows."
                ),
            )
            assoc_help.Wrap(500)
            self._register_assoc_button = wx.Button(page, label=_("&Registrar como player padrão"))
            self._register_assoc_button.SetName(_("Registrar como player padrão"))
            self._unregister_assoc_button = wx.Button(page, label=_("&Desregistrar associações"))
            self._unregister_assoc_button.SetName(_("Desregistrar associações"))

            self._register_assoc_button.Bind(wx.EVT_BUTTON, self._on_register_associations)
            self._unregister_assoc_button.Bind(wx.EVT_BUTTON, self._on_unregister_associations)

            button_row = wx.BoxSizer(wx.HORIZONTAL)
            button_row.Add(self._register_assoc_button, 0, wx.RIGHT, 6)
            button_row.Add(self._unregister_assoc_button, 0, 0)

            assoc_box.Add(assoc_help, 0, wx.ALL | wx.EXPAND, 6)
            assoc_box.Add(button_row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)
        else:
            assoc_box = None

        log_box = wx.StaticBoxSizer(wx.StaticBox(page, label=_("Registro de logs")), wx.VERTICAL)
        self.logging_enabled_checkbox = wx.CheckBox(page, label=_("Registrar &logs de diagnóstico"))
        self._configure_checkbox(
            self.logging_enabled_checkbox,
            _("Registrar logs de diagnóstico"),
            _(
                "Quando ligado, o player grava um arquivo de log rotativo em disco. "
                "Útil para depurar problemas e anexar ao relato de bugs."
            ),
        )
        self.logging_enabled_checkbox.Bind(wx.EVT_CHECKBOX, self._on_toggle_logging_enabled)

        log_level_group, self.logging_level_choice = self._build_choice_control_group(
            page,
            label_text=_("Nível de detalhe"),
            help_text=_(
                "Controla quanta informação é registrada. "
                '"Apenas erros" é o mais silencioso; "Depuração" é o mais detalhado e pode gerar arquivos grandes.'
            ),
            choices=[LOGGING_LEVEL_LABELS[lvl] for lvl in LOGGING_LEVELS],
        )

        open_log_folder_button = wx.Button(page, label=_("Abrir pasta de &logs"))
        open_log_folder_button.SetName(_("Abrir pasta de logs"))
        open_log_folder_button.Bind(wx.EVT_BUTTON, self._on_open_log_folder)

        rotation_note = wx.StaticText(
            page,
            label=_(
                "Os logs são rotacionados automaticamente a cada 2 MB e até 3 arquivos anteriores são mantidos. "
                "Os logs de sessões anteriores ficam em keytune.log.1, .2 e .3 na mesma pasta."
            ),
        )
        rotation_note.Wrap(520)

        log_box.Add(self.logging_enabled_checkbox, 0, wx.ALL | wx.EXPAND, 6)
        log_box.Add(log_level_group, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 6)
        log_box.Add(open_log_folder_button, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)
        log_box.Add(rotation_note, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 6)

        page_sizer.Add(info_label, 0, wx.ALL | wx.EXPAND, 10)
        page_sizer.Add(language_box, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)
        page_sizer.Add(general_box, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)
        page_sizer.Add(note_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)
        if assoc_box:
            page_sizer.Add(assoc_box, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)
        page_sizer.Add(log_box, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)

        self.notebook.AddPage(page, _("Geral"), select=True)

    def _build_playback_tab(self):
        page, page_sizer = self._create_tab_page(_("Reprodução"))

        info_label = wx.StaticText(
            page,
            label=_("Configurações ligadas ao volume, ao avanço na mídia e ao comportamento padrão de playlists novas."),
        )
        info_label.Wrap(520)

        playback_box = wx.StaticBoxSizer(wx.StaticBox(page, label=_("Controles de reprodução")), wx.VERTICAL)
        self.shuffle_new_playlists_checkbox = wx.CheckBox(page, label=_("Ativar e&mbaralhamento em novas playlists"))
        self.disable_video_output_checkbox = wx.CheckBox(page, label=_("Desativar saída de &vídeo (tocar só o áudio)"))
        self._configure_checkbox(
            self.shuffle_new_playlists_checkbox,
            _("Ativar embaralhamento em novas playlists"),
            _("Ativa o modo aleatório automaticamente em playlists criadas depois de salvar as preferências."),
        )
        self._configure_checkbox(
            self.disable_video_output_checkbox,
            _("Desativar saída de vídeo"),
            _(
                "Mantém a reprodução apenas em áudio, inclusive em arquivos de vídeo. "
                "Útil para evitar a abertura de janelas externas de vídeo no Windows."
            ),
        )

        volume_group, self.default_volume_ctrl = self._build_spin_control_group(
            page,
            label_text=_("Volume padrão"),
            help_text=_("Define o volume inicial do player. 0 é mudo e 100 é o máximo."),
            min_value=0,
            max_value=100,
        )
        volume_step_group, self.volume_step_ctrl = self._build_spin_control_group(
            page,
            label_text=_("Passo de volume"),
            help_text=_("Valor usado ao aumentar ou diminuir o volume com as setas para cima e para baixo."),
            min_value=1,
            max_value=25,
        )
        crossfade_group, self.crossfade_ctrl = self._build_spin_control_group(
            page,
            label_text=_("Crossfade (segundos, 0 desativa)"),
            help_text=_(
                "Define por quantos segundos duas faixas de áudio se sobrepõem na transição. "
                "Use 0 para desativar. O crossfade só é aplicado entre arquivos de áudio e "
                "acontece automaticamente no final de cada faixa."
            ),
            min_value=0,
            max_value=MAX_CROSSFADE_SECONDS,
        )
        self.crossfade_on_manual_change_checkbox = wx.CheckBox(
            page, label=_("Aplicar crossfade ao trocar de faixa &manualmente")
        )
        self._configure_checkbox(
            self.crossfade_on_manual_change_checkbox,
            _("Aplicar crossfade ao trocar de faixa manualmente"),
            _(
                "Quando ligado, o crossfade também é usado ao avançar ou voltar com os controles. "
                "Por padrão, o crossfade só é aplicado no fim natural de cada faixa."
            ),
        )
        seek_step_group, self.seek_step_ctrl = self._build_spin_control_group(
            page,
            label_text=_("Passo de busca (segundos)"),
            help_text=_("Valor usado para avançar ou retroceder na mídia com as setas esquerda e direita."),
            min_value=1,
            max_value=120,
        )
        repeat_group, self.repeat_mode_choice = self._build_choice_control_group(
            page,
            label_text=_("Repetição padrão"),
            help_text=_("Modo de repetição aplicado automaticamente às playlists novas."),
            choices=[REPEAT_MODE_LABELS[mode] for mode in REPEAT_MODES],
        )
        audio_output_group, self.audio_output_choice = self._build_choice_control_group(
            page,
            label_text=_("Dispositivo de áudio"),
            help_text=_(
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

        self.notebook.AddPage(page, _("Reprodução"))

    def _build_accessibility_tab(self):
        page, page_sizer = self._create_tab_page(_("Acessibilidade"))

        info_label = wx.StaticText(
            page,
            label=_("Configurações ligadas aos anúncios enviados ao leitor de tela e à navegação das preferências."),
        )
        info_label.Wrap(520)

        accessibility_box = wx.StaticBoxSizer(wx.StaticBox(page, label=_("Leitor de tela")), wx.VERTICAL)
        self.announcements_enabled_checkbox = wx.CheckBox(page, label=_("Ativar a&núncios de acessibilidade"))
        self._configure_checkbox(
            self.announcements_enabled_checkbox,
            _("Ativar anúncios de acessibilidade"),
            _("Liga ou desliga os anúncios enviados ao leitor de tela."),
        )
        accessibility_box.Add(self.announcements_enabled_checkbox, 0, wx.ALL | wx.EXPAND, 6)

        help_label = wx.StaticText(
            page,
            label=_("Se essa opção estiver desligada, o player deixa de anunciar mudanças como tempo, volume e troca de abas."),
        )
        help_label.Wrap(520)

        page_sizer.Add(info_label, 0, wx.ALL | wx.EXPAND, 10)
        page_sizer.Add(accessibility_box, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)
        page_sizer.Add(help_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)

        self.notebook.AddPage(page, _("Acessibilidade"))

    def _build_additional_resources_tab(self):
        page, page_sizer = self._create_tab_page(_("Recursos adicionais"))
        self._additional_resources_page = page

        info_label = wx.StaticText(
            page,
            label=_(
                "Configure integrações e componentes opcionais do player. "
                "Novos recursos adicionais poderão aparecer aqui no futuro, sem misturar essas opções com as preferências gerais."
            ),
        )
        info_label.Wrap(520)

        self.youtube_music_resources_box = wx.StaticBoxSizer(
            wx.StaticBox(page, label=_("Integração com YouTube Music e YouTube")),
            wx.VERTICAL,
        )
        self.youtube_music_manage_dependencies_checkbox = wx.CheckBox(
            page,
            label=_("Ativar &recursos adicionais para YouTube Music e YouTube (yt-dlp e ytmusicapi)"),
        )
        self.youtube_music_auto_update_dependencies_checkbox = wx.CheckBox(
            page,
            label=_("Atualizar automaticamente as dependências do YouTube Music"),
        )
        self.youtube_music_use_nightly_yt_dlp_checkbox = wx.CheckBox(
            page,
            label=_("Usar versão &nightly do yt-dlp (recomendado)"),
        )

        self._configure_checkbox(
            self.youtube_music_manage_dependencies_checkbox,
            _("Ativar integração com YouTube Music e YouTube"),
            _(
                "Baixa e mantém um yt-dlp executável atualizado junto com os recursos Python do "
                "YouTube Music em uma pasta local de recursos adicionais."
            ),
        )
        self._configure_checkbox(
            self.youtube_music_auto_update_dependencies_checkbox,
            _("Atualizar automaticamente dependências do YouTube Music"),
            _("Verifica e aplica atualização automática das dependências no intervalo definido abaixo."),
        )
        self._configure_checkbox(
            self.youtube_music_use_nightly_yt_dlp_checkbox,
            _("Usar versão nightly do yt-dlp"),
            _(
                "Baixa builds nightly oficiais do yt-dlp. Recomendado porque YouTube e YouTube Music quebram "
                "extractors com frequência e o nightly costuma receber correções antes do canal estável."
            ),
        )

        self.youtube_music_dependency_interval_group, self.youtube_music_dependency_update_interval_ctrl = self._build_spin_control_group(
            page,
            label_text=_("Intervalo de atualização (horas)"),
            help_text=_(
                "Define de quanto em quanto tempo o player tenta atualizar o yt-dlp e os recursos Python "
                "quando a aba YouTube Music é aberta."
            ),
            min_value=1,
            max_value=720,
        )

        self.youtube_music_resources_box.Add(self.youtube_music_manage_dependencies_checkbox, 0, wx.ALL | wx.EXPAND, 6)
        self.youtube_music_resources_box.Add(self.youtube_music_auto_update_dependencies_checkbox, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 6)
        self.youtube_music_resources_box.Add(self.youtube_music_use_nightly_yt_dlp_checkbox, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 6)
        self.youtube_music_resources_box.Add(self.youtube_music_dependency_interval_group, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 6)

        self.youtube_music_dependencies_note_label = wx.StaticText(
            page,
            label=_(
                "Na primeira execução, o download pode levar alguns minutos e exige internet. "
                "Ao desativar esta opção, o player apenas para de gerenciar esses recursos automaticamente; "
                "os arquivos já baixados não são removidos."
            ),
        )
        self.youtube_music_dependencies_note_label.Wrap(520)
        self.youtube_music_resources_box.Add(self.youtube_music_dependencies_note_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 6)

        self.youtube_music_library_box = wx.StaticBoxSizer(
            wx.StaticBox(page, label=_("Biblioteca do YouTube Music")),
            wx.VERTICAL,
        )

        page_size_group, self.youtube_music_library_page_size_ctrl = self._build_spin_control_group(
            page,
            label_text=_("Playlists carregadas por vez"),
            help_text=_(
                "Define quantas playlists da sua biblioteca são trazidas em cada carregamento. "
                "Valores menores aceleram a abertura; ao chegar ao final da lista o player oferece carregar mais."
            ),
            min_value=MIN_YOUTUBE_MUSIC_LIBRARY_PAGE_SIZE,
            max_value=MAX_YOUTUBE_MUSIC_LIBRARY_PAGE_SIZE,
        )

        home_limit_group, self.youtube_music_home_discovery_limit_ctrl = self._build_spin_control_group(
            page,
            label_text=_("Mixes personalizadas para descobrir"),
            help_text=_(
                "Limite máximo de itens varridos na página inicial do YouTube Music para encontrar "
                "mixes personalizadas. Valores menores deixam a sincronização mais rápida."
            ),
            min_value=MIN_YOUTUBE_MUSIC_HOME_DISCOVERY_LIMIT,
            max_value=MAX_YOUTUBE_MUSIC_HOME_DISCOVERY_LIMIT,
        )

        self.youtube_music_autoplay_related_checkbox = wx.CheckBox(
            page,
            label=_("Reproduzir conteúdo relacionado ao fim da &playlist (rádio automática)"),
        )
        self._configure_checkbox(
            self.youtube_music_autoplay_related_checkbox,
            _("Reproduzir conteúdo relacionado ao fim da playlist"),
            _(
                "Quando a playlist termina e a última faixa é do YouTube Music, o player busca faixas "
                "relacionadas (a rádio do YouTube Music) e continua tocando automaticamente. "
                "Também pode ser ligado ou desligado com a tecla A durante a reprodução."
            ),
        )

        self.youtube_music_save_history_checkbox = wx.CheckBox(
            page,
            label=_("Salvar músicas escutadas no &histórico do YouTube Music"),
        )
        self._configure_checkbox(
            self.youtube_music_save_history_checkbox,
            _("Salvar músicas escutadas no histórico do YouTube Music"),
            _(
                "Quando ligada, ao escutar uma faixa do YouTube Music por tempo suficiente o player "
                "marca essa faixa como assistida no seu histórico do YouTube Music. Desligue para "
                "tocar sem registrar nada no histórico da sua conta."
            ),
        )

        self.youtube_music_library_box.Add(page_size_group, 0, wx.ALL | wx.EXPAND, 6)
        self.youtube_music_library_box.Add(home_limit_group, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 6)
        self.youtube_music_library_box.Add(
            self.youtube_music_autoplay_related_checkbox, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 6
        )
        self.youtube_music_library_box.Add(
            self.youtube_music_save_history_checkbox, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 6
        )

        self.youtube_music_manage_dependencies_checkbox.Bind(
            wx.EVT_CHECKBOX,
            self._on_toggle_youtube_music_manage_dependencies,
        )
        self.youtube_music_auto_update_dependencies_checkbox.Bind(
            wx.EVT_CHECKBOX,
            self._on_toggle_youtube_music_auto_update_dependencies,
        )

        page_sizer.Add(info_label, 0, wx.ALL | wx.EXPAND, 10)
        page_sizer.Add(self.youtube_music_resources_box, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)
        page_sizer.Add(self.youtube_music_library_box, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)

        self.notebook.AddPage(page, _("Recursos adicionais"))

    def _create_tab_page(self, name):
        page = wx.Panel(self.notebook)
        page.SetName(name)
        page_sizer = wx.BoxSizer(wx.VERTICAL)
        page.SetSizer(page_sizer)
        return page, page_sizer

    def _on_toggle_logging_enabled(self, _event):
        self._refresh_logging_controls()
        if self.logging_enabled_checkbox.GetValue():
            self._announce_from_parent(_("Registro de logs ativado. Nível de detalhe disponível."))
        else:
            self._announce_from_parent(_("Registro de logs desativado. Nível de detalhe indisponível."))

    def _refresh_logging_controls(self):
        enabled = self.logging_enabled_checkbox.GetValue()
        self.logging_level_choice.Enable(enabled)

    def _on_open_log_folder(self, _event):
        import os

        log_dir = get_log_dir()
        os.makedirs(log_dir, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(log_dir)
        else:
            subprocess.Popen(["xdg-open", log_dir])

    def _configure_checkbox(self, checkbox, name, help_text):
        checkbox.SetName(name)
        checkbox.SetToolTip(help_text)

    def _configure_control(self, control, name, help_text):
        control.SetName(name)
        control.SetToolTip(help_text)

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
        # A plain vertical sizer, not a per-control StaticBox: each control here
        # already lives inside a section StaticBox (e.g. "Controles de
        # reprodução"), so wrapping every single field in its own box repeated
        # the same caption as a third copy of the label (box caption == visible
        # label == accessible name) and nested groupings the screen reader
        # announces on entry. The visible label and accessible name remain.
        box_sizer = wx.BoxSizer(wx.VERTICAL)
        help_label = wx.StaticText(parent, label=help_text)
        visible_label.Wrap(500)
        help_label.Wrap(500)

        box_sizer.Add(visible_label, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 6)
        box_sizer.Add(control, 0, wx.ALL | wx.EXPAND, 6)
        box_sizer.Add(help_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 6)
        return box_sizer

    def _announce_from_parent(self, message):
        if not message:
            return
        parent = self.GetParent()
        announce = getattr(parent, "_announce", None)
        if callable(announce):
            announce(message)

    def _on_toggle_youtube_music_manage_dependencies(self, _event):
        self._refresh_additional_resources_controls()
        if self.youtube_music_manage_dependencies_checkbox.GetValue():
            self._announce_from_parent(_("Integração com YouTube Music ativada. Opções adicionais disponíveis."))
        else:
            self._announce_from_parent(_("Integração com YouTube Music desativada. Opções adicionais ocultadas."))

    def _on_toggle_youtube_music_auto_update_dependencies(self, _event):
        self._refresh_additional_resources_controls()
        if self.youtube_music_auto_update_dependencies_checkbox.GetValue():
            self._announce_from_parent(_("Atualização automática ativada. Intervalo de atualização disponível."))
        else:
            self._announce_from_parent(_("Atualização automática desativada. Intervalo de atualização indisponível."))

    def _refresh_additional_resources_controls(self):
        managed_dependencies_enabled = self.youtube_music_manage_dependencies_checkbox.GetValue()
        auto_update_enabled = self.youtube_music_auto_update_dependencies_checkbox.GetValue()
        self.youtube_music_auto_update_dependencies_checkbox.Enable(managed_dependencies_enabled)
        self.youtube_music_use_nightly_yt_dlp_checkbox.Enable(managed_dependencies_enabled)
        self.youtube_music_dependency_update_interval_ctrl.Enable(managed_dependencies_enabled and auto_update_enabled)
        self._set_additional_resources_item_visibility(
            self.youtube_music_resources_box,
            self.youtube_music_auto_update_dependencies_checkbox,
            managed_dependencies_enabled,
        )
        self._set_additional_resources_item_visibility(
            self.youtube_music_resources_box,
            self.youtube_music_use_nightly_yt_dlp_checkbox,
            managed_dependencies_enabled,
        )
        self._set_additional_resources_item_visibility(
            self.youtube_music_resources_box,
            self.youtube_music_dependency_interval_group,
            managed_dependencies_enabled,
        )
        self._set_additional_resources_item_visibility(
            self.youtube_music_resources_box,
            self.youtube_music_dependencies_note_label,
            managed_dependencies_enabled,
        )
        self._set_additional_resources_item_visibility(
            self._additional_resources_page.GetSizer(),
            self.youtube_music_library_box,
            managed_dependencies_enabled,
        )
        self._additional_resources_page.Layout()
        self.notebook.Layout()
        self.Layout()

    def _set_additional_resources_item_visibility(self, sizer, item, visible):
        try:
            sizer.Show(item, visible, True)
        except TypeError:
            sizer.Show(item, visible)

    def _audio_output_choice_labels(self):
        self._audio_output_choice_ids = [""]
        labels = [_("Padrão do sistema")]

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
            labels.append(_("Dispositivo salvo indisponível — {device}").format(device=selected_device_id))
            self._audio_output_choice_ids.append(selected_device_id)

        return labels

    def _populate_controls(self, settings):
        try:
            language_index = self._language_choice_codes.index(settings.language or "")
        except ValueError:
            language_index = 0
        self.language_choice.SetSelection(language_index)
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
        self.youtube_music_autoplay_related_checkbox.SetValue(settings.youtube_music_autoplay_related)
        self.youtube_music_save_history_checkbox.SetValue(settings.youtube_music_save_history)
        self.logging_enabled_checkbox.SetValue(settings.logging_enabled)
        try:
            logging_level_index = list(LOGGING_LEVELS).index(settings.logging_level)
        except ValueError:
            logging_level_index = list(LOGGING_LEVELS).index("WARNING")
        self.logging_level_choice.SetSelection(logging_level_index)
        self._refresh_logging_controls()

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
        selected_language_index = self.language_choice.GetSelection()
        if 0 <= selected_language_index < len(self._language_choice_codes):
            settings.language = self._language_choice_codes[selected_language_index]
        else:
            settings.language = ""
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
        settings.youtube_music_autoplay_related = self.youtube_music_autoplay_related_checkbox.GetValue()
        settings.youtube_music_save_history = self.youtube_music_save_history_checkbox.GetValue()
        selected_audio_output_index = self.audio_output_choice.GetSelection()
        if 0 <= selected_audio_output_index < len(self._audio_output_choice_ids):
            settings.audio_output_device_id = self._audio_output_choice_ids[selected_audio_output_index]
        else:
            settings.audio_output_device_id = ""

        if not settings.remember_last_folder:
            settings.last_open_dir = ""

        settings.logging_enabled = self.logging_enabled_checkbox.GetValue()
        selected_level_index = self.logging_level_choice.GetSelection()
        if 0 <= selected_level_index < len(LOGGING_LEVELS):
            settings.logging_level = LOGGING_LEVELS[selected_level_index]

        return settings

    def _on_register_associations(self, _event):
        from ..file_associations import register_file_associations

        if register_file_associations():
            response = wx.MessageBox(
                _("Associações registradas com sucesso.")
                + "\n\n"
                + _("Para definir o KeyTune como player padrão, abra as configurações de Aplicativos padrão do Windows. Deseja abri-las agora?"),
                _("Associação de arquivos"),
                wx.YES_NO | wx.ICON_INFORMATION,
                self,
            )
            if response == wx.YES:
                self._open_default_apps_settings()
        else:
            wx.MessageBox(
                _("Não foi possível registrar as associações de arquivo."),
                _("Associação de arquivos"),
                wx.OK | wx.ICON_ERROR,
                self,
            )

    def _open_default_apps_settings(self):
        try:
            import os

            os.startfile("ms-settings:defaultapps")
        except OSError:
            wx.MessageBox(
                _("Não foi possível abrir as configurações do Windows.")
                + "\n\n"
                + _("Abra manualmente: Configurações > Aplicativos > Aplicativos padrão."),
                _("Aplicativos padrão"),
                wx.OK | wx.ICON_INFORMATION,
                self,
            )

    def _on_unregister_associations(self, _event):
        from ..file_associations import unregister_file_associations

        if unregister_file_associations():
            wx.MessageBox(
                _("Associações removidas."),
                _("Associação de arquivos"),
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
        else:
            wx.MessageBox(
                _("Não foi possível remover as associações de arquivo."),
                _("Associação de arquivos"),
                wx.OK | wx.ICON_ERROR,
                self,
            )
