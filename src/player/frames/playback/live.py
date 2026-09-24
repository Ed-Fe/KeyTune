"""Live-broadcast helpers for the playback frame."""

import wx

from ...i18n import _
from ...log import get_logger

_logger = get_logger(__name__)

# Waits before each reconnection attempt. A short first delay recovers from a
# blip; the later ones give a real outage a moment before we give up.
LIVE_RECONNECT_DELAYS_MS = (2000, 5000, 10000)


def is_live_media(media) -> bool:
    """True only for a media object explicitly flagged as a live broadcast.

    The strict ``is True`` keeps test doubles and half-initialised players
    (whose attributes are truthy mocks) from being mistaken for a live.
    """
    return getattr(media, "is_live", False) is True


class LivePlaybackMixin:
    """Reconnection and end-of-broadcast handling for live playback.

    A live has no "next track": when MPV stops receiving data we re-resolve the
    broadcast (its manifest goes stale) a few times, then report that it ended
    or that the connection could not be restored.
    """

    def _on_media_live_ended(self, _event, player_key):
        wx.CallAfter(self._handle_live_ended, player_key)

    def _handle_live_ended(self, player_key):
        if player_key != getattr(self, "_active_player_key", None):
            return
        self._schedule_live_reconnect()

    def _schedule_live_reconnect(self):
        attempts = getattr(self, "_live_reconnect_attempts", 0)
        if attempts >= len(LIVE_RECONNECT_DELAYS_MS):
            self._handle_live_finished(_("Não foi possível reconectar à transmissão ao vivo."))
            return

        state = self._get_active_playlist_state()
        tab_index = self._get_active_playlist_index()
        media_path = getattr(state, "current_media_path", None)
        if state is None or not media_path:
            return

        self._cancel_live_reconnect(reset=False)
        self._live_reconnect_attempts = attempts + 1
        if attempts == 0:
            self._announce(_("A conexão com a transmissão ao vivo foi perdida. Reconectando."))
        if hasattr(self, "_set_status_message"):
            self._set_status_message(_("Reconectando à transmissão ao vivo..."), auto_clear_ms=0)

        _logger.info("Live connection lost; reconnect attempt %d scheduled", attempts + 1)
        self._live_reconnect_timer = wx.CallLater(
            LIVE_RECONNECT_DELAYS_MS[attempts],
            self._reconnect_live,
            media_path,
            tab_index,
            self._playback_request_serial,
        )

    def _reconnect_live(self, media_path, tab_index, request_serial):
        self._live_reconnect_timer = None
        # Anything the user started meanwhile owns the player now.
        if request_serial != self._playback_request_serial:
            return
        state = self._get_playlist_state(tab_index)
        if state is None or state.current_media_path != media_path:
            return

        self._queue_media_start(
            media_path,
            tab_index=tab_index,
            announce_message="",
            expect_live=True,
            live_reconnect=True,
        )

    def _cancel_live_reconnect(self, *, reset=True):
        timer = getattr(self, "_live_reconnect_timer", None)
        if timer is not None:
            try:
                timer.Stop()
            except Exception:
                pass
            self._live_reconnect_timer = None
        if reset:
            self._live_reconnect_attempts = 0

    def _handle_live_finished(self, message=None):
        """Stop treating the media as playing once the live cannot continue."""
        self._cancel_live_reconnect()
        message = message or _("A transmissão ao vivo terminou.")
        state = self._get_active_playlist_state()
        if state is not None:
            state.was_playing = False
        if hasattr(self, "_set_status_message"):
            self._set_status_message(message, auto_clear_ms=0)
        self._announce(message)
        self._update_time_bar()
        self._refresh_playlist_browser()
