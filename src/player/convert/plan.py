"""Montagem, sem efeitos colaterais, dos comandos do FFmpeg de cada conversão."""

from __future__ import annotations

from dataclasses import dataclass, replace
import os
from pathlib import Path

from ..download.options import SAMPLE_RATE_ORIGINAL
from ..i18n import _
from .options import (
    AUDIO_FORMATS,
    DEFAULT_AUDIO_BITRATE,
    DEFAULT_VIDEO_HEIGHT,
    KIND_AUDIO,
    KIND_VIDEO,
    MODE_AUDIO_TO_AUDIO,
    MODE_AUDIO_TO_VIDEO,
    MODE_SOURCE_KIND,
    MODE_VIDEO_TO_AUDIO,
    MODE_VIDEO_TO_VIDEO,
    media_kind,
    video_width_for_height,
)
from .probe import MediaInfo, StreamInfo


@dataclass(frozen=True, slots=True)
class ConvertRequest:
    mode: str
    source_path: str
    output_directory: str
    # Formato de áudio (mp3, flac...) ou de contêiner (mp4, mkv...), conforme o modo.
    target_format: str
    audio_bitrate_kbps: int = DEFAULT_AUDIO_BITRATE
    sample_rate: int = SAMPLE_RATE_ORIGINAL
    video_height: int = DEFAULT_VIDEO_HEIGHT
    # Áudio para vídeo: usar a capa embutida como imagem, quando existir.
    use_cover: bool = True


# Formatos de áudio que aceitam uma capa embutida ao converter áudio para áudio.
_COVER_CAPABLE_AUDIO_FORMATS = frozenset({"mp3", "m4a", "flac"})
_STILL_FRAME_RATE = 10

# Codecs que cada contêiner aceita sem recodificar; None aceita qualquer um.
_COPYABLE_VIDEO_CODECS = {
    "mp4": {"h264", "hevc", "av1", "mpeg4", "vp9"},
    "mov": {"h264", "hevc", "mpeg4", "prores", "mjpeg"},
    "mkv": None,
    "webm": {"vp8", "vp9", "av1"},
    "avi": {"h264", "mpeg4", "mjpeg", "msmpeg4v3", "mpeg2video"},
}
_COPYABLE_AUDIO_CODECS = {
    "mp4": {"aac", "mp3", "ac3", "eac3", "opus", "alac", "flac"},
    "mov": {"aac", "mp3", "ac3", "alac", "pcm_s16le", "pcm_s24le"},
    "mkv": None,
    "webm": {"vorbis", "opus"},
    "avi": {"mp3", "ac3", "pcm_s16le"},
}
_REENCODE_VIDEO_ARGS = {
    "webm": ("libvpx-vp9", "-crf", "32", "-b:v", "0", "-row-mt", "1"),
}
_DEFAULT_REENCODE_VIDEO_ARGS = ("libx264", "-crf", "20", "-preset", "medium", "-pix_fmt", "yuv420p")
_REENCODE_AUDIO_ARGS = {
    "webm": ("libopus", "-b:a", "128k"),
    "avi": ("libmp3lame", "-b:a", "192k"),
}
_DEFAULT_REENCODE_AUDIO_ARGS = ("aac", "-b:a", "192k")


def _base_command(ffmpeg_path) -> list[str]:
    return [
        str(ffmpeg_path),
        "-hide_banner",
        "-nostdin",
        "-loglevel", "error",
        "-nostats",
        # Progresso em linhas chave=valor no stdout, fácil de ler.
        "-progress", "pipe:1",
    ]


def unique_output_path(directory, stem: str, extension: str) -> Path:
    """Caminho livre em *directory*: ``nome.ext``, ``nome (1).ext``, ..."""
    directory = Path(directory)
    candidate = directory / f"{stem}.{extension}"
    counter = 1
    while candidate.exists():
        candidate = directory / f"{stem} ({counter}).{extension}"
        counter += 1
    return candidate


def default_output_stem(source_path) -> str:
    return os.path.splitext(os.path.basename(str(source_path)))[0] or "conversao"


