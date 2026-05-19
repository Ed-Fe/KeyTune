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
