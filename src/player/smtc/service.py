"""Bridge between the player and the Windows System Media Transport Controls.

The SMTC is the Windows-wide "now playing" surface. Registering with it lets
the app receive transport commands coming from Bluetooth headphones (AVRCP),
multimedia keyboards, smartwatches, the Windows volume overlay and Alexa when
the PC is paired/connected, all through a single API.
"""

from __future__ import annotations

import sys
import threading
from typing import Callable, Optional


_SMTC_DEPS_AVAILABLE = False
_SMTC_IMPORT_ERROR: Optional[Exception] = None

if sys.platform == "win32":
    try:  # pragma: no cover - prefer the maintained pywinrt distribution
        from winrt.windows.media import (
            MediaPlaybackStatus,
            MediaPlaybackType,
            SystemMediaTransportControlsButton,
        )
        from winrt.windows.media.playback import MediaPlayer

        _SMTC_DEPS_AVAILABLE = True
    except Exception as _exc_winrt:
        try:  # pragma: no cover - fallback to the legacy winsdk package
            from winsdk.windows.media import (  # type: ignore[import-not-found]
                MediaPlaybackStatus,
                MediaPlaybackType,
                SystemMediaTransportControlsButton,
            )
            from winsdk.windows.media.playback import MediaPlayer  # type: ignore[import-not-found]

            _SMTC_DEPS_AVAILABLE = True
        except Exception as _exc_winsdk:
            _SMTC_IMPORT_ERROR = _exc_winrt or _exc_winsdk
else:  # pragma: no cover - non-Windows platforms simply skip SMTC
    _SMTC_IMPORT_ERROR = RuntimeError("SMTC só está disponível no Windows.")


def is_smtc_supported() -> bool:
    """Return True when the System Media Transport Controls are usable."""

    return bool(_SMTC_DEPS_AVAILABLE)


def smtc_dependency_error_message() -> str:
    """Return a localized message describing why SMTC is unavailable."""

    if _SMTC_DEPS_AVAILABLE:
        return ""
    if _SMTC_IMPORT_ERROR is not None:
        return (
            "Controles de mídia do sistema indisponíveis. "
            "Instale o pacote 'winrt-Windows.Media.Playback' no Windows. "
            f"Detalhes: {_SMTC_IMPORT_ERROR}"
        )
    return "Controles de mídia do sistema indisponíveis."


def _build_status_map():
    if not _SMTC_DEPS_AVAILABLE:
        return {}
    return {
        "playing": MediaPlaybackStatus.PLAYING,
        "paused": MediaPlaybackStatus.PAUSED,
        "stopped": MediaPlaybackStatus.STOPPED,
        "closed": MediaPlaybackStatus.CLOSED,
        "changing": MediaPlaybackStatus.CHANGING,
    }


_PLAYBACK_STATUS_MAP = _build_status_map()


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
        if not _SMTC_DEPS_AVAILABLE:
            return False
        with self._lock:
            if self._available:
                return True
            try:
                player = MediaPlayer()
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
                smtc.playback_status = MediaPlaybackStatus.CLOSED

                self._button_token = smtc.add_button_pressed(self._on_button_pressed)
                self._media_player = player
                self._smtc = smtc
                self._updater = smtc.display_updater
                self._available = True
                return True
            except Exception:
                self._cleanup_locked()
                return False

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
            if button == SystemMediaTransportControlsButton.PLAY:
                callback = self._on_play
            elif button == SystemMediaTransportControlsButton.PAUSE:
                callback = self._on_pause
            elif button == SystemMediaTransportControlsButton.STOP:
                callback = self._on_stop
            elif button == SystemMediaTransportControlsButton.NEXT:
                callback = self._on_next
            elif button == SystemMediaTransportControlsButton.PREVIOUS:
                callback = self._on_previous
            else:
                callback = None
        except Exception:
            callback = None

        if callable(callback):
            try:
                callback()
            except Exception:
                pass

    def set_playback_status(self, status: str) -> None:
        if not _SMTC_DEPS_AVAILABLE:
            return
        with self._lock:
            smtc = self._smtc
            if smtc is None:
                return
            mapped = _PLAYBACK_STATUS_MAP.get(status)
            if mapped is None:
                mapped = MediaPlaybackStatus.CLOSED
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
                updater.type = MediaPlaybackType.MUSIC
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
