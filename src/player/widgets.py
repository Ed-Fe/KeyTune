"""Linhas de controles acessíveis reutilizadas pelos diálogos de download e conversão."""

from __future__ import annotations

import wx

from .i18n import _


def add_choice_row(parent, sizer, label_text, help_text, labels):
    """Rótulo visível, lista de opções e ajuda; o nome acessível é o próprio rótulo."""
    label = wx.StaticText(parent, label=f"{label_text}:")
    choice = wx.Choice(parent, choices=labels, name=label_text)
    choice.SetToolTip(help_text)
    help_label = wx.StaticText(parent, label=help_text)
    label.Wrap(500)
    help_label.Wrap(500)
    sizer.Add(label, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 6)
    sizer.Add(choice, 0, wx.ALL | wx.EXPAND, 6)
    sizer.Add(help_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 6)
    return choice


def add_directory_row(parent, sizer, label_text, help_text, dialog_message, browse_name):
    """Campo de pasta com botão «Escolher pasta...»; devolve o campo de texto.

    O botão fica em ``campo.browse_button`` para quem precisar habilitá-lo ou
    desabilitá-lo junto com o campo.
    """
    label = wx.StaticText(parent, label=f"{label_text}:")
    directory_ctrl = wx.TextCtrl(parent, name=label_text)
    directory_ctrl.SetToolTip(help_text)
    browse_button = wx.Button(parent, label=_("Escolher &pasta..."))
    browse_button.SetName(browse_name)

    def on_browse(_event):
        dialog = wx.DirDialog(
            parent,
            dialog_message,
            defaultPath=directory_ctrl.GetValue().strip(),
            style=wx.DD_DEFAULT_STYLE | wx.DD_NEW_DIR_BUTTON,
        )
        try:
            if dialog.ShowModal() == wx.ID_OK:
                directory_ctrl.SetValue(dialog.GetPath())
        finally:
            dialog.Destroy()

    browse_button.Bind(wx.EVT_BUTTON, on_browse)
    directory_ctrl.browse_button = browse_button
    row = wx.BoxSizer(wx.HORIZONTAL)
    row.Add(directory_ctrl, 1, wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 6)
    row.Add(browse_button, 0, wx.ALIGN_CENTER_VERTICAL)
    sizer.Add(label, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 6)
    sizer.Add(row, 0, wx.ALL | wx.EXPAND, 6)
    return directory_ctrl
