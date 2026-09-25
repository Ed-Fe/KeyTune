"""Opções da conversão de mídia: modos, formatos, qualidades e rótulos.

Módulo sem wxPython, compartilhado pelo diálogo, pelo montador de comandos do
FFmpeg e pelo fluxo da janela. Os rótulos são traduzidos na hora da chamada.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from ..constants import AUDIO_ONLY_EXTENSIONS, VIDEO_EXTENSIONS
from ..i18n import _


KIND_AUDIO = "audio"
KIND_VIDEO = "video"

MODE_AUDIO_TO_VIDEO = "audio_to_video"
MODE_VIDEO_TO_AUDIO = "video_to_audio"
MODE_AUDIO_TO_AUDIO = "audio_to_audio"
MODE_VIDEO_TO_VIDEO = "video_to_video"
MODES = (MODE_AUDIO_TO_VIDEO, MODE_VIDEO_TO_AUDIO, MODE_AUDIO_TO_AUDIO, MODE_VIDEO_TO_VIDEO)

# Tipo de mídia que cada modo aceita como origem e o que ele produz.
MODE_SOURCE_KIND = {
    MODE_AUDIO_TO_VIDEO: KIND_AUDIO,
    MODE_VIDEO_TO_AUDIO: KIND_VIDEO,
    MODE_AUDIO_TO_AUDIO: KIND_AUDIO,
    MODE_VIDEO_TO_VIDEO: KIND_VIDEO,
}
MODE_TARGET_KIND = {
    MODE_AUDIO_TO_VIDEO: KIND_VIDEO,
    MODE_VIDEO_TO_AUDIO: KIND_AUDIO,
    MODE_AUDIO_TO_AUDIO: KIND_AUDIO,
    MODE_VIDEO_TO_VIDEO: KIND_VIDEO,
}


@dataclass(frozen=True, slots=True)
class AudioFormatSpec:
    extension: str
    codec: str
    lossy: bool


AUDIO_FORMATS = {
    "mp3": AudioFormatSpec("mp3", "libmp3lame", True),
    "m4a": AudioFormatSpec("m4a", "aac", True),
    "ogg": AudioFormatSpec("ogg", "libvorbis", True),
    "opus": AudioFormatSpec("opus", "libopus", True),
    "flac": AudioFormatSpec("flac", "flac", False),
    "wav": AudioFormatSpec("wav", "pcm_s16le", False),
}
AUDIO_FORMAT_IDS = tuple(AUDIO_FORMATS)
DEFAULT_AUDIO_FORMAT = "mp3"

AUDIO_BITRATES = (128, 192, 256, 320)
DEFAULT_AUDIO_BITRATE = 192

# Formatos de vídeo gerados a partir de um áudio.
AUDIO_TO_VIDEO_FORMATS = ("mp4", "mkv", "webm")
# Formatos de destino ao trocar só o contêiner de um vídeo.
VIDEO_CONTAINER_FORMATS = ("mp4", "mkv", "webm", "avi", "mov")
DEFAULT_VIDEO_FORMAT = "mp4"

VIDEO_HEIGHTS = (1080, 720, 480)
DEFAULT_VIDEO_HEIGHT = 720


def media_kind(path) -> str:
    """Tipo de uma mídia local pela extensão: ``audio``, ``video`` ou vazio."""
    extension = os.path.splitext(str(path or ""))[1].lower()
    if extension in AUDIO_ONLY_EXTENSIONS:
        return KIND_AUDIO
    if extension in VIDEO_EXTENSIONS:
        return KIND_VIDEO
    return ""


def video_width_for_height(height: int) -> int:
    """Largura 16:9 par para a altura pedida (o H.264 exige dimensões pares)."""
    return int(round(int(height) * 16 / 9 / 2)) * 2


def mode_label(mode: str) -> str:
    return {
        MODE_AUDIO_TO_VIDEO: _("Áudio para vídeo"),
        MODE_VIDEO_TO_AUDIO: _("Vídeo para áudio"),
        MODE_AUDIO_TO_AUDIO: _("Áudio para outro formato de áudio"),
        MODE_VIDEO_TO_VIDEO: _("Vídeo para outro formato de vídeo"),
    }.get(mode, mode)


def audio_format_label(format_id: str) -> str:
    return {
        "mp3": _("MP3"),
        "m4a": _("M4A (AAC)"),
        "ogg": _("OGG (Vorbis)"),
        "opus": _("Opus"),
        "flac": _("FLAC (sem perdas)"),
        "wav": _("WAV (sem compressão)"),
    }.get(format_id, format_id)


def video_format_label(format_id: str) -> str:
    return {
        "mp4": _("MP4"),
        "mkv": _("MKV"),
        "webm": _("WebM"),
        "avi": _("AVI"),
        "mov": _("MOV"),
    }.get(format_id, format_id)


def bitrate_label(bitrate_kbps: int) -> str:
    return _("{bitrate} kbps").format(bitrate=bitrate_kbps)


def video_height_label(height: int) -> str:
    return _("{height}p").format(height=height)
