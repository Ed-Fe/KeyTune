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
        # An active Auto DJ plan drives the blend length (a whole number of
        # beats of the outgoing track), overriding the user's fixed crossfade
        # setting — and making the crossfade engage even when that setting is 0.
        plan = getattr(self, "_auto_dj_pending_plan", None)
        if plan and plan.get("duration_ms"):
            return int(plan["duration_ms"])
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
        # Auto DJ may request a cue-in position (the incoming track's first
        # beat) so the blend starts on a beat rather than on the intro/silence.
        auto_dj_start_ms = 0
        auto_dj_start_getter = getattr(self, "_auto_dj_incoming_start_ms", None)
        if callable(auto_dj_start_getter):
            auto_dj_start_ms = auto_dj_start_getter()
        # Phase-lock: when active, the incoming track is loaded paused at its cue
        # point and unpaused later, exactly on a beat of the outgoing track.
        phase_lock = False
        phase_lock_getter = getattr(self, "_auto_dj_phase_lock_active", None)
        if callable(phase_lock_getter):
            phase_lock = bool(phase_lock_getter())
        # Bass swap: attach the labeled bass filters up front — the incoming
        # enters with its low band cut, the outgoing gets a transparent (0 dB)
        # node — so mid-blend gain changes are in-place af-commands instead of
        # chain rebuilds (which glitch the audio).
        bass_swap = False
        bass_swap_getter = getattr(self, "_auto_dj_bass_swap_active", None)
        if callable(bass_swap_getter):
            bass_swap = bool(bass_swap_getter())
        if bass_swap:
            attach_bass = getattr(self, "_auto_dj_attach_bass_filter", None)
            gains_getter = getattr(self, "_auto_dj_bass_swap_gains", None)
            if callable(attach_bass) and callable(gains_getter):
                incoming_bass_db, outgoing_bass_db = gains_getter(0.0)
                attach_bass(incoming_key, incoming_bass_db)
                attach_bass(outgoing_key, outgoing_bass_db)
            else:
                bass_swap = False
        request = self._queue_media_start(
            media_path,
            tab_index=tab_index,
            announce_message=announce_message,
            player_key=incoming_key,
            initial_volume=0,
            crossfade=True,
            start_position_ms=auto_dj_start_ms,
            pause_incoming=phase_lock,
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
            "phase_lock": phase_lock,
            "armed_target_ms": None,
            "armed_at": None,
            "bass_swap": bass_swap,
            "bass_last_incoming_db": None,
            "bass_last_outgoing_db": None,
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
        self._auto_dj_pending_plan = None
        clear_bass_filters = getattr(self, "_auto_dj_clear_bass_filters", None)
        if callable(clear_bass_filters):
            clear_bass_filters()
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

        if crossfade_state.get("bass_swap"):
            self._apply_bass_swap_gains(crossfade_state, progress)

        if progress >= 1.0:
            self._finish_crossfade()

        return True

    def _apply_bass_swap_gains(self, crossfade_state, progress):
        """Drive the low-band handover during a running Auto DJ blend.

        Gain changes go through ``af-command`` (no chain rebuild) and are only
        pushed when they moved audibly (>= 0.5 dB) since the last push, so the
        15 ms timer does not spam the players.
        """

        gains_getter = getattr(self, "_auto_dj_bass_swap_gains", None)
        gain_setter = getattr(self, "_auto_dj_set_bass_gain", None)
        if not callable(gains_getter) or not callable(gain_setter):
            return

        incoming_db, outgoing_db = gains_getter(progress)

        last_incoming_db = crossfade_state.get("bass_last_incoming_db")
        if last_incoming_db is None or abs(incoming_db - last_incoming_db) >= 0.5:
            gain_setter(crossfade_state.get("incoming_key"), incoming_db)
            crossfade_state["bass_last_incoming_db"] = incoming_db

        last_outgoing_db = crossfade_state.get("bass_last_outgoing_db")
        if last_outgoing_db is None or abs(outgoing_db - last_outgoing_db) >= 0.5:
            gain_setter(crossfade_state.get("outgoing_key"), outgoing_db)
            crossfade_state["bass_last_outgoing_db"] = outgoing_db

    def _finish_crossfade(self):
        crossfade_state = getattr(self, "_crossfade_state", None)
        if not crossfade_state:
            return

        outgoing_key = crossfade_state.get("outgoing_key")
        if outgoing_key:
            self._apply_volume_to_player(outgoing_key, 0)
            self._stop_player(outgoing_key, unload=True)

        self._crossfade_state = None
        # The incoming (now active) track keeps the Auto DJ tempo-match rate that
        # was applied to it; only the plan bookkeeping is cleared here.
        self._auto_dj_pending_plan = None
        clear_bass_filters = getattr(self, "_auto_dj_clear_bass_filters", None)
        if callable(clear_bass_filters):
            clear_bass_filters()
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
            if crossfade_state.get("phase_lock"):
                # The incoming track is loaded paused at its cue point. Once it
                # is ready, arm the transition (compute the outgoing beat to
                # unpause on) instead of starting the blend immediately.
                if self._crossfade_incoming_ready_paused(incoming_player):
                    self._arm_phase_lock_crossfade()
                return
            if incoming_player is not None and incoming_player.is_playing():
                self._begin_pending_crossfade()
            return

        if crossfade_state.get("phase") == "armed":
            self._tick_phase_lock_armed()
            return

        if crossfade_state.get("phase") == "running":
            self._apply_crossfade_volumes()

    def _crossfade_incoming_ready_paused(self, player):
        """Readiness signal for a paused, cued incoming track: the file has
        loaded (so its duration is known and the cue seek has been applied)."""

        if player is None:
            return False
        try:
            length = player.get_length()
        except Exception:
            return False
        return length is not None and length > 0

    def _arm_phase_lock_crossfade(self):
        crossfade_state = getattr(self, "_crossfade_state", None)
        if not crossfade_state or crossfade_state.get("phase") != "pending":
            return

        outgoing_player = self._managed_player(crossfade_state.get("outgoing_key"))
        if outgoing_player is None or not outgoing_player.is_playing():
            # No outgoing beat grid to lock onto — just start the blend now.
            self._begin_pending_crossfade()
            return

        outgoing_time_ms = outgoing_player.get_time()
        target_ms = None
        target_getter = getattr(self, "_auto_dj_next_beat_target_ms", None)
        if callable(target_getter) and outgoing_time_ms is not None and outgoing_time_ms >= 0:
            target_ms = target_getter(outgoing_time_ms)

        if target_ms is None:
            # Past the last analyzed beat (near the track's end); fire now.
            self._begin_pending_crossfade()
            return

        crossfade_state["armed_target_ms"] = target_ms
        crossfade_state["armed_at"] = time.monotonic()
        crossfade_state["phase"] = "armed"

    def _tick_phase_lock_armed(self):
        crossfade_state = getattr(self, "_crossfade_state", None)
        if not crossfade_state or crossfade_state.get("phase") != "armed":
            return

        outgoing_player = self._managed_player(crossfade_state.get("outgoing_key"))
        if (
            outgoing_player is None
            or not outgoing_player.is_playing()
            or crossfade_state.get("outgoing_ended")
        ):
            self._begin_pending_crossfade()
            return

        # Safety net: never stay armed for more than ~2 s (e.g. if the user
        # seeked the outgoing track past the target beat).
        armed_at = crossfade_state.get("armed_at")
        if armed_at is not None and (time.monotonic() - armed_at) > 2.0:
            self._begin_pending_crossfade()
            return

        outgoing_time_ms = outgoing_player.get_time()
        if outgoing_time_ms is None or outgoing_time_ms < 0:
            return

        target_ms = crossfade_state.get("armed_target_ms")
        if target_ms is None or outgoing_time_ms >= target_ms:
            self._begin_pending_crossfade()

    def _begin_pending_crossfade(self):
        crossfade_state = getattr(self, "_crossfade_state", None)
        if not crossfade_state or crossfade_state.get("phase") not in ("pending", "armed"):
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

        if crossfade_state.get("phase_lock"):
            # Unpause the pre-loaded, cued incoming track at this exact instant
            # (we are on a beat of the outgoing track) so their beats align.
            try:
                incoming_player.play()
            except Exception:
                pass

        self._apply_equalizer_state_to_player(incoming_player, state)
        self._set_active_player(player_key)
        self._bind_player_to_window()
        self._prepare_youtube_music_history_tracking(media_path)
        self._update_title()
        self._update_time_bar()
        self._refresh_playlist_browser()

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
                # An Auto DJ plan ends the blend at the outgoing track's energy
                # cue-out (its outro), not at the end of the file — the produced
                # fade-out past that point is cut off entirely.
                outgoing_end = outgoing_length
                end_getter = getattr(self, "_auto_dj_outgoing_end_ms", None)
                if callable(end_getter):
                    plan_end_ms = end_getter()
                    if plan_end_ms:
                        outgoing_end = min(outgoing_end, plan_end_ms)
                actual_remaining = max(0, outgoing_end - outgoing_time)
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