def extract_cover_command(ffmpeg_path, source_path, cover_stream: StreamInfo, cover_path) -> list[str]:
    return [
        *_base_command(ffmpeg_path),
        "-i", str(source_path),
        "-map", f"0:{cover_stream.index}",
        "-frames:v", "1",
        str(cover_path),
    ]


def build_conversion_command(
    ffmpeg_path,
    request: ConvertRequest,
    info: MediaInfo,
    output_path,
    *,
    cover_path=None,
) -> list[str]:
    if request.mode in (MODE_AUDIO_TO_AUDIO, MODE_VIDEO_TO_AUDIO):
        return _build_audio_command(ffmpeg_path, request, info, output_path)
    if request.mode == MODE_AUDIO_TO_VIDEO:
        return _build_audio_to_video_command(ffmpeg_path, request, info, output_path, cover_path)
    if request.mode == MODE_VIDEO_TO_VIDEO:
        return _build_video_to_video_command(ffmpeg_path, request, info, output_path)
    raise ValueError(f"Modo de conversão desconhecido: {request.mode}")


def _audio_codec_args(format_id: str, bitrate_kbps: int, sample_rate: int) -> list[str]:
    spec = AUDIO_FORMATS[format_id]
    arguments = ["-c:a", spec.codec]
    if spec.lossy:
        arguments.extend(("-b:a", f"{int(bitrate_kbps)}k"))
    # O Opus só trabalha em 48 kHz (e submúltiplos): o FFmpeg reamostra sozinho
    # e recusaria a taxa pedida, então ela não é repassada.
    if sample_rate != SAMPLE_RATE_ORIGINAL and format_id != "opus":
        arguments.extend(("-ar", str(int(sample_rate))))
    return arguments


def _first_audio_stream(info: MediaInfo) -> StreamInfo:
    audio_streams = info.audio_streams
    if not audio_streams:
        raise RuntimeError(_("Este arquivo não tem faixa de áudio para converter."))
    return audio_streams[0]


def _build_audio_command(ffmpeg_path, request, info, output_path):
    audio_stream = _first_audio_stream(info)
    command = [*_base_command(ffmpeg_path), "-i", str(request.source_path), "-map", f"0:{audio_stream.index}"]

    # A capa só acompanha a conversão de áudio para áudio: num vídeo, a imagem
    # "de verdade" viraria uma capa gigante e sem sentido.
    if (
        request.mode == MODE_AUDIO_TO_AUDIO
        and request.target_format in _COVER_CAPABLE_AUDIO_FORMATS
        and info.cover_streams
    ):
        command.extend(("-map", f"0:{info.cover_streams[0].index}", "-c:v", "copy"))
        command.extend(("-disposition:v:0", "attached_pic"))
        if request.target_format == "mp3":
            command.extend(("-id3v2_version", "3"))

    command.extend(("-map_metadata", "0"))
    command.extend(_audio_codec_args(request.target_format, request.audio_bitrate_kbps, request.sample_rate))
    command.append(str(output_path))
    return command


def _build_audio_to_video_command(ffmpeg_path, request, info, output_path, cover_path):
    audio_stream = _first_audio_stream(info)
    height = int(request.video_height)
    width = video_width_for_height(height)
    fps = _STILL_FRAME_RATE

    command = _base_command(ffmpeg_path)
    if cover_path:
        command.extend(("-loop", "1", "-framerate", str(fps), "-i", str(cover_path)))
    else:
        command.extend(("-f", "lavfi", "-i", f"color=c=black:s={width}x{height}:r={fps}"))
    command.extend(("-i", str(request.source_path)))
    command.extend(("-map", "0:v:0", "-map", f"1:{audio_stream.index}", "-map_metadata", "1"))
    # A imagem cabe inteira no quadro, com faixas pretas nas sobras.
    command.extend(
        (
            "-vf",
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,format=yuv420p",
            "-r", str(fps),
        )
    )
    if request.target_format == "webm":
        command.extend(
            ("-c:v", "libvpx-vp9", "-crf", "35", "-b:v", "0", "-deadline", "realtime", "-cpu-used", "8")
        )
        command.extend(("-g", str(fps), "-c:a", "libopus", "-b:a", "160k"))
    else:
        command.extend(("-c:v", "libx264", "-tune", "stillimage", "-preset", "veryfast", "-crf", "23"))
        command.extend(("-g", str(fps), "-c:a", "aac", "-b:a", "192k"))
        if request.target_format == "mp4":
            command.extend(("-movflags", "+faststart"))
    # A imagem se repete sem fim: o áudio dita a duração do vídeo.
    command.extend(("-shortest", str(output_path)))
    return command


