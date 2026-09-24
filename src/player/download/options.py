"""Opções de download: identificadores, padrões e rótulos.

Módulo sem wxPython, para que as preferências, o diálogo de download e o
montador de comandos do yt-dlp compartilhem a mesma tabela de opções. Os rótulos
são traduzidos na hora da chamada (não na importação), porque o idioma já está
ativo quando a interface os pede.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..i18n import _


DOWNLOAD_KIND_AUDIO = "audio"
DOWNLOAD_KIND_VIDEO = "video"
DOWNLOAD_KINDS = (DOWNLOAD_KIND_AUDIO, DOWNLOAD_KIND_VIDEO)

# "original" mantém o áudio como o YouTube o entrega (sem recodificar, sem FFmpeg).
AUDIO_QUALITY_ORIGINAL = "original"


@dataclass(frozen=True, slots=True)
class AudioQualitySpec:
    # Codec de destino do yt-dlp (--audio-format); vazio mantém o original.
    codec: str = ""
    # Taxa de bits em kbps, só para codecs com perdas; 0 quando não se aplica.
    bitrate_kbps: int = 0

    @property
    def converts(self):
        return bool(self.codec)


AUDIO_QUALITY_SPECS = {
    AUDIO_QUALITY_ORIGINAL: AudioQualitySpec(),
    "mp3_320": AudioQualitySpec("mp3", 320),
    "mp3_256": AudioQualitySpec("mp3", 256),
    "mp3_192": AudioQualitySpec("mp3", 192),
    "mp3_128": AudioQualitySpec("mp3", 128),
    "flac": AudioQualitySpec("flac", 0),
}
AUDIO_QUALITIES = tuple(AUDIO_QUALITY_SPECS)

# "best" não limita a altura: baixa a maior resolução que o vídeo oferecer.
VIDEO_QUALITY_BEST = "best"
VIDEO_HEIGHTS = (2160, 1440, 1080, 720, 480, 360, 240, 144)
VIDEO_QUALITIES = (VIDEO_QUALITY_BEST, *(str(height) for height in VIDEO_HEIGHTS))

# 0 mantém a taxa de amostragem do arquivo baixado. O YouTube entrega 44,1 kHz
# ou 48 kHz, então taxas maiores só inflariam o arquivo sem ganho de qualidade.
SAMPLE_RATE_ORIGINAL = 0
SAMPLE_RATES = (SAMPLE_RATE_ORIGINAL, 44100, 48000)

DEFAULT_DOWNLOAD_KIND = DOWNLOAD_KIND_AUDIO
DEFAULT_DOWNLOAD_AUDIO_QUALITY = AUDIO_QUALITY_ORIGINAL
DEFAULT_DOWNLOAD_VIDEO_QUALITY = VIDEO_QUALITY_BEST
DEFAULT_DOWNLOAD_SAMPLE_RATE = SAMPLE_RATE_ORIGINAL
DEFAULT_DOWNLOAD_ALWAYS_ASK = True


def default_download_directory() -> str:
    """Pasta usada enquanto o usuário não escolher outra: Downloads/KeyTune."""
    return str(Path.home() / "Downloads" / "KeyTune")


def resolve_download_directory(configured_directory) -> str:
    return str(configured_directory or "").strip() or default_download_directory()


def download_kind_label(kind: str) -> str:
    return {
        DOWNLOAD_KIND_AUDIO: _("Áudio"),
        DOWNLOAD_KIND_VIDEO: _("Vídeo"),
    }.get(kind, kind)


def audio_quality_label(quality: str) -> str:
    if quality == AUDIO_QUALITY_ORIGINAL:
        return _("Original (sem conversão)")
    if quality == "flac":
        return _("FLAC (sem perdas)")
    spec = AUDIO_QUALITY_SPECS.get(quality)
    if spec is not None and spec.codec == "mp3":
        return _("MP3 {bitrate} kbps").format(bitrate=spec.bitrate_kbps)
    return quality


def video_quality_label(quality: str) -> str:
    if quality == VIDEO_QUALITY_BEST:
        return _("Melhor disponível")
    return _("{height}p").format(height=quality)


def sample_rate_label(sample_rate: int) -> str:
    if sample_rate == SAMPLE_RATE_ORIGINAL:
        return _("Original")
    return _("{rate} Hz").format(rate=sample_rate)


def normalize_download_kind(value, fallback=DEFAULT_DOWNLOAD_KIND) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in DOWNLOAD_KINDS else fallback


def normalize_audio_quality(value, fallback=DEFAULT_DOWNLOAD_AUDIO_QUALITY) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in AUDIO_QUALITY_SPECS else fallback


def normalize_video_quality(value, fallback=DEFAULT_DOWNLOAD_VIDEO_QUALITY) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in VIDEO_QUALITIES else fallback


def normalize_sample_rate(value, fallback=DEFAULT_DOWNLOAD_SAMPLE_RATE) -> int:
    try:
        numeric_value = int(value)
    except (TypeError, ValueError):
        return fallback
    return numeric_value if numeric_value in SAMPLE_RATES else fallback
