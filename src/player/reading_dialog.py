"""Campo e caixa de leitura: texto somente leitura para reler linha a linha e copiar.

Todo campo somente leitura do KeyTune nasce em ``create_reading_field``, para
que todos se leiam do mesmo jeito.
"""

import wx

from .i18n import _

# Sem quebra automática: cada seta lê uma linha inteira do texto (um parágrafo,
# em texto corrido), e não o pedaço que coube na largura da janela. Linhas
# longas rolam para o lado.
READING_FIELD_STYLE = wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_DONTWRAP | wx.HSCROLL | wx.VSCROLL


def create_reading_field(parent, name, text=""):
    """O campo somente leitura padrão, com o cursor no começo; devolve o campo.

    Crie o rótulo visível logo antes de chamar: no Windows é desse texto
    vizinho que o leitor de tela tira o nome de um campo de edição. Um campo
    sem rótulo visível recebe o nome por ``attach_named_accessible``.
    """
    text_ctrl = wx.TextCtrl(parent, value=text, style=READING_FIELD_STYLE)
    text_ctrl.SetName(name)
    text_ctrl.SetInsertionPoint(0)
    return text_ctrl


def add_reading_field(parent, sizer, label_text, text, *, border=10):
    """Rótulo visível seguido do campo somente leitura; devolve o campo."""
    label = wx.StaticText(parent, label=f"{label_text}:")
    text_ctrl = create_reading_field(parent, label_text, text)
    sizer.Add(label, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, border)
    sizer.Add(text_ctrl, 1, wx.ALL | wx.EXPAND, border)
    return text_ctrl


def show_reading_dialog(parent, *, title, label, text, actions=()):
    """Mostra *text* numa caixa só de leitura, com o cursor no começo; Esc fecha.

    *label*: o rótulo do campo, sem os dois-pontos.
    *actions*: pares ``(rótulo, função)``; cada um vira um botão que fecha a
    caixa e só então chama a função.
    """
    chosen = []
    dialog = wx.Dialog(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
    try:
        sizer = wx.BoxSizer(wx.VERTICAL)
        text_ctrl = add_reading_field(dialog, sizer, label, text)
        text_ctrl.SetMinSize((520, 260))

        buttons = wx.BoxSizer(wx.HORIZONTAL)
        for action_label, callback in actions:
            action_button = wx.Button(dialog, wx.ID_ANY, action_label)

            def on_action(_event, callback=callback):
                chosen.append(callback)
                dialog.EndModal(wx.ID_OK)

            action_button.Bind(wx.EVT_BUTTON, on_action)
            buttons.Add(action_button, 0, wx.RIGHT, 8)
        close_button = wx.Button(dialog, wx.ID_CLOSE, _("&Fechar"))
        close_button.Bind(wx.EVT_BUTTON, lambda _event: dialog.EndModal(wx.ID_CLOSE))
        buttons.Add(close_button, 0)
        dialog.SetEscapeId(wx.ID_CLOSE)

        sizer.Add(buttons, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.ALIGN_RIGHT, 10)
        dialog.SetSizerAndFit(sizer)
        dialog.CentreOnParent()
        dialog.ShowModal()
    finally:
        dialog.Destroy()
    for callback in chosen:
        callback()
    return True