def _can_copy(stream: StreamInfo, container: str) -> bool:
    table = _COPYABLE_VIDEO_CODECS if stream.codec_type == "video" else _COPYABLE_AUDIO_CODECS
    allowed = table.get(container)
    return allowed is None or stream.codec_name in allowed


def _build_video_to_video_command(ffmpeg_path, request, info, output_path):
    container = request.target_format
    video_streams = info.video_streams
    if not video_streams:
        raise RuntimeError(_("Este arquivo não tem faixa de vídeo para converter."))

    command = [*_base_command(ffmpeg_path), "-i", str(request.source_path)]
    selected = [*video_streams, *info.audio_streams]
    if container == "mkv":
        # O Matroska guarda qualquer legenda como está.
        selected.extend(info.subtitle_streams)

    for output_index, stream in enumerate(selected):
        command.extend(("-map", f"0:{stream.index}"))
        if stream.codec_type == "subtitle" or _can_copy(stream, container):
            command.extend((f"-c:{output_index}", "copy"))
            # O Apple/QuickTime só reconhece HEVC marcado como hvc1.
            if stream.codec_name == "hevc" and container in ("mp4", "mov"):
                command.extend((f"-tag:{output_index}", "hvc1"))
        elif stream.codec_type == "video":
            encoder, *encoder_args = _REENCODE_VIDEO_ARGS.get(container, _DEFAULT_REENCODE_VIDEO_ARGS)
            command.extend((f"-c:{output_index}", encoder, *encoder_args))
        else:
            encoder, *encoder_args = _REENCODE_AUDIO_ARGS.get(container, _DEFAULT_REENCODE_AUDIO_ARGS)
            command.extend((f"-c:{output_index}", encoder, *encoder_args))

    command.extend(("-map_metadata", "0"))
    if container in ("mp4", "mov"):
        command.extend(("-movflags", "+faststart"))
    command.append(str(output_path))
    return command


def output_extension(request: ConvertRequest) -> str:
    if request.mode in (MODE_AUDIO_TO_AUDIO, MODE_VIDEO_TO_AUDIO):
        return AUDIO_FORMATS[request.target_format].extension
    return request.target_format


def modes_for_sources(source_paths) -> dict[str, int]:
    """Quantos arquivos cada modo de conversão consegue tratar, sem os que ficam a zero."""
    audio_count = sum(1 for path in source_paths if media_kind(path) == KIND_AUDIO)
    video_count = sum(1 for path in source_paths if media_kind(path) == KIND_VIDEO)
    counts = {
        MODE_AUDIO_TO_AUDIO: audio_count,
        MODE_AUDIO_TO_VIDEO: audio_count,
        MODE_VIDEO_TO_AUDIO: video_count,
        MODE_VIDEO_TO_VIDEO: video_count,
    }
    return {mode: count for mode, count in counts.items() if count}


def build_batch_requests(template: ConvertRequest, source_paths, *, same_folder: bool):
    """Um pedido por arquivo a partir de *template*; devolve ``(pedidos, ignorados)``.

    Ignora o que não é do tipo que o modo converte e, ao trocar só o contêiner
    de um vídeo, o que já está no formato de destino.
    """
    requests = []
    skipped = 0
    for path in source_paths:
        if media_kind(path) != MODE_SOURCE_KIND[template.mode]:
            skipped += 1
            continue
        extension = os.path.splitext(str(path))[1].lstrip(".").lower()
        if template.mode == MODE_VIDEO_TO_VIDEO and extension == template.target_format:
            skipped += 1
            continue
        output_directory = os.path.dirname(str(path)) if same_folder else template.output_directory
        requests.append(replace(template, source_path=str(path), output_directory=output_directory))
    return tuple(requests), skipped
