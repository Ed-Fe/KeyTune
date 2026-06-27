"""Playlist/screen tab management for the player frame.

The tab responsibilities used to live in a single oversized
``frames/library_tabs.py`` module (1100+ lines mixing tab lifecycle,
playlist transport/announcements, item removal and YouTube Music related
autoplay). They are now split into focused mixins, one per concern, and
recomposed here into :class:`FrameLibraryTabsMixin` so the public import
surface (``from player.frames.library_tabs import FrameLibraryTabsMixin``)
and the ``library.py`` composition stay unchanged.
"""

from .item_removal import PlaylistItemRemovalMixin
from .playback_control import PlaylistPlaybackMixin
from .related_autoplay import RelatedAutoplayMixin
from .tabs import TabManagementMixin


class FrameLibraryTabsMixin(
    TabManagementMixin,
    PlaylistPlaybackMixin,
    PlaylistItemRemovalMixin,
    RelatedAutoplayMixin,
):
    """Aggregate library-tab mixin composed from focused sub-mixins."""


__all__ = ["FrameLibraryTabsMixin"]
