"""File/command handlers for the player frame.

The command responsibilities used to live in a single oversized
``frames/commands.py`` module (1000+ lines mixing file/clipboard open flows,
playback transport handlers, playlist-browser handlers, app/preferences/timer
events and keyboard navigation). They are now split into focused mixins, one
per concern, and recomposed here into :class:`FrameCommandMixin` so the public
import surface (``from player.frames.commands import FrameCommandMixin``) and
the ``base.py`` composition stay unchanged.
"""

from .app_commands import AppCommandsMixin
from .browser_commands import BrowserCommandsMixin
from .key_navigation import KeyNavigationMixin
from .open_commands import OpenCommandsMixin
from .transport_commands import TransportCommandsMixin


class FrameCommandMixin(
    OpenCommandsMixin,
    TransportCommandsMixin,
    BrowserCommandsMixin,
    AppCommandsMixin,
    KeyNavigationMixin,
):
    """Aggregate command mixin composed from focused sub-mixins."""


__all__ = ["FrameCommandMixin"]
