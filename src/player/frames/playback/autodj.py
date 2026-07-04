"""Auto DJ mixin — beat/tempo-aware automatic mixing on top of the existing
dual-player crossfade.

Design notes
------------
- The heavy lifting (BPM + beat grid) is done offline by
  :mod:`player.autodj.analysis` on a background thread and cached to disk.
- We do NOT re-invent the crossfade: once a transition is due we stash a small
  *plan* (blend duration + incoming playback rate) in ``_auto_dj_pending_plan``
  and reuse ``_play_media(..., allow_crossfade=True)``. The crossfade code reads
  the plan through ``_crossfade_duration_ms`` (duration) and
  ``_auto_dj_incoming_playback_rate`` (tempo match).
- Everything is gated on ``auto_dj_enabled`` (default off). When off, or when
  librosa is missing, behavior is exactly as before.

What a transition does today: the incoming track is cued at its energy cue-in
(skipping the intro), loaded paused and unpaused exactly on a beat of the
outgoing track (phase lock); the blend ends at the outgoing track's energy
cue-out, cutting its produced fade-out; and during the blend the low band is
handed over from the outgoing to the incoming track (bass swap), so the two
basslines never stack.
"""

from __future__ import annotations

import os
import threading

import wx

from ...autodj import analysis as autodj_analysis
from ...autodj import planner
from ...constants import REPEAT_ALL, REPEAT_ONE
from ...i18n import _
from ...library import is_audio_playback_media
from ...log import get_logger

_logger = get_logger(__name__)

# Extra lead time before the track ends: enough to load the incoming (paused),
# arm the phase-lock, and wait up to one beat of the outgoing track to unpause.
_AUTO_DJ_HEADROOM_MS = 2000

# Label of the per-player low-shelf filter used by the bass swap; addressed at
# runtime via mpv's ``af-command`` so gain changes do not rebuild the chain.
_AUTO_DJ_BASS_FILTER_LABEL = "ktautodjbass"
_AUTO_DJ_BASS_FREQUENCY_HZ = 200


