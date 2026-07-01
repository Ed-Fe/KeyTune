"""Bridge between the player and the Windows System Media Transport Controls.

The SMTC is the Windows-wide "now playing" surface. Registering with it lets
the app receive transport commands coming from Bluetooth headphones (AVRCP),
multimedia keyboards, smartwatches, the Windows volume overlay and Alexa when
the PC is paired/connected, all through a single API.
"""

from __future__ import annotations

import sys
import threading
from ..i18n import _
from typing import Callable, Optional

from ..log import get_logger


_logger = get_logger(__name__)

_SMTC_LOAD_LOCK = threading.Lock()
_SMTC_LOADED = False
_SMTC_DEPS_AVAILABLE = False
_SMTC_IMPORT_ERROR: Optional[Exception] = None

_MediaPlaybackStatus = None
_MediaPlaybackType = None
_SystemMediaTransportControlsButton = None
_MediaPlayer = None
_PLAYBACK_STATUS_MAP: dict = {}


def _load_smtc_dependencies() -> bool:
    """Import the optional winrt/winsdk SMTC bindings on first use.

    The winrt packages are comparatively slow to import, so this is deferred
    out of the startup import path and only triggered when the SMTC layer is
    actually queried or started.
    """

    global _SMTC_LOADED, _SMTC_DEPS_AVAILABLE, _SMTC_IMPORT_ERROR
    global _MediaPlaybackStatus, _MediaPlaybackType
    global _SystemMediaTransportControlsButton, _MediaPlayer
    global _PLAYBACK_STATUS_MAP

    if _SMTC_LOADED:
        return _SMTC_DEPS_AVAILABLE

    with _SMTC_LOAD_LOCK:
        if _SMTC_LOADED:
            return _SMTC_DEPS_AVAILABLE

        if sys.platform != "win32":  # pragma: no cover - non-Windows platforms skip SMTC
            _SMTC_IMPORT_ERROR = RuntimeError("SMTC só está disponível no Windows.")
            _SMTC_LOADED = True
            return False

        try:  # pragma: no cover - prefer the maintained pywinrt distribution
            from winrt.windows.media import (
                MediaPlaybackStatus,
                MediaPlaybackType,
                SystemMediaTransportControlsButton,
            )
            from winrt.windows.media.playback import MediaPlayer
        except Exception as exc_winrt:
            try:  # pragma: no cover - fallback to the legacy winsdk package
                from winsdk.windows.media import (  # type: ignore[import-not-found]
                    MediaPlaybackStatus,
                    MediaPlaybackType,
                    SystemMediaTransportControlsButton,
                )
                from winsdk.windows.media.playback import MediaPlayer  # type: ignore[import-not-found]
            except Exception as exc_winsdk:
                _SMTC_IMPORT_ERROR = exc_winrt or exc_winsdk
                _SMTC_LOADED = True
                return False

        _MediaPlaybackStatus = MediaPlaybackStatus
        _MediaPlaybackType = MediaPlaybackType
        _SystemMediaTransportControlsButton = SystemMediaTransportControlsButton
        _MediaPlayer = MediaPlayer
        _PLAYBACK_STATUS_MAP = {
            "playing": MediaPlaybackStatus.PLAYING,
            "paused": MediaPlaybackStatus.PAUSED,
            "stopped": MediaPlaybackStatus.STOPPED,
            "closed": MediaPlaybackStatus.CLOSED,
            "changing": MediaPlaybackStatus.CHANGING,
        }
        _SMTC_DEPS_AVAILABLE = True
        _SMTC_LOADED = True
        return True


def is_smtc_supported() -> bool:
    """Return True when the System Media Transport Controls are usable."""

    return bool(_load_smtc_dependencies())


def smtc_dependency_error_message() -> str:
    """Return a localized message describing why SMTC is unavailable."""

    if _load_smtc_dependencies():
        return ""
    if _SMTC_IMPORT_ERROR is not None:
        return (
            _("Controles de mídia do sistema indisponíveis. Instale o pacote 'winrt-Windows.Media.Playback' no Windows.")
            + " "
            + _("Detalhes: {error}").format(error=_SMTC_IMPORT_ERROR)
        )
    return _("Controles de mídia do sistema indisponíveis.")


