"""Offline BPM / beat-grid analysis for the Auto DJ, with an on-disk cache.

``librosa`` is an *optional* dependency. Importing it is deferred and guarded so
the application keeps working (and this module keeps importing) when it is
absent — :func:`is_available` simply reports ``False`` and callers fall back to
their normal, non-beatmatched behavior.

To try the Auto DJ, install the analysis backend once:

    pip install librosa
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from dataclasses import dataclass

from ..log import get_logger
from ..session import get_app_storage_dir

_logger = get_logger(__name__)

# Bump when the cached payload shape or the analysis method changes so stale
# entries from older versions are ignored rather than misread.
_CACHE_VERSION = 3
_CACHE_DIR_NAME = "autodj_cache"

_librosa = None
_librosa_import_attempted = False
_import_lock = threading.Lock()


def _load_librosa():
    """Import ``librosa`` lazily, at most once, tolerating its absence."""

    global _librosa, _librosa_import_attempted
    with _import_lock:
        if not _librosa_import_attempted:
            _librosa_import_attempted = True
            try:
                import librosa  # type: ignore

                _librosa = librosa
            except Exception as exc:  # ImportError, or a broken numba/llvmlite, etc.
                _logger.info("librosa unavailable; Auto DJ beat analysis disabled (%s)", exc)
                _librosa = None
    return _librosa


def is_available() -> bool:
    """Return ``True`` when the analysis backend (librosa) can be used."""

    return _load_librosa() is not None


@dataclass(slots=True)
class TrackAnalysis:
    bpm: float
    beats: list[float]  # beat onset times, in seconds
    duration: float
    cue_in: float = 0.0  # first "full energy" beat (seconds) — where the mix opens up
    cue_out: float = 0.0  # last "full energy" beat (seconds) — where the outro collapses

    def to_dict(self) -> dict:
        return {
            "bpm": self.bpm,
            "beats": self.beats,
            "duration": self.duration,
            "cue_in": self.cue_in,
            "cue_out": self.cue_out,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "TrackAnalysis | None":
        try:
            bpm = float(payload["bpm"])
            beats = [float(value) for value in payload.get("beats", [])]
            duration = float(payload.get("duration", 0.0))
            cue_in = float(payload.get("cue_in", beats[0] if beats else 0.0))
            cue_out = float(payload.get("cue_out", duration))
        except (KeyError, TypeError, ValueError):
            return None
        if bpm <= 0:
            return None
        return cls(bpm=bpm, beats=beats, duration=duration, cue_in=cue_in, cue_out=cue_out)


def _cache_dir() -> str:
    cache_dir = os.path.join(get_app_storage_dir(), _CACHE_DIR_NAME)
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir


def _cache_signature(path: str) -> tuple[int, int] | None:
    try:
        stat_result = os.stat(path)
    except OSError:
        return None
    return (int(stat_result.st_mtime), int(stat_result.st_size))


def _cache_path_for(path: str, signature: tuple[int, int]) -> str:
    digest = hashlib.sha1(
        f"{os.path.abspath(path)}|{signature[0]}|{signature[1]}|v{_CACHE_VERSION}".encode("utf-8")
    ).hexdigest()
    return os.path.join(_cache_dir(), f"{digest}.json")


def _read_cache(cache_path: str) -> TrackAnalysis | None:
    try:
        with open(cache_path, "r", encoding="utf-8") as cache_file:
            payload = json.load(cache_file)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("version") != _CACHE_VERSION:
        return None
    return TrackAnalysis.from_dict(payload)


def _write_cache(cache_path: str, analysis: TrackAnalysis) -> None:
    payload = analysis.to_dict()
    payload["version"] = _CACHE_VERSION
    try:
        with open(cache_path, "w", encoding="utf-8") as cache_file:
            json.dump(payload, cache_file)
    except OSError as exc:
        _logger.debug("Could not write Auto DJ analysis cache to %s: %s", cache_path, exc)


def analyze_track(path: str) -> TrackAnalysis | None:
    """Analyze ``path`` and return its :class:`TrackAnalysis`, or ``None``.

    Results are cached on disk keyed by the file's path + mtime + size, so the
    (potentially multi-second) librosa pass runs only once per file. Safe to
    call from a background thread; it performs no UI work.
    """

    librosa = _load_librosa()
    if librosa is None or not path:
        return None

    signature = _cache_signature(path)
    if signature is None:
        return None

    cache_path = _cache_path_for(path, signature)
    cached = _read_cache(cache_path)
    if cached is not None:
        return cached

    try:
        import numpy as np

        # 22.05 kHz mono is plenty for tempo/beat tracking and keeps the load
        # fast. ``beat_track`` returns the global tempo estimate and the beat
        # frame indices, which we convert to onset times in seconds.
        samples, sample_rate = librosa.load(path, sr=22050, mono=True)
        tempo, beat_frames = librosa.beat.beat_track(y=samples, sr=sample_rate)
        beat_times = librosa.frames_to_time(beat_frames, sr=sample_rate)
        duration = float(librosa.get_duration(y=samples, sr=sample_rate))
        rms = librosa.feature.rms(y=samples)[0]
    except Exception as exc:
        _logger.info("Auto DJ analysis failed for %s: %s", path, exc)
        return None

    try:
        # ``tempo`` may be a numpy scalar or a length-1 array depending on the
        # librosa version; normalize to a plain float.
        bpm = float(tempo if not hasattr(tempo, "__len__") else tempo[0])
    except (TypeError, ValueError, IndexError):
        return None

    if bpm <= 0:
        return None

    cue_in = _detect_cue_in(np, beat_frames, beat_times, rms, duration)
    cue_out = _detect_cue_out(np, beat_frames, beat_times, rms, duration)

    analysis = TrackAnalysis(
        bpm=bpm,
        beats=[float(value) for value in beat_times],
        duration=duration,
        cue_in=cue_in,
        cue_out=cue_out,
    )
    _write_cache(cache_path, analysis)
    return analysis


def _detect_cue_in(np, beat_frames, beat_times, rms, duration) -> float:
    """Pick the first beat where the track reaches "full" energy.

    Uses the per-beat RMS energy to skip quiet intros/build-ups so the Auto DJ
    can bring the incoming track in where the groove actually opens up, instead
    of over the intro. Falls back to the first beat when nothing stands out.
    """

    try:
        if len(beat_times) == 0:
            return 0.0
        first_beat = float(beat_times[0])
        if len(rms) == 0:
            return first_beat

        beat_indices = np.clip(beat_frames, 0, len(rms) - 1)
        beat_energy = rms[beat_indices]
        if len(beat_energy) == 0:
            return first_beat

        # 80th percentile approximates the energy of the "full" sections; the
        # intro is where the sustained energy first climbs near that level.
        reference = float(np.percentile(beat_energy, 80))
        if reference <= 0:
            return first_beat

        threshold = 0.55 * reference
        sustain = min(4, len(beat_energy))
        cue_index = 0
        for i in range(len(beat_energy)):
            if beat_energy[i] >= threshold:
                window = beat_energy[i : i + sustain]
                if float(np.mean(window)) >= threshold:
                    cue_index = i
                    break

        cue_in = float(beat_times[cue_index])
        # Safety: never cue past 40% of the track, so a mostly-quiet song does
        # not skip its entire first half.
        if duration and duration > 0:
            cue_in = min(cue_in, float(duration) * 0.4)
        return max(0.0, cue_in)
    except Exception:
        return float(beat_times[0]) if len(beat_times) else 0.0


def _detect_cue_out(np, beat_frames, beat_times, rms, duration) -> float:
    """Pick the last beat where the track still holds "full" energy.

    Symmetric to :func:`_detect_cue_in`, scanning the per-beat RMS backwards
    from the end. The Auto DJ ends its blend here — cutting off the produced
    fade-out/quiet outro that would otherwise make every transition sound like
    a plain fade regardless of beat alignment. Falls back to the track's full
    duration when nothing stands out.
    """

    fallback = float(duration) if duration and duration > 0 else (
        float(beat_times[-1]) if len(beat_times) else 0.0
    )
    try:
        if len(beat_times) == 0 or len(rms) == 0:
            return fallback

        beat_indices = np.clip(beat_frames, 0, len(rms) - 1)
        beat_energy = rms[beat_indices]
        if len(beat_energy) == 0:
            return fallback

        reference = float(np.percentile(beat_energy, 80))
        if reference <= 0:
            return fallback

        threshold = 0.55 * reference
        sustain = min(4, len(beat_energy))
        cue_index = len(beat_energy) - 1
        for i in range(len(beat_energy) - 1, -1, -1):
            if beat_energy[i] >= threshold:
                window = beat_energy[max(0, i - sustain + 1) : i + 1]
                if float(np.mean(window)) >= threshold:
                    cue_index = i
                    break

        cue_out = float(beat_times[cue_index])
        # Safety: never cut more than the final 40% of the track, so a song
        # with a long quiet ending still plays most of its body.
        if duration and duration > 0:
            cue_out = max(cue_out, float(duration) * 0.6)
            cue_out = min(cue_out, float(duration))
        return cue_out
    except Exception:
        return fallback
