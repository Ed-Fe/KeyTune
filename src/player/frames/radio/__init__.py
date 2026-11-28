"""Rádios online na janela do player.

Cada responsabilidade fica num mixin próprio, recompostos aqui em
:class:`FrameRadioMixin`: a aba (``lifecycle``), a pilha de listas e a busca
(``navigation``), as ações sobre as rádios (``actions``), o cadastro no
diretório público (``directory``) e o que acontece quando uma rádio toca
(``now_playing``).
"""

from .actions import RadioActionsMixin
from .directory import RadioDirectoryMixin
from .lifecycle import RadioLifecycleMixin
from .navigation import RadioNavigationMixin
from .now_playing import RadioNowPlayingMixin


class FrameRadioMixin(
    RadioLifecycleMixin,
    RadioNavigationMixin,
    RadioActionsMixin,
    RadioDirectoryMixin,
    RadioNowPlayingMixin,
):
    """Aggregate online-radio mixin composed from focused sub-mixins."""


__all__ = ["FrameRadioMixin"]
