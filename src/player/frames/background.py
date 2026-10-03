"""Trabalho de disco fora da thread da interface."""

import threading

import wx


def run_in_background(owner, work, on_done):
    """Roda *work* em outra thread e entrega o resultado a *on_done* na interface.

    *owner* é a janela dona do pedido: se ela já tiver sido destruída quando o
    trabalho terminar, o resultado é descartado.
    """

    def deliver(result):
        if owner:
            on_done(result)

    threading.Thread(target=lambda: wx.CallAfter(deliver, work()), daemon=True).start()
