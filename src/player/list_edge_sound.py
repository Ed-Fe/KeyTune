"""O som de quando a seta bate no começo ou no fim de uma lista, ou a lista está vazia."""

import wx

from . import interface_sounds


def list_edge_reached(window, key_code):
    """Se *key_code* pede para passar do primeiro ou do último item da lista *window*, ou ela está vazia."""
    if key_code in (wx.WXK_UP, wx.WXK_NUMPAD_UP):
        towards_end = False
    elif key_code in (wx.WXK_DOWN, wx.WXK_NUMPAD_DOWN):
        towards_end = True
    else:
        return False
    try:
        if isinstance(window, wx.ListCtrl):
            count, current = window.GetItemCount(), window.GetFocusedItem()
        elif isinstance(window, wx.ListBox):
            count = window.GetCount()
            if window.HasMultipleSelection():
                selections = list(window.GetSelections())
                current = selections[0] if len(selections) == 1 else -1
            else:
                current = window.GetSelection()
        else:
            return False
    except Exception:
        return False
    if count <= 1:
        # Numa lista vazia, ou com uma linha só (o aviso de "lista vazia" é uma),
        # qualquer seta já bate na borda.
        return True
    if current < 0:
        return False
    return current == (count - 1 if towards_end else 0)


def play_list_edge_sound(window, event):
    """Toca o som da borda quando a tecla de *event* bate nela na lista *window*; a tecla segue o caminho dela."""
    if event.HasAnyModifiers() or not list_edge_reached(window, event.GetKeyCode()):
        return False
    is_auto_repeat = getattr(event, "IsAutoRepeat", None)
    if callable(is_auto_repeat) and is_auto_repeat():
        # Com a tecla segurada o som toca uma vez só, no primeiro toque.
        return False
    return interface_sounds.play_for(wx.GetTopLevelParent(window), interface_sounds.SOUND_LIST_EDGE)
