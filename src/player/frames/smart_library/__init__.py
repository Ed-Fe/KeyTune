"""Comportamento da janela para a biblioteca inteligente.

O mixin público é recomposto a partir de sub-mixins focados, seguindo o padrão
já usado por `frames/commands/`, `frames/playback/` e `frames/youtube_music/`.
"""

from .history import SmartLibraryHistoryMixin
from .indexing import SmartLibraryIndexingMixin
from .lifecycle import SmartLibraryLifecycleMixin
from .marks import SmartLibraryMarksMixin
from .playback_tracking import SmartLibraryPlaybackTrackingMixin
from .ratings import SmartLibraryRatingsMixin
from .resume import SmartLibraryResumeMixin
from .search import SmartLibrarySearchMixin
from .smart_playlists import SmartLibraryPlaylistsMixin


class FrameSmartLibraryMixin(
    SmartLibrarySearchMixin,
    SmartLibraryPlaylistsMixin,
    SmartLibraryRatingsMixin,
    SmartLibraryMarksMixin,
    SmartLibraryHistoryMixin,
    SmartLibraryResumeMixin,
    SmartLibraryPlaybackTrackingMixin,
    SmartLibraryIndexingMixin,
    SmartLibraryLifecycleMixin,
):
    """Busca global, favoritos, avaliações, histórico, retomada e playlists inteligentes."""


__all__ = ["FrameSmartLibraryMixin"]
