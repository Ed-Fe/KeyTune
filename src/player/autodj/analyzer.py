"""Resultado da análise de áudio usada pelo AutoDJ."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AudioAnalysis:
    bpm: float
    beats_ms: tuple[int, ...]
    confidence: float
    energy: float
    musical_key: str | None = None
    entry_ms: int | None = None
    exit_ms: int | None = None
    musical_mode: str | None = None
    key_confidence: float = 0.0
    downbeat_offset: int = 0
    phrase_boundaries_ms: tuple[int, ...] = ()
    section_boundaries_ms: tuple[int, ...] = ()
    entry_energy: float | None = None
    exit_energy: float | None = None
    loudness_db: float | None = None
    entry_vocal_probability: float = 0.0
    exit_vocal_probability: float = 0.0
    analysis_truncated: bool = False
    entry_loudness_db: float | None = None
    exit_loudness_db: float | None = None
