import math
import threading
import time

import wx

from ...constants import CROSSFADE_TIMER_INTERVAL_MS, SHORT_FADE_MS, SHORT_FADE_STEPS
from ...library import is_audio_playback_media
from .helpers import is_youtube_music_media


class CrossfadeMixin:
    def _ensure_crossfade_timer_running(self):
        """Start the high-frequency crossfade timer only while a crossfade is
        active.

        The 15 ms timer drives the pending->running transition and the smooth
        volume ramp. Keeping it stopped while idle avoids ~64 needless CPU
        wakeups per second (Windows timer resolution), which let the machine
        idle properly and saves battery. End-of-track detection does NOT rely
        on this timer — it is event-driven via MPV's ``eof-reached`` observer.
        """
        timer = getattr(self, "crossfade_timer", None)
        if timer is not None and not timer.IsRunning():
            timer.Start(CROSSFADE_TIMER_INTERVAL_MS)

    def _stop_crossfade_timer(self):
        timer = getattr(self, "crossfade_timer", None)
        if timer is not None and timer.IsRunning():
            timer.Stop()

    def _crossfade_duration_ms(self):
        crossfade_seconds = int(getattr(self.settings, "crossfade_seconds", 0) or 0)
        return max(0, crossfade_seconds * 1000)

    def _crossfade_startup_headroom_ms(self):
        duration_ms = self._crossfade_duration_ms()
        if duration_ms <= 0:
            return 0

        return max(300, min(1200, duration_ms // 2))

    def _crossfade_pending_timeout_seconds(self, media_path=None, *, outgoing_ended=False):
        if is_youtube_music_media(media_path):
            return 20.0 if outgoing_ended else 15.0

        return 5.0

    def _can_crossfade_to_media(self, media_path):
        if self._crossfade_duration_ms() <= 0 or self._crossfade_state is not None:
            return False

        current_media_path = self._player_loaded_media_path()
        if not current_media_path or not media_path:
            return False

        if self._media_paths_match(current_media_path, media_path):
            return False

        if not is_audio_playback_media(current_media_path) or not is_audio_playback_media(media_path):
            return False

        if self._youtube_music_media_requires_prefetched_stream(media_path):
            self._prefetch_media_stream(media_path)

        if self.player.get_media() is None or not self.player.is_playing():
            return False

        media_length = self.player.get_length()
        return media_length is not None and media_length > 0

    def _start_crossfade(self, media_path, *, tab_index, announce_message=None):
        duration_ms = self._crossfade_duration_ms()
        if duration_ms <= 0 or self._crossfade_state is not None:
            return False

        outgoing_key = self._active_player_key
        incoming_key = self._inactive_player_key()
        if not outgoing_key or not incoming_key:
            return False

        self._stop_player(incoming_key, unload=True)
        self._apply_volume_to_player(outgoing_key, self.current_volume)
        request = self._queue_media_start(
            media_path,
            tab_index=tab_index,
            announce_message=announce_message,
            player_key=incoming_key,
            initial_volume=0,
            crossfade=True,
        )
        self._crossfade_state = {
            "phase": "pending",
            "duration_ms": duration_ms,
            "incoming_key": incoming_key,
            "outgoing_key": outgoing_key,
            "request_serial": request["serial"],
            "tab_index": tab_index,
            "media_path": media_path,
            "announce_message": announce_message,
            "created_at": time.monotonic(),
            "started_at": None,
            "outgoing_ended": False,
            "pending_timeout_seconds": self._crossfade_pending_timeout_seconds(media_path),
        }
        self._ensure_crossfade_timer_running()
        return True

    def _cancel_crossfade_transition(
        self,
        *,
        stop_incoming=True,
        stop_outgoing=False,
        invalidate_requests=False,
    ):
        crossfade_state = getattr(self, "_crossfade_state", None)
        if invalidate_requests:
            # Bump the serial unconditionally so that any in-flight playback
            # request (e.g. a YouTube Music stream still being resolved on
            # the worker thread) is treated as stale by `_finish_media_start`
            # and its player is stopped instead of silently starting playback
            # after the user already stopped/closed/unloaded.
            self._next_playback_request_serial()

        if not crossfade_state:
            return

        incoming_key = crossfade_state.get("incoming_key")
        outgoing_key = crossfade_state.get("outgoing_key")
        phase = crossfade_state.get("phase")

        if stop_incoming and incoming_key:
            should_stop_incoming = phase == "pending" or incoming_key != self._active_player_key
            if should_stop_incoming:
                self._stop_player(incoming_key, unload=True)

        if stop_outgoing and outgoing_key:
            self._stop_player(outgoing_key, unload=True)

        self._crossfade_state = None
        self._stop_crossfade_timer()
        self._apply_current_volume()

    def _apply_crossfade_volumes(self):
        crossfade_state = getattr(self, "_crossfade_state", None)
        if not crossfade_state or crossfade_state.get("phase") != "running":
            return False

        started_at = crossfade_state.get("started_at")
        duration_ms = max(1, int(crossfade_state.get("duration_ms") or 0))
        if started_at is None:
            return False

        elapsed_ms = max(0, int(round((time.monotonic() - started_at) * 1000)))
        progress = max(0.0, min(1.0, elapsed_ms / duration_ms))
        incoming_volume = int(round(self.current_volume * math.sin((math.pi / 2.0) * progress)))
        outgoing_volume = int(round(self.current_volume * math.cos((math.pi / 2.0) * progress)))

        if crossfade_state.get("outgoing_ended"):
            outgoing_volume = 0

        self._apply_volume_to_player(crossfade_state["incoming_key"], incoming_volume)
        self._apply_volume_to_player(crossfade_state["outgoing_key"], outgoing_volume)

        if progress >= 1.0:
            self._finish_crossfade()

        return True

    def _finish_crossfade(self):
        crossfade_state = getattr(self, "_crossfade_state", None)
        if not crossfade_state:
            return

        outgoing_key = crossfade_state.get("outgoing_key")
        if outgoing_key:
            self._apply_volume_to_player(outgoing_key, 0)
            self._stop_player(outgoing_key, unload=True)

        self._crossfade_state = None
        self._stop_crossfade_timer()
        self._apply_current_volume()

    def _tick_crossfade(self):
        crossfade_state = getattr(self, "_crossfade_state", None)
        if not crossfade_state:
            # Nothing to drive at high frequency. Idle the timer until the next
            # crossfade is started (the automatic-start check now runs on the
            # slower progress timer). This is also the safety net for any path
            # that clears ``_crossfade_state`` without stopping the timer.
            self._stop_crossfade_timer()
            return

        if crossfade_state.get("phase") == "pending":
            created_at = crossfade_state.get("created_at")
            pending_timeout_seconds = float(
                crossfade_state.get(
                    "pending_timeout_seconds",
                    self._crossfade_pending_timeout_seconds(
                        crossfade_state.get("media_path"),
                        outgoing_ended=bool(crossfade_state.get("outgoing_ended")),
                    ),
                )
            )
            if crossfade_state.get("outgoing_ended"):
                pending_timeout_seconds = max(
                    pending_timeout_seconds,
                    self._crossfade_pending_timeout_seconds(
                        crossfade_state.get("media_path"),
                        outgoing_ended=True,
                    ),
                )
                crossfade_state["pending_timeout_seconds"] = pending_timeout_seconds

            if created_at is not None and (time.monotonic() - created_at) > pending_timeout_seconds:
                if not self._fallback_pending_crossfade_to_regular_playback():
                    self._cancel_crossfade_transition(
                        stop_incoming=True, stop_outgoing=False, invalidate_requests=False,
                    )
                return
            incoming_player = self._managed_player(crossfade_state.get("incoming_key"))
            if incoming_player is not None and incoming_player.is_playing():
                self._begin_pending_crossfade()
            return

        if crossfade_state.get("phase") == "running":
            self._apply_crossfade_volumes()

    def _begin_pending_crossfade(self):
        crossfade_state = getattr(self, "_crossfade_state", None)
        if not crossfade_state or crossfade_state.get("phase") != "pending":
            return False

        tab_index = crossfade_state.get("tab_index")
        media_path = crossfade_state.get("media_path")
        player_key = crossfade_state.get("incoming_key")
        state = self._get_playlist_state(tab_index)
        if not state or state.current_media_path != media_path:
            self._cancel_crossfade_transition(stop_incoming=True, stop_outgoing=False, invalidate_requests=False)
            return False

        incoming_player = self._managed_player(player_key)
        if incoming_player is None:
            self._cancel_crossfade_transition(stop_incoming=True, stop_outgoing=False, invalidate_requests=False)
            return False

        self._apply_equalizer_state_to_player(incoming_player, state)
        self._set_active_player(player_key)
        self._bind_player_to_window()
        self._prepare_youtube_music_history_tracking(media_path)
        self._update_title()
        self._update_time_bar()
        self._refresh_playlist_browser()

        # The incoming track's _finish_media_start returned early (crossfade
        # branch) before applying display metadata / fetching lyrics, so do it
        # here — this is where the incoming media actually becomes the active one.
        resolved_display_title = str(crossfade_state.get("resolved_display_title", "") or "").strip()
        resolved_display_artist = str(crossfade_state.get("resolved_display_artist", "") or "").strip()
        self._apply_media_display_metadata(media_path, resolved_display_title, resolved_display_artist)
        self._refresh_lyrics_for_active_media(resolved_display_title, resolved_display_artist)

        announce_message = crossfade_state.get("announce_message")
        if announce_message is not None:
            if announce_message:
                self._announce(announce_message)
        else:
            self._announce(self._describe_playlist_position(state))

        self._apply_volume_to_player(player_key, 0)

        outgoing_player = self._managed_player(crossfade_state.get("outgoing_key"))
        if crossfade_state.get("outgoing_ended") or outgoing_player is None or not outgoing_player.is_playing():
            crossfade_state["duration_ms"] = 500
        else:
            outgoing_time = outgoing_player.get_time()
            outgoing_length = outgoing_player.get_length()
            if (
                outgoing_time is not None
                and outgoing_time >= 0
                and outgoing_length is not None
                and outgoing_length > 0
            ):
                actual_remaining = max(0, outgoing_length - outgoing_time)
                crossfade_state["duration_ms"] = max(
                    500, min(crossfade_state["duration_ms"], actual_remaining),
                )

        crossfade_state["phase"] = "running"
        crossfade_state["started_at"] = time.monotonic()
        self._apply_crossfade_volumes()
        self._prefetch_upcoming_media_stream(state)
        return True

    def _fallback_pending_crossfade_to_regular_playback(self):
        crossfade_state = getattr(self, "_crossfade_state", None)
        if not crossfade_state or crossfade_state.get("phase") != "pending":
            return False

        tab_index = crossfade_state.get("tab_index")
        media_path = crossfade_state.get("media_path")
        announce_message = crossfade_state.get("announce_message")
        state = self._get_playlist_state(tab_index)
        if not state or state.current_media_path != media_path:
            return False

        self._cancel_crossfade_transition(
            stop_incoming=True,
            stop_outgoing=False,
            invalidate_requests=True,
        )
        self._queue_media_start(
            media_path,
            tab_index=tab_index,
            announce_message=announce_message,
        )
        return True

    def _handle_playback_timer_tick(self):
        self._tick_crossfade()

    def _perform_short_fade_out(self, player_key, on_complete):
        """Quick fade-out on `player_key` then run `on_complete()` on the UI thread.

        Used by pause/stop to soften the audio cut. Falls back to running
        `on_complete` immediately when the player is missing or already silent.
        """

        def finish():
            if on_complete is not None:
                on_complete()

        player = self._managed_player(player_key)
        if player is None:
            finish()
            return

        try:
            start_volume = max(0, min(100, int(self.current_volume)))
        except (TypeError, ValueError):
            start_volume = 0

        if start_volume <= 0 or not player.is_playing():
            finish()
            return

        steps = max(1, int(SHORT_FADE_STEPS))
        step_delay_seconds = max(0.001, (SHORT_FADE_MS / 1000.0) / steps)

        def worker():
            for step in range(1, steps + 1):
                fade_volume = int(round(start_volume * (1.0 - step / steps)))
                self._apply_volume_to_player(player_key, fade_volume)
                if step < steps:
                    time.sleep(step_delay_seconds)
            wx.CallAfter(finish)

        threading.Thread(target=worker, daemon=True).start()
