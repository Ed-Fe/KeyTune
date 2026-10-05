"""Player rápido: toca um arquivo aberto pelo Windows numa janela pequena.

A janela fica em ``frame.py`` e só é importada quando o player rápido abre.
"""

from .launch import quick_player_paths

__all__ = ["quick_player_paths"]
