"""High quality local/online analysis powered by librosa."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

from ..i18n import _
from .analyzer import AudioAnalysis

KEY_NAMES = ("C", "C♯", "D", "D♯", "E", "F", "F♯", "G", "G♯", "A", "A♯", "B")
MAJOR_PROFILE = (6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88)
MINOR_PROFILE = (6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17)
PHRASE_BEATS = 16
MINIMUM_ENTRY_MS = 4_000
_ONSET_HOP_LENGTH = 512
_WORKER_TIMEOUT_SECONDS = 15 * 60


def _bounded_worker_output(output_file, *, maximum_bytes=4096) -> str:
    """Read only the tail of worker diagnostics to keep memory usage bounded."""
    try:
        output_file.flush()
        output_file.seek(0, os.SEEK_END)
        output_file.seek(max(0, output_file.tell() - maximum_bytes))
        output = output_file.read().decode("utf-8", errors="replace")
    except OSError:
        return ""
    return " ".join(output.split())[-1000:]


class AutoDJAnalyzerProcessError(RuntimeError):
    """The isolated analyzer process exited without a usable result."""


class AutoDJAnalysisCancelled(RuntimeError):
    """The caller no longer needs an in-flight analysis."""


class LibrosaAnalyzer:
    """Estimate tempo, beat grid, RMS energy and chroma key.

    Imports librosa lazily so ordinary playback can still start when the
    optional analysis runtime is damaged or unavailable.
    """

    supports_analysis_deadline = True
    # Older remote results may have been computed from silently truncated audio.
    analysis_version = 13

    def __init__(self, *, sample_rate=22050, maximum_duration_seconds=15 * 60):
        self.sample_rate = sample_rate
        self.maximum_duration_seconds = maximum_duration_seconds

    def analyze(self, path: str | Path, *, cancel_event=None, deadline=None) -> AudioAnalysis:
        from .dependencies import get_autodj_worker_command

        if not os.environ.get("KEYTUNE_AUTODJ_ANALYZER_WORKER"):
            return self._analyze_with_worker(
                get_autodj_worker_command(), path, cancel_event=cancel_event, deadline=deadline
            )
        return self._analyze_in_process(path)

    @staticmethod
    def _cancelled(cancel_event, deadline):
        return bool(
            (cancel_event is not None and cancel_event.is_set())
            or (deadline is not None and time.monotonic() >= deadline)
        )

    @staticmethod
    def _stop_worker(process):
        if process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

    def _analyze_with_worker(self, worker_command, path, *, cancel_event=None, deadline=None):
        creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        with tempfile.TemporaryDirectory(prefix="keytune-autodj-result-") as temporary:
            result_path = Path(temporary) / "result.json"
            output_path = Path(temporary) / "worker-output.log"
            with output_path.open("w+b") as worker_output_file:
                command = [
                    *worker_command,
                    str(path),
                    str(self.sample_rate),
                    str(self.maximum_duration_seconds),
                    str(result_path),
                ]
                if cancel_event is None and deadline is None:
                    try:
                        process = subprocess.run(
                            command,
                            check=False,
                            stdout=worker_output_file,
                            stderr=subprocess.STDOUT,
                            timeout=_WORKER_TIMEOUT_SECONDS,
                            creationflags=creation_flags,
                        )
                    except subprocess.TimeoutExpired as exc:
                        worker_output = _bounded_worker_output(worker_output_file)
                        message = _("O processo isolado do AutoDJ excedeu o tempo limite de análise.")
                        if worker_output:
                            message += " " + _("Detalhes: {detail}").format(detail=worker_output)
                        raise AutoDJAnalyzerProcessError(message) from exc
                else:
                    process = subprocess.Popen(
                        command,
                        stdout=worker_output_file,
                        stderr=subprocess.STDOUT,
                        creationflags=creation_flags,
                    )
                    worker_deadline = time.monotonic() + _WORKER_TIMEOUT_SECONDS
                    try:
                        while process.poll() is None:
                            if self._cancelled(cancel_event, deadline):
                                self._stop_worker(process)
                                raise AutoDJAnalysisCancelled(
                                    _("A análise do AutoDJ foi cancelada porque o resultado não é mais necessário.")
                                )
                            if time.monotonic() >= worker_deadline:
                                self._stop_worker(process)
                                raise subprocess.TimeoutExpired(process.args, _WORKER_TIMEOUT_SECONDS)
                            time.sleep(0.05)
                    except subprocess.TimeoutExpired as exc:
                        worker_output = _bounded_worker_output(worker_output_file)
                        message = _("O processo isolado do AutoDJ excedeu o tempo limite de análise.")
                        if worker_output:
                            message += " " + _("Detalhes: {detail}").format(detail=worker_output)
                        raise AutoDJAnalyzerProcessError(message) from exc
                worker_output = _bounded_worker_output(worker_output_file)
            try:
                response = json.loads(result_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError, TypeError):
                response = None
        if not isinstance(response, dict):
            exit_code = process.returncode & 0xFFFFFFFF
            message = _(
                "O processo isolado do AutoDJ encerrou sem resultado (código {exit_code})."
            ).format(exit_code=f"0x{exit_code:08X}")
            if worker_output:
                message += " " + _("Detalhes: {detail}").format(detail=worker_output)
            raise AutoDJAnalyzerProcessError(
                message
            )
        if not response.get("ok"):
            detail = str(response.get("error") or _("O analisador opcional do AutoDJ falhou."))
            raise RuntimeError(detail)
        payload = response.get("result")
        if not isinstance(payload, dict):
            raise AutoDJAnalyzerProcessError(
                _("O analisador opcional do AutoDJ retornou um resultado inválido.")
            )
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
            raise RuntimeError(
                _("A análise avançada requer a biblioteca librosa. Detalhes: {detail}").format(
                    detail=str(exc) or exc.__class__.__name__
                )
            ) from exc

        samples, sample_rate, analysis_truncated = self._load_audio(path, librosa, np)
        if samples.size == 0:
            return AudioAnalysis(0, (), 0, 0)
        onset_envelope = librosa.onset.onset_strength(y=samples, sr=sample_rate)
        tempo_hint = self._tempo_hint(onset_envelope, sample_rate, librosa, np)
        tempo_value, beat_frames, beat_confidence = self._estimate_beats_from_onsets(
            onset_envelope,
            sample_rate,
            np,
            tempo_hint=tempo_hint,
        )
        beats_ms = tuple(
            int(round(frame * _ONSET_HOP_LENGTH * 1000 / sample_rate))
            for frame in beat_frames
        )
        valid_beat_frames = beat_frames[beat_frames < onset_envelope.size]
        confidence = self._beat_grid_confidence(
            onset_envelope,
            valid_beat_frames,
            beat_confidence,
            np,
        )
        rms = librosa.feature.rms(y=samples)
        if rms.size:
            mean_rms_db = 20.0 * np.log10(max(float(np.mean(rms)), 1e-8))
            energy = float(np.clip((mean_rms_db + 35.0) / 30.0, 0.0, 1.0))
        else:
            energy = 0.0
        harmonic = librosa.effects.harmonic(y=samples, margin=4.0)
        chroma = librosa.feature.chroma_cqt(y=harmonic, sr=sample_rate)
        musical_key, musical_mode, key_confidence = self._estimate_key(chroma, np)
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
        entry_ms = self._select_entry_point(
            entry_ms,
            section_boundaries_ms or phrase_boundaries_ms,
            beats_ms,
        )
        exit_ms = self._align_mix_point(exit_ms, section_boundaries_ms or phrase_boundaries_ms, after=False)
        entry_energy = self._energy_around(entry_ms, beats_ms, beat_frames, rms, np, forward=True)
        exit_energy = self._energy_around(exit_ms, beats_ms, beat_frames, rms, np, forward=False)
        entry_loudness_db = self._loudness_around(
            entry_ms, samples, sample_rate, tempo_value, np, forward=True
        )
        exit_loudness_db = self._loudness_around(
            exit_ms, samples, sample_rate, tempo_value, np, forward=False
        )
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
            analysis_truncated=analysis_truncated,
            entry_loudness_db=entry_loudness_db,
            exit_loudness_db=exit_loudness_db,
        )

    @staticmethod
    def _tempo_hint(onset_envelope, sample_rate, librosa, np):
        """Estimate a prior-weighted global tempo without invoking the beat tracker."""
        try:
            values = np.asarray(
                librosa.feature.tempo(
                    onset_envelope=onset_envelope,
                    sr=sample_rate,
                    hop_length=_ONSET_HOP_LENGTH,
                    max_tempo=200.0,
                ),
                dtype=float,
            ).reshape(-1)
        except Exception:
            return None
        if not values.size or not np.isfinite(values[0]) or values[0] <= 0:
            return None
        return float(values[0])

    @staticmethod
    def _estimate_beats_from_onsets(onset_envelope, sample_rate, np, *, tempo_hint=None):
        """Build a beat grid without librosa's Numba-backed beat tracker.

        In frozen builds, the third-party JIT compiler used by
        ``librosa.beat.beat_track`` can terminate the isolated worker. A
        normalized onset autocorrelation produces a stable grid without
        invoking that compiler.
        """
        onset = np.nan_to_num(
            np.asarray(onset_envelope, dtype=float).reshape(-1),
            nan=0.0,
            posinf=0.0,
            neginf=0.0,
        )
        if onset.size < 4 or not float(np.max(onset)):
            return 0.0, np.asarray((), dtype=int), 0.0
        minimum_bpm, maximum_bpm = 60.0, 200.0
        minimum_lag = max(1, int(round(60.0 * sample_rate / (_ONSET_HOP_LENGTH * maximum_bpm))))
        maximum_lag = min(
            onset.size - 1,
            int(round(60.0 * sample_rate / (_ONSET_HOP_LENGTH * minimum_bpm))),
        )
        centered_onset = onset - float(np.mean(onset))
        scores = []
        for lag in range(minimum_lag, maximum_lag + 1):
            left, right = centered_onset[:-lag], centered_onset[lag:]
            denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
            if denominator:
                scores.append((float(np.dot(left, right)) / denominator, lag))
        if not scores:
            return 0.0, np.asarray((), dtype=int), 0.0
        score_by_lag = {lag: score for score, lag in scores}
        if tempo_hint is not None and np.isfinite(tempo_hint) and tempo_hint > 0:
            hinted_lag = int(
                round(60.0 * sample_rate / (_ONSET_HOP_LENGTH * float(tempo_hint)))
            )
            integer_lag = max(minimum_lag, min(maximum_lag, hinted_lag))
            best_score = score_by_lag.get(integer_lag, 0.0)
            harmonic_peaks = [(best_score, integer_lag)]
            for score, lag in scores:
                harmonic_ratio = integer_lag / lag
                harmonic_order = round(harmonic_ratio)
                if (
                    harmonic_order >= 2
                    and abs(harmonic_ratio - harmonic_order) <= 0.08
                    and score >= best_score * 0.5
                    and score >= score_by_lag.get(lag - 1, float("-inf"))
                    and score >= score_by_lag.get(lag + 1, float("-inf"))
                ):
                    harmonic_peaks.append((score, lag))
            best_score, integer_lag = min(harmonic_peaks, key=lambda item: item[1])
        else:
            raw_best_score, raw_best_lag = max(scores)
            harmonic_peaks = [(raw_best_score, raw_best_lag)]
            for score, lag in scores:
                left_score = score_by_lag.get(lag - 1, float("-inf"))
                right_score = score_by_lag.get(lag + 1, float("-inf"))
                harmonic_ratio = raw_best_lag / lag
                harmonic_order = round(harmonic_ratio)
                related_harmonic = (
                    harmonic_order >= 2
                    and abs(harmonic_ratio - harmonic_order) <= 0.08
                )
                if (
                    score >= raw_best_score * 0.5
                    and score >= left_score
                    and score >= right_score
                    and related_harmonic
                ):
                    harmonic_peaks.append((score, lag))
            best_score, integer_lag = min(harmonic_peaks, key=lambda item: item[1])
        left_score = score_by_lag.get(integer_lag - 1, best_score)
        right_score = score_by_lag.get(integer_lag + 1, best_score)
        curvature = left_score - (2.0 * best_score) + right_score
        fractional_offset = (
            0.5 * (left_score - right_score) / curvature
            if abs(curvature) > 1e-9
            else 0.0
        )
        best_lag = max(
            float(minimum_lag),
            min(
                float(maximum_lag),
                float(integer_lag) + max(-0.5, min(0.5, fractional_offset)),
            ),
        )
        phase_scores = []
        frame_numbers = np.arange(int(np.ceil(onset.size / best_lag)) + 1)
        for phase in range(max(1, int(round(best_lag)))):
            grid = np.rint(phase + frame_numbers * best_lag).astype(int)
            grid = grid[grid < onset.size]
            phase_scores.append(float(np.sum(onset[grid])))
        phase_scores = np.asarray(phase_scores)
        first_frame = int(np.argmax(phase_scores))
        beat_frames = np.rint(
            first_frame + np.arange(int(np.ceil((onset.size - first_frame) / best_lag))) * best_lag
        ).astype(int)
        beat_frames = np.unique(beat_frames[beat_frames < onset.size])
        bpm = 60.0 * sample_rate / (_ONSET_HOP_LENGTH * best_lag)
        average_score = sum(score for score, _lag in scores) / len(scores)
        confidence = max(
            0.0,
            min(
                1.0,
                (best_score - average_score) / max(1e-9, 1.0 - average_score),
            ),
        )
        return bpm, beat_frames, confidence

    @staticmethod
    def _beat_grid_confidence(onset_envelope, beat_frames, periodicity_confidence, np):
        """Combine periodicity with local onset alignment without outlier bias."""
        onset = np.nan_to_num(
            np.asarray(onset_envelope, dtype=float).reshape(-1),
            nan=0.0,
            posinf=0.0,
            neginf=0.0,
        )
        onset = np.maximum(onset, 0.0)
        frames = np.asarray(beat_frames, dtype=int).reshape(-1)
        if not onset.size or not frames.size or not float(np.max(onset)):
            return 0.0
        aligned_strengths = np.asarray(
            [
                np.max(onset[max(0, int(frame) - 2):min(onset.size, int(frame) + 3)])
                for frame in frames
                if 0 <= int(frame) < onset.size
            ]
        )
        if not aligned_strengths.size:
            return 0.0
        onset_reference = float(np.percentile(onset, 95))
        if onset_reference <= 0:
            positive_onsets = onset[onset > 0]
            onset_reference = float(np.mean(positive_onsets)) if positive_onsets.size else 0.0
        alignment_confidence = min(
            1.0,
            float(np.mean(aligned_strengths)) / max(onset_reference, 1e-9),
        )
        periodicity = float(periodicity_confidence)
        if not np.isfinite(periodicity):
            return 0.0
        return max(0.0, min(1.0, periodicity * alignment_confidence))

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
    def _select_entry_point(position_ms, boundaries_ms, beats_ms, *, minimum_ms=MINIMUM_ENTRY_MS):
        """Choose the first phrase boundary, or beat, at or after the minimum intro."""
        if not beats_ms:
            return position_ms
        target_ms = max(int(position_ms or 0), int(minimum_ms))
        maximum_entry_ms = max(int(beats_ms[0]), int(beats_ms[-1] * 0.4))
        if target_ms > maximum_entry_ms:
            original_position_ms = int(position_ms or 0)
            if original_position_ms <= maximum_entry_ms:
                return next(
                    (value for value in beats_ms if value >= original_position_ms),
                    beats_ms[0],
                )
            return next(
                (value for value in reversed(beats_ms) if value <= maximum_entry_ms),
                beats_ms[0],
            )
        boundary = next((value for value in boundaries_ms if target_ms <= value <= maximum_entry_ms), None)
        if boundary is not None:
            return boundary
        beat = next(
            (value for value in beats_ms if target_ms <= value <= maximum_entry_ms),
            None,
        )
        if beat is not None:
            return beat
        # Very short cues must remain playable instead of starting at their end.
        return beats_ms[0]

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
    def _loudness_around(position_ms, samples, sample_rate, bpm, np, *, forward):
        """Measure RMS loudness in the transition region without energy normalization."""
        if position_ms is None or not len(samples) or sample_rate <= 0:
            return None
        window_seconds = max(2.0, min(8.0, 8.0 * 60.0 / max(float(bpm or 0), 60.0)))
        anchor = max(0, min(len(samples), int(round(position_ms * sample_rate / 1000.0))))
        window_samples = max(1, int(round(window_seconds * sample_rate)))
        start = anchor if forward else max(0, anchor - window_samples)
        end = min(len(samples), anchor + window_samples if forward else anchor)
        window = np.asarray(samples[start:end], dtype=float)
        if not window.size:
            return None
        rms = float(np.sqrt(np.mean(window * window)))
        if not np.isfinite(rms):
            return None
        return round(20.0 * float(np.log10(max(rms, 1e-8))), 2)

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
                return (
                    np.concatenate(chunks),
                    self.sample_rate,
                    sample_count >= maximum_samples,
                )
        except (ImportError, OSError, RuntimeError):
            pass
        except Exception as exc:
            if not type(exc).__module__.startswith("av."):
                raise
        samples, sample_rate = librosa.load(
            str(path), sr=self.sample_rate, mono=True, duration=self.maximum_duration_seconds
        )
        maximum_samples = self.sample_rate * self.maximum_duration_seconds
        return samples, sample_rate, len(samples) >= maximum_samples
