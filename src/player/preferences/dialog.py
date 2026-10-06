from dataclasses import replace
import wx

import os
import subprocess
import sys

from ..audio_output import is_selectable_audio_output_device_id, normalize_audio_output_device_id

from ..constants import (
    AUTODJ_BEAT_COUNTS,
    AUTODJ_PROFILES,
    LOGGING_LEVEL_LABELS,
    LOGGING_LEVELS,
    MAX_CROSSFADE_SECONDS,
    MAX_SMART_LIBRARY_CACHE_LIMIT,
    MAX_SMART_LIBRARY_HISTORY_LIMIT,
    MAX_SMART_LIBRARY_RESUME_EDGE_SECONDS,
    MAX_SMART_LIBRARY_RESUME_MINIMUM_MINUTES,
    MAX_YOUTUBE_MUSIC_HOME_DISCOVERY_LIMIT,
    MAX_YOUTUBE_MUSIC_LIBRARY_PAGE_SIZE,
    MIN_SMART_LIBRARY_CACHE_LIMIT,
    MIN_SMART_LIBRARY_HISTORY_LIMIT,
    MIN_SMART_LIBRARY_RESUME_EDGE_SECONDS,
    MIN_SMART_LIBRARY_RESUME_MINIMUM_MINUTES,
    MIN_YOUTUBE_MUSIC_HOME_DISCOVERY_LIMIT,
    MIN_YOUTUBE_MUSIC_LIBRARY_PAGE_SIZE,
    REPEAT_MODE_LABELS,
    REPEAT_MODES,
)
from ..download.ffmpeg import ffmpeg_available
from ..download.panel import DownloadOptionsPanel
from ..i18n import _, available_languages, language_display_name
from ..log import get_log_dir
from ..widgets import (
    ROW_BORDER,
    add_choice_row,
    add_labeled_row,
    create_group,
    describe_control,
    equalize_row_controls,
)


AUTODJ_PROFILE_LABELS = {
    "smooth": _("Suave"),
    "party": _("Festa"),
    "electronic": _("Eletrônica"),
}


