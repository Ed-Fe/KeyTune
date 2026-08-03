import wx

from ..i18n import _


ITEM_SEARCH_DIALOG_TITLE = _("Localizar item")


class ItemSearchDialog(wx.Dialog):
    """Caixa de busca da playlist ou pasta ativa (Ctrl+F).

    Só coleta o texto procurado: a varredura dos itens e a navegação entre os
    resultados (F3 / Shift+F3) ficam no frame, que conhece a lista ativa.
    """

    def __init__(self, parent, initial_query="", context_label=""):
        super().__init__(parent, title=ITEM_SEARCH_DIALOG_TITLE)

        root_sizer = wx.BoxSizer(wx.VERTICAL)

        description_text = context_label or _("Localiza itens da lista ativa.")
        description = wx.StaticText(self, label=description_text)
        description.Wrap(420)

        query_label = wx.StaticText(self, label=_("&Localizar"))
        self.query_text = wx.TextCtrl(
            self,
            value=str(initial_query or ""),
            style=wx.TE_PROCESS_ENTER,
        )
        self.query_text.SetName(_("Texto a localizar"))

        hint = wx.StaticText(
            self,
            label=_(
                "A busca ignora acentos e maiúsculas e encontra o texto em qualquer parte do nome. "
                "Use F3 para o próximo resultado e Shift+F3 para o anterior."
            ),
        )
        hint.Wrap(420)
        hint.SetForegroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT))

        button_sizer = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
        if button_sizer is not None:
            ok_button = self.FindWindow(wx.ID_OK)
            if ok_button is not None:
                ok_button.SetLabel(_("&Localizar"))
            cancel_button = self.FindWindow(wx.ID_CANCEL)
            if cancel_button is not None:
                cancel_button.SetLabel(_("&Cancelar"))

        root_sizer.Add(description, 0, wx.ALL | wx.EXPAND, 12)
        root_sizer.Add(query_label, 0, wx.LEFT | wx.RIGHT, 12)
        root_sizer.Add(self.query_text, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 12)
        root_sizer.Add(hint, 0, wx.ALL | wx.EXPAND, 12)
        if button_sizer is not None:
            root_sizer.Add(button_sizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.ALIGN_RIGHT, 12)

        self.SetSizerAndFit(root_sizer)
        self.SetMinSize((460, 220))
        self.SetEscapeId(wx.ID_CANCEL)
        self.CentreOnParent()

        self.query_text.Bind(wx.EVT_TEXT_ENTER, self._on_confirm)

        self.query_text.SetFocus()
        self.query_text.SelectAll()

    def get_query(self):
        return str(self.query_text.GetValue() or "").strip()

    def _on_confirm(self, _event):
        # Enter no campo de texto equivale a acionar "Localizar".
        if self.IsModal():
            self.EndModal(wx.ID_OK)
            return
        self.SetReturnCode(wx.ID_OK)
        self.Show(False)
