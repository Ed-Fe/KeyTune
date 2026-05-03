"""Frame mixin wiring Windows System Media Transport Controls (SMTC).

Receives Bluetooth/AVRCP, multimedia-key, smartwatch and Alexa transport
commands and forwards them to the existing playback methods. Also keeps the
Windows "now playing" overlay metadata and status in sync with the player.
"""

from __future__ import annotations

import os

import wx

from ..smtc import SmtcService, is_smtc_supported


class FrameSmtcMixin:
    """Bridge SMTC button events into the frame's playback commands."""

    def _initialize_smtc_service(self) -> None:
        self._smtc_service = None
        if not is_smtc_supported():
            return

        service = SmtcService(
            on_play=self._smtc_dispatch_play,
            on_pause=self._smtc_dispatch_pause,
            on_stop=self._smtc_dispatch_stop,
            on_next=self._smtc_dispatch_next,
            on_previous=self._smtc_dispatch_previous,
        )
        if not service.start():
            return
        self._smtc_service = service

    def _shutdown_smtc_service(self) -> None:
        service = getattr(self, "_smtc_service", None)
        if service is None:
            return
        try:
            service.stop()
        finally:
            self._smtc_service = None

    # --- Button dispatchers (called from a background thread) ---
    def _smtc_dispatch_play(self) -> None:
        wx.CallAfter(self._smtc_handle_play_or_resume)

    def _smtc_dispatch_pause(self) -> None:
        wx.CallAfter(self._smtc_handle_pause)

    def _smtc_dispatch_stop(self) -> None:
        wx.CallAfter(self._smtc_handle_stop)

    def _smtc_dispatch_next(self) -> None:
        wx.CallAfter(self.on_next_track, None)

    def _smtc_dispatch_previous(self) -> None:
        wx.CallAfter(self.on_previous_track, None)

    # --- UI-thread handlers ---
    def _smtc_handle_play_or_resume(self) -> None:
        player = getattr(self, "player", None)
        if player is None:
            return
        try:
            if player.is_playing():
                return
        except Exception:
            pass
        self.on_play_pause(None)

    def _smtc_handle_pause(self) -> None:
        player = getattr(self, "player", None)
        if player is None:
            return
        try:
            if not player.is_playing():
                return
        except Exception:
            pass
        self.on_play_pause(None)

    def _smtc_handle_stop(self) -> None:
        if hasattr(self, "on_stop"):
            self.on_stop(None)

    # --- Status / metadata sync ---
    def _refresh_smtc_state(self) -> None:
        service = getattr(self, "_smtc_service", None)
        if service is None or not service.is_available():
            return

        state = None
        get_active_state = getattr(self, "_get_active_playlist_state", None)
        if callable(get_active_state):
            state = get_active_state()
        if state is None:
            get_state = getattr(self, "_get_playlist_state", None)
            if callable(get_state):
                state = get_state()

        media_path = getattr(state, "current_media_path", "") if state else ""
        if not media_path:
            service.set_playback_status("closed")
            service.clear_metadata()
            return

        title, artist = self._smtc_titles_for_media(media_path, state)
        service.set_metadata(title=title, artist=artist)

        status = "stopped"
        player = getattr(self, "player", None)
        if player is not None:
            try:
                if player.get_media() is None:
                    status = "closed"
                elif player.is_playing():
                    status = "playing"
                else:
                    status = "paused"
            except Exception:
                status = "stopped"
        service.set_playback_status(status)

    def _smtc_titles_for_media(self, media_path, state):
        label_method = getattr(self, "_media_label", None)
        title = ""
        if callable(label_method):
            try:
                title = str(label_method(media_path) or "").strip()
            except Exception:
                title = ""
        if not title:
            title = os.path.basename(str(media_path)) or str(media_path)

        artist = ""
        if state is not None:
            artist = str(getattr(state, "title", "") or "").strip()

        return title, artist
