"""Profile-specific AutoDJ volume and EQ automation."""

from dataclasses import dataclass
import math

from .planner import TransitionProfile


@dataclass(frozen=True)
class MixValues:
    incoming_volume: float
    outgoing_volume: float
    incoming_bass_db: float
    outgoing_bass_db: float
    incoming_mid_db: float
    outgoing_mid_db: float


@dataclass(frozen=True)
class MixProfile:
    incoming_fade_end: float
    outgoing_fade_start: float
    bass_cut_db: float
    mid_cut_db: float
    bass_swap_start: float
    bass_swap_end: float


MIX_PROFILES = {
    TransitionProfile.SMOOTH: MixProfile(0.25, 0.75, -9.0, -2.0, 0.25, 0.75),
    TransitionProfile.PARTY: MixProfile(0.18, 0.82, -18.0, -4.0, 0.40, 0.60),
    TransitionProfile.ELECTRONIC: MixProfile(0.12, 0.88, -24.0, -6.0, 0.44, 0.56),
}


def _smoothstep(value, start, end):
    if end <= start:
        return 1.0 if value >= end else 0.0
    normalized = max(0.0, min(1.0, (value - start) / (end - start)))
    return normalized * normalized * (3.0 - 2.0 * normalized)


def mix_values(progress, profile=TransitionProfile.SMOOTH):
    normalized_profile = TransitionProfile(profile)
    settings = MIX_PROFILES[normalized_profile]
    progress = max(0.0, min(1.0, float(progress)))

    incoming_progress = _smoothstep(progress, 0.0, settings.incoming_fade_end)
    outgoing_progress = _smoothstep(progress, settings.outgoing_fade_start, 1.0)
    incoming_volume = math.sin((math.pi / 2.0) * incoming_progress)
    outgoing_volume = math.cos((math.pi / 2.0) * outgoing_progress)

    bass_swap = _smoothstep(progress, settings.bass_swap_start, settings.bass_swap_end)
    incoming_bass_db = settings.bass_cut_db * (1.0 - bass_swap)
    outgoing_bass_db = settings.bass_cut_db * bass_swap

    incoming_mid_restore = _smoothstep(progress, settings.bass_swap_start * 0.5, settings.bass_swap_end)
    outgoing_mid_cut = _smoothstep(progress, settings.bass_swap_start, min(1.0, settings.bass_swap_end + 0.2))
    incoming_mid_db = settings.mid_cut_db * (1.0 - incoming_mid_restore)
    outgoing_mid_db = settings.mid_cut_db * outgoing_mid_cut

    return MixValues(
        incoming_volume=incoming_volume,
        outgoing_volume=outgoing_volume,
        incoming_bass_db=incoming_bass_db,
        outgoing_bass_db=outgoing_bass_db,
        incoming_mid_db=incoming_mid_db,
        outgoing_mid_db=outgoing_mid_db,
    )


def build_mix_lavfi_filters(bass_gain_db, mid_gain_db):
    return (
        f"equalizer@autodj_bass_80=f=80:t=q:w=1:g={bass_gain_db:.2f}",
        f"equalizer@autodj_bass_180=f=180:t=q:w=1:g={bass_gain_db * 0.7:.2f}",
        f"equalizer@autodj_mid=f=1200:t=q:w=0.8:g={mid_gain_db:.2f}",
    )