class PreferencesDialog(wx.Dialog):
    def __init__(self, parent, settings, *, audio_output_devices=None):
        super().__init__(
            parent,
            title=_("Preferências"),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self._settings = settings
        self._autodj_optional_resources_confirmed = bool(
            getattr(settings, "autodj_optional_resources_confirmed", False)
        )
        self._audio_output_devices = list(audio_output_devices or [])
        self._audio_output_choice_ids = []

        panel = wx.Panel(self)
        root_sizer = wx.BoxSizer(wx.VERTICAL)

        # Várias linhas de guias: se os nomes não couberem (fonte maior, tradução
        # mais longa), as guias quebram em outra linha em vez de ficarem escondidas
        # atrás de setas de rolagem.
        self.notebook = wx.Notebook(panel, style=wx.NB_MULTILINE)
        self.notebook.SetName(_("Categorias de preferências"))

        self._build_general_tab()
        self._build_playback_tab()
        self._build_accessibility_tab()
        self._build_smart_library_tab()
        self._build_download_tab()
        self._build_keytube_tab()
        self._build_radio_tab()
        self._build_additional_resources_tab()
        equalize_row_controls(self.notebook)

        root_sizer.Add(self.notebook, 1, wx.ALL | wx.EXPAND, 10)

        button_sizer = wx.StdDialogButtonSizer()
        self.save_button = wx.Button(panel, wx.ID_OK, _("&Salvar"))
        self.cancel_button = wx.Button(panel, wx.ID_CANCEL, _("&Cancelar"))
        self.save_button.SetDefault()
        self.save_button.Bind(wx.EVT_BUTTON, self._on_save_preferences)
        button_sizer.AddButton(self.save_button)
        button_sizer.AddButton(self.cancel_button)
        button_sizer.Realize()
        root_sizer.Add(button_sizer, 0, wx.ALL | wx.EXPAND, 10)

        panel.SetSizer(root_sizer)

        frame_sizer = wx.BoxSizer(wx.VERTICAL)
        frame_sizer.Add(panel, 1, wx.EXPAND)
        self.SetSizer(frame_sizer)
        self.SetMinSize(self.FromDIP(wx.Size(620, 480)))
        # As guias rolam, então o diálogo tem um tamanho próprio em vez de
        # crescer até caber a guia mais longa.
        display_size = wx.Display(max(wx.Display.GetFromWindow(parent) if parent else 0, 0)).GetClientArea().GetSize()
        wanted_size = self.FromDIP(wx.Size(720, 600))
        self.SetSize((min(wanted_size.width, display_size.width), min(wanted_size.height, display_size.height)))
        self.SetEscapeId(wx.ID_CANCEL)
        self.CentreOnParent()

        self._populate_controls(settings)
        # ESC handling is provided by SetEscapeId(wx.ID_CANCEL) above;
        # an extra EVT_CHAR_HOOK would duplicate that behavior.

    def _build_general_tab(self):
        page, page_sizer = self._create_tab_page()

        box, sizer = self._create_group(page, page_sizer, _("Idioma"))
        self._language_choice_codes = [""]
        language_labels = [_("Automático (seguir o sistema)")]
        for code in available_languages():
            self._language_choice_codes.append(code)
            language_labels.append(language_display_name(code))
        self.language_choice = self._add_choice(
            box, sizer, _("Idioma da interface"), _("Aplicado na próxima vez que o KeyTune for aberto."), language_labels
        )

        box, sizer = self._create_group(page, page_sizer, _("Inicialização e sessão"))
        self.restore_session_checkbox = self._add_checkbox(
            box, sizer, _("&Restaurar sessão ao iniciar"), _("Reabre as abas da última sessão.")
        )
        self.remember_window_size_checkbox = self._add_checkbox(
            box, sizer, _("Lembrar tamanho da &janela"), _("Restaura o tamanho da janela principal.")
        )
        self.remember_last_folder_checkbox = self._add_checkbox(
            box, sizer, _("Lembrar última &pasta usada"), _("Abre os diálogos de arquivo na última pasta usada.")
        )
        self.confirm_on_exit_checkbox = self._add_checkbox(
            box, sizer, _("Con&firmar ao sair"), _("Pede confirmação antes de fechar.")
        )
        self.quick_player_checkbox = self._add_checkbox(
            box,
            sizer,
            _("Usar o player rápido ao abrir arqui&vos pelo Windows"),
            _("Toca numa janela pequena, sem carregar as playlists."),
        )

        box, sizer = self._create_group(page, page_sizer, _("Bandeja do sistema"))
        self.minimize_to_tray_checkbox = self._add_checkbox(
            box,
            sizer,
            _("M&inimizar para a bandeja do sistema"),
            _("Ao minimizar, a janela sai da barra de tarefas e fica um ícone perto do relógio."),
        )
        self.close_to_tray_checkbox = self._add_checkbox(
            box,
            sizer,
            _("Ao fechar, manter tocando na band&eja"),
            _("Fechar a janela só a esconde; para sair, use Arquivo > Sair ou o menu do ícone."),
        )

        if sys.platform == "win32":
            box, sizer = self._create_group(page, page_sizer, _("Associação de arquivos"))
            self._register_assoc_button = wx.Button(box, label=_("Re&gistrar como player padrão"))
            self._unregister_assoc_button = wx.Button(box, label=_("&Desregistrar associações"))
            describe_control(
                self._register_assoc_button,
                self._register_assoc_button.GetLabelText(),
                _("Põe o KeyTune no menu Abrir com do Windows para áudio, vídeo e playlists."),
            )
            self._register_assoc_button.Bind(wx.EVT_BUTTON, self._on_register_associations)
            self._unregister_assoc_button.Bind(wx.EVT_BUTTON, self._on_unregister_associations)

            button_row = wx.BoxSizer(wx.HORIZONTAL)
            button_row.Add(self._register_assoc_button, 0, wx.RIGHT, 6)
            button_row.Add(self._unregister_assoc_button, 0, 0)
            sizer.Add(button_row, 0, wx.ALL, ROW_BORDER)

        box, sizer = self._create_group(page, page_sizer, _("Registro de logs"))
        self.logging_enabled_checkbox = self._add_checkbox(
            box, sizer, _("Registrar &logs de diagnóstico"), _("Grava um arquivo de log, útil para relatar problemas.")
        )
        self.logging_enabled_checkbox.Bind(wx.EVT_CHECKBOX, self._on_toggle_logging_enabled)
        self.logging_level_choice = self._add_choice(
            box,
            sizer,
            _("Nível de detalhe"),
            _("Quanto mais detalhado, maior o arquivo."),
            [LOGGING_LEVEL_LABELS[lvl] for lvl in LOGGING_LEVELS],
        )
        open_log_folder_button = wx.Button(box, label=_("Abrir pasta de l&ogs"))
        open_log_folder_button.Bind(wx.EVT_BUTTON, self._on_open_log_folder)
        sizer.Add(open_log_folder_button, 0, wx.ALL, ROW_BORDER)

        self.notebook.AddPage(page, _("Geral"), select=True)

    def _build_playback_tab(self):
        page, page_sizer = self._create_tab_page()

        box, sizer = self._create_group(page, page_sizer, _("Volume"))
        self.default_volume_ctrl = self._add_spin(
            box, sizer, _("Volume padrão"), _("Volume inicial, de 0 a 100."), 0, 100
        )
        self.volume_step_ctrl = self._add_spin(
            box, sizer, _("Passo de volume"), _("Quanto o volume muda a cada seta para cima ou para baixo."), 1, 25
        )

        box, sizer = self._create_group(page, page_sizer, _("Avanço e transição entre faixas"))
        self.seek_step_ctrl = self._add_spin(
            box,
            sizer,
            _("Passo de busca (segundos)"),
            _("Quanto a mídia avança ou volta a cada seta esquerda ou direita."),
            1,
            120,
        )
        self.crossfade_ctrl = self._add_spin(
            box,
            sizer,
            _("Crossfade (segundos, 0 desativa)"),
            _("Sobreposição entre duas faixas de áudio."),
            0,
            MAX_CROSSFADE_SECONDS,
        )
        self.crossfade_on_manual_change_checkbox = self._add_checkbox(
            box,
            sizer,
            _("Aplicar crossfade ao trocar de fai&xa manualmente"),
            _("Usa o crossfade também ao avançar ou voltar pelos controles."),
        )

        box, sizer = self._create_group(page, page_sizer, _("Playlists novas"))
        self.repeat_mode_choice = self._add_choice(
            box,
            sizer,
            _("Repetição padrão"),
            _("Modo de repetição das playlists novas."),
            [REPEAT_MODE_LABELS[mode] for mode in REPEAT_MODES],
        )
        self.shuffle_new_playlists_checkbox = self._add_checkbox(
            box,
            sizer,
            _("Ativar e&mbaralhamento em novas playlists"),
            _("Playlists novas já começam em modo aleatório."),
        )

        box, sizer = self._create_group(page, page_sizer, _("Saída de áudio e vídeo"))
        self.audio_output_choice = self._add_choice(
            box,
            sizer,
            _("Dispositivo de áudio"),
            _("Saída de áudio usada na reprodução."),
            self._audio_output_choice_labels(),
        )
        self.disable_video_output_checkbox = self._add_checkbox(
            box,
            sizer,
            _("Desativar saída de &vídeo (tocar só o áudio)"),
            _("Toca só o áudio, mesmo em arquivos de vídeo."),
        )
        self.live_video_checkbox = self._add_checkbox(
            box,
            sizer,
            _("Mostrar o vídeo das &transmissões ao vivo"),
            _("Vale mesmo com a saída de vídeo desativada. Ctrl+Alt+V alterna."),
        )

        self.notebook.AddPage(page, _("Reprodução"))

    def _build_accessibility_tab(self):
        page, page_sizer = self._create_tab_page()

        box, sizer = self._create_group(page, page_sizer, _("Leitor de tela"))
        self.announcements_enabled_checkbox = self._add_checkbox(
            box,
            sizer,
            _("Ativar a&núncios de acessibilidade"),
            _("Anuncia mudanças como tempo, volume e troca de abas."),
        )

        self.notebook.AddPage(page, _("Acessibilidade"))

    def _build_smart_library_tab(self):
        page, page_sizer = self._create_tab_page()

        box, sizer = self._create_group(page, page_sizer, _("Índice da biblioteca"))
        self.smart_library_enabled_checkbox = self._add_checkbox(
            box,
            sizer,
            _("Ativar a &biblioteca inteligente"),
            _("Busca global (Ctrl+G), favoritos, avaliações, histórico e retomada. Tudo fica no seu computador."),
        )
        self.smart_library_index_opened_folders_checkbox = self._add_checkbox(
            box,
            sizer,
            _("Indexar automaticamente as &pastas abertas no navegador"),
            _("As mídias da pasta entram no índice em segundo plano."),
        )

        box, sizer = self._create_group(page, page_sizer, _("Histórico de reprodução"))
        self.smart_library_history_enabled_checkbox = self._add_checkbox(
            box, sizer, _("Guardar um &histórico local de reprodução"), _("Registra as faixas ouvidas.")
        )
        self.smart_library_history_limit_ctrl = self._add_spin(
            box,
            sizer,
            _("Reproduções guardadas no histórico"),
            _("Acima desse número, as mais antigas saem."),
            MIN_SMART_LIBRARY_HISTORY_LIMIT,
            MAX_SMART_LIBRARY_HISTORY_LIMIT,
        )

        box, sizer = self._create_group(page, page_sizer, _("Retomar de onde parou"))
        self.smart_library_resume_enabled_checkbox = self._add_checkbox(
            box,
            sizer,
            _("&Lembrar a posição de mídias longas"),
            _("Podcasts, audiolivros e vídeos longos voltam do ponto onde pararam."),
        )
        self.smart_library_resume_minimum_ctrl = self._add_spin(
            box,
            sizer,
            _("Duração mínima para lembrar a posição (minutos)"),
            _("Mídias mais curtas sempre recomeçam do início."),
            MIN_SMART_LIBRARY_RESUME_MINIMUM_MINUTES,
            MAX_SMART_LIBRARY_RESUME_MINIMUM_MINUTES,
        )
        self.smart_library_resume_edge_ctrl = self._add_spin(
            box,
            sizer,
            _("Margem ignorada no início e no fim (segundos)"),
            _("Parar dentro dessa margem não cria ponto de retomada."),
            MIN_SMART_LIBRARY_RESUME_EDGE_SECONDS,
            MAX_SMART_LIBRARY_RESUME_EDGE_SECONDS,
        )

        box, sizer = self._create_group(page, page_sizer, _("Cache de metadados e análises"))
        self.smart_library_cache_limit_ctrl = self._add_spin(
            box,
            sizer,
            _("Entradas guardadas no cache"),
            _("Ao atingir o limite, as mais antigas saem."),
            MIN_SMART_LIBRARY_CACHE_LIMIT,
            MAX_SMART_LIBRARY_CACHE_LIMIT,
        )

        self.smart_library_enabled_checkbox.Bind(wx.EVT_CHECKBOX, self._on_toggle_smart_library_enabled)
        self.smart_library_history_enabled_checkbox.Bind(wx.EVT_CHECKBOX, self._on_toggle_smart_library_history)
        self.smart_library_resume_enabled_checkbox.Bind(wx.EVT_CHECKBOX, self._on_toggle_smart_library_resume)

        self.notebook.AddPage(page, _("Biblioteca"))

    def _on_toggle_smart_library_enabled(self, _event):
        self._refresh_smart_library_controls()
        if self.smart_library_enabled_checkbox.GetValue():
            self._announce_from_parent(_("Biblioteca inteligente ativada. Opções disponíveis."))
        else:
            self._announce_from_parent(_("Biblioteca inteligente desativada. Opções indisponíveis."))

    def _on_toggle_smart_library_history(self, _event):
        self._refresh_smart_library_controls()

    def _on_toggle_smart_library_resume(self, _event):
        self._refresh_smart_library_controls()

    def _refresh_smart_library_controls(self):
        library_enabled = self.smart_library_enabled_checkbox.GetValue()
        history_enabled = library_enabled and self.smart_library_history_enabled_checkbox.GetValue()
        resume_enabled = library_enabled and self.smart_library_resume_enabled_checkbox.GetValue()

        self.smart_library_index_opened_folders_checkbox.Enable(library_enabled)
        self.smart_library_history_enabled_checkbox.Enable(library_enabled)
        self.smart_library_history_limit_ctrl.Enable(history_enabled)
        self.smart_library_resume_enabled_checkbox.Enable(library_enabled)
        self.smart_library_resume_minimum_ctrl.Enable(resume_enabled)
        self.smart_library_resume_edge_ctrl.Enable(resume_enabled)
        self.smart_library_cache_limit_ctrl.Enable(library_enabled)

    def _build_download_tab(self):
        page, page_sizer = self._create_tab_page()

        box, sizer = self._create_group(page, page_sizer, _("Opções de download"))
        self.download_options_panel = DownloadOptionsPanel(box, kind_label=_("Tipo de download padrão"))
        sizer.Add(self.download_options_panel, 0, wx.EXPAND)
        self.download_always_ask_checkbox = self._add_checkbox(
            box,
            sizer,
            _("Sempre &mostrar o diálogo ao baixar"),
            _("Confirma formato e qualidade a cada download (Ctrl+Shift+B)."),
        )
        if not ffmpeg_available():
            self._add_note(
                box,
                sizer,
                _("Converter o áudio e baixar vídeo em alta resolução exigem o FFmpeg; o KeyTune oferece instalá-lo quando precisar."),
            )

        self.notebook.AddPage(page, _("Download"))

    def _build_keytube_tab(self):
        page, page_sizer = self._create_tab_page()

        from ..youtube_music.audio_tracks import AUDIO_CHOICE_ORIGINAL, AUDIO_LANGUAGES
        from ..youtube_music.content_locale import CONTENT_LANGUAGES, CONTENT_REGIONS

        box, sizer = self._create_group(page, page_sizer, _("Biblioteca"))
        self.youtube_music_library_page_size_ctrl = self._add_spin(
            box,
            sizer,
            _("Playlists carregadas por vez"),
            _("Valores menores abrem a biblioteca mais rápido."),
            MIN_YOUTUBE_MUSIC_LIBRARY_PAGE_SIZE,
            MAX_YOUTUBE_MUSIC_LIBRARY_PAGE_SIZE,
        )
        self.youtube_music_home_discovery_limit_ctrl = self._add_spin(
            box,
            sizer,
            _("Mixes personalizadas para descobrir"),
            _("Itens da página inicial varridos em busca de mixes."),
            MIN_YOUTUBE_MUSIC_HOME_DISCOVERY_LIMIT,
            MAX_YOUTUBE_MUSIC_HOME_DISCOVERY_LIMIT,
        )
        box, sizer = self._create_group(page, page_sizer, _("Reprodução"))
        self.youtube_music_autoplay_related_checkbox = self._add_checkbox(
            box,
            sizer,
            _("Tocar faixas relacionadas ao fim da &playlist"),
            _("A rádio automática do YouTube Music. A tecla A alterna."),
        )
        self.youtube_music_save_history_checkbox = self._add_checkbox(
            box,
            sizer,
            _("Salvar o que ouvi no &histórico do YouTube Music"),
            _("Marca as faixas ouvidas no histórico da sua conta."),
        )

        box, sizer = self._create_group(page, page_sizer, _("Idioma e região"))
        self._youtube_content_language_codes = [""] + [code for code, _label in CONTENT_LANGUAGES]
        self.youtube_content_language_choice = self._add_choice(
            box,
            sizer,
            _("Idioma do conteúdo"),
            _("Usado nas buscas, nos comentários e nos nomes das faixas de áudio."),
            [_("O mesmo do KeyTune")] + [label for _code, label in CONTENT_LANGUAGES],
        )
        self._youtube_content_region_codes = [""] + [code for code, _label in CONTENT_REGIONS]
        self.youtube_content_region_choice = self._add_choice(
            box,
            sizer,
            _("Região do conteúdo"),
            _("País usado nas buscas do YouTube e do YouTube Music."),
            [_("Automática")] + [label for _code, label in CONTENT_REGIONS],
        )
        self._youtube_audio_language_codes = ["", AUDIO_CHOICE_ORIGINAL] + [code for code, _label in AUDIO_LANGUAGES]
        self.youtube_audio_language_choice = self._add_choice(
            box,
            sizer,
            _("Áudio dos vídeos dublados"),
            _("Faixa tocada nos vídeos com mais de um áudio."),
            [_("A que o YouTube entregar"), _("Original do vídeo")] + [label for _code, label in AUDIO_LANGUAGES],
        )

        self.notebook.AddPage(page, _("KeyTube"))

    def _build_radio_tab(self):
        page, page_sizer = self._create_tab_page()

        from ..youtube_music.content_locale import CONTENT_REGIONS

        box, sizer = self._create_group(page, page_sizer, _("Região"))
        self._radio_country_choices = [("", _("Automático (seguir o sistema)"))] + list(CONTENT_REGIONS)
        saved_radio_code = str(getattr(self._settings, "radio_country_code", "") or "").strip().upper()
        if saved_radio_code and saved_radio_code not in {code for code, _label in self._radio_country_choices}:
            # Escolhido na própria aba de rádios, fora da lista curta daqui.
            saved_radio_name = str(getattr(self._settings, "radio_country_name", "") or "").strip()
            self._radio_country_choices.append((saved_radio_code, saved_radio_name or saved_radio_code))
        self.radio_country_choice = self._add_choice(
            box,
            sizer,
            _("Meu país"),
            _("País do início da aba e da busca. Outros países: menu de ações do país, na aba."),
            [label for _code, label in self._radio_country_choices],
        )

        self.notebook.AddPage(page, _("Rádios online"))

    def _build_additional_resources_tab(self):
        page, page_sizer = self._create_tab_page()

        box, sizer = self._create_group(page, page_sizer, _("Componentes do YouTube"))
        self.youtube_music_manage_dependencies_checkbox = self._add_checkbox(
            box,
            sizer,
            _("Ativar a integração com &YouTube e YouTube Music"),
            _("Baixa e mantém o yt-dlp, o ytmusicapi e o Node.js. Necessário para o KeyTube."),
        )
        self.youtube_music_use_nightly_yt_dlp_checkbox = self._add_checkbox(
            box,
            sizer,
            _("Usar versão &nightly do yt-dlp (recomendado)"),
            _("Recebe correções do YouTube antes da versão estável."),
        )
        self.youtube_music_use_youtubejs_checkbox = self._add_checkbox(
            box, sizer, _("Usar YouTube.&js (recomendado)"), _("Melhora a resolução e a reprodução.")
        )
        self.youtube_music_auto_update_dependencies_checkbox = self._add_checkbox(
            box,
            sizer,
            _("Atualizar os componentes a&utomaticamente"),
            _("Verifica atualizações ao abrir o KeyTube, no intervalo a seguir."),
        )
        self.youtube_music_dependency_update_interval_ctrl = self._add_spin(
            box, sizer, _("Intervalo de atualização (horas)"), _("Horas entre as verificações."), 1, 720
        )

        box, sizer = self._create_group(page, page_sizer, _("AutoDJ"))
        self.autodj_enabled_checkbox = self._add_checkbox(
            box,
            sizer,
            _("Baixar recursos e ativar &AutoDJ"),
            _("Baixa as bibliotecas de análise de áudio: librosa, NumPy, SciPy, Numba e PyAV."),
        )
        self.autodj_profile_choice = self._add_choice(
            box,
            sizer,
            _("Perfil do AutoDJ"),
            _("Estilo da sequência e das transições."),
            [AUTODJ_PROFILE_LABELS[profile] for profile in AUTODJ_PROFILES],
        )
        self.autodj_beats_choice = self._add_choice(
            box,
            sizer,
            _("Duração da transição do AutoDJ"),
            _("Batidas de sobreposição entre duas faixas."),
            [_("{count} batidas").format(count=count) for count in AUTODJ_BEAT_COUNTS],
        )
        self.autodj_transition_sounds_checkbox = self._add_checkbox(
            box,
            sizer,
            _("Tocar efeitos de &DJ nas transições"),
            _("Um efeito curto no início de cada transição."),
        )

        self.youtube_music_manage_dependencies_checkbox.Bind(
            wx.EVT_CHECKBOX,
            self._on_toggle_youtube_music_manage_dependencies,
        )
        self.youtube_music_auto_update_dependencies_checkbox.Bind(
            wx.EVT_CHECKBOX,
            self._on_toggle_youtube_music_auto_update_dependencies,
        )
        self.autodj_enabled_checkbox.Bind(wx.EVT_CHECKBOX, self._on_toggle_autodj_resource)

        self.notebook.AddPage(page, _("Recursos adicionais"))

    def _create_tab_page(self):
        # Rolável: uma guia longa não empurra os botões do diálogo para fora da
        # tela, e o controle que recebe o foco é trazido para a área visível.
        page = wx.ScrolledWindow(self.notebook, style=wx.TAB_TRAVERSAL | wx.VSCROLL)
        page.SetScrollRate(0, 16)
        page_sizer = wx.BoxSizer(wx.VERTICAL)
        page_sizer.AddSpacer(8)
        page.SetSizer(page_sizer)
        return page, page_sizer

    def _create_group(self, page, page_sizer, label):
        """Abre um grupo na página; os controles dele têm a caixa devolvida como pai."""
        box, sizer = create_group(page, label)
        page_sizer.Add(sizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)
        return box, sizer

    def _add_checkbox(self, box, sizer, label, help_text):
        checkbox = wx.CheckBox(box, label=label)
        describe_control(checkbox, checkbox.GetLabelText(), help_text)
        sizer.Add(checkbox, 0, wx.ALL | wx.EXPAND, ROW_BORDER)
        return checkbox

    def _add_spin(self, box, sizer, label_text, help_text, min_value, max_value):
        label = wx.StaticText(box, label=f"{label_text}:")
        control = wx.SpinCtrl(box, min=min_value, max=max_value, name=label_text)
        describe_control(control, label_text, help_text)
        add_labeled_row(sizer, label, control)
        return control

    def _add_choice(self, box, sizer, label_text, help_text, choices):
        return add_choice_row(box, sizer, label_text, help_text, choices)

    def _add_note(self, box, sizer, text):
        note = wx.StaticText(box, label=text)
        note.Wrap(560)
        sizer.Add(note, 0, wx.ALL | wx.EXPAND, ROW_BORDER)
        return note

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
        log_dir = get_log_dir()
        os.makedirs(log_dir, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(log_dir)
        else:
            subprocess.Popen(["xdg-open", log_dir])

    @staticmethod
    def _choice_index(codes, code):
        """A posição de *code* na lista da caixa; a primeira (o padrão) quando ele não está lá."""
        try:
            return codes.index(code or "")
        except ValueError:
            return 0

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
            self._announce_from_parent(_("Integração com o YouTube ativada. Opções dos componentes disponíveis."))
        else:
            self._announce_from_parent(_("Integração com o YouTube desativada. Opções dos componentes indisponíveis."))

    def _on_toggle_autodj_resource(self, _event):
        self._refresh_additional_resources_controls()
        if self.autodj_enabled_checkbox.GetValue():
            self._announce_from_parent(_("AutoDJ selecionado. As bibliotecas serão baixadas após a confirmação."))
        else:
            self._announce_from_parent(_("AutoDJ desativado."))

    def _on_toggle_youtube_music_auto_update_dependencies(self, _event):
        self._refresh_additional_resources_controls()
        if self.youtube_music_auto_update_dependencies_checkbox.GetValue():
            self._announce_from_parent(_("Atualização automática ativada. Intervalo de atualização disponível."))
        else:
            self._announce_from_parent(_("Atualização automática desativada. Intervalo de atualização indisponível."))

    def _refresh_additional_resources_controls(self):
        # Só habilita ou desabilita, e só o que está nesta guia: as opções da
        # guia KeyTube ficam sempre ao alcance do teclado, mesmo antes de a
        # integração ser ativada.
        managed_dependencies_enabled = self.youtube_music_manage_dependencies_checkbox.GetValue()
        auto_update_enabled = self.youtube_music_auto_update_dependencies_checkbox.GetValue()
        for control in (
            self.youtube_music_use_nightly_yt_dlp_checkbox,
            self.youtube_music_use_youtubejs_checkbox,
            self.youtube_music_auto_update_dependencies_checkbox,
        ):
            control.Enable(managed_dependencies_enabled)
        self.youtube_music_dependency_update_interval_ctrl.Enable(managed_dependencies_enabled and auto_update_enabled)

        autodj_enabled = self.autodj_enabled_checkbox.GetValue()
        self.autodj_transition_sounds_checkbox.Enable(autodj_enabled)
        self.autodj_profile_choice.Enable(autodj_enabled)
        self.autodj_beats_choice.Enable(autodj_enabled)

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
        self.quick_player_checkbox.SetValue(settings.quick_player_enabled)
        self.minimize_to_tray_checkbox.SetValue(settings.minimize_to_tray)
        self.close_to_tray_checkbox.SetValue(settings.close_to_tray)
        self.announcements_enabled_checkbox.SetValue(settings.announcements_enabled)
        self.disable_video_output_checkbox.SetValue(settings.disable_video_output)
        self.live_video_checkbox.SetValue(settings.live_video_enabled)
        self.default_volume_ctrl.SetValue(settings.default_volume)
        self.crossfade_ctrl.SetValue(settings.crossfade_seconds)
        self.crossfade_on_manual_change_checkbox.SetValue(settings.crossfade_on_manual_track_change)
        self.autodj_enabled_checkbox.SetValue(settings.autodj_enabled)
        self.autodj_transition_sounds_checkbox.SetValue(settings.autodj_transition_sounds_enabled)
        self.autodj_profile_choice.SetSelection(AUTODJ_PROFILES.index(settings.autodj_profile))
        self.autodj_beats_choice.SetSelection(AUTODJ_BEAT_COUNTS.index(settings.autodj_beats))
        self.volume_step_ctrl.SetValue(settings.volume_step)
        self.seek_step_ctrl.SetValue(settings.seek_step_seconds)
        self.shuffle_new_playlists_checkbox.SetValue(settings.shuffle_new_playlists)
        self.youtube_music_manage_dependencies_checkbox.SetValue(settings.youtube_music_manage_dependencies)
        self.youtube_music_auto_update_dependencies_checkbox.SetValue(settings.youtube_music_auto_update_dependencies)
        self.youtube_music_use_nightly_yt_dlp_checkbox.SetValue(settings.youtube_music_use_nightly_yt_dlp)
        self.youtube_music_use_youtubejs_checkbox.SetValue(settings.youtube_music_use_youtubejs)
        self.youtube_music_dependency_update_interval_ctrl.SetValue(settings.youtube_music_dependency_update_interval_hours)
        self.youtube_music_library_page_size_ctrl.SetValue(settings.youtube_music_library_page_size)
        self.youtube_music_home_discovery_limit_ctrl.SetValue(settings.youtube_music_home_discovery_limit)
        self.youtube_music_autoplay_related_checkbox.SetValue(settings.youtube_music_autoplay_related)
        self.youtube_music_save_history_checkbox.SetValue(settings.youtube_music_save_history)
        self.youtube_content_language_choice.SetSelection(
            self._choice_index(self._youtube_content_language_codes, settings.youtube_content_language)
        )
        self.youtube_content_region_choice.SetSelection(
            self._choice_index(self._youtube_content_region_codes, settings.youtube_content_region)
        )
        self.youtube_audio_language_choice.SetSelection(
            self._choice_index(self._youtube_audio_language_codes, settings.youtube_audio_language)
        )
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

        self.radio_country_choice.SetSelection(
            self._choice_index([code for code, _label in self._radio_country_choices], settings.radio_country_code)
        )

        self.smart_library_enabled_checkbox.SetValue(settings.smart_library_enabled)
        self.smart_library_index_opened_folders_checkbox.SetValue(settings.smart_library_index_opened_folders)
        self.smart_library_history_enabled_checkbox.SetValue(settings.smart_library_history_enabled)
        self.smart_library_history_limit_ctrl.SetValue(settings.smart_library_history_limit)
        self.smart_library_resume_enabled_checkbox.SetValue(settings.smart_library_resume_enabled)
        self.smart_library_resume_minimum_ctrl.SetValue(settings.smart_library_resume_minimum_minutes)
        self.smart_library_resume_edge_ctrl.SetValue(settings.smart_library_resume_edge_seconds)
        self.smart_library_cache_limit_ctrl.SetValue(settings.smart_library_cache_limit)
        self._refresh_smart_library_controls()

        self.download_options_panel.set_values(
            kind=settings.download_kind,
            audio_quality=settings.download_audio_quality,
            video_quality=settings.download_video_quality,
            sample_rate=settings.download_sample_rate,
            directory=settings.download_directory,
        )
        self.download_always_ask_checkbox.SetValue(settings.download_always_ask)

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
        settings.quick_player_enabled = self.quick_player_checkbox.GetValue()
        settings.minimize_to_tray = self.minimize_to_tray_checkbox.GetValue()
        settings.close_to_tray = self.close_to_tray_checkbox.GetValue()
        settings.announcements_enabled = self.announcements_enabled_checkbox.GetValue()
        settings.disable_video_output = self.disable_video_output_checkbox.GetValue()
        settings.live_video_enabled = self.live_video_checkbox.GetValue()
        settings.default_volume = int(self.default_volume_ctrl.GetValue())
        settings.crossfade_seconds = int(self.crossfade_ctrl.GetValue())
        settings.crossfade_on_manual_track_change = self.crossfade_on_manual_change_checkbox.GetValue()
        settings.autodj_enabled = self.autodj_enabled_checkbox.GetValue()
        settings.autodj_optional_resources_confirmed = self._autodj_optional_resources_confirmed
        settings.autodj_transition_sounds_enabled = self.autodj_transition_sounds_checkbox.GetValue()
        settings.autodj_profile = AUTODJ_PROFILES[self.autodj_profile_choice.GetSelection()]
        settings.autodj_beats = AUTODJ_BEAT_COUNTS[self.autodj_beats_choice.GetSelection()]
        settings.volume_step = int(self.volume_step_ctrl.GetValue())
        settings.seek_step_seconds = int(self.seek_step_ctrl.GetValue())
        settings.shuffle_new_playlists = self.shuffle_new_playlists_checkbox.GetValue()
        settings.repeat_mode_new_playlists = REPEAT_MODES[self.repeat_mode_choice.GetSelection()]
        settings.youtube_music_manage_dependencies = self.youtube_music_manage_dependencies_checkbox.GetValue()
        settings.youtube_music_auto_update_dependencies = self.youtube_music_auto_update_dependencies_checkbox.GetValue()
        settings.youtube_music_use_nightly_yt_dlp = self.youtube_music_use_nightly_yt_dlp_checkbox.GetValue()
        settings.youtube_music_use_youtubejs = self.youtube_music_use_youtubejs_checkbox.GetValue()
        settings.youtube_music_dependency_update_interval_hours = int(
            self.youtube_music_dependency_update_interval_ctrl.GetValue()
        )
        settings.youtube_music_library_page_size = int(self.youtube_music_library_page_size_ctrl.GetValue())
        settings.youtube_music_home_discovery_limit = int(self.youtube_music_home_discovery_limit_ctrl.GetValue())
        settings.youtube_music_autoplay_related = self.youtube_music_autoplay_related_checkbox.GetValue()
        settings.youtube_music_save_history = self.youtube_music_save_history_checkbox.GetValue()
        settings.youtube_content_language = self._youtube_content_language_codes[
            max(self.youtube_content_language_choice.GetSelection(), 0)
        ]
        settings.youtube_content_region = self._youtube_content_region_codes[
            max(self.youtube_content_region_choice.GetSelection(), 0)
        ]
        settings.youtube_audio_language = self._youtube_audio_language_codes[
            max(self.youtube_audio_language_choice.GetSelection(), 0)
        ]
        selected_audio_output_index = self.audio_output_choice.GetSelection()
        if 0 <= selected_audio_output_index < len(self._audio_output_choice_ids):
            settings.audio_output_device_id = self._audio_output_choice_ids[selected_audio_output_index]
        else:
            settings.audio_output_device_id = ""

        if not settings.remember_last_folder:
            settings.last_open_dir = ""

        radio_country_code, radio_country_name = self._radio_country_choices[
            max(self.radio_country_choice.GetSelection(), 0)
        ]
        # Sem mudança de país, o nome escolhido na aba de rádios fica como está.
        if radio_country_code != settings.radio_country_code:
            settings.radio_country_code = radio_country_code
            settings.radio_country_name = radio_country_name if radio_country_code else ""

        settings.smart_library_enabled = self.smart_library_enabled_checkbox.GetValue()
        settings.smart_library_index_opened_folders = self.smart_library_index_opened_folders_checkbox.GetValue()
        settings.smart_library_history_enabled = self.smart_library_history_enabled_checkbox.GetValue()
        settings.smart_library_history_limit = int(self.smart_library_history_limit_ctrl.GetValue())
        settings.smart_library_resume_enabled = self.smart_library_resume_enabled_checkbox.GetValue()
        settings.smart_library_resume_minimum_minutes = int(self.smart_library_resume_minimum_ctrl.GetValue())
        settings.smart_library_resume_edge_seconds = int(self.smart_library_resume_edge_ctrl.GetValue())
        settings.smart_library_cache_limit = int(self.smart_library_cache_limit_ctrl.GetValue())

        download_choice = self.download_options_panel.get_choice()
        settings.download_kind = download_choice.kind
        settings.download_audio_quality = download_choice.audio_quality
        settings.download_video_quality = download_choice.video_quality
        settings.download_sample_rate = download_choice.sample_rate
        settings.download_directory = self.download_options_panel.get_directory_setting()
        settings.download_always_ask = self.download_always_ask_checkbox.GetValue()

        settings.logging_enabled = self.logging_enabled_checkbox.GetValue()
        selected_level_index = self.logging_level_choice.GetSelection()
        if 0 <= selected_level_index < len(LOGGING_LEVELS):
            settings.logging_level = LOGGING_LEVELS[selected_level_index]

        return settings

    def _on_save_preferences(self, _event):
        proposed_settings = self.get_settings()
        components = []
        youtube_newly_enabled = (
            proposed_settings.youtube_music_manage_dependencies
            and not self._settings.youtube_music_manage_dependencies
        )
        youtubejs_newly_enabled = (
            proposed_settings.youtube_music_manage_dependencies
            and proposed_settings.youtube_music_use_youtubejs
            and not self._settings.youtube_music_use_youtubejs
        )
        if youtube_newly_enabled:
            components.extend(["yt-dlp", "ytmusicapi", _("Node.js portátil (se não houver um compatível)")])
            if proposed_settings.youtube_music_use_youtubejs:
                components.append("YouTube.js")
        elif youtubejs_newly_enabled:
            components.extend([_("Node.js portátil (se não houver um compatível)"), "YouTube.js"])
        autodj_needs_confirmation = (
            proposed_settings.autodj_enabled
            and (
                not self._settings.autodj_enabled
                or not self._autodj_optional_resources_confirmed
            )
        )
        if autodj_needs_confirmation:
            components.append(_("AutoDJ: librosa, NumPy, SciPy, Numba e PyAV"))

        if components:
            message = _(
                "Para melhorar a reprodução e habilitar os recursos selecionados, o KeyTune instalará:\n\n{components}\n\n"
                "Os arquivos ficarão apenas na pasta de recursos do KeyTune. Deseja instalar e ativar agora?"
            ).format(components="\n".join(f"• {component}" for component in components))
            response = wx.MessageBox(
                message,
                _("Preparar recursos adicionais"),
                wx.YES_NO | wx.NO_DEFAULT | wx.ICON_INFORMATION,
                self,
            )
            if response != wx.YES:
                return
            if autodj_needs_confirmation:
                self._autodj_optional_resources_confirmed = True
        self.EndModal(wx.ID_OK)

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
