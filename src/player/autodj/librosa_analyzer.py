"""High quality local/online analysis powered by librosa."""

from __future__ import annotations

from pathlib import Path

from .analyzer import AudioAnalysis

KEY_NAMES = ("C", "C♯", "D", "D♯", "E", "F", "F♯", "G", "G♯", "A", "A♯", "B")


class LibrosaAnalyzer:
    """Estimate tempo, beat grid, RMS energy and chroma key.

    Imports librosa lazily so ordinary playback can still start when the
    optional analysis runtime is damaged or unavailable.
    """

    analysis_version = 2

    def __init__(self, *, sample_rate=22050, maximum_duration_seconds=15 * 60):
        self.sample_rate = sample_rate
        self.maximum_duration_seconds = maximum_duration_seconds

    def analyze(self, path: str | Path) -> AudioAnalysis:
        try:
            import librosa
            import numpy as np
        except ImportError as exc:
            raise RuntimeError("A análise avançada requer a biblioteca librosa.") from exc

        samples, sample_rate = self._load_audio(path, librosa, np)
        if samples.size == 0:
            return AudioAnalysis(0, (), 0, 0)
        onset_envelope = librosa.onset.onset_strength(y=samples, sr=sample_rate)
        tempo, beat_frames = librosa.beat.beat_track(
            onset_envelope=onset_envelope, sr=sample_rate, units="frames"
        )
        beat_times = librosa.frames_to_time(beat_frames, sr=sample_rate)
        beats_ms = tuple(int(round(value * 1000)) for value in beat_times)
        onset_peak = float(np.max(onset_envelope)) if onset_envelope.size else 0.0
        valid_beat_frames = beat_frames[beat_frames < onset_envelope.size]
        beat_strength = float(np.mean(onset_envelope[valid_beat_frames])) if valid_beat_frames.size else 0.0
        confidence = min(1.0, beat_strength / onset_peak) if onset_peak else 0.0
        rms = librosa.feature.rms(y=samples)
        energy = min(1.0, float(np.mean(rms)) * 4) if rms.size else 0.0
        chroma = librosa.feature.chroma_cqt(y=samples, sr=sample_rate)
        musical_key = KEY_NAMES[int(np.argmax(np.mean(chroma, axis=1)))] if chroma.size else None
        tempo_value = float(np.asarray(tempo).reshape(-1)[0]) if np.asarray(tempo).size else 0.0
        return AudioAnalysis(
            bpm=round(tempo_value, 2),
            beats_ms=beats_ms,
            confidence=round(confidence, 3),
            energy=round(energy, 4),
            musical_key=musical_key,
            entry_ms=beats_ms[0] if beats_ms else None,
            exit_ms=beats_ms[-1] if beats_ms else None,
        )

    def _load_audio(self, path, librosa, np):
        """Prefer bundled FFmpeg codecs from PyAV, then fall back to librosa."""
        try:
            import av

            maximum_samples = self.sample_rate * self.maximum_duration_seconds
            chunks = []
            sample_count = 0
            resampler = av.audio.resampler.AudioResampler(
                format="fltp", layout="mono", rate=self.sample_rate
            )
            with av.open(str(path)) as container:
                audio_stream = next((stream for stream in container.streams if stream.type == "audio"), None)
                if audio_stream is None:
                    raise ValueError("A mídia não contém uma faixa de áudio.")
                for frame in container.decode(audio_stream):
                    for converted in resampler.resample(frame):
                        values = converted.to_ndarray().reshape(-1).astype("float32", copy=False)
                        remaining = maximum_samples - sample_count
                        if remaining <= 0:
                            break
                        values = values[:remaining]
                        chunks.append(values)
                        sample_count += values.size
                    if sample_count >= maximum_samples:
                        break
            if chunks:
                return np.concatenate(chunks), self.sample_rate
        except ImportError:
            pass
        return librosa.load(
            str(path), sr=self.sample_rate, mono=True, duration=self.maximum_duration_seconds
        )
