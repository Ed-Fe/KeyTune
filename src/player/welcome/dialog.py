import wx


class WelcomeDialog(wx.Dialog):
    """First-run tutorial: a short wizard explaining the player, its features, and where to get help."""

    def __init__(self, parent, *, on_open_manual=None, on_show_shortcuts=None):
        super().__init__(
            parent,
            title="Bem-vindo ao KeyTune",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self._on_open_manual = on_open_manual
        self._on_show_shortcuts = on_show_shortcuts
        self._pages = []

        panel = wx.Panel(self)
        root_sizer = wx.BoxSizer(wx.VERTICAL)

        self.page_title_label = wx.StaticText(panel, label="")
        self.page_title_label.SetFont(self.page_title_label.GetFont().Bold())
        root_sizer.Add(self.page_title_label, 0, wx.ALL | wx.EXPAND, 10)

        self.book = wx.Simplebook(panel)
        self.book.SetName("Conteúdo da página atual")

        self._add_about_page()
        self._add_interface_page()
        self._add_features_page()
        self._add_help_page()

        root_sizer.Add(self.book, 1, wx.LEFT | wx.RIGHT | wx.EXPAND, 10)

        self.page_indicator_label = wx.StaticText(panel, label="")
        self.page_indicator_label.SetForegroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT))
        root_sizer.Add(self.page_indicator_label, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 10)

        nav_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.skip_button = wx.Button(panel, label="Pu&lar tutorial")
        self.skip_button.SetName("Pular tutorial")
        self.skip_button.SetHelpText("Fecha a apresentação imediatamente, sem ver as páginas restantes.")
        self.skip_button.Bind(wx.EVT_BUTTON, self._on_skip)

        self.back_button = wx.Button(panel, label="&Voltar")
        self.back_button.SetName("Voltar")
        self.back_button.SetHelpText("Volta para a página anterior do tutorial.")
        self.back_button.Bind(wx.EVT_BUTTON, self._on_back)

        self.next_button = wx.Button(panel, label="&Avançar")
        self.next_button.SetName("Avançar")
        self.next_button.SetHelpText("Avança para a próxima página do tutorial.")
        self.next_button.Bind(wx.EVT_BUTTON, self._on_next)
        self.next_button.SetDefault()

        nav_sizer.Add(self.skip_button, 0, wx.RIGHT, 20)
        nav_sizer.AddStretchSpacer(1)
        nav_sizer.Add(self.back_button, 0, wx.RIGHT, 8)
        nav_sizer.Add(self.next_button, 0, 0)
        root_sizer.Add(nav_sizer, 0, wx.ALL | wx.EXPAND, 10)

        panel.SetSizer(root_sizer)

        frame_sizer = wx.BoxSizer(wx.VERTICAL)
        frame_sizer.Add(panel, 1, wx.EXPAND)
        self.SetSizerAndFit(frame_sizer)
        self.SetMinSize((640, 520))
        self.SetEscapeId(wx.ID_CANCEL)

        self._current_page_index = 0
        self._show_page(0)

    def _create_page(self, title, name, help_text, text):
        page = wx.Panel(self.book)
        page_sizer = wx.BoxSizer(wx.VERTICAL)

        text_label = wx.StaticText(page, label=f"{name}:")
        page_sizer.Add(text_label, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 10)

        text_ctrl = wx.TextCtrl(
            page,
            value=text,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_BESTWRAP,
        )
        text_ctrl.SetName(name)
        text_ctrl.SetHelpText(help_text)
        text_ctrl.SetInsertionPoint(0)
        page_sizer.Add(text_ctrl, 1, wx.ALL | wx.EXPAND, 10)

        page.SetSizer(page_sizer)
        page.text_ctrl = text_ctrl
        self.book.AddPage(page, title)
        self._pages.append(title)
        return page, page_sizer

    def _add_about_page(self):
        self._create_page(
            "Sobre o KeyTune",
            "Sobre o KeyTune",
            "Apresenta o player e o que é possível fazer com ele.",
            "O KeyTune é um player de áudio e vídeo pensado para ser usado inteiramente pelo teclado "
            "e para funcionar bem com leitores de tela. Não é preciso usar o mouse em nenhum momento.\n\n"
            "Você pode abrir arquivos de mídia, pastas e playlists, organizar tudo em abas e, "
            "opcionalmente, conectar sua conta do YouTube Music para tocar suas playlists e sua biblioteca.\n\n"
            "As próximas páginas mostram como a interface é organizada, quais recursos estão disponíveis "
            "e onde encontrar ajuda sempre que precisar.",
        )

    def _add_interface_page(self):
        self._create_page(
            "Interface",
            "Como a interface é organizada",
            "Descreve as áreas principais da janela do player: abas, lista de itens, player e barras inferiores.",
            "A janela principal é dividida em algumas áreas:\n\n"
            "Abas, na parte de cima: cada aba é uma playlist aberta. Use Ctrl+Tab e Ctrl+Shift+Tab "
            "para alternar entre elas, e Ctrl+T para criar uma nova.\n\n"
            "Lista de itens, à esquerda em cada aba: mostra os arquivos da playlist atual ou os itens "
            "de uma pasta. Use as setas para navegar, Enter para tocar ou abrir, e Tab para mover o foco "
            "entre a lista e o player.\n\n"
            "Área do player, à direita: mostra o vídeo quando houver, ou apenas indica que o áudio está "
            "tocando. O controle de reprodução é feito por teclado: Espaço para tocar ou pausar, "
            "setas esquerda/direita para avançar ou voltar, e setas para cima/baixo para o volume.\n\n"
            "Barra de tempo e barra de status, na parte de baixo: mostram o andamento da mídia atual "
            "e mensagens rápidas sobre as ações realizadas.",
        )

    def _add_features_page(self):
        self._create_page(
            "Recursos do player",
            "Recursos principais do KeyTune",
            "Resume os recursos do player além da reprodução básica: playlists, equalizador, YouTube Music e preferências.",
            "Além de tocar arquivos locais, o KeyTune tem alguns recursos que podem ser úteis:\n\n"
            "Playlists: crie, salve e reabra playlists em abas separadas, com embaralhar e modos de "
            "repetição configuráveis.\n\n"
            "Equalizador: ajuste a resposta de frequência da reprodução e salve seus próprios presets "
            "pelo menu Reprodução.\n\n"
            "YouTube Music (opcional): conecte sua conta para abrir suas playlists, curtir faixas e "
            "tocar conteúdo relacionado automaticamente ao fim de uma playlist.\n\n"
            "Preferências: em Configurações > Preferências é possível ajustar volume padrão, crossfade, "
            "restauração de sessão, anúncios do leitor de tela e mais.",
        )

    def _add_help_page(self):
        page, page_sizer = self._create_page(
            "Atalhos e ajuda",
            "Onde encontrar ajuda",
            "Explica como abrir a ajuda rápida de atalhos e o manual completo do KeyTune.",
            "A qualquer momento, pressione F1 para abrir uma ajuda rápida com a lista completa de atalhos "
            "de teclado do KeyTune.\n\n"
            "Para uma explicação mais detalhada de todos os recursos, abra o manual do usuário. "
            "Os dois também estão disponíveis pelo menu Ajuda.",
        )

        button_row = wx.BoxSizer(wx.HORIZONTAL)
        shortcuts_button = wx.Button(page, label="Ver ajuda rápida de atalhos (&F1)")
        shortcuts_button.SetName("Ver ajuda rápida de atalhos")
        shortcuts_button.SetHelpText("Abre a mesma janela de atalhos mostrada ao pressionar F1.")
        shortcuts_button.Bind(wx.EVT_BUTTON, self._on_show_shortcuts_clicked)

        manual_button = wx.Button(page, label="Abrir &manual do usuário")
        manual_button.SetName("Abrir manual do usuário")
        manual_button.SetHelpText("Abre o manual completo do KeyTune no navegador padrão.")
        manual_button.Bind(wx.EVT_BUTTON, self._on_open_manual_clicked)

        button_row.Add(shortcuts_button, 0, wx.RIGHT, 8)
        button_row.Add(manual_button, 0, 0)
        page_sizer.Add(button_row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

    def _show_page(self, index):
        self._current_page_index = index
        self.book.SetSelection(index)
        page_title = self._pages[index]
        self.page_title_label.SetLabel(page_title)
        self.page_indicator_label.SetLabel(f"Página {index + 1} de {len(self._pages)}: {page_title}")

        self.back_button.Enable(index > 0)
        is_last_page = index == len(self._pages) - 1
        self.next_button.SetLabel("&Concluir" if is_last_page else "&Avançar")
        self.next_button.SetName("Concluir" if is_last_page else "Avançar")

        self.Layout()
        current_page = self.book.GetPage(index)
        current_page.text_ctrl.SetFocus()

    def _on_back(self, _event):
        if self._current_page_index > 0:
            self._show_page(self._current_page_index - 1)

    def _on_next(self, _event):
        if self._current_page_index < len(self._pages) - 1:
            self._show_page(self._current_page_index + 1)
            return
        self.EndModal(wx.ID_OK)

    def _on_skip(self, _event):
        self.EndModal(wx.ID_OK)

    def _on_show_shortcuts_clicked(self, _event):
        if self._on_show_shortcuts is not None:
            self._on_show_shortcuts()

    def _on_open_manual_clicked(self, _event):
        if self._on_open_manual is not None:
            self._on_open_manual()
