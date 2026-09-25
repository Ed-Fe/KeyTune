"""Diálogo com os itens que falharam num download ou numa conversão em lote."""

from __future__ import annotations

import wx

from .i18n import _


class TaskFailuresDialog(wx.Dialog):
    """Lista somente leitura de item e motivo, com opção de copiar tudo."""

    def __init__(self, parent, title, failures):
        super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self._failures = list(failures)

        root = wx.BoxSizer(wx.VERTICAL)
        intro = wx.StaticText(
            self, label=_("{count} itens falharam. Os demais foram concluídos.").format(count=len(self._failures))
        )
        root.Add(intro, 0, wx.ALL | wx.EXPAND, 10)

        self.list_ctrl = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.list_ctrl.SetName(_("Itens que falharam"))
        self.list_ctrl.InsertColumn(0, _("Item"), width=260)
        self.list_ctrl.InsertColumn(1, _("Motivo"), width=380)
        for row, (name, reason) in enumerate(self._failures):
            self.list_ctrl.InsertItem(row, str(name))
            self.list_ctrl.SetItem(row, 1, str(reason))
        if self._failures:
            self.list_ctrl.Select(0)
            self.list_ctrl.Focus(0)
        root.Add(self.list_ctrl, 1, wx.LEFT | wx.RIGHT | wx.EXPAND, 10)

        buttons = wx.StdDialogButtonSizer()
        copy_button = wx.Button(self, label=_("&Copiar lista"))
        copy_button.Bind(wx.EVT_BUTTON, self._on_copy)
        close_button = wx.Button(self, wx.ID_CLOSE, _("&Fechar"))
        close_button.SetDefault()
        close_button.Bind(wx.EVT_BUTTON, lambda event: self.EndModal(wx.ID_CLOSE))
        buttons.AddButton(close_button)
        buttons.Realize()
        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(copy_button, 0, wx.RIGHT, 8)
        row.Add(buttons, 0)
        root.Add(row, 0, wx.ALL | wx.ALIGN_RIGHT, 10)

        self.SetEscapeId(wx.ID_CLOSE)
        self.SetSizerAndFit(root)
        self.SetMinSize((520, 300))
        self.CentreOnParent()
        self.list_ctrl.SetFocus()

    def failures_text(self):
        return "\n".join(f"{name}: {reason}" for name, reason in self._failures)

    def _on_copy(self, event):
        if wx.TheClipboard.Open():
            try:
                wx.TheClipboard.SetData(wx.TextDataObject(self.failures_text()))
            finally:
                wx.TheClipboard.Close()


def offer_task_failures(parent, dialog_title, failures):
    """Pergunta se o usuário quer ver as falhas de um lote e, se quiser, mostra o diálogo."""
    if not failures or wx.GetApp() is None:
        return
    answer = wx.MessageBox(
        _("{count} itens falharam. Deseja ver os detalhes?").format(count=len(failures)),
        dialog_title,
        wx.YES_NO | wx.YES_DEFAULT | wx.ICON_QUESTION,
        parent,
    )
    if answer != wx.YES:
        return
    dialog = TaskFailuresDialog(parent, dialog_title, failures)
    try:
        dialog.ShowModal()
    finally:
        dialog.Destroy()
