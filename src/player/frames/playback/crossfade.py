import contextlib
import math
import threading
import time

import wx

from ...autodj import TransitionProfile, mix_values
from ...constants import CROSSFADE_TIMER_INTERVAL_MS, SHORT_FADE_MS, SHORT_FADE_STEPS
from ...library import is_audio_playback_media
from ...log import get_logger
from .helpers import is_youtube_music_media
from .monitor import monitoring_enabled, playback_output_volume, track_output_volume
from ...announcements import ANNOUNCE_TRACK_CHANGE


_logger = get_logger(__name__)

# Passo normal do temporizador do crossfade é ~15 ms; acima disto a rampa de
# volume dá "degraus" que podem soar como falha no áudio.
_CROSSFADE_TICK_LAG_WARN_S = 0.15

# Letra e busca da faixa seguinte esperam este tempo depois do início da transição.
_CROSSFADE_DEFERRED_WORK_MS = 2500
# Quando registrar o estado dos players depois do início da transição.
_CROSSFADE_SAMPLE_DELAYS_MS = (150, 500, 1000, 2000)


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

    @staticmethod
    def _autodj_preload_lead_ms(media_path):
        return 3000 if is_youtube_music_media(media_path) else 1200

    def _crossfade_pending_timeout_seconds(self, media_path=None, *, outgoing_ended=False):
        if is_youtube_music_media(media_path):
            return 20.0 if outgoing_ended else 15.0

        return 5.0

    def _can_crossfade_to_media(self, media_path, *, duration_override_ms=None):
        duration_ms = self._crossfade_duration_ms() if duration_override_ms is None else int(duration_override_ms or 0)
        if duration_ms <= 0 or self._crossfade_state is not None:
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

    def _start_crossfade(self, media_path, *, tab_index, announce_message=None, autodj_transition=None):
        duration_ms = (
            self._autodj_transition_duration_ms(autodj_transition)
            if autodj_transition is not None
            else self._crossfade_duration_ms()
        )
        if duration_ms <= 0 or self._crossfade_state is not None:
            return False

        autodj_plan = autodj_transition.get("plan") if autodj_transition is not None else None

        outgoing_key = self._active_player_key
        incoming_key = self._inactive_player_key()
        if not outgoing_key or not incoming_key:
            return False

        discard_preload = getattr(self, "_discard_preload", None)
        take_preloaded = getattr(self, "_take_preloaded_incoming", None)
        if autodj_transition is not None:
            if callable(discard_preload):
                discard_preload("AutoDJ")
            preloaded = None
        else:
            preloaded = take_preloaded(media_path, tab_index, incoming_key) if callable(take_preloaded) else None
        if preloaded is None:
            self._stop_player(incoming_key, unload=True)
        outgoing_gain_db = float(getattr(self, "_current_track_gain_db", 0.0) or 0.0)
        self._apply_volume_to_player(
            outgoing_key,
            playback_output_volume(self) * math.pow(10.0, outgoing_gain_db / 20.0),
        )
        if preloaded is None:
            request = self._queue_media_start(
                media_path,
                tab_index=tab_index,
                announce_message=announce_message,
                player_key=incoming_key,
                initial_volume=0,
                crossfade=True,
                start_position_ms=getattr(autodj_plan, "incoming_start_ms", 0) or 0,
                pause_after_start=autodj_transition is not None,
            )
        else:
            request = {"serial": preloaded["serial"]}
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
            "autodj": autodj_transition is not None,
            "autodj_profile": (
                autodj_transition.get("profile", TransitionProfile.SMOOTH.value)
                if autodj_transition is not None
                else None
            ),
            "autodj_filter_step": None,
            "tempo_ratio": float(getattr(autodj_plan, "tempo_ratio", 1.0) or 1.0),
            "incoming_beat_ms": float(getattr(autodj_plan, "incoming_beat_ms", 0.0) or 0.0),
            "incoming_start_ms": getattr(autodj_plan, "incoming_start_ms", None),
            "scheduled_outgoing_start_ms": getattr(autodj_plan, "outgoing_start_ms", None),
            "scheduled_outgoing_end_ms": getattr(autodj_plan, "outgoing_end_ms", None),
            "incoming_ready": preloaded is not None,
            "preloaded": preloaded is not None,
            "resolved_display_title": preloaded["resolved_display_title"] if preloaded is not None else "",
            "resolved_display_artist": preloaded["resolved_display_artist"] if preloaded is not None else "",
            "next_phase_correction_at": 0.0,
            "phase_rate": None,
            "outgoing_gain_db": outgoing_gain_db,
            "incoming_gain_db": float(getattr(autodj_plan, "incoming_gain_db", 0.0) or 0.0),
        }
        self._ensure_crossfade_timer_running()
        try:
            self._log_crossfade_start(
                outgoing_key, media_path, duration_ms, autodj_transition is not None, preloaded is not None
            )
        except Exception:
            _logger.debug("Crossfade start diagnostics failed.", exc_info=True)
        return True

    def _log_crossfade_start(self, outgoing_key, media_path, duration_ms, autodj, preloaded=False):
        outgoing_player = self._managed_player(outgoing_key)
        outgoing_time = outgoing_player.get_time() if outgoing_player is not None else None
        outgoing_length = outgoing_player.get_length() if outgoing_player is not None else None
        _logger.debug(
            "Crossfade start: duration=%sms outgoing=%r at %sms of %sms (remaining %sms) "
            "incoming=%r autodj=%s stream=%s preloaded=%s outgoing: %s",
            duration_ms,
            outgoing_key,
            outgoing_time,
            outgoing_length,
            (outgoing_length - outgoing_time) if outgoing_time is not None and outgoing_length else None,
            media_path,
            autodj,
            is_youtube_music_media(media_path),
            preloaded,
            ", ".join(f"{name}={value}" for name, value in self._player_diagnostics(outgoing_key).items()),
        )

    def _cancel_crossfade_transition(
        self,
        *,
        stop_incoming=True,
        stop_outgoing=False,
        invalidate_requests=False,
        restore_selection=False,
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
        _logger.debug(
            "Crossfade cancelled in phase %r (stop_incoming=%s stop_outgoing=%s outgoing_ended=%s).",
            phase,
            stop_incoming,
            stop_outgoing,
            crossfade_state.get("outgoing_ended"),
        )

        if restore_selection and phase == "pending":
            state = self._get_playlist_state(crossfade_state.get("tab_index"))
            snapshot = crossfade_state.get("playlist_before_transition")
            if state is not None and snapshot and state.current_media_path == crossfade_state.get("media_path"):
                for name, value in snapshot.items():
                    setattr(state, name, value)
                self._update_title()
                self._refresh_playlist_browser()

        if stop_incoming and incoming_key:
            should_stop_incoming = phase == "pending" or incoming_key != self._active_player_key
            if should_stop_incoming:
                self._stop_player(incoming_key, unload=True)

        if stop_outgoing and outgoing_key:
            self._stop_player(outgoing_key, unload=True)

        self._restore_autodj_mix_filters(crossfade_state)
        self._crossfade_state = None
        self._stop_crossfade_timer()
        self._apply_current_volume()
        self._apply_current_playback_rate()

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
        volume = playback_output_volume(self)
        if crossfade_state.get("autodj"):
            outgoing_player = self._managed_player(crossfade_state.get("outgoing_key"))
            outgoing_time = outgoing_player.get_time() if outgoing_player is not None else None
            scheduled_start_ms = crossfade_state.get("scheduled_outgoing_start_ms")
            scheduled_end_ms = crossfade_state.get("scheduled_outgoing_end_ms")
            if (
                outgoing_time is not None
                and scheduled_start_ms is not None
                and scheduled_end_ms is not None
                and scheduled_end_ms > scheduled_start_ms
            ):
                progress = max(
                    0.0,
                    min(1.0, (outgoing_time - scheduled_start_ms) / (scheduled_end_ms - scheduled_start_ms)),
                )
            values = mix_values(
                progress,
                crossfade_state.get("autodj_profile") or TransitionProfile.SMOOTH,
            )
            incoming_volume = int(round(volume * values.incoming_volume))
            outgoing_volume = int(round(volume * values.outgoing_volume))
            self._apply_autodj_mix_filters(crossfade_state, progress, values)
            self._correct_autodj_phase(crossfade_state, outgoing_time)
        else:
            incoming_volume = int(round(volume * math.sin((math.pi / 2.0) * progress)))
            outgoing_volume = int(round(volume * math.cos((math.pi / 2.0) * progress)))
        incoming_gain_db = float(crossfade_state.get("incoming_gain_db", 0.0) or 0.0)
        if crossfade_state.get("autodj"):
            # Loudness matching only protects the overlap. Restore the incoming
            # track to its original level during the second half of the mix.
            recovery_progress = max(0.0, min(1.0, (progress - 0.5) * 2.0))
            gain_recovery = recovery_progress * recovery_progress * (3.0 - (2.0 * recovery_progress))
            incoming_gain_db *= 1.0 - gain_recovery
        outgoing_gain_db = float(crossfade_state.get("outgoing_gain_db", 0.0) or 0.0)
        incoming_volume = int(round(incoming_volume * math.pow(10.0, incoming_gain_db / 20.0)))
        outgoing_volume = int(round(outgoing_volume * math.pow(10.0, outgoing_gain_db / 20.0)))

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
        started_at = crossfade_state.get("started_at")
        _logger.debug(
            "Crossfade finished: ran %sms (planned %sms).",
            int((time.monotonic() - started_at) * 1000) if started_at is not None else None,
            crossfade_state.get("duration_ms"),
        )
        if outgoing_key:
            self._apply_volume_to_player(outgoing_key, 0)
            self._stop_player(outgoing_key, unload=True)

        self._restore_autodj_mix_filters(crossfade_state)
        self._current_track_gain_db = 0.0
        state = self._get_active_playlist_state()
        if state is not None:
            state.playback_gain_db = self._current_track_gain_db
        self._crossfade_state = None
        self._stop_crossfade_timer()
        self._apply_current_volume()
        self._apply_current_playback_rate()

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
                _logger.warning(
                    "Crossfade: incoming %r not playing after %.1fs (outgoing_ended=%s); falling back.",
                    crossfade_state.get("media_path"),
                    time.monotonic() - created_at,
                    crossfade_state.get("outgoing_ended"),
                )
                if not self._fallback_pending_crossfade_to_regular_playback():
                    self._cancel_crossfade_transition(
                        stop_incoming=True, stop_outgoing=False, invalidate_requests=False,
                    )
                return
            incoming_player = self._managed_player(crossfade_state.get("incoming_key"))
            if crossfade_state.get("preloaded"):
                # A faixa já está carregada e parada: só falta dar o play.
                if incoming_player is not None:
                    if crossfade_state.get("play_requested_at") is None:
                        crossfade_state["play_requested_at"] = time.monotonic()
                    incoming_player.play()
                    if incoming_player.is_playing():
                        self._begin_pending_crossfade()
                return
            if crossfade_state.get("autodj"):
                if not self._autodj_transition_due(crossfade_state):
                    return
                if incoming_player is not None and crossfade_state.get("incoming_ready"):
                    incoming_player.play()
                    if incoming_player.is_playing():
                        self._begin_pending_crossfade()
                return
            if incoming_player is not None and incoming_player.is_playing():
                self._begin_pending_crossfade()
            return

        if crossfade_state.get("phase") == "running":
            now = time.monotonic()
            last_tick = crossfade_state.get("last_tick_at")
            crossfade_state["last_tick_at"] = now
            if last_tick is not None and now - last_tick > _CROSSFADE_TICK_LAG_WARN_S:
                _logger.warning(
                    "Crossfade: UI thread stalled %.0fms between volume steps (expected ~%sms).",
                    (now - last_tick) * 1000,
                    CROSSFADE_TIMER_INTERVAL_MS,
                )
            self._apply_crossfade_volumes()

    def _autodj_transition_due(self, crossfade_state):
        if not crossfade_state.get("autodj") or crossfade_state.get("outgoing_ended"):
            return True
        scheduled_start_ms = crossfade_state.get("scheduled_outgoing_start_ms")
        outgoing_player = self._managed_player(crossfade_state.get("outgoing_key"))
        if scheduled_start_ms is None or outgoing_player is None:
            return True
        outgoing_time = outgoing_player.get_time()
        return outgoing_time is not None and outgoing_time >= scheduled_start_ms

    def _begin_pending_crossfade(self):
        crossfade_state = getattr(self, "_crossfade_state", None)
        if not crossfade_state or crossfade_state.get("phase") != "pending":
            return False
        if not self._autodj_transition_due(crossfade_state):
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
        if crossfade_state.get("autodj") and not incoming_player.is_playing():
            return False

        begin_started_at = time.monotonic()
        stage_times_ms = {}

        def mark_stage(name, since):
            now = time.monotonic()
            stage_times_ms[name] = int((now - since) * 1000)
            return now

        # Também na faixa pré-carregada: o equalizador pode ter mudado desde
        # que ela ficou pronta.
        self._apply_equalizer_state_to_player(incoming_player, state)
        self._set_active_player(player_key)
        self._current_track_gain_db = 0.0
        state.playback_gain_db = self._current_track_gain_db
        self._bind_player_to_window()
        self._prepare_youtube_music_history_tracking(media_path)
        # Same reason as the YouTube Music tracking above: the incoming track's
        # _finish_media_start took the crossfade branch and returned before
        # arming the smart-library tracking, so arm it here instead.
        self._prepare_smart_library_tracking(media_path)
        remember_radio_playback = getattr(self, "_remember_youtube_music_radio_playback", None)
        if callable(remember_radio_playback):
            remember_radio_playback(media_path)
        stage_started_at = mark_stage("activate", begin_started_at)
        self._update_title()
        self._update_time_bar()
        self._refresh_playlist_browser()
        stage_started_at = mark_stage("ui", stage_started_at)

        # The incoming track's _finish_media_start returned early (crossfade
        # branch) before applying display metadata / fetching lyrics, so do it
        # here — this is where the incoming media actually becomes the active one.
        resolved_display_title = str(crossfade_state.get("resolved_display_title", "") or "").strip()
        resolved_display_artist = str(crossfade_state.get("resolved_display_artist", "") or "").strip()
        self._apply_media_display_metadata(media_path, resolved_display_title, resolved_display_artist)
        # A letra e a resolução da faixa seguinte (rede e CPU) esperam o começo
        # da transição passar: não disputam a saída de áudio no primeiro segundo.
        self._schedule_after_crossfade_start(media_path, state, resolved_display_title, resolved_display_artist)
        stage_started_at = mark_stage("metadata", stage_started_at)

        announce_message = crossfade_state.get("announce_message")
        if announce_message is not None:
            if announce_message:
                self._announce(announce_message, ANNOUNCE_TRACK_CHANGE)
        else:
            self._announce(self._describe_playlist_position(state), ANNOUNCE_TRACK_CHANGE)
        stage_started_at = mark_stage("announce", stage_started_at)

        self._apply_volume_to_player(player_key, 0)
        tempo_ratio = float(crossfade_state.get("tempo_ratio", 1.0) or 1.0)
        self._apply_playback_rate_to_player(
            player_key,
            max(0.25, min(4.0, getattr(self, "current_playback_rate", 1.0) * tempo_ratio)),
        )

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
                scheduled_end_ms = crossfade_state.get("scheduled_outgoing_end_ms")
                actual_remaining = max(
                    0,
                    (scheduled_end_ms - outgoing_time)
                    if scheduled_end_ms is not None
                    else (outgoing_length - outgoing_time),
                )
                crossfade_state["duration_ms"] = max(
                    500, min(crossfade_state["duration_ms"], actual_remaining),
                )

        crossfade_state["phase"] = "running"
        crossfade_state["started_at"] = time.monotonic()
        waited_ms = int((crossfade_state["started_at"] - (crossfade_state.get("created_at") or crossfade_state["started_at"])) * 1000)
        play_requested_at = crossfade_state.get("play_requested_at")
        play_to_playing_ms = (
            int((crossfade_state["started_at"] - play_requested_at) * 1000) if play_requested_at is not None else None
        )
        begin_total_ms = int((crossfade_state["started_at"] - begin_started_at) * 1000)
        log = _logger.warning if crossfade_state.get("outgoing_ended") or begin_total_ms > 100 else _logger.debug
        log(
            "Crossfade running: incoming took %sms to start (play->playing %sms; preloaded=%s); "
            "outgoing_ended=%s; final duration=%sms; UI work %sms %s.",
            waited_ms,
            play_to_playing_ms,
            bool(crossfade_state.get("preloaded")),
            bool(crossfade_state.get("outgoing_ended")),
            crossfade_state.get("duration_ms"),
            begin_total_ms,
            stage_times_ms,
        )
        self._schedule_crossfade_samples(crossfade_state)
        if crossfade_state.get("autodj") and bool(
            getattr(self.settings, "autodj_transition_sounds_enabled", False)
        ):
            self._play_autodj_transition_sound(crossfade_state.get("autodj_profile"))
        self._apply_crossfade_volumes()
        return True

    def _schedule_after_crossfade_start(self, media_path, state, title, artist):
        """Letra e pré-busca da faixa seguinte, um pouco depois do começo da transição."""

        def run():
            try:
                if self._get_active_playlist_state() is not state or state.current_media_path != media_path:
                    return
                self._refresh_lyrics_for_active_media(title, artist)
                self._prefetch_upcoming_media_stream(state)
            except Exception:
                _logger.debug("Deferred post-crossfade work failed.", exc_info=True)

        wx.CallLater(_CROSSFADE_DEFERRED_WORK_MS, run)

    def _schedule_crossfade_samples(self, crossfade_state):
        """Registra o estado dos dois players logo depois do início da transição.

        Mostra se algum ficou parado esperando dados (``core-idle``,
        ``paused-for-cache``), em que saída de áudio cada um está e quanto
        a janela demorou para responder.
        """
        incoming_key = crossfade_state.get("incoming_key")
        outgoing_key = crossfade_state.get("outgoing_key")
        started_at = crossfade_state.get("started_at") or time.monotonic()

        def sample(delay_ms):
            def run():
                try:
                    late_ms = int((time.monotonic() - started_at) * 1000) - delay_ms
                    _logger.debug(
                        "Crossfade sample +%dms (UI late by %dms): outgoing[%s] incoming[%s]",
                        delay_ms,
                        late_ms,
                        ", ".join(f"{k}={v}" for k, v in self._player_diagnostics(outgoing_key).items()),
                        ", ".join(f"{k}={v}" for k, v in self._player_diagnostics(incoming_key).items()),
                    )
                except Exception:
                    _logger.debug("Crossfade sample failed.", exc_info=True)

            wx.CallLater(delay_ms, run)

        for delay_ms in _CROSSFADE_SAMPLE_DELAYS_MS:
            sample(delay_ms)

    def _correct_autodj_phase(self, crossfade_state, outgoing_time):
        if outgoing_time is None or time.monotonic() < float(crossfade_state.get("next_phase_correction_at", 0.0)):
            return
        crossfade_state["next_phase_correction_at"] = time.monotonic() + 0.1
        incoming_player = self._managed_player(crossfade_state.get("incoming_key"))
        get_incoming_time = getattr(incoming_player, "get_time", None)
        if not callable(get_incoming_time):
            return
        incoming_time = get_incoming_time()
        outgoing_start_ms = crossfade_state.get("scheduled_outgoing_start_ms")
        incoming_start_ms = crossfade_state.get("incoming_start_ms")
        beat_ms = float(crossfade_state.get("incoming_beat_ms", 0.0) or 0.0)
        tempo_ratio = float(crossfade_state.get("tempo_ratio", 1.0) or 1.0)
        if incoming_time is None or outgoing_start_ms is None or incoming_start_ms is None or beat_ms <= 0:
            return
        expected_incoming_time = incoming_start_ms + max(0.0, outgoing_time - outgoing_start_ms) * tempo_ratio
        phase_error_ms = expected_incoming_time - incoming_time
        correction = max(-0.012, min(0.012, (phase_error_ms / beat_ms) * 0.04))
        base_rate = max(0.25, min(4.0, getattr(self, "current_playback_rate", 1.0) * tempo_ratio))
        target_rate = max(0.25, min(4.0, base_rate * (1.0 + correction)))
        previous_rate = crossfade_state.get("phase_rate")
        if previous_rate is not None and abs(previous_rate - target_rate) < 0.0005:
            return
        crossfade_state["phase_rate"] = target_rate
        self._apply_playback_rate_to_player(crossfade_state.get("incoming_key"), target_rate)

    def _apply_autodj_mix_filters(self, crossfade_state, progress, values):
        update_filter = getattr(self, "_update_autodj_mix_filter_on_player", None)
        if not callable(update_filter):
            return
        filter_step = min(20, int(progress * 20))
        if crossfade_state.get("autodj_filter_step") == filter_step:
            return
        crossfade_state["autodj_filter_step"] = filter_step
        update_filter(
            self._managed_player(crossfade_state.get("incoming_key")),
            values.incoming_bass_db,
            values.incoming_mid_db,
        )
        update_filter(
            self._managed_player(crossfade_state.get("outgoing_key")),
            values.outgoing_bass_db,
            values.outgoing_mid_db,
        )

    def _restore_autodj_mix_filters(self, crossfade_state):
        if not crossfade_state or not crossfade_state.get("autodj"):
            return
        update_filter = getattr(self, "_update_autodj_mix_filter_on_player", None)
        if not callable(update_filter):
            return
        for player_key in (crossfade_state.get("incoming_key"), crossfade_state.get("outgoing_key")):
            player = self._managed_player(player_key)
            if player is not None:
                update_filter(player, 0.0, 0.0)

    def _fallback_pending_crossfade_to_regular_playback(self):
        crossfade_state = getattr(self, "_crossfade_state", None)
        if not crossfade_state or crossfade_state.get("phase") != "pending":
            return False

        tab_index = crossfade_state.get("tab_index")
        media_path = crossfade_state.get("media_path")
        announce_message = crossfade_state.get("announce_message")
        # _cancel_crossfade_transition(invalidate_requests=True) below clears
        # self._crossfade_state, so grab the pre-transition snapshot first —
        # otherwise a failure on this retry would have no way to restore a
        # queued pick/AutoDJ hand-off already consumed by the original advance.
        revert_snapshot = crossfade_state.get("playlist_before_transition")
        state = self._get_playlist_state(tab_index)
        if not state or state.current_media_path != media_path:
            return False

        self._cancel_crossfade_transition(
            stop_incoming=True,
            stop_outgoing=False,
            invalidate_requests=True,
        )
        state.playback_gain_db = 0.0
        self._queue_media_start(
            media_path,
            tab_index=tab_index,
            announce_message=announce_message,
            revert_snapshot=revert_snapshot,
        )
        return True

    def _handle_playback_timer_tick(self):
        self._tick_crossfade()

    def _perform_short_fade_out(self, player_key, on_complete):
        """Quick fade-out on `player_key` then run `on_complete()` on the UI thread.

        Used by pause/stop to soften the audio cut. Falls back to running
        `on_complete` immediately when the player is missing or already silent.
        """

        request_serial = getattr(self, "_playback_request_serial", None)
        player = self._managed_player(player_key)
        media = player.get_media() if player is not None else None

        def is_current():
            return (
                request_serial == getattr(self, "_playback_request_serial", None)
                and player is self._managed_player(player_key)
                and (player is None or player.get_media() is media)
            )

        def finish():
            lock = getattr(self, "_playback_backend_lock", None)
            with lock if lock is not None else contextlib.nullcontext():
                if is_current() and on_complete is not None:
                    on_complete()

        if player is None:
            finish()
            return

        monitored = monitoring_enabled(getattr(self, "settings", None))
        try:
            start_level = track_output_volume(self) if monitored else self.current_volume
            start_volume = max(0, min(100, int(start_level)))
        except (TypeError, ValueError):
            start_volume = 0

        if start_volume <= 0 or not player.is_playing():
            finish()
            return

        steps = max(1, int(SHORT_FADE_STEPS))
        step_delay_seconds = max(0.001, (SHORT_FADE_MS / 1000.0) / steps)

        def worker():
            for step in range(1, steps + 1):
                lock = getattr(self, "_playback_backend_lock", None)
                with lock if lock is not None else contextlib.nullcontext():
                    if not is_current():
                        return
                    volume = start_volume
                    if monitored or monitoring_enabled(getattr(self, "settings", None)):
                        volume = max(0, min(100, track_output_volume(self)))
                    fade_volume = int(round(volume * (1.0 - step / steps)))
                    self._apply_volume_to_player(player_key, fade_volume)
                if step < steps:
                    time.sleep(step_delay_seconds)
            wx.CallAfter(finish)

        threading.Thread(target=worker, daemon=True).start()
