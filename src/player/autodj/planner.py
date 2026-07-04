"""Pure decision logic for the Auto DJ.

Everything here is side-effect free and independent of wxPython / MPV so it can
be unit tested in isolation. The questions it answers:

- *How fast should the incoming track play* so its beat sits on top of the
  outgoing track's beat (tempo match / beatmatch)?
- *How long should the blend be*, expressed as a whole number of beats?
- *How loud should each track's low band be* at a given point of the blend
  (the bass swap that keeps the two basslines from stacking)?
"""

from __future__ import annotations

import math

# A "good" beatmatch keeps the time-stretch subtle. Beyond this the pitch/tempo
# artifacts get obvious, so we clamp and flag the match as loose instead.
DEFAULT_MAX_STRETCH = 0.08

# Default blend length. 8 beats == 2 bars in 4/4: long enough to feel smooth,
# short enough that the beat-locked incoming track becomes clearly audible on
# the grid instead of washing in like a slow fade.
DEFAULT_TRANSITION_BEATS = 8

# Bass swap (DJ-style EQ blend): the incoming track enters with its low band
# cut so the two basslines/kicks never stack; midway through the blend the
# bass is handed over from the outgoing to the incoming track. -15 dB on a
# low shelf is a strong "bass kill" without sounding filtered overall.
BASS_SWAP_CUT_DB = -15.0
BASS_SWAP_START = 0.35  # blend progress where the handover begins
BASS_SWAP_END = 0.65  # blend progress where the handover completes

_HALF_STEP = math.sqrt(2.0)  # boundary for folding a tempo into another's octave


def normalize_bpm_to_reference(bpm: float, reference_bpm: float) -> float:
    """Fold ``bpm`` up/down by octaves until it sits closest to ``reference_bpm``.

    Handles half-/double-time relationships (e.g. a 70 BPM track is rhythmically
    compatible with a 140 BPM one) by bringing them into the same octave before
    any ratio is computed.
    """

    if bpm <= 0 or reference_bpm <= 0:
        return bpm

    folded = bpm
    while folded < reference_bpm / _HALF_STEP:
        folded *= 2.0
    while folded > reference_bpm * _HALF_STEP:
        folded /= 2.0
    return folded


def compute_incoming_rate(
    outgoing_effective_bpm: float,
    incoming_bpm: float,
    max_stretch: float = DEFAULT_MAX_STRETCH,
) -> tuple[float, bool]:
    """Return ``(playback_rate, matched)`` for the incoming track.

    ``playback_rate`` is what to feed MPV's ``speed`` so the incoming track's
    tempo lines up with the outgoing track's *currently playing* tempo
    (``outgoing_effective_bpm`` already accounts for any speed applied to the
    outgoing track). ``matched`` is ``True`` when a clean beatmatch was possible
    within ``max_stretch``; when the tempos are too far apart the rate is clamped
    and ``matched`` is ``False`` (the transition still happens, just not
    beat-locked).
    """

    if outgoing_effective_bpm <= 0 or incoming_bpm <= 0:
        return (1.0, False)

    target_bpm = normalize_bpm_to_reference(outgoing_effective_bpm, incoming_bpm)
    ratio = target_bpm / incoming_bpm

    matched = abs(ratio - 1.0) <= max_stretch
    lower, upper = 1.0 - max_stretch, 1.0 + max_stretch
    clamped_ratio = min(upper, max(lower, ratio))
    return (round(clamped_ratio, 4), matched)


def next_beat_time(beats, after_seconds: float):
    """Return the first beat time strictly greater than ``after_seconds``.

    Used to phase-lock the transition: the incoming track is unpaused when the
    outgoing track reaches this beat. Returns ``None`` when there is no beat
    ahead (e.g. we are already past the last analyzed beat).
    """

    for beat in beats:
        if beat > after_seconds:
            return float(beat)
    return None


def bass_swap_gains(progress: float) -> tuple[float, float]:
    """Return ``(incoming_gain_db, outgoing_gain_db)`` for the low band at
    blend ``progress`` (0.0–1.0).

    Before the swap window the incoming plays with its bass cut and the
    outgoing keeps its bass; inside the window the gains cross linearly (in
    dB); after it the roles are reversed. This is what keeps the low end clean
    during the overlap — two full basslines summed is what makes a transition
    sound like mud/plain fade.
    """

    try:
        clamped = max(0.0, min(1.0, float(progress)))
    except (TypeError, ValueError):
        clamped = 0.0

    if clamped <= BASS_SWAP_START:
        return (BASS_SWAP_CUT_DB, 0.0)
    if clamped >= BASS_SWAP_END:
        return (0.0, BASS_SWAP_CUT_DB)

    handover = (clamped - BASS_SWAP_START) / (BASS_SWAP_END - BASS_SWAP_START)
    return (BASS_SWAP_CUT_DB * (1.0 - handover), BASS_SWAP_CUT_DB * handover)


def beat_length_ms(bpm: float) -> float:
    """Milliseconds per beat at ``bpm``."""

    if bpm <= 0:
        return 0.0
    return 60000.0 / bpm


def transition_duration_ms(
    effective_bpm: float,
    beats: int = DEFAULT_TRANSITION_BEATS,
    min_ms: int = 3000,
    max_ms: int = 20000,
) -> int:
    """Length of the blend in milliseconds, ``beats`` long, clamped to a range."""

    per_beat = beat_length_ms(effective_bpm)
    if per_beat <= 0:
        return min(max_ms, max(min_ms, 8000))
    raw = per_beat * max(1, beats)
    return int(min(max_ms, max(min_ms, raw)))
