"""High quality local/online analysis powered by librosa."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

from .analyzer import AudioAnalysis

KEY_NAMES = ("C", "C♯", "D", "D♯", "E", "F", "F♯", "G", "G♯", "A", "A♯", "B")
MAJOR_PROFILE = (6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88)
MINOR_PROFILE = (6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17)
PHRASE_BEATS = 16
_WORKER_RESULT_PREFIX = "KEYTUNE_AUTODJ_RESULT="
_WORKER_TIMEOUT_SECONDS = 15 * 60


class LibrosaAnalyzer:
    """Estimate tempo, beat grid, RMS energy and chroma key.

    Imports librosa lazily so ordinary playback can still start when the
    optional analysis runtime is damaged or unavailable.
    """

    analysis_version = 6

    def __init__(self, *, sample_rate=22050, maximum_duration_seconds=15 * 60):
        self.sample_rate = sample_rate
        self.maximum_duration_seconds = maximum_duration_seconds

    def analyze(self, path: str | Path) -> AudioAnalysis:
        from .dependencies import get_autodj_analyzer_executable_path

        worker_path = get_autodj_analyzer_executable_path()
        if not os.environ.get("KEYTUNE_AUTODJ_ANALYZER_WORKER") and worker_path.is_file():
            return self._analyze_with_worker(worker_path, path)
        return self._analyze_in_process(path)

    def _analyze_with_worker(self, worker_path, path):
        creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        completed = subprocess.run(
            [
                str(worker_path),
                str(path),
                str(self.sample_rate),
                str(self.maximum_duration_seconds),
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_WORKER_TIMEOUT_SECONDS,
            creationflags=creation_flags,
        )
        result_line = next(
            (line for line in reversed(completed.stdout.splitlines()) if line.startswith(_WORKER_RESULT_PREFIX)),
            "",
        )
        if completed.returncode != 0 or not result_line:
            detail = completed.stderr.strip() or "O analisador opcional do AutoDJ não retornou um resultado."
            raise RuntimeError(detail)
        try:
            payload = json.loads(result_line[len(_WORKER_RESULT_PREFIX):])
        except (json.JSONDecodeError, TypeError) as exc:
            raise RuntimeError("O analisador opcional do AutoDJ retornou um resultado inválido.") from exc
        for field_name in ("beats_ms", "phrase_boundaries_ms", "section_boundaries_ms"):
            payload[field_name] = tuple(payload.get(field_name) or ())
        return AudioAnalysis(**payload)

    def _analyze_in_process(self, path: str | Path) -> AudioAnalysis:
        from .dependencies import activate_autodj_dependencies

        activate_autodj_dependencies()
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
        if rms.size:
            mean_rms_db = 20.0 * np.log10(max(float(np.mean(rms)), 1e-8))
            energy = float(np.clip((mean_rms_db + 35.0) / 30.0, 0.0, 1.0))
        else:
            energy = 0.0
        harmonic = librosa.effects.harmonic(y=samples, margin=4.0)
        chroma = librosa.feature.chroma_cqt(y=harmonic, sr=sample_rate)
        musical_key, musical_mode, key_confidence = self._estimate_key(chroma, np)
        tempo_value = float(np.asarray(tempo).reshape(-1)[0]) if np.asarray(tempo).size else 0.0
        entry_ms, exit_ms = self._mix_points(beats_ms, beat_frames, rms, np)
        downbeat_offset = self._downbeat_offset(beat_frames, onset_envelope, rms, np)
        phrase_boundaries_ms = tuple(
            beats_ms[index]
            for index in range(downbeat_offset, len(beats_ms), PHRASE_BEATS)
        )
        section_boundaries_ms = self._structural_boundaries(
            beats_ms,
            beat_frames,
            downbeat_offset,
            chroma,
            onset_envelope,
            rms,
            np,
        )
        entry_ms = self._align_mix_point(entry_ms, section_boundaries_ms or phrase_boundaries_ms, after=True)
        exit_ms = self._align_mix_point(exit_ms, section_boundaries_ms or phrase_boundaries_ms, after=False)
        entry_energy = self._energy_around(entry_ms, beats_ms, beat_frames, rms, np, forward=True)
        exit_energy = self._energy_around(exit_ms, beats_ms, beat_frames, rms, np, forward=False)
        entry_vocal_probability = self._vocal_probability_around(
            entry_ms, samples, harmonic, sample_rate, tempo_value, librosa, np, forward=True
        )
        exit_vocal_probability = self._vocal_probability_around(
            exit_ms, samples, harmonic, sample_rate, tempo_value, librosa, np, forward=False
        )
        return AudioAnalysis(
            bpm=round(tempo_value, 2),
            beats_ms=beats_ms,
            confidence=round(confidence, 3),
            energy=round(energy, 4),
            musical_key=musical_key,
            entry_ms=entry_ms,
            exit_ms=exit_ms,
            musical_mode=musical_mode,
            key_confidence=round(key_confidence, 3),
            downbeat_offset=downbeat_offset,
            phrase_boundaries_ms=phrase_boundaries_ms,
            section_boundaries_ms=section_boundaries_ms,
            entry_energy=entry_energy,
            exit_energy=exit_energy,
            loudness_db=round(mean_rms_db, 2) if rms.size else None,
            entry_vocal_probability=entry_vocal_probability,
            exit_vocal_probability=exit_vocal_probability,
        )

    @staticmethod
    def _estimate_key(chroma, np):
        if not chroma.size:
            return None, None, 0.0
        vector = np.mean(chroma, axis=1)
        if not vector.size or not float(np.max(vector)):
            return None, None, 0.0
        vector = (vector - np.mean(vector)) / max(float(np.std(vector)), 1e-8)
        candidates = []
        for mode, raw_profile in (("major", MAJOR_PROFILE), ("minor", MINOR_PROFILE)):
            profile = np.asarray(raw_profile, dtype=float)
            profile = (profile - np.mean(profile)) / max(float(np.std(profile)), 1e-8)
            for root in range(12):
                candidates.append((float(np.dot(vector, np.roll(profile, root))), root, mode))
        candidates.sort(reverse=True)
        best_score, root, mode = candidates[0]
        second_score = candidates[1][0]
        confidence = max(0.0, min(1.0, (best_score - second_score) / max(abs(best_score), 1e-8)))
        return KEY_NAMES[root], mode, confidence

    @staticmethod
    def _downbeat_offset(beat_frames, onset_envelope, rms, np):
        if len(beat_frames) < 8:
            return 0
        levels = np.asarray(rms).reshape(-1)
        accents = []
        for frame in beat_frames:
            frame = max(0, int(frame))
            onset = float(onset_envelope[min(frame, onset_envelope.size - 1)]) if onset_envelope.size else 0.0
            level = float(levels[min(frame, levels.size - 1)]) if levels.size else 0.0
            accents.append(onset + level)
        phase_scores = [float(np.mean(accents[phase::4])) for phase in range(4)]
        return int(np.argmax(phase_scores))

    @staticmethod
    def _structural_boundaries(beats_ms, beat_frames, downbeat_offset, chroma, onset_envelope, rms, np):
        candidates = list(range(downbeat_offset, len(beats_ms), PHRASE_BEATS))
        if len(candidates) <= 2:
            return tuple(beats_ms[index] for index in candidates)
        levels = np.asarray(rms).reshape(-1)
        beat_features = []
        for frame in beat_frames:
            frame = max(0, int(frame))
            chroma_frame = chroma[:, min(frame, chroma.shape[1] - 1)] if chroma.size else np.zeros(12)
            onset = float(onset_envelope[min(frame, onset_envelope.size - 1)]) if onset_envelope.size else 0.0
            level = float(levels[min(frame, levels.size - 1)]) if levels.size else 0.0
            beat_features.append(np.concatenate((np.asarray(chroma_frame), (onset, level))))
        features = np.asarray(beat_features)
        scale = np.std(features, axis=0)
        scale[scale < 1e-8] = 1.0
        features = (features - np.mean(features, axis=0)) / scale
        scores = []
        for index in candidates:
            left = features[max(0, index - 8):index]
            right = features[index:min(len(features), index + 8)]
            score = float(np.linalg.norm(np.mean(right, axis=0) - np.mean(left, axis=0))) if left.size and right.size else 0.0
            scores.append(score)
        threshold = float(np.percentile(scores[1:-1], 60)) if len(scores) > 3 else 0.0
        selected = [
            beats_ms[index]
            for position, (index, score) in enumerate(zip(candidates, scores))
            if position in (0, len(candidates) - 1) or score >= threshold
        ]
        return tuple(selected)

    @staticmethod
    def _align_mix_point(position_ms, boundaries_ms, *, after):
        if position_ms is None or not boundaries_ms:
            return position_ms
        if after:
            return next((value for value in boundaries_ms if value >= position_ms), boundaries_ms[-1])
        return next((value for value in reversed(boundaries_ms) if value <= position_ms), boundaries_ms[0])

    @staticmethod
    def _energy_around(position_ms, beats_ms, beat_frames, rms, np, *, forward):
        if position_ms is None or not beats_ms:
            return None
        levels = np.asarray(rms).reshape(-1)
        if not levels.size:
            return None
        anchor = min(range(len(beats_ms)), key=lambda index: abs(beats_ms[index] - position_ms))
        start = anchor if forward else max(0, anchor - 7)
        end = min(len(beat_frames), anchor + 8 if forward else anchor + 1)
        window = [levels[min(levels.size - 1, max(0, int(beat_frames[index])))] for index in range(start, end)]
        if not window:
            return None
        mean_db = 20.0 * np.log10(max(float(np.mean(window)), 1e-8))
        return round(float(np.clip((mean_db + 35.0) / 30.0, 0.0, 1.0)), 4)

    @staticmethod
    def _vocal_probability_around(position_ms, samples, harmonic, sample_rate, bpm, librosa, np, *, forward):
        if position_ms is None or not len(samples):
            return 0.0
        window_seconds = max(2.0, min(8.0, 8.0 * 60.0 / max(float(bpm or 0), 60.0)))
        anchor = max(0, min(len(samples), int(round(position_ms * sample_rate / 1000.0))))
        window_samples = int(round(window_seconds * sample_rate))
        start = anchor if forward else max(0, anchor - window_samples)
        end = min(len(samples), anchor + window_samples if forward else anchor)
        mixture = np.asarray(samples[start:end])
        harmonic_window = np.asarray(harmonic[start:end])
        if not mixture.size or not harmonic_window.size:
            return 0.0
        mixture_rms = float(np.sqrt(np.mean(mixture * mixture)))
        harmonic_rms = float(np.sqrt(np.mean(harmonic_window * harmonic_window)))
        if mixture_rms <= 1e-8:
            return 0.0
        harmonic_ratio = min(1.0, harmonic_rms / mixture_rms)
        spectrum = np.abs(librosa.stft(harmonic_window, n_fft=2048, hop_length=512))
        if not spectrum.size:
            return 0.0
        frequencies = librosa.fft_frequencies(sr=sample_rate, n_fft=2048)
        midband = spectrum[(frequencies >= 150) & (frequencies <= 4000)]
        midband_ratio = float(np.sum(midband) / max(float(np.sum(spectrum)), 1e-8))
        probability = np.clip((harmonic_ratio * 0.55 + midband_ratio * 0.45 - 0.30) / 0.55, 0.0, 1.0)
        return round(float(probability), 3)

    @staticmethod
    def _mix_points(beats_ms, beat_frames, rms, np):
        if not beats_ms:
            return None, None

        levels = np.asarray(rms).reshape(-1)
        if not levels.size or not float(np.max(levels)):
            return beats_ms[0], beats_ms[-1]

        beat_levels = np.asarray([
            levels[min(levels.size - 1, max(0, int(frame)))]
            for frame in beat_frames
        ])
        reference = float(np.percentile(beat_levels, 75))
        if reference <= 0:
            return beats_ms[0], beats_ms[-1]
        threshold = reference * 0.35

        def is_active(start, end):
            window = beat_levels[start:end]
            return bool(
                window.size
                and float(np.mean(window)) >= threshold
                and int(np.count_nonzero(window >= threshold)) >= max(1, int(np.ceil(window.size * 0.75)))
            )

        entry_index = next(
            (
                index
                for index in range(0, len(beats_ms), 4)
                if is_active(index, min(len(beat_levels), index + 8))
            ),
            0,
        )
        exit_index = next(
            (
                index
                for index in range(((len(beats_ms) - 1) // 4) * 4, -1, -4)
                if is_active(max(0, index - 7), index + 1)
            ),
            len(beats_ms) - 1,
        )
        return beats_ms[entry_index], beats_ms[exit_index]

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
