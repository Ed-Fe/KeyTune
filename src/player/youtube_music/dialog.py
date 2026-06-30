import os

import wx

from ..i18n import _, ngettext


class YouTubeMusicBrowserAuthDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(
            parent,
            title=_("Conectar ao YouTube Music"),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self.SetMinSize((640, 480))
        self._build_ui()
        self.SetSize((780, 560))
        self.Layout()
        self.SetEscapeId(wx.ID_CANCEL)
        self.CentreOnParent()

    def _configure_file_picker_accessibility(self):
        picker_text_ctrl = None
        try:
            picker_text_ctrl = self.browser_file_picker.GetTextCtrl()
        except Exception:
            picker_text_ctrl = None

        if isinstance(picker_text_ctrl, wx.TextCtrl):
            picker_text_ctrl.SetName(_("Caminho do arquivo de conexão"))

        picker_button = None
        try:
            picker_button = self.browser_file_picker.GetPickerCtrl()
        except Exception:
            picker_button = None

        if isinstance(picker_button, wx.Control):
            picker_button.SetLabel(_("&Procurar..."))
            picker_button.SetName(_("Procurar arquivo de conexão"))
            picker_button.SetToolTip(_("Abre a janela para escolher um arquivo de conexão exportado do navegador."))

    def _build_ui(self):
        root_sizer = wx.BoxSizer(wx.VERTICAL)

        instructions = wx.StaticText(
            self,
            label=_(
                "Conecte sua conta do YouTube Music usando uma destas opções:\n\n"
                "1. Caminho mais simples: faça login em music.youtube.com no navegador e exporte os cookies da sessão para um arquivo.\n"
                "2. Se você já tiver um browser.json, um JSON de cookies ou um cookies.txt, selecione esse arquivo abaixo.\n"
                "3. O campo de texto é opcional e serve apenas para quem prefere colar manualmente os dados do navegador."
            ),
        )
        instructions.Wrap(720)

        headers_label = wx.StaticText(self, label=_("Dados copiados do navegador (opcional)"))
        self.headers_value = wx.TextCtrl(
            self,
            style=wx.TE_MULTILINE,
        )
        self.headers_value.SetName(_("Dados de conexão do YouTube Music"))

        file_row = wx.BoxSizer(wx.HORIZONTAL)
        file_label = wx.StaticText(self, label=_("Arquivo de conexão"))
        self.browser_file_picker = wx.FilePickerCtrl(
            self,
            wildcard=(
                _("Arquivos de autenticação (*.json;*.txt)") + "|*.json;*.txt|"
                + _("Arquivos JSON (*.json)") + "|*.json|"
                + _("Arquivos de texto (*.txt)") + "|*.txt|"
                + _("Todos os arquivos") + "|*.*"
            ),
            style=wx.FLP_OPEN | wx.FLP_FILE_MUST_EXIST,
        )
        self._configure_file_picker_accessibility()
        file_row.Add(file_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        file_row.Add(self.browser_file_picker, 1, wx.EXPAND)

        note = wx.StaticText(
            self,
            label=_(
                "Dica: se quiser o caminho mais fácil, use uma extensão de exportar cookies no navegador para gerar "
                "um arquivo JSON ou cookies.txt da sessão já conectada no YouTube Music."
            ),
        )
        note.Wrap(720)

        rotation_warning = wx.StaticText(
            self,
            label=_(
                "Importante — para a conexão durar: o Google troca os cookies da sessão por segurança sempre que você "
                "continua navegando no YouTube logado, o que invalida os cookies já exportados (a conta aparece como "
                "desconectada no dia seguinte, mesmo usando o mesmo arquivo). Para uma conexão estável, abra uma janela "
                "anônima/privada, faça login em music.youtube.com, exporte os cookies e feche a janela anônima sem abrir "
                "o YouTube de novo nela. Assim os cookies exportados não são mais trocados pelo navegador."
            ),
        )
        rotation_warning.Wrap(720)
        rotation_warning.SetName(_("Aviso sobre validade dos cookies do YouTube Music"))

        button_sizer = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
        # Use FindWindow (descendant-scoped) instead of FindWindowById, which is
        # static and searches all top-level windows globally and could rename
        # buttons that share wx.ID_OK in other open dialogs.
        ok_button = self.FindWindow(wx.ID_OK)
        if ok_button is not None:
            ok_button.SetLabel(_("&Conectar"))
            ok_button.SetName(_("Conectar ao YouTube Music"))
            ok_button.SetToolTip(_("Valida o arquivo ou o texto informado e conecta sua conta do YouTube Music."))
        cancel_button = self.FindWindow(wx.ID_CANCEL)
        if cancel_button is not None:
            cancel_button.SetLabel(_("&Cancelar"))

        root_sizer.Add(instructions, 0, wx.ALL | wx.EXPAND, 12)
        root_sizer.Add(headers_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
        root_sizer.Add(self.headers_value, 1, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)
        root_sizer.Add(file_row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)
        root_sizer.Add(note, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)
        root_sizer.Add(rotation_warning, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)
        if button_sizer is not None:
            root_sizer.Add(button_sizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.ALIGN_RIGHT, 12)

        self.SetSizer(root_sizer)

    def get_headers_raw(self):
        return self.headers_value.GetValue().strip()

    def get_browser_json_path(self):
        path = self.browser_file_picker.GetPath().strip()
        return path if path and os.path.isfile(path) else ""


class YouTubeMusicCreatePlaylistDialog(wx.Dialog):
    """Collect a name and privacy level for a new YouTube Music playlist."""

    # (label, ytmusicapi privacy_status) in the order shown.  Private is first
    # so it is the default selection, matching YouTube Music's own default.
    _PRIVACY_CHOICES = (
        (_("Privada"), "PRIVATE"),
        (_("Não listada"), "UNLISTED"),
        (_("Pública"), "PUBLIC"),
    )

    def __init__(self, parent, *, default_name="", track_count=0):
        super().__init__(parent, title=_("Criar playlist do YouTube Music"))
        self._track_count = max(0, int(track_count or 0))
        self._playlist_name = ""
        self._privacy_status = "PRIVATE"
        self._build_ui(default_name=str(default_name or ""))
        self.Fit()
        self.SetMinSize(self.GetSize())
        self.Layout()
        self.SetEscapeId(wx.ID_CANCEL)
        self.CentreOnParent()

    def _build_ui(self, *, default_name):
        root_sizer = wx.BoxSizer(wx.VERTICAL)

        if self._track_count > 0:
            intro_text = ngettext(
                "A nova playlist será criada com {count} faixa da seleção atual.",
                "A nova playlist será criada com {count} faixas da seleção atual.",
                self._track_count,
            ).format(count=self._track_count)
        else:
            intro_text = _("Informe o nome e a privacidade da nova playlist.")
        intro = wx.StaticText(self, label=intro_text)
        intro.Wrap(440)

        name_label = wx.StaticText(self, label=_("&Nome da playlist:"))
        self.name_value = wx.TextCtrl(self, value=default_name, style=wx.TE_PROCESS_ENTER)
        self.name_value.SetName(_("Nome da nova playlist do YouTube Music"))
        self.name_value.Bind(wx.EVT_TEXT_ENTER, self._on_confirm)

        self.privacy_box = wx.RadioBox(
            self,
            label=_("Privacidade"),
            choices=[label for label, _status in self._PRIVACY_CHOICES],
            majorDimension=1,
            style=wx.RA_SPECIFY_COLS,
        )
        self.privacy_box.SetSelection(0)
        self.privacy_box.SetName(_("Privacidade da nova playlist do YouTube Music"))

        privacy_hint = wx.StaticText(
            self,
            label=_(
                "Privada: só você vê. Não listada: visível para quem tiver o link. "
                "Pública: aparece no seu perfil e pode surgir em buscas."
            ),
        )
        privacy_hint.Wrap(440)

        button_sizer = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
        # Descendant-scoped FindWindow so we don't rename wx.ID_OK buttons that
        # may exist in other open dialogs.
        ok_button = self.FindWindow(wx.ID_OK)
        if ok_button is not None:
            ok_button.SetLabel(_("&Criar"))
            ok_button.SetName(_("Criar playlist do YouTube Music"))
            ok_button.SetToolTip(_("Cria a playlist com o nome e a privacidade informados."))
            ok_button.Bind(wx.EVT_BUTTON, self._on_confirm)
        cancel_button = self.FindWindow(wx.ID_CANCEL)
        if cancel_button is not None:
            cancel_button.SetLabel(_("&Cancelar"))

        root_sizer.Add(intro, 0, wx.ALL | wx.EXPAND, 12)
        root_sizer.Add(name_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
        root_sizer.Add(self.name_value, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)
        root_sizer.Add(self.privacy_box, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)
        root_sizer.Add(privacy_hint, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)
        if button_sizer is not None:
            root_sizer.Add(button_sizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.ALIGN_RIGHT, 12)

        self.SetSizer(root_sizer)
        self.name_value.SetFocus()

    def _on_confirm(self, _event):
        name = str(self.name_value.GetValue() or "").strip()
        if not name:
            wx.MessageBox(
                _("Informe um nome para a nova playlist."),
                _("Criar playlist do YouTube Music"),
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            self.name_value.SetFocus()
            return

        selection = self.privacy_box.GetSelection()
        if not 0 <= selection < len(self._PRIVACY_CHOICES):
            selection = 0
        self._playlist_name = name
        self._privacy_status = self._PRIVACY_CHOICES[selection][1]
        self.EndModal(wx.ID_OK)

    def get_playlist_name(self):
        return self._playlist_name

    def get_privacy_status(self):
        return self._privacy_status


class YouTubeMusicJavascriptRuntimeDialog(wx.Dialog):
    ACTION_INSTALL_DENO = "install-deno"
    ACTION_INSTALL_NODE = "install-node"
    ACTION_INSTALL_BUN = "install-bun"
    ACTION_OPEN_DENO = "open-deno"
    ACTION_OPEN_NODE = "open-node"
    ACTION_OPEN_BUN = "open-bun"
    ACTION_OPEN_GUIDE = "open-guide"

    def __init__(self, parent, *, winget_available):
        super().__init__(
            parent,
            title=_("Runtime JavaScript do YouTube Music"),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self._winget_available = bool(winget_available)
        self._selected_action = ""
        self.SetMinSize((620, 420))
        self._build_ui()
        self.SetSize((760, 500))
        self.Layout()
        self.SetEscapeId(wx.ID_CANCEL)
        self.CentreOnParent()

    def _set_action(self, action):
        self._selected_action = str(action or "").strip()
        self.EndModal(wx.ID_OK)

    def _bind_action_button(self, button, action, *, help_text):
        button.SetName(button.GetLabelText())
        button.SetToolTip(help_text)
        button.Bind(wx.EVT_BUTTON, lambda _event: self._set_action(action))

    def _build_action_button(self, parent, *, label, action, help_text):
        button = wx.Button(parent, label=label)
        self._bind_action_button(button, action, help_text=help_text)
        return button

    def _build_ui(self):
        root_sizer = wx.BoxSizer(wx.VERTICAL)

        install_hint = (
            _("Os botões de instalação abrem o Windows Package Manager em uma janela separada. Dependendo da configuração do sistema, o Windows pode pedir confirmação.")
            if self._winget_available
            else _("O Windows Package Manager não está disponível nesta instalação. Use os botões abaixo para abrir os sites oficiais.")
        )
        primary_button_labels = {
            True: (
                (_("Instalar &Deno"), self.ACTION_INSTALL_DENO),
                (_("Instalar &Node.js"), self.ACTION_INSTALL_NODE),
                (_("Instalar &Bun"), self.ACTION_INSTALL_BUN),
            ),
            False: (
                (_("Abrir site do &Deno"), self.ACTION_OPEN_DENO),
                (_("Abrir site do &Node.js"), self.ACTION_OPEN_NODE),
                (_("Abrir site do &Bun"), self.ACTION_OPEN_BUN),
            ),
        }

        instructions = wx.StaticText(
            self,
            label=_(
                "Para abrir músicas e vídeos do YouTube com mais estabilidade, o player precisa de um "
                "complemento do sistema chamado runtime JavaScript.\n\n"
                "Sem ele, o YouTube pode bloquear a preparação do áudio ou do vídeo e a reprodução não começa.\n\n"
                "Você pode instalar qualquer uma destas opções:\n"
                "1. Deno 2+ (recomendado pelo projeto yt-dlp)\n"
                "2. Node.js 20+ (opção mais conhecida)\n"
                "3. Bun 1.0.31+ (descontinuado no yt-dlp; use só se não puder instalar Deno ou Node.js)\n\n"
            ).format() + f"{install_hint}\n\n" + _(
                "Depois da instalação, feche e abra o player novamente para que o novo runtime seja "
                "encontrado no PATH do sistema."
            ),
        )
        instructions.Wrap(720)
        instructions.SetName(_("Instruções sobre runtime JavaScript do YouTube Music"))

        note = wx.StaticText(
            self,
            label=_(
                "Se preferir entender o cenário técnico antes de instalar, abra a guia oficial do yt-dlp sobre EJS e desafios JavaScript."
            ),
        )
        note.Wrap(720)

        primary_button_row = wx.BoxSizer(wx.HORIZONTAL)
        for label, action in primary_button_labels[self._winget_available]:
            button = self._build_action_button(
                self,
                label=label,
                action=action,
                help_text=_("Executa a ação: {label}.").format(label=label),
            )
            primary_button_row.Add(button, 0, wx.RIGHT, 8)

        secondary_button_row = wx.BoxSizer(wx.HORIZONTAL)
        guide_button = self._build_action_button(
            self,
            label=_("Abrir guia do &yt-dlp"),
            action=self.ACTION_OPEN_GUIDE,
            help_text=_("Abre a documentação oficial do yt-dlp sobre o uso de runtimes JavaScript no YouTube."),
        )
        close_button = wx.Button(self, wx.ID_CANCEL, _("&Fechar"))
        close_button.SetName(_("Fechar"))
        close_button.SetToolTip(_("Fecha esta janela sem abrir instaladores nem sites."))
        secondary_button_row.Add(guide_button, 0, wx.RIGHT, 8)
        secondary_button_row.Add(close_button, 0)

        root_sizer.Add(instructions, 1, wx.ALL | wx.EXPAND, 12)
        root_sizer.Add(note, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)
        root_sizer.Add(primary_button_row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
        root_sizer.Add(secondary_button_row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.ALIGN_RIGHT, 12)

        self.SetSizer(root_sizer)

    def get_selected_action(self):
        return self._selected_action
