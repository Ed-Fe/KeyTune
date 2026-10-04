"""Linhas de controles acessíveis reutilizadas pelos diálogos de download e conversão."""

from __future__ import annotations

import wx

from .accessibility import attach_named_accessible
from .i18n import _

# Margem em volta de cada linha de um grupo.
ROW_BORDER = 4


def create_group(parent, label):
    """Grupo com moldura; devolve ``(caixa, sizer)``.

    Os controles do grupo são criados com a *caixa* como pai: só assim o leitor
    de tela anuncia o nome do grupo ao entrar nele. Com a caixa apenas ao lado
    dos controles, ela é só um desenho na tela.
    """
    box = wx.StaticBox(parent, label=label)
    return box, wx.StaticBoxSizer(box, wx.VERTICAL)


def describe_control(control, name, help_text):
    """Dá ao controle um nome e a ajuda como descrição acessível.

    O tooltip só aparece com o mouse; a descrição chega ao leitor de tela junto
    com o controle, sem virar um texto solto lido ao abrir o diálogo.
    """
    control.SetName(name)
    control.SetToolTip(help_text)
    control.SetHelpText(help_text)
    attach_named_accessible(control, name=name, description=help_text)


def add_labeled_row(sizer, label, control):
    """Põe o rótulo e o controle na mesma linha: o rótulo à esquerda, o controle à direita."""
    row = wx.BoxSizer(wx.HORIZONTAL)
    row.Add(label, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
    row.Add(control, 0, wx.ALIGN_CENTER_VERTICAL)
    sizer.Add(row, 0, wx.ALL | wx.EXPAND, ROW_BORDER)


def equalize_row_controls(root, max_width=360):
    """Deixa as listas e os campos numéricos sob *root* com a mesma largura.

    Vale a do mais largo, até *max_width* (em pixels independentes de escala),
    para a coluna da direita ficar uniforme.
    """
    controls = []

    def collect(window):
        for child in window.GetChildren():
            if isinstance(child, (wx.Choice, wx.SpinCtrl)):
                controls.append(child)
            else:
                collect(child)

    collect(root)
    if not controls:
        return
    width = min(max(control.GetBestSize().width for control in controls), root.FromDIP(max_width))
    for control in controls:
        control.SetMinSize((width, -1))


def add_choice_row(parent, sizer, label_text, help_text, labels):
    """Rótulo visível e lista de opções numa linha; a ajuda, curta, vai como descrição acessível.

    Um texto de ajuda visível seria lido por inteiro pelo leitor de tela ao abrir o
    diálogo, antes de qualquer controle.
    """
    label = wx.StaticText(parent, label=f"{label_text}:")
    choice = wx.Choice(parent, choices=labels, name=label_text)
    describe_control(choice, label_text, help_text)
    add_labeled_row(sizer, label, choice)
    return choice


def add_directory_row(parent, sizer, label_text, help_text, dialog_message, browse_name):
    """Campo de pasta com botão «Escolher pasta...»; devolve o campo de texto.

    O botão fica em ``campo.browse_button`` para quem precisar habilitá-lo ou
    desabilitá-lo junto com o campo.
    """
    label = wx.StaticText(parent, label=f"{label_text}:")
    directory_ctrl = wx.TextCtrl(parent, name=label_text)
    describe_control(directory_ctrl, label_text, help_text)
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
    sizer.Add(label, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, ROW_BORDER)
    sizer.Add(row, 0, wx.ALL | wx.EXPAND, ROW_BORDER)
    return directory_ctrl
