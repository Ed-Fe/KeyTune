"""YouTube Music integration for the player frame.

The YouTube Music responsibilities used to live in a single oversized
``frames/youtube_music.py`` module (2000+ lines mixing dependency management,
background-task orchestration, library/search state, auth, search, playlist
editing, catalog browsing and tab lifecycle). They are now split into focused
mixins, one per concern, and recomposed here into
:class:`FrameYouTubeMusicMixin` so the public import surface
(``from player.frames.youtube_music import FrameYouTubeMusicMixin``) and the
``base.py`` composition stay unchanged.
"""

import wx

from player.youtube_music.dialog import YouTubeMusicJavascriptRuntimeDialog

from ._helpers import (
    find_all_available_javascript_runtimes,
    is_missing_javascript_runtime_error_message,
)
from .auth import AuthMixin
from .browse import BrowseMixin
from .dependencies import DependencyMixin
from .lifecycle import LifecycleMixin
from .playlists import PlaylistEditMixin
from .search import SearchMixin
from .state import LibraryStateMixin
from .tasks import BackgroundTaskMixin


class FrameYouTubeMusicMixin(
    DependencyMixin,
    BackgroundTaskMixin,
    LibraryStateMixin,
    AuthMixin,
    SearchMixin,
    PlaylistEditMixin,
    BrowseMixin,
    LifecycleMixin,
):
    """Aggregate YouTube Music mixin composed from focused sub-mixins."""


__all__ = [
    "FrameYouTubeMusicMixin",
    "YouTubeMusicJavascriptRuntimeDialog",
    "find_all_available_javascript_runtimes",
    "is_missing_javascript_runtime_error_message",
]
