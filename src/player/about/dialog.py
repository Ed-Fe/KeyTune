import wx

from ..constants import APP_LICENSE, APP_TITLE, APP_VERSION, GITHUB_REPOSITORY_NAME, GITHUB_REPOSITORY_OWNER
from ..i18n import _

REPOSITORY_URL = f"https://github.com/{GITHUB_REPOSITORY_OWNER}/{GITHUB_REPOSITORY_NAME}"


class AboutDialog(wx.Dialog):
    def __init__(self, parent, *, on_open_credits=None):
        super().__init__(
            parent,
            title=_("Sobre o {app}").format(app=APP_TITLE),
            style=wx.DEFAULT_DIALOG_STYLE,
        )

        self._on_open_credits = on_open_credits

        panel = wx.Panel(self)
        root_sizer = wx.BoxSizer(wx.VERTICAL)

        title_label = wx.StaticText(panel, label=f"{APP_TITLE} {APP_VERSION}")
        title_label.SetFont(title_label.GetFont().Bold())
        title_label.SetName(_("{app} versão {version}").format(app=APP_TITLE, version=APP_VERSION))

        description_label = wx.StaticText(
            panel,
            label=_(
                "Player de áudio e vídeo pensado para ser usado inteiramente pelo teclado "
                "e para funcionar bem com leitores de tela."
            ),
        )
        description_label.Wrap(480)
        description_label.SetName(_("Descrição do aplicativo"))

        license_label = wx.StaticText(panel, label=_("Licenciado sob a licença {license}.").format(license=APP_LICENSE))
        license_label.SetName(_("Licença do aplicativo"))

        root_sizer.Add(title_label, 0, wx.ALL | wx.EXPAND, 10)
        root_sizer.Add(description_label, 0, wx.LEFT | wx.RIGHT | wx.EXPAND, 10)
        root_sizer.Add(license_label, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 10)

        button_row = wx.BoxSizer(wx.HORIZONTAL)

        source_button = wx.Button(panel, label=_("Ver código-fonte no &GitHub"))
        source_button.SetName(_("Ver código-fonte no GitHub"))
        source_button.Bind(wx.EVT_BUTTON, self._on_open_source_clicked)

        credits_button = wx.Button(panel, label=_("Ver &créditos completos"))
        credits_button.SetName(_("Ver créditos completos"))
        credits_button.Bind(wx.EVT_BUTTON, self._on_open_credits_clicked)

        button_row.Add(source_button, 0, wx.RIGHT, 8)
        button_row.Add(credits_button, 0, 0)
        root_sizer.Add(button_row, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.BOTTOM, 10)

        button_sizer = wx.StdDialogButtonSizer()
        close_button = wx.Button(panel, wx.ID_OK, _("&Fechar"))
        close_button.SetDefault()
        button_sizer.AddButton(close_button)
        button_sizer.Realize()
        root_sizer.Add(button_sizer, 0, wx.ALL | wx.EXPAND, 10)

        panel.SetSizer(root_sizer)

        frame_sizer = wx.BoxSizer(wx.VERTICAL)
        frame_sizer.Add(panel, 1, wx.EXPAND)
        self.SetSizerAndFit(frame_sizer)
        self.SetMinSize((520, 320))
        self.SetEscapeId(wx.ID_OK)
        self.CentreOnParent()

    def _on_open_source_clicked(self, _event):
        try:
            launched = wx.LaunchDefaultBrowser(REPOSITORY_URL)
        except Exception:
            launched = False

        if not launched:
            wx.MessageBox(
                _("Não foi possível abrir o repositório do GitHub no navegador padrão."),
                _("Sobre o {app}").format(app=APP_TITLE),
                wx.OK | wx.ICON_ERROR,
                self,
            )

    def _on_open_credits_clicked(self, _event):
        if self._on_open_credits is not None:
            self._on_open_credits()
