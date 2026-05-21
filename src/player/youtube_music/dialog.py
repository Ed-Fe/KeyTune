import os

import wx


class YouTubeMusicBrowserAuthDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(
            parent,
            title="Conectar ao YouTube Music",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self.SetMinSize((640, 480))
        self._build_ui()
        self.SetSize((780, 560))
        self.Layout()
        self.SetEscapeId(wx.ID_CANCEL)

    def _configure_file_picker_accessibility(self):
        picker_text_ctrl = None
        try:
            picker_text_ctrl = self.browser_file_picker.GetTextCtrl()
        except Exception:
            picker_text_ctrl = None

        if isinstance(picker_text_ctrl, wx.TextCtrl):
            picker_text_ctrl.SetName("Caminho do arquivo de conexão")
            picker_text_ctrl.SetHelpText(
                "Mostra o caminho do arquivo selecionado para conectar sua conta do YouTube Music."
            )

        picker_button = None
        try:
            picker_button = self.browser_file_picker.GetPickerCtrl()
        except Exception:
            picker_button = None

        if isinstance(picker_button, wx.Control):
            picker_button.SetLabel("&Procurar...")
            picker_button.SetName("Procurar arquivo de conexão")
            picker_button.SetHelpText(
                "Abre a janela para escolher um arquivo de conexão exportado do navegador."
            )
            picker_button.SetToolTip(picker_button.GetHelpText())

    def _build_ui(self):
        root_sizer = wx.BoxSizer(wx.VERTICAL)

        instructions = wx.StaticText(
            self,
            label=(
                "Conecte sua conta do YouTube Music usando uma destas opções:\n\n"
                "1. Caminho mais simples: faça login em music.youtube.com no navegador e exporte os cookies da sessão para um arquivo.\n"
                "2. Se você já tiver um browser.json, um JSON de cookies ou um cookies.txt, selecione esse arquivo abaixo.\n"
                "3. O campo de texto é opcional e serve apenas para quem prefere colar manualmente os dados do navegador."
            ),
        )
        instructions.Wrap(720)

        headers_label = wx.StaticText(self, label="Dados copiados do navegador (opcional)")
        self.headers_value = wx.TextCtrl(
            self,
            style=wx.TE_MULTILINE,
        )
        self.headers_value.SetName("Dados de conexão do YouTube Music")
        self.headers_value.SetHelpText(
            "Cole aqui os dados copiados do navegador apenas se você não for usar um arquivo."
        )

        file_row = wx.BoxSizer(wx.HORIZONTAL)
        file_label = wx.StaticText(self, label="Arquivo de conexão")
        self.browser_file_picker = wx.FilePickerCtrl(
            self,
            wildcard=(
                "Arquivos de autenticação (*.json;*.txt)|*.json;*.txt|"
                "Arquivos JSON (*.json)|*.json|"
                "Arquivos de texto (*.txt)|*.txt|"
                "Todos os arquivos|*.*"
            ),
            style=wx.FLP_OPEN | wx.FLP_FILE_MUST_EXIST,
        )
        self.browser_file_picker.SetHelpText(
            "Escolha o arquivo exportado do navegador para conectar sua conta do YouTube Music."
        )
        self._configure_file_picker_accessibility()
        file_row.Add(file_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        file_row.Add(self.browser_file_picker, 1, wx.EXPAND)

        note = wx.StaticText(
            self,
            label=(
                "Dica: se quiser o caminho mais fácil, use uma extensão de exportar cookies no navegador para gerar "
                "um arquivo JSON ou cookies.txt da sessão já conectada no YouTube Music."
            ),
        )
        note.Wrap(720)

        button_sizer = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
        # Use FindWindow (descendant-scoped) instead of FindWindowById, which is
        # static and searches all top-level windows globally and could rename
        # buttons that share wx.ID_OK in other open dialogs.
        ok_button = self.FindWindow(wx.ID_OK)
        if ok_button is not None:
            ok_button.SetLabel("&Conectar")
            ok_button.SetName("Conectar ao YouTube Music")
            ok_button.SetHelpText(
                "Valida o arquivo ou o texto informado e conecta sua conta do YouTube Music."
            )
            ok_button.SetToolTip(ok_button.GetHelpText())
        cancel_button = self.FindWindow(wx.ID_CANCEL)
        if cancel_button is not None:
            cancel_button.SetLabel("&Cancelar")

        root_sizer.Add(instructions, 0, wx.ALL | wx.EXPAND, 12)
        root_sizer.Add(headers_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
        root_sizer.Add(self.headers_value, 1, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)
        root_sizer.Add(file_row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)
        root_sizer.Add(note, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)
        if button_sizer is not None:
            root_sizer.Add(button_sizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.ALIGN_RIGHT, 12)

        self.SetSizer(root_sizer)

    def get_headers_raw(self):
        return self.headers_value.GetValue().strip()

    def get_browser_json_path(self):
        path = self.browser_file_picker.GetPath().strip()
        return path if path and os.path.isfile(path) else ""


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
            title="Runtime JavaScript do YouTube Music",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self._winget_available = bool(winget_available)
        self._selected_action = ""
        self.SetMinSize((620, 420))
        self._build_ui()
        self.SetSize((760, 500))
        self.Layout()
        self.SetEscapeId(wx.ID_CANCEL)

    def _set_action(self, action):
        self._selected_action = str(action or "").strip()
        self.EndModal(wx.ID_OK)

    def _bind_action_button(self, button, action, *, help_text):
        button.SetName(button.GetLabelText())
        button.SetHelpText(help_text)
        button.SetToolTip(help_text)
        button.Bind(wx.EVT_BUTTON, lambda _event: self._set_action(action))

    def _build_action_button(self, parent, *, label, action, help_text):
        button = wx.Button(parent, label=label)
        self._bind_action_button(button, action, help_text=help_text)
        return button

    def _build_ui(self):
        root_sizer = wx.BoxSizer(wx.VERTICAL)

        install_hint = (
            "Os botões de instalação abrem o Windows Package Manager em uma janela separada. "
            "Dependendo da configuração do sistema, o Windows pode pedir confirmação."
            if self._winget_available
            else "O Windows Package Manager não está disponível nesta instalação. Use os botões abaixo para abrir os sites oficiais."
        )
        primary_button_labels = {
            True: (
                ("Instalar &Deno", self.ACTION_INSTALL_DENO),
                ("Instalar &Node.js", self.ACTION_INSTALL_NODE),
                ("Instalar &Bun", self.ACTION_INSTALL_BUN),
            ),
            False: (
                ("Abrir site do &Deno", self.ACTION_OPEN_DENO),
                ("Abrir site do &Node.js", self.ACTION_OPEN_NODE),
                ("Abrir site do &Bun", self.ACTION_OPEN_BUN),
            ),
        }

        instructions = wx.StaticText(
            self,
            label=(
                "O yt-dlp agora depende de um runtime JavaScript para o suporte atual ao YouTube e ao YouTube Music.\n\n"
                "Sem isso, o YouTube pode bloquear a resolução das assinaturas e o player não recebe um formato reproduzível.\n\n"
                "Opções compatíveis:\n"
                "1. Deno 2+ (recomendado pelo projeto yt-dlp)\n"
                "2. Node.js 20+ (opção mais conhecida)\n"
                "3. Bun 1.0.31+ (alternativa)\n\n"
                f"{install_hint}\n\n"
                "Depois da instalação, feche e abra o player novamente para que o novo runtime seja encontrado no PATH do sistema."
            ),
        )
        instructions.SetLabel(
            "Para abrir mÃºsicas e vÃ­deos do YouTube com mais estabilidade, o player precisa de um complemento do sistema chamado runtime JavaScript.\n\n"
            "Sem ele, o YouTube pode bloquear a preparaÃ§Ã£o do Ã¡udio ou do vÃ­deo e a reproduÃ§Ã£o nÃ£o comeÃ§a.\n\n"
            "VocÃª pode instalar qualquer uma destas opÃ§Ãµes:\n"
            "1. Deno 2+ (recomendado)\n"
            "2. Node.js 20+\n"
            "3. Bun 1.0.31+\n\n"
            f"{install_hint}\n\n"
            "Depois da instalaÃ§Ã£o, feche e abra o player novamente."
        )
        instructions.SetLabel(
            "Para abrir musicas e videos do YouTube com mais estabilidade, o player precisa de um complemento do sistema chamado runtime JavaScript.\n\n"
            "Sem ele, o YouTube pode bloquear a preparacao do audio ou do video e a reproducao nao comeca.\n\n"
            "Voce pode instalar qualquer uma destas opcoes:\n"
            "1. Deno 2+ (recomendado)\n"
            "2. Node.js 20+\n"
            "3. Bun 1.0.31+\n\n"
            f"{install_hint}\n\n"
            "Depois da instalacao, feche e abra o player novamente."
        )
        instructions.Wrap(720)
        instructions.SetName("Instruções sobre runtime JavaScript do YouTube Music")
        instructions.SetHelpText(
            "Explica por que o yt-dlp precisa de um runtime JavaScript e oferece caminhos para instalar ou abrir a documentação."
        )

        instructions.SetName("Instrucoes sobre runtime JavaScript do YouTube Music")
        instructions.SetHelpText(
            "Explica por que a reproducao do YouTube precisa desse componente e oferece caminhos para instalar ou abrir a documentacao."
        )

        note = wx.StaticText(
            self,
            label=(
                "Se preferir entender o cenário técnico antes de instalar, abra a guia oficial do yt-dlp sobre EJS e desafios JavaScript."
            ),
        )
        note.SetLabel(
            "Se quiser ver a explicacao tecnica completa, abra a documentacao oficial do yt-dlp."
        )
        note.Wrap(720)

        primary_button_row = wx.BoxSizer(wx.HORIZONTAL)
        for label, action in primary_button_labels[self._winget_available]:
            button = self._build_action_button(
                self,
                label=label,
                action=action,
                help_text=f"Executa a ação: {label}.",
            )
            primary_button_row.Add(button, 0, wx.RIGHT, 8)

        secondary_button_row = wx.BoxSizer(wx.HORIZONTAL)
        guide_button = self._build_action_button(
            self,
            label="Abrir guia do &yt-dlp",
            action=self.ACTION_OPEN_GUIDE,
            help_text="Abre a documentação oficial do yt-dlp sobre o uso de runtimes JavaScript no YouTube.",
        )
        close_button = wx.Button(self, wx.ID_CANCEL, "&Fechar")
        close_button.SetName("Fechar")
        close_button.SetHelpText("Fecha esta janela sem abrir instaladores nem sites.")
        close_button.SetToolTip(close_button.GetHelpText())
        secondary_button_row.Add(guide_button, 0, wx.RIGHT, 8)
        secondary_button_row.Add(close_button, 0)

        root_sizer.Add(instructions, 1, wx.ALL | wx.EXPAND, 12)
        root_sizer.Add(note, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)
        root_sizer.Add(primary_button_row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
        root_sizer.Add(secondary_button_row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.ALIGN_RIGHT, 12)

        self.SetSizer(root_sizer)

    def get_selected_action(self):
        return self._selected_action
