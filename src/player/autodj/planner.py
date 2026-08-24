"""Phrase-aware transition selection with conservative fallback."""

from dataclasses import dataclass
from enum import Enum

from .analyzer import AudioAnalysis


class TransitionProfile(str, Enum):
    SMOOTH = "smooth"
    PARTY = "party"
    ELECTRONIC = "electronic"


@dataclass(frozen=True)
class TransitionPlan:
    beat_count: int
    outgoing_start_ms: int | None
    incoming_start_ms: int | None
    tempo_ratio: float
    confidence: float
    fallback_crossfade: bool
    reason: str = ""


class AutoDJPlanner:
    def __init__(self, *, max_tempo_adjustment=0.06, minimum_confidence=0.45):
        self.max_tempo_adjustment = max_tempo_adjustment; self.minimum_confidence = minimum_confidence

    def plan(self, outgoing: AudioAnalysis, incoming: AudioAnalysis, *, beats=16, profile=TransitionProfile.SMOOTH):
        if beats not in (8, 16, 32): raise ValueError("A transição deve ter 8, 16 ou 32 batidas.")
        confidence = min(outgoing.confidence, incoming.confidence)
        if not outgoing.bpm or not incoming.bpm or confidence < self.minimum_confidence:
            return TransitionPlan(beats, None, None, 1, confidence, True, "confiança insuficiente")
        ratio = outgoing.bpm / incoming.bpm
        if abs(ratio - 1) > self.max_tempo_adjustment:
            return TransitionPlan(beats, None, None, 1, confidence, True, "ajuste de tempo excederia o limite")
        outgoing_start = outgoing.beats_ms[-beats] if len(outgoing.beats_ms) >= beats else outgoing.entry_ms
        incoming_start = incoming.entry_ms or (incoming.beats_ms[0] if incoming.beats_ms else 0)
        return TransitionPlan(beats, outgoing_start, incoming_start, round(ratio, 5), confidence, False)

    @staticmethod
    def choose_next(candidates, *, recent_artists=(), current_energy=None, profile=TransitionProfile.SMOOTH):
        recent = {item.casefold() for item in recent_artists}
        eligible = [item for item in candidates if str(item.get("artist", "")).casefold() not in recent] or list(candidates)
        if current_energy is None: return eligible[0] if eligible else None
        target_delta = {TransitionProfile.SMOOTH: 0, TransitionProfile.PARTY: .08, TransitionProfile.ELECTRONIC: .03}[profile]
        return min(eligible, key=lambda item: abs(item.get("energy", current_energy) - (current_energy + target_delta)), default=None)