class AutoDjMixin:
    # ------------------------------------------------------------------ state
    def _initialize_auto_dj_state(self):
        self.auto_dj_enabled = False
        self._auto_dj_pending_plan = None
        self._auto_dj_analysis_cache = {}
        self._auto_dj_pending_analysis = set()
        # player_key -> current bass-swap gain (dB) for players whose filter
        # chain currently carries the labeled bass filter.
        self._auto_dj_bass_filter_gains = {}

    # ------------------------------------------------------------------ toggle
    def toggle_auto_dj(self):
        if not getattr(self, "auto_dj_enabled", False):
            if not autodj_analysis.is_available():
                self._announce(
                    _(
                        "Auto DJ indisponível: instale a biblioteca de análise com "
                        "'pip install librosa' para detectar o BPM das faixas."
                    )
                )
                return
            self.auto_dj_enabled = True
            self._auto_dj_prime_analysis()
            self._announce(
                _("Auto DJ ativado. As faixas serão analisadas e mixadas casando o BPM.")
            )
        else:
            self.auto_dj_enabled = False
            self._auto_dj_pending_plan = None
            self._announce(_("Auto DJ desativado."))
        self._refresh_auto_dj_menu_state()

    def _refresh_auto_dj_menu_state(self):
        menu_id = getattr(self, "menu_toggle_auto_dj_id", None)
        menu_bar = self.GetMenuBar() if hasattr(self, "GetMenuBar") else None
        if menu_id is None or menu_bar is None:
            return
        try:
            menu_bar.Check(menu_id, bool(getattr(self, "auto_dj_enabled", False)))
        except Exception:
            pass

    # ------------------------------------------------------------- analysis
    def _auto_dj_is_analyzable(self, path):
        """Only local audio files on disk can be analyzed by librosa."""

        if not path or not is_audio_playback_media(path):
            return False
        try:
            return os.path.isfile(path)
        except OSError:
            return False

    def _auto_dj_get_analysis(self, path):
        """Return the cached :class:`TrackAnalysis` for ``path``, scheduling a
        background analysis when it is not ready yet (returns ``None`` then)."""

        cache = getattr(self, "_auto_dj_analysis_cache", None)
        if cache is None:
            return None
        if path in cache:
            return cache[path]

        pending = self._auto_dj_pending_analysis
        if path in pending:
            return None
        pending.add(path)

        def worker():
            result = autodj_analysis.analyze_track(path)
            wx.CallAfter(self._auto_dj_store_analysis, path, result)

        threading.Thread(target=worker, daemon=True).start()
        return None

    def _auto_dj_store_analysis(self, path, result):
        self._auto_dj_pending_analysis.discard(path)
        if result is not None:
            self._auto_dj_analysis_cache[path] = result

    def _auto_dj_prime_analysis(self):
        """Kick off analysis of the current and next tracks up front so the
        first transition after enabling Auto DJ is ready in time."""

        state = self._get_playlist_state()
        if not state or state.is_folder_tab:
            return
        current_path = state.current_media_path
        if self._auto_dj_is_analyzable(current_path):
            self._auto_dj_get_analysis(current_path)
        try:
            next_path = state.peek_in_playback_order(1, wrap=state.repeat_mode == REPEAT_ALL)
        except Exception:
            next_path = None
        if next_path and self._auto_dj_is_analyzable(next_path):
            self._auto_dj_get_analysis(next_path)

    # ---------------------------------------------------- plan / crossfade hooks
    def _auto_dj_incoming_playback_rate(self, default_rate):
        """Playback rate to apply to the *incoming* crossfade player.

        Used by the playback engine when it loads the incoming track during a
        crossfade: with an active plan this is the tempo-match rate, otherwise
        the caller's default (the user's global speed).
        """

        plan = getattr(self, "_auto_dj_pending_plan", None)
        if plan and plan.get("incoming_rate"):
            return float(plan["incoming_rate"])
        return default_rate

    def _auto_dj_incoming_start_ms(self):
        """Cue-in position (ms) for the incoming crossfade track: its energy
        cue point, so the blend overlaps the groove instead of the intro."""

        plan = getattr(self, "_auto_dj_pending_plan", None)
        if plan and plan.get("incoming_start_ms"):
            return int(plan["incoming_start_ms"])
        return 0

    def _auto_dj_phase_lock_active(self):
        """Whether the current transition should phase-lock (load the incoming
        paused and unpause it on a beat of the outgoing track)."""

        plan = getattr(self, "_auto_dj_pending_plan", None)
        return bool(plan and plan.get("phase_lock"))

    def _auto_dj_bass_swap_active(self):
        """Whether the current transition should hand the low band over from
        the outgoing to the incoming track (bass swap)."""

        plan = getattr(self, "_auto_dj_pending_plan", None)
        return bool(plan and plan.get("bass_swap"))

    def _auto_dj_outgoing_end_ms(self):
        """Media-time (ms) where the blend must end on the outgoing track (its
        energy cue-out), or ``None`` to run until the end of the file."""

        plan = getattr(self, "_auto_dj_pending_plan", None)
        if plan and plan.get("outgoing_end_ms"):
            return int(plan["outgoing_end_ms"])
        return None

    def _auto_dj_bass_swap_gains(self, progress):
        """``(incoming_gain_db, outgoing_gain_db)`` for blend ``progress``."""

        return planner.bass_swap_gains(progress)

    # ---------------------------------------------------------- bass filter
    def _auto_dj_player_key_for(self, player):
        if player is None:
            return None
        for player_key in getattr(self, "_player_keys", ()):
            if self._managed_player(player_key) is player:
                return player_key
        return None

    def _auto_dj_bass_filter_segment_for_player(self, player):
        """Labeled ``af`` segment for ``player``'s bass-swap filter, or ``""``.

        Consumed by ``_apply_audio_filter_chain_to_player`` so the filter is
        preserved whenever the equalizer/pitch chain is (re)built for a player
        taking part in a transition.
        """

        gains = getattr(self, "_auto_dj_bass_filter_gains", None)
        if not gains:
            return ""
        player_key = self._auto_dj_player_key_for(player)
        if player_key not in gains:
            return ""
        return (
            f"@{_AUTO_DJ_BASS_FILTER_LABEL}:lavfi=[bass="
            f"g={float(gains[player_key]):.1f}:f={_AUTO_DJ_BASS_FREQUENCY_HZ}:w=0.5]"
        )

    def _auto_dj_attach_bass_filter(self, player_key, gain_db):
        """Insert the bass filter into ``player_key``'s chain at ``gain_db``.

        Rebuilds the chain once (via the equalizer path, which folds in every
        active segment); later gain changes go through ``af-command`` only.
        """

        if player_key is None:
            return
        self._auto_dj_bass_filter_gains[player_key] = float(gain_db)
        player = self._managed_player(player_key)
        if player is not None:
            self._apply_equalizer_state_to_player(player)

    def _auto_dj_set_bass_gain(self, player_key, gain_db):
        gains = getattr(self, "_auto_dj_bass_filter_gains", None)
        if gains is None or player_key not in gains:
            return
        normalized_gain_db = float(gain_db)
        gains[player_key] = normalized_gain_db
        player = self._managed_player(player_key)
        if player is not None and hasattr(player, "audio_filter_command"):
            player.audio_filter_command(
                _AUTO_DJ_BASS_FILTER_LABEL, "gain", f"{normalized_gain_db:.1f}", "bass"
            )

    def _auto_dj_clear_bass_filters(self):
        """Drop all bass-swap filters (transition finished or cancelled)."""

        gains = getattr(self, "_auto_dj_bass_filter_gains", None)
        if not gains:
            return
        entries = list(gains.items())
        gains.clear()
        for player_key, gain_db in entries:
            player = self._managed_player(player_key)
            if player is None:
                continue
            if abs(gain_db) < 0.5:
                # Effectively transparent: neutralize it in place and let the
                # next chain application drop the node, instead of rebuilding
                # the chain now and risking an audible glitch on the (new)
                # active track.
                if hasattr(player, "audio_filter_command"):
                    player.audio_filter_command(_AUTO_DJ_BASS_FILTER_LABEL, "gain", "0.0", "bass")
                continue
            self._apply_equalizer_state_to_player(player)

    def _auto_dj_next_beat_target_ms(self, outgoing_current_ms):
        """Media-time (ms) of the next outgoing beat to unpause the incoming on.

        Returns ``None`` when no beat lies ahead (fire immediately). A small lead
        ensures the target is at least one timer tick away so the fast crossfade
        timer can catch the crossing.
        """

        plan = getattr(self, "_auto_dj_pending_plan", None)
        if not plan:
            return None
        beats = plan.get("outgoing_beats") or []
        if not beats:
            return None
        try:
            current_seconds = max(0.0, float(outgoing_current_ms) / 1000.0)
        except (TypeError, ValueError):
            return None
        lead_seconds = 0.08
        target = planner.next_beat_time(beats, current_seconds + lead_seconds)
        if target is None:
            return None
        return target * 1000.0

    def _maybe_start_auto_dj_transition(self):
        """Poll (from the progress timer) and start a beatmatched transition
        when the current track is close enough to its end.

        Returns ``True`` when a transition was started so the caller can skip the
        regular time-based crossfade for this tick.
        """

        if not getattr(self, "auto_dj_enabled", False):
            return False
        if getattr(self, "_crossfade_state", None) is not None:
            return False
        if not autodj_analysis.is_available():
            return False

        state = self._get_playlist_state()
        if (
            not state
            or state.is_folder_tab
            or not state.current_media_path
            or state.repeat_mode == REPEAT_ONE
        ):
            return False
        if self.player.get_media() is None or not self.player.is_playing():
            return False

        current_path = state.current_media_path
        if not self._auto_dj_is_analyzable(current_path):
            return False

        current_time = self.player.get_time()
        total_time = self.player.get_length()
        if current_time is None or current_time < 0 or total_time is None or total_time <= 0:
            return False

        should_wrap = state.repeat_mode == REPEAT_ALL
        next_path = state.peek_in_playback_order(1, wrap=should_wrap)
        if not next_path or not self._auto_dj_is_analyzable(next_path):
            return False

        outgoing = self._auto_dj_get_analysis(current_path)
        incoming = self._auto_dj_get_analysis(next_path)
        if outgoing is None or incoming is None:
            # Not analyzed yet — the background workers are running; try again on
            # a later tick. There is still headroom before the track ends.
            return False

        try:
            current_rate = float(self.player.get_rate()) or 1.0
        except (TypeError, ValueError):
            current_rate = 1.0
        outgoing_effective_bpm = outgoing.bpm * current_rate

        incoming_rate, matched = planner.compute_incoming_rate(outgoing_effective_bpm, incoming.bpm)
        duration_ms = planner.transition_duration_ms(outgoing_effective_bpm)

        # End the blend at the outgoing track's energy cue-out — where its
        # outro collapses — not at the end of the file. Mixing over a produced
        # fade-out sounds like a plain fade no matter how beat-locked it is.
        cue_out_ms = total_time
        outgoing_cue_out = getattr(outgoing, "cue_out", 0.0) or 0.0
        if outgoing_cue_out > 0:
            cue_out_ms = min(total_time, int(round(outgoing_cue_out * 1000)))

        remaining_time = cue_out_ms - max(0, current_time)
        if remaining_time <= 0 or remaining_time > duration_ms + _AUTO_DJ_HEADROOM_MS:
            return False

        # Advance the playback order exactly like the built-in auto crossfade so
        # the playlist position, wrap handling and announcements stay consistent.
        wrapped_cycle = False
        if should_wrap:
            state.sync_playback_order()
            if state.shuffle_enabled:
                wrapped_cycle = state.playback_order_position == len(state.playback_order) - 1
            else:
                wrapped_cycle = state.current_index == state.item_count - 1

        target = state.move_in_playback_order(1, wrap=should_wrap)
        if not target:
            return False

        # Cue the incoming track in at its energy-based cue point (where the mix
        # opens up), snapped to a beat, so the blend starts on the groove — not
        # the intro/silence.
        incoming_cue_seconds = incoming.cue_in if incoming.cue_in > 0 else (
            incoming.beats[0] if incoming.beats else 0.0
        )
        incoming_start_ms = max(0, int(round(incoming_cue_seconds * 1000)))

        self._auto_dj_pending_plan = {
            "duration_ms": duration_ms,
            "incoming_rate": incoming_rate,
            "matched": matched,
            "incoming_start_ms": incoming_start_ms,
            # Phase-lock: unpause the incoming exactly when the outgoing track
            # crosses one of its beats, so their beats land on top of each other.
            "phase_lock": True,
            "outgoing_beats": list(outgoing.beats),
            # Bass swap: hand the low band over mid-blend instead of summing
            # both tracks' bass.
            "bass_swap": True,
            # Where the blend must end on the outgoing track (its cue-out).
            "outgoing_end_ms": int(cue_out_ms),
        }

        announce_message = self._auto_dj_transition_announcement(
            outgoing_effective_bpm,
            incoming,
            incoming_rate,
            matched,
            state,
            wrapped_cycle=wrapped_cycle,
        )
        self._play_media(
            index=self._get_active_playlist_index(),
            announce_message=announce_message,
            allow_crossfade=True,
        )

        if getattr(self, "_crossfade_state", None) is None:
            # The crossfade did not actually start (e.g. a guard rejected it and
            # regular playback was queued instead); drop the stale plan.
            self._auto_dj_pending_plan = None
            return False
        return True

    def _auto_dj_transition_announcement(
        self, outgoing_bpm, incoming, incoming_rate, matched, state, *, wrapped_cycle=False
    ):
        position = self._describe_playlist_position(state)
        loop_prefix = _("Nova volta da playlist. ") if wrapped_cycle else ""
        if matched:
            incoming_effective = incoming.bpm * incoming_rate
            return "{prefix}{msg}".format(
                prefix=loop_prefix,
                msg=_("Auto DJ: mixando {out:.0f} para {inn:.0f} BPM. {pos}").format(
                    out=round(outgoing_bpm), inn=round(incoming_effective), pos=position
                ),
            )
        return "{prefix}{msg}".format(
            prefix=loop_prefix,
            msg=_(
                "Auto DJ: BPMs distantes ({out:.0f} e {inn:.0f}), transição aproximada. {pos}"
            ).format(out=round(outgoing_bpm), inn=round(incoming.bpm), pos=position),
        )
