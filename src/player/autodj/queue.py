"""Rolling-horizon queue planning for AutoDJ sessions."""

from dataclasses import dataclass

from .analyzer import AudioAnalysis
from .planner import AutoDJPlanner, TransitionPlan, TransitionProfile


@dataclass(frozen=True)
class QueueCandidate:
    path: str
    artist: str
    analysis: AudioAnalysis
    source_index: int = 0


@dataclass(frozen=True)
class QueueSelection:
    path: str
    artist: str
    analysis: AudioAnalysis
    plan: TransitionPlan


class AutoDJQueuePlanner:
    def __init__(self, planner=None):
        self.planner = planner or AutoDJPlanner()

    def plan(self, current, candidates, *, count=5, recent_artists=(), beats=16, profile=TransitionProfile.SMOOTH):
        profile = TransitionProfile(profile)
        current_analysis = current
        recent = [str(artist) for artist in recent_artists if artist]
        remaining = list(candidates)
        selections = []

        while remaining and len(selections) < max(0, int(count)):
            scored = []
            for candidate in remaining:
                transition = self.planner.plan(current_analysis, candidate.analysis, beats=beats, profile=profile)
                loudness_delta = 0.0
                if current_analysis.loudness_db is not None and candidate.analysis.loudness_db is not None:
                    loudness_delta = abs(current_analysis.loudness_db - candidate.analysis.loudness_db)
                scored.append({
                    "path": candidate.path,
                    "artist": candidate.artist,
                    "energy": candidate.analysis.energy,
                    "entry_energy": candidate.analysis.entry_energy,
                    "musical_key": candidate.analysis.musical_key,
                    "musical_mode": candidate.analysis.musical_mode,
                    "key_confidence": candidate.analysis.key_confidence,
                    "current_key": current_analysis.musical_key,
                    "current_mode": current_analysis.musical_mode,
                    "tempo_delta": abs(float(transition.tempo_ratio) - 1.0),
                    "loudness_delta": loudness_delta,
                    "analysis_confidence": min(current_analysis.confidence, candidate.analysis.confidence),
                    "current_exit_vocal": current_analysis.exit_vocal_probability,
                    "entry_vocal": candidate.analysis.entry_vocal_probability,
                    "order_index": candidate.source_index,
                    "fallback_crossfade": transition.fallback_crossfade,
                    "candidate": candidate,
                    "plan": transition,
                })

            chosen = self.planner.choose_next(
                scored,
                recent_artists=recent[-3:],
                current_energy=(
                    current_analysis.exit_energy
                    if current_analysis.exit_energy is not None
                    else current_analysis.energy
                ),
                profile=profile,
            )
            if chosen is None:
                break
            candidate = chosen["candidate"]
            selections.append(QueueSelection(candidate.path, candidate.artist, candidate.analysis, chosen["plan"]))
            remaining = [item for item in remaining if item.path != candidate.path]
            current_analysis = candidate.analysis
            if candidate.artist:
                recent.append(candidate.artist)

        return selections
