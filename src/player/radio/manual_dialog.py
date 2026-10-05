import wx

from ..i18n import _

ADD_RADIO_MANUALLY_DIALOG_TITLE = _("Adicionar rádio manualmente")


class AddRadioManuallyDialog(wx.Dialog):
    """Nome e endereço de uma rádio que não está no diretório, para ir direto às favoritas."""

    def __init__(self, parent):
        super().__init__(parent, title=ADD_RADIO_MANUALLY_DIALOG_TITLE)

        root_sizer = wx.BoxSizer(wx.VERTICAL)

        description = wx.StaticText(
            self,
            label=_(
                "Use quando não achar a rádio na busca: digite um nome para ela e o "
                "endereço direto do stream ou de um arquivo M3U. Ao confirmar, ela vai "
                "para as rádios favoritas."
            ),
        )
        description.Wrap(420)

        name_label = wx.StaticText(self, label=_("&Nome da rádio"))
        self.name_text = wx.TextCtrl(self)
        self.name_text.SetName(_("Nome da rádio"))

        url_label = wx.StaticText(self, label=_("&Endereço do stream ou M3U"))
        self.url_text = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
        self.url_text.SetName(_("Endereço do stream ou M3U da rádio"))

        button_sizer = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
        ok_button = self.FindWindow(wx.ID_OK)
        if ok_button is not None:
            ok_button.SetLabel(_("&OK"))
            ok_button.Bind(wx.EVT_BUTTON, self._on_confirm)
        cancel_button = self.FindWindow(wx.ID_CANCEL)
        if cancel_button is not None:
            cancel_button.SetLabel(_("&Cancelar"))

        root_sizer.Add(description, 0, wx.ALL | wx.EXPAND, 12)
        root_sizer.Add(name_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
        root_sizer.Add(self.name_text, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 12)
        root_sizer.Add(url_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
        root_sizer.Add(self.url_text, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 12)
        if button_sizer is not None:
            root_sizer.Add(button_sizer, 0, wx.ALL | wx.ALIGN_RIGHT, 12)

        self.SetSizerAndFit(root_sizer)
        self.SetMinSize((460, 260))
        self.SetEscapeId(wx.ID_CANCEL)
        self.CentreOnParent()

        self.url_text.Bind(wx.EVT_TEXT_ENTER, self._on_confirm)

        self.name_text.SetFocus()

    def get_name(self):
        return str(self.name_text.GetValue() or "").strip()

    def get_stream_url(self):
        return str(self.url_text.GetValue() or "").strip()

    def _on_confirm(self, event):
        if not self.get_name():
            wx.MessageBox(_("Digite um nome para a rádio."), _("Nome em branco"), wx.OK | wx.ICON_WARNING, self)
            self.name_text.SetFocus()
            return
        if not self.get_stream_url():
            wx.MessageBox(
                _("Digite o endereço do stream ou do arquivo M3U."),
                _("Endereço em branco"),
                wx.OK | wx.ICON_WARNING,
                self,
            )
            self.url_text.SetFocus()
            return
        if self.IsModal():
            self.EndModal(wx.ID_OK)
            return
        self.SetReturnCode(wx.ID_OK)
        self.Show(False)