class SmtcService:
    """Wraps a hidden ``MediaPlayer`` to expose its SMTC to the system shell.

    The ``MediaPlayer`` is never used to play audio: it exists only because it
    is the simplest way to obtain a ``SystemMediaTransportControls`` instance
    from a Win32 app without going through the COM interop directly.
    """

    def __init__(
        self,
        *,
        on_play: Optional[Callable[[], None]] = None,
        on_pause: Optional[Callable[[], None]] = None,
        on_stop: Optional[Callable[[], None]] = None,
        on_next: Optional[Callable[[], None]] = None,
        on_previous: Optional[Callable[[], None]] = None,
    ) -> None:
        self._on_play = on_play
        self._on_pause = on_pause
        self._on_stop = on_stop
        self._on_next = on_next
        self._on_previous = on_previous

        self._lock = threading.Lock()
        self._media_player = None
        self._smtc = None
        self._updater = None
        self._button_token = None
        self._available = False

    def start(self) -> bool:
        if not _load_smtc_dependencies():
            return False
        with self._lock:
            return self._start_locked()

    def _start_locked(self) -> bool:
        if self._available:
            return True
        try:
            player = _MediaPlayer()
            # Disable automatic command handling so SMTC button events are
            # delivered to our handler instead of being consumed by the
            # MediaPlayer's default behavior.
            try:
                player.command_manager.is_enabled = False
            except Exception:
                pass

            smtc = player.system_media_transport_controls
            smtc.is_enabled = True
            smtc.is_play_enabled = True
            smtc.is_pause_enabled = True
            smtc.is_stop_enabled = True
            smtc.is_next_enabled = True
            smtc.is_previous_enabled = True
            smtc.playback_status = _MediaPlaybackStatus.CLOSED

            self._button_token = smtc.add_button_pressed(self._on_button_pressed)
            self._media_player = player
            self._smtc = smtc
            self._updater = smtc.display_updater
            self._available = True
            return True
        except Exception as exc:
            _logger.warning("Failed to start SMTC service: %s", exc)
            self._cleanup_locked()
            return False

    def reassert(self) -> bool:
        """Reclaim ownership of the system media transport controls.

        Windows can silently drop a stale SMTC session when the audio
        endpoint changes — most notably when a Bluetooth accessory (Alexa,
        headphones, speakers) disconnects and reconnects. After that, AVRCP
        transport commands from the device stop reaching our ``ButtonPressed``
        handler and the controls appear "dead". Re-enabling the controls
        reclaims the session; if the underlying object has become unusable we
        rebuild it from scratch so a fresh registration is published.
        """
        if not _load_smtc_dependencies():
            return False
        with self._lock:
            if not self._available or self._smtc is None:
                return self._start_locked()
            try:
                smtc = self._smtc
                smtc.is_enabled = True
                smtc.is_play_enabled = True
                smtc.is_pause_enabled = True
                smtc.is_stop_enabled = True
                smtc.is_next_enabled = True
                smtc.is_previous_enabled = True
                return True
            except Exception as exc:
                _logger.warning("SMTC reassert failed; rebuilding session: %s", exc)
                self._cleanup_locked()
                return self._start_locked()

    def stop(self) -> None:
        with self._lock:
            self._cleanup_locked()

    def is_available(self) -> bool:
        return bool(self._available)

    def _cleanup_locked(self) -> None:
        smtc = self._smtc
        if smtc is not None and self._button_token is not None:
            try:
                smtc.remove_button_pressed(self._button_token)
            except Exception:
                pass
        if smtc is not None:
            try:
                smtc.is_enabled = False
            except Exception:
                pass
        if self._media_player is not None:
            try:
                self._media_player.close()
            except Exception:
                pass
        self._smtc = None
        self._updater = None
        self._button_token = None
        self._media_player = None
        self._available = False

    def _on_button_pressed(self, _sender, args) -> None:
        if not _SMTC_DEPS_AVAILABLE:
            return
        try:
            button = args.button
        except Exception:
            return

        try:
            if button == _SystemMediaTransportControlsButton.PLAY:
                callback = self._on_play
            elif button == _SystemMediaTransportControlsButton.PAUSE:
                callback = self._on_pause
            elif button == _SystemMediaTransportControlsButton.STOP:
                callback = self._on_stop
            elif button == _SystemMediaTransportControlsButton.NEXT:
                callback = self._on_next
            elif button == _SystemMediaTransportControlsButton.PREVIOUS:
                callback = self._on_previous
            else:
                callback = None
        except Exception:
            callback = None

        if callable(callback):
            try:
                callback()
            except Exception as exc:
                _logger.warning("SMTC button handler raised: %s", exc)

    def set_playback_status(self, status: str) -> None:
        if not _SMTC_DEPS_AVAILABLE:
            return
        with self._lock:
            smtc = self._smtc
            if smtc is None:
                return
            mapped = _PLAYBACK_STATUS_MAP.get(status)
            if mapped is None:
                mapped = _MediaPlaybackStatus.CLOSED
            try:
                smtc.playback_status = mapped
            except Exception:
                pass

    def set_metadata(
        self,
        *,
        title: str = "",
        artist: str = "",
        album: str = "",
    ) -> None:
        if not _SMTC_DEPS_AVAILABLE:
            return
        with self._lock:
            updater = self._updater
            if updater is None:
                return
            try:
                updater.type = _MediaPlaybackType.MUSIC
                music = updater.music_properties
                music.title = title or ""
                music.artist = artist or ""
                music.album_title = album or ""
                updater.update()
            except Exception:
                pass

    def clear_metadata(self) -> None:
        if not _SMTC_DEPS_AVAILABLE:
            return
        with self._lock:
            updater = self._updater
            if updater is None:
                return
            try:
                updater.clear_all()
                updater.update()
            except Exception:
                pass
