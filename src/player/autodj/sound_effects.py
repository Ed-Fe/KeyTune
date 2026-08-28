"""Packaged sound effects for AutoDJ transitions."""

from pathlib import Path

_PROFILE_EFFECTS = {
    "smooth": "fast_small_sweep_transition.wav",
    "party": "dj_record_swipe.wav",
    "electronic": "swell_vinyl_scratch.wav",
}


def transition_sound_path(profile):
    """Return the packaged effect for an AutoDJ profile, if it is available."""
    filename = _PROFILE_EFFECTS.get(str(profile or "smooth"), _PROFILE_EFFECTS["smooth"])
    path = Path(__file__).with_name("sounds") / filename
    return path if path.is_file() else None
