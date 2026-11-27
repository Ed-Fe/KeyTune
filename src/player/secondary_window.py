"""Janelas secundárias sem modo modal: o player continua usável com elas abertas.

Uma janela secundária (o manual, por exemplo) é aberta uma vez só: pedir de novo
traz a que já está aberta para a frente, com o foco onde a pessoa deixou. ``Alt+F6``
alterna entre a janela principal e a secundária aberta mais recente, que é o
atalho do Windows para trocar de janela dentro do mesmo programa (Office, Bloco de
Notas). Fechar a janela secundária devolve o foco à principal.
"""

from __future__ import annotations

import wx

_REGISTRY_ATTRIBUTE = "_secondary_windows"


def _alive(window) -> bool:
    try:
        return bool(window) and not window.IsBeingDeleted()
    except RuntimeError:
        return False


def _registry(owner) -> dict:
    registry = owner.__dict__.get(_REGISTRY_ATTRIBUTE)
    if registry is None:
        registry = {}
        owner.__dict__[_REGISTRY_ATTRIBUTE] = registry
    return registry


def bring_to_front(window) -> None:
    """Ativa *window*; o foco volta ao controle em que estava."""
    if window.IsIconized():
        window.Iconize(False)
    window.Show()
    window.Raise()


def is_secondary_window_open(owner, key: str) -> bool:
    """Se a janela secundária *key* de *owner* já está aberta (para não recriar seu conteúdo)."""
    window = _registry(owner).get(key)
    return window is not None and _alive(window)


def show_secondary_window(owner, key: str, factory):
    """Mostra a janela *key* de *owner*, criando-a com *factory* só se não houver uma aberta.

    *factory* recebe nada e devolve a janela (um ``wx.Dialog`` ou ``wx.Frame``
    com *owner* como pai), ainda escondida. Devolve a janela mostrada.
    """
    registry = _registry(owner)
    window = registry.get(key)
    if window is not None and _alive(window):
        bring_to_front(window)
        return window

    window = factory()
    registry[key] = window

    def on_destroy(event):
        if event.GetEventObject() is window and registry.get(key) is window:
            registry.pop(key, None)
            # Com a secundária fechada, a principal volta a ser a janela ativa.
            if _alive(owner) and owner.IsShown():
                wx.CallAfter(_reactivate, owner)
        event.Skip()

    window.Bind(wx.EVT_WINDOW_DESTROY, on_destroy)
    window.Show()
    return window


def _reactivate(owner) -> None:
    if _alive(owner) and not owner.IsActive():
        owner.Raise()


def latest_secondary_window(owner):
    """A janela secundária aberta mais recente de *owner*, ou ``None``."""
    windows = [window for window in _registry(owner).values() if _alive(window)]
    return windows[-1] if windows else None


def is_switch_window_key(event) -> bool:
    """``Alt+F6``: o atalho de trocar entre a janela principal e a secundária."""
    return (
        event.GetKeyCode() == wx.WXK_F6
        and event.AltDown()
        and not event.ControlDown()
        and not event.ShiftDown()
    )


def switch_to_secondary_window(owner) -> bool:
    """Da janela principal, vai para a secundária aberta; ``False`` se não houver."""
    window = latest_secondary_window(owner)
    if window is None:
        return False
    bring_to_front(window)
    return True
