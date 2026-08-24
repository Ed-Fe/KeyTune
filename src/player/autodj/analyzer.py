"""Background-friendly BPM, beat, energy and key analysis for PCM WAV audio."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import statistics
import wave


@dataclass(frozen=True)
class AudioAnalysis:
    bpm: float
    beats_ms: tuple[int, ...]
    confidence: float
    energy: float
    musical_key: str | None = None
    entry_ms: int | None = None
    exit_ms: int | None = None


class WaveAnalyzer:
    """Dependency-free envelope autocorrelation; optional decoders may feed PCM later."""

    analysis_version = 1

    def analyze(self, path: str | Path) -> AudioAnalysis:
        with wave.open(str(path), "rb") as source:
            rate, channels, width, frames = source.getframerate(), source.getnchannels(), source.getsampwidth(), source.getnframes()
            if width not in (1, 2):
                raise ValueError("A análise integrada aceita WAV PCM de 8 ou 16 bits.")
            raw = source.readframes(frames)
        samples = self._mono_samples(raw, channels, width)
        hop = max(1, rate // 100)
        envelope = [sum(abs(value) for value in samples[index:index + hop]) / hop for index in range(0, len(samples), hop)]
        if len(envelope) < 400 or max(envelope, default=0) == 0:
            return AudioAnalysis(0, (), 0, 0)
        flux = [max(0.0, envelope[index] - envelope[index - 1]) for index in range(1, len(envelope))]
        mean = statistics.fmean(flux)
        centered = [value - mean for value in flux]
        min_lag, max_lag = round(60 * 100 / 200), round(60 * 100 / 60)
        scores = []
        for lag in range(min_lag, min(max_lag, len(centered) // 2) + 1):
            scores.append((sum(centered[i] * centered[i - lag] for i in range(lag, len(centered))), lag))
        best_score, best_lag = max(scores, default=(0, 1))
        positive_total = sum(max(0, score) for score, _ in scores) or 1
        confidence = min(1.0, max(0.0, best_score / positive_total * 8))
        bpm = 6000 / best_lag
        threshold = mean + (statistics.pstdev(flux) * 0.75)
        candidates = [index for index, value in enumerate(flux) if value >= threshold]
        origin = candidates[0] if candidates else 0
        beats = tuple(round((origin + step * best_lag) * 10) for step in range(max(0, int((len(envelope) - origin) / best_lag))))
        rms = math.sqrt(sum(value * value for value in samples) / max(1, len(samples)))
        scale = 32768 if width == 2 else 128
        return AudioAnalysis(round(bpm, 2), beats, round(confidence, 3), round(min(1.0, rms / scale), 4), entry_ms=beats[0] if beats else None, exit_ms=beats[-1] if beats else None)

    @staticmethod
    def _mono_samples(raw, channels, width):
        if width == 1:
            values = [byte - 128 for byte in raw]
        else:
            values = [int.from_bytes(raw[i:i + 2], "little", signed=True) for i in range(0, len(raw) - 1, 2)]
        if channels <= 1: return values
        return [sum(values[i:i + channels]) / channels for i in range(0, len(values) - channels + 1, channels)]
