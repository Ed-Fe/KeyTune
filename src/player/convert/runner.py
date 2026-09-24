"""Execução da conversão pelo FFmpeg, com progresso e cancelamento."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import subprocess
import tempfile

from .. import process_control
from ..download.ffmpeg import FFMPEG_EXECUTABLE_NAME, FFPROBE_EXECUTABLE_NAME
from ..i18n import _
from ..log import get_logger
from ..process_control import CancelToken
from .options import MODE_AUDIO_TO_VIDEO
from .plan import (
    ConvertRequest,
    build_conversion_command,
    default_output_stem,
    extract_cover_command,
    output_extension,
    unique_output_path,
)
from .probe import probe_media


_logger = get_logger(__name__)

_PROGRESS_LINE = re.compile(r"^[a-z_0-9]+=\S*$")
_ERROR_TAIL_LINES = 8
_COVER_TIMEOUT_SECONDS = 60


class ConversionCancelled(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ConversionResult:
    path: str


def parse_progress_percent(line: str, duration_seconds: float):
    """Porcentagem de uma linha ``out_time_us=...`` do ``-progress``; None se não for uma."""
    if not line.startswith("out_time_us="):
        return None
    try:
        elapsed_seconds = int(line.split("=", 1)[1]) / 1_000_000
    except ValueError:
        return None
    if duration_seconds <= 0:
        return None
    return max(0, min(100, int(elapsed_seconds * 100 / duration_seconds)))


def run_conversion(
    request: ConvertRequest,
    *,
    ffmpeg_directory,
    progress_callback=None,
    cancel_token: CancelToken | None = None,
) -> ConversionResult:
    ffmpeg_path = Path(ffmpeg_directory) / FFMPEG_EXECUTABLE_NAME
    ffprobe_path = Path(ffmpeg_directory) / FFPROBE_EXECUTABLE_NAME
    source_path = Path(request.source_path)
    if not source_path.is_file():
        raise RuntimeError(_("O arquivo de origem não foi encontrado."))

    info = probe_media(ffprobe_path, source_path)

    raw_directory = str(request.output_directory or "").strip() or str(source_path.parent)
    try:
        output_directory = Path(raw_directory).expanduser()
        output_directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RuntimeError(_("Não foi possível usar a pasta de destino escolhida.")) from exc

    output_path = unique_output_path(output_directory, default_output_stem(source_path), output_extension(request))

    with tempfile.TemporaryDirectory(prefix="keytune-convert-") as work_dir:
        cover_path = None
        if request.mode == MODE_AUDIO_TO_VIDEO and request.use_cover and info.cover_streams:
            cover_path = _extract_cover(ffmpeg_path, source_path, info.cover_streams[0], work_dir)

        command = build_conversion_command(ffmpeg_path, request, info, output_path, cover_path=cover_path)
        _logger.info("Starting conversion (%s) to %s", request.mode, output_path.suffix)
        try:
            _run_ffmpeg(command, info.duration_seconds, progress_callback, cancel_token)
        except BaseException:
            # Nunca deixa um arquivo pela metade para trás.
            _remove_quietly(output_path)
            raise

    return ConversionResult(path=str(output_path))


def _extract_cover(ffmpeg_path, source_path, cover_stream, work_dir):
    cover_path = Path(work_dir) / "cover.png"
    try:
        completed = subprocess.run(
            extract_cover_command(ffmpeg_path, source_path, cover_stream, cover_path),
            check=False,
            capture_output=True,
            timeout=_COVER_TIMEOUT_SECONDS,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    # Capa ilegível não impede a conversão: o vídeo sai com fundo preto.
    if completed.returncode != 0 or not cover_path.is_file():
        return None
    return cover_path


def _run_ffmpeg(command, duration_seconds, progress_callback, cancel_token):
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError as exc:
        raise RuntimeError(_("Não foi possível iniciar o FFmpeg.")) from exc

    if cancel_token is not None:
        cancel_token.attach(process)

    output_tail: list[str] = []
    try:
        for raw_line in process.stdout:
            line = raw_line.strip()
            if not line:
                continue
            percent = parse_progress_percent(line, duration_seconds)
            if percent is not None:
                if progress_callback is not None:
                    progress_callback(percent)
                continue
            if _PROGRESS_LINE.match(line):
                continue
            output_tail.append(line)
            del output_tail[:-_ERROR_TAIL_LINES]
        return_code = process.wait()
    finally:
        if process.poll() is None:
            process_control.terminate_process_tree(process)
            process.wait()
        if hasattr(process.stdout, "close"):
            process.stdout.close()

    if cancel_token is not None and cancel_token.cancelled:
        raise ConversionCancelled(_("Conversão cancelada."))
    if return_code != 0:
        message = output_tail[-1] if output_tail else ""
        raise RuntimeError(message or _("O FFmpeg não conseguiu converter o arquivo."))


def _remove_quietly(path: Path):
    try:
        if path.exists():
            os.remove(path)
    except OSError:
        pass
