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
    outgoing_end_ms: int | None = None
    incoming_beat_ms: float = 0.0
    incoming_gain_db: float = 0.0
    vocal_overlap: float = 0.0


class AutoDJPlanner:
    def __init__(self, *, max_tempo_adjustment=0.06, minimum_confidence=0.18):
        self.max_tempo_adjustment = max_tempo_adjustment; self.minimum_confidence = minimum_confidence

    def plan(self, outgoing: AudioAnalysis, incoming: AudioAnalysis, *, beats=16, profile=TransitionProfile.SMOOTH):
        if beats not in (8, 16, 32): raise ValueError("A transição deve ter 8, 16 ou 32 batidas.")
        vocal_overlap = min(outgoing.exit_vocal_probability, incoming.entry_vocal_probability)
        if vocal_overlap >= 0.55:
            beats = 8
        confidence = min(outgoing.confidence, incoming.confidence)
        if not outgoing.bpm or not incoming.bpm or confidence < self.minimum_confidence:
            return TransitionPlan(beats, None, None, 1, confidence, True, "confiança insuficiente")
        ratio = outgoing.bpm / incoming.bpm
        if abs(ratio - 1) > self.max_tempo_adjustment:
            return TransitionPlan(beats, None, None, 1, confidence, True, "ajuste de tempo excederia o limite")
        if outgoing.phrase_boundaries_ms:
            outgoing_boundary = self._value_at_or_before(outgoing.phrase_boundaries_ms, outgoing.exit_ms)
            outgoing_end_index = self._beat_index_at_or_before(outgoing.beats_ms, outgoing_boundary)
        else:
            outgoing_end_index = self._beat_index_at_or_before(outgoing.beats_ms, outgoing.exit_ms)
            outgoing_end_index -= outgoing_end_index % 4
        outgoing_start_index = outgoing_end_index - beats
        if outgoing_start_index < 0:
            return TransitionPlan(beats, None, None, 1, confidence, True, "grade de batidas insuficiente")

        if incoming.phrase_boundaries_ms:
            incoming_boundary = self._value_at_or_after(incoming.phrase_boundaries_ms, incoming.entry_ms)
            incoming_start_index = self._beat_index_at_or_after(incoming.beats_ms, incoming_boundary)
        else:
            incoming_start_index = self._beat_index_at_or_after(incoming.beats_ms, incoming.entry_ms)
            incoming_start_index += (-incoming_start_index) % 4
        if incoming_start_index >= len(incoming.beats_ms):
            return TransitionPlan(beats, None, None, 1, confidence, True, "ponto de entrada indisponível")

        return TransitionPlan(
            beats,
            outgoing.beats_ms[outgoing_start_index],
            incoming.beats_ms[incoming_start_index],
            round(ratio, 5),
            confidence,
            False,
            outgoing_end_ms=outgoing.beats_ms[outgoing_end_index],
            incoming_beat_ms=60000.0 / incoming.bpm,
            incoming_gain_db=self._incoming_gain_db(outgoing, incoming),
            vocal_overlap=vocal_overlap,
        )

    @staticmethod
    def _incoming_gain_db(outgoing, incoming):
        if outgoing.exit_energy is not None and incoming.entry_energy is not None:
            outgoing_loudness = outgoing.exit_energy * 30.0 - 35.0
            incoming_loudness = incoming.entry_energy * 30.0 - 35.0
        else:
            outgoing_loudness = outgoing.loudness_db
            incoming_loudness = incoming.loudness_db
        if outgoing_loudness is None or incoming_loudness is None:
            return 0.0
        return round(max(-6.0, min(0.0, outgoing_loudness - incoming_loudness)), 2)

    @staticmethod
    def _value_at_or_before(values, position):
        if not values:
            return position
        if position is None:
            return values[-1]
        return next((value for value in reversed(values) if value <= position), values[0])

    @staticmethod
    def _value_at_or_after(values, position):
        if not values:
            return position
        if position is None:
            return values[0]
        return next((value for value in values if value >= position), values[-1])

    @staticmethod
    def _beat_index_at_or_before(beats_ms, position_ms):
        if not beats_ms:
            return -1
        if position_ms is None:
            return len(beats_ms) - 1
        for index in range(len(beats_ms) - 1, -1, -1):
            if beats_ms[index] <= position_ms:
                return index
        return 0

    @staticmethod
    def _beat_index_at_or_after(beats_ms, position_ms):
        if not beats_ms:
            return 0
        if position_ms is None:
            return 0
        for index, beat_ms in enumerate(beats_ms):
            if beat_ms >= position_ms:
                return index
        return len(beats_ms)

    @staticmethod
    def choose_next(candidates, *, recent_artists=(), current_energy=None, profile=TransitionProfile.SMOOTH):
        profile = TransitionProfile(profile)
        recent = {item.casefold() for item in recent_artists}
        eligible = [item for item in candidates if str(item.get("artist", "")).casefold() not in recent] or list(candidates)
        if not eligible:
            return None
        compatible = [item for item in eligible if not item.get("fallback_crossfade")]
        if compatible:
            eligible = compatible
        if current_energy is None:
            current_energy = eligible[0].get("energy", 0.5)
        target_delta = {TransitionProfile.SMOOTH: 0, TransitionProfile.PARTY: .08, TransitionProfile.ELECTRONIC: .03}[profile]
        target_energy = max(0.0, min(1.0, current_energy + target_delta))
        current_key = next((item.get("current_key") for item in eligible if item.get("current_key")), None)
        current_mode = next((item.get("current_mode") for item in eligible if item.get("current_mode")), None)

        def key_distance(candidate_key, candidate_mode):
            keys = ("C", "C♯", "D", "D♯", "E", "F", "F♯", "G", "G♯", "A", "A♯", "B")
            if current_key not in keys or candidate_key not in keys:
                return 0.5
            current_root = keys.index(current_key)
            candidate_root = keys.index(candidate_key)
            semitones = (candidate_root - current_root) % 12
            if not current_mode or not candidate_mode:
                distance = min(semitones, 12 - semitones)
                return 0.0 if distance in (0, 5) else min(1.0, distance / 3.0)
            if current_mode == candidate_mode and semitones in (0, 5, 7):
                return 0.0 if semitones == 0 else 0.12
            if (current_mode, candidate_mode, semitones) in {
                ("major", "minor", 9),
                ("minor", "major", 3),
            }:
                return 0.05
            if semitones == 0:
                return 0.25
            circle_steps = min((semitones * 7) % 12, (-semitones * 7) % 12)
            return min(1.0, 0.25 + circle_steps / 6.0)

        def candidate_score(item):
            candidate_energy = item.get("entry_energy")
            if candidate_energy is None:
                candidate_energy = item.get("energy", current_energy)
            energy_cost = abs(float(candidate_energy) - target_energy)
            harmonic_cost = key_distance(item.get("musical_key"), item.get("musical_mode"))
            key_uncertainty = 1.0 - float(item.get("key_confidence", 0.0) or 0.0)
            tempo_cost = min(1.0, float(item.get("tempo_delta", 0.0)) / 0.06)
            loudness_cost = min(1.0, float(item.get("loudness_delta", 0.0)) / 8.0)
            confidence_cost = 1.0 - float(item.get("analysis_confidence", 0.0) or 0.0)
            order_cost = min(1.0, float(item.get("order_index", 0)) / 8.0)
            vocal_cost = min(
                float(item.get("current_exit_vocal", 0.0) or 0.0),
                float(item.get("entry_vocal", 0.0) or 0.0),
            )
            return (
                energy_cost * 0.28
                + harmonic_cost * (0.23 - key_uncertainty * 0.08)
                + tempo_cost * 0.16
                + loudness_cost * 0.10
                + confidence_cost * 0.08
                + vocal_cost * 0.12
                + order_cost * 0.05
            )

        return min(eligible, key=candidate_score)
