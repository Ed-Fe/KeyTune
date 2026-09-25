"""Leitura das faixas de uma mídia com o ffprobe."""

from __future__ import annotations

from dataclasses import dataclass
import json
import subprocess

from ..i18n import _


PROBE_TIMEOUT_SECONDS = 30


@dataclass(frozen=True, slots=True)
class StreamInfo:
    index: int
    codec_type: str
    codec_name: str
    # Capa embutida (imagem presa a um áudio), que não é vídeo de verdade.
    attached_pic: bool = False


@dataclass(frozen=True, slots=True)
class MediaInfo:
    duration_seconds: float
    streams: tuple[StreamInfo, ...]

    @property
    def audio_streams(self):
        return tuple(stream for stream in self.streams if stream.codec_type == "audio")

    @property
    def video_streams(self):
        return tuple(
            stream for stream in self.streams if stream.codec_type == "video" and not stream.attached_pic
        )

    @property
    def cover_streams(self):
        return tuple(
            stream for stream in self.streams if stream.codec_type == "video" and stream.attached_pic
        )

    @property
    def subtitle_streams(self):
        return tuple(stream for stream in self.streams if stream.codec_type == "subtitle")


def parse_probe_output(text: str) -> MediaInfo:
    """Interpreta a saída JSON do ``ffprobe -show_streams -show_format``."""
    try:
        payload = json.loads(text)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(_("Não foi possível ler as informações do arquivo.")) from exc
    if not isinstance(payload, dict):
        raise RuntimeError(_("Não foi possível ler as informações do arquivo."))

    streams = []
    for raw_stream in payload.get("streams") or []:
        if not isinstance(raw_stream, dict):
            continue
        try:
            index = int(raw_stream.get("index"))
        except (TypeError, ValueError):
            continue
        disposition = raw_stream.get("disposition") or {}
        streams.append(
            StreamInfo(
                index=index,
                codec_type=str(raw_stream.get("codec_type") or ""),
                codec_name=str(raw_stream.get("codec_name") or ""),
                attached_pic=bool(disposition.get("attached_pic")),
            )
        )

    duration = 0.0
    try:
        duration = float((payload.get("format") or {}).get("duration") or 0)
    except (TypeError, ValueError):
        duration = 0.0
    return MediaInfo(duration_seconds=max(0.0, duration), streams=tuple(streams))


def probe_media(ffprobe_path, source_path) -> MediaInfo:
    command = [
        str(ffprobe_path),
        "-v", "error",
        "-show_streams",
        "-show_format",
        "-of", "json",
        str(source_path),
    ]
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=PROBE_TIMEOUT_SECONDS,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(_("Não foi possível ler as informações do arquivo.")) from exc

    if completed.returncode != 0:
        raise RuntimeError(_("O arquivo não pôde ser lido. Ele pode estar corrompido ou em um formato sem suporte."))
    return parse_probe_output(completed.stdout)
