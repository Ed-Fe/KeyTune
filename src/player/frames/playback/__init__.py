"""Playback subsystem for the player frame.

The playback responsibilities used to live in a single oversized
``frames/playback.py`` module. They are now split into focused mixins, one per
concern, and recomposed here into :class:`FramePlaybackMixin` so the public
import surface (``from player.frames.playback import FramePlaybackMixin``) and
``base.py`` composition stay unchanged.
"""

from .audio_output import AudioOutputMixin
from .autodj import AutoDjMixin
from .backend import PlayerBackendMixin
from .controls import PlaybackControlsMixin
from .crossfade import CrossfadeMixin
from .engine import PlaybackEngineMixin
from .helpers import (
    _STREAM_ARTIFACT_TITLE_SUFFIXES,
    _default_remote_media_label,
    _looks_like_stream_artifact_title,
    _normalize_runtime_title_token,
    _should_apply_runtime_stream_title,
    is_music_youtube_url,
    is_youtube_music_media,
)
from .media_metadata import MediaMetadataMixin
from .youtube_history import YouTubeHistoryMixin


class FramePlaybackMixin(
    PlayerBackendMixin,
    AudioOutputMixin,
    AutoDjMixin,
    CrossfadeMixin,
    PlaybackEngineMixin,
    YouTubeHistoryMixin,
    MediaMetadataMixin,
    PlaybackControlsMixin,
):
    """Aggregate playback mixin composed from focused sub-mixins."""


__all__ = [
    "FramePlaybackMixin",
    "AutoDjMixin",
    "is_music_youtube_url",
    "is_youtube_music_media",
    "_STREAM_ARTIFACT_TITLE_SUFFIXES",
    "_default_remote_media_label",
    "_looks_like_stream_artifact_title",
    "_normalize_runtime_title_token",
    "_should_apply_runtime_stream_title",
]
