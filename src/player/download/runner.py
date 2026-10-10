"""Execução do download pelo yt-dlp, com progresso e cancelamento.

Separado de ``yt_dlp_runtime.download_media`` (usado pelos plugins) porque aqui
o download é longo e interativo: a saída do yt-dlp é lida linha a linha para
alimentar o progresso e o processo pode ser interrompido a qualquer momento.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
import urllib.request

from .. import process_control
from ..i18n import _
from ..log import get_logger
from ..process_control import CancelToken
from ..youtube_music.auth import sanitize_sensitive_text
from ..youtube_music.yt_dlp_runtime import find_yt_dlp_executable_path
from .plan import DownloadChoice, DownloadPlan, is_youtube_url


_logger = get_logger(__name__)

FILENAME_TEMPLATE = "%(title).200B [%(id)s].%(ext)s"
_PROBE_USER_AGENT = "Mozilla/5.0 KeyTune"


def output_template(file_stem: str = "") -> str:
    """Modelo do nome do arquivo: o nome pedido ou, sem ele, o título e o id do vídeo."""
    if not file_stem:
        return FILENAME_TEMPLATE
    # No modelo do yt-dlp, "%" é especial e precisa ser dobrado para valer como texto.
    return file_stem.replace("%", "%%") + ".%(ext)s"


PROGRESS_PREFIX = "KTP|"
RESULT_PREFIX = "KTF|"
_PROGRESS_TEMPLATE = (
    "download:" + PROGRESS_PREFIX
    + "%(progress.status)s|%(progress.downloaded_bytes)s|%(progress.total_bytes)s|%(progress.total_bytes_estimate)s"
)
_RESULT_TEMPLATE = "after_move:" + RESULT_PREFIX + "%(filepath)s|%(height)s|%(abr)s"
_ANSI_PATTERN = re.compile(r"\x1b\[[0-9;]*m")
_ERROR_TAIL_LINES = 12
# Trecho da mensagem do yt-dlp quando um item é barrado pelo --match-filter.
_FILTERED_OUT_MARKER = "does not pass filter"


class DownloadCancelled(RuntimeError):
    pass


class _EndlessStreamRefused(RuntimeError):
    """O item foi barrado pelo --match-filter."""


@dataclass(frozen=True, slots=True)
class DownloadProgress:
    downloaded_bytes: int
    total_bytes: int
    # True quando o yt-dlp terminou de baixar um arquivo e passa a processá-lo
    # (unir, converter, gravar metadados).
    finished: bool = False

    @property
    def percent(self):
        if self.total_bytes <= 0:
            return None
        return max(0, min(100, int(self.downloaded_bytes * 100 / self.total_bytes)))


@dataclass(frozen=True, slots=True)
class DownloadResult:
    paths: tuple[str, ...]
    height: int | None = None


# O token vive num módulo neutro para a conversão também poder usá-lo.
DownloadCancelToken = CancelToken


def build_command(
    executable_path,
    url,
    choice: DownloadChoice,
    plan: DownloadPlan,
    *,
    output_directory,
    ffmpeg_directory="",
    cookie_file_path="",
    http_headers=None,
    js_runtimes=None,
    file_stem="",
    allow_direct_link=False,
):
    command = [
        str(executable_path),
        "--ignore-config",
        "--encoding", "utf-8",
        "--no-playlist",
        "--newline",
        "--progress",
        "--progress-template", _PROGRESS_TEMPLATE,
        "--print", _RESULT_TEMPLATE,
        "--paths", str(output_directory),
        "--output", output_template(file_stem),
        "--force-overwrites",
        *_stream_guard_arguments(url, allow_direct_link),
        "--format", plan.format_selector,
    ]
    if ffmpeg_directory:
        command.extend(("--ffmpeg-location", str(ffmpeg_directory)))
    command.extend(plan.arguments)

    if cookie_file_path:
        command.extend(("--cookies", str(cookie_file_path)))
    for header_name, header_value in sorted((http_headers or {}).items()):
        if str(header_name).strip() and str(header_value).strip():
            command.extend(("--add-header", f"{str(header_name).strip()}:{str(header_value).strip()}"))
    for runtime_name, runtime_path in sorted((js_runtimes or {}).items()):
        runtime_argument = str(runtime_name).strip()
        if not runtime_argument:
            continue
        if str(runtime_path).strip():
            runtime_argument += f":{str(runtime_path).strip()}"
        command.extend(("--js-runtimes", runtime_argument))

    command.extend(("--", url))
    return command


def _stream_guard_arguments(url, allow_direct_link):
    """O que impede o yt-dlp de baixar algo que não termina, o que prenderia a fila."""
    if is_youtube_url(url):
        return ("--match-filter", "!is_live")
    # Fora do YouTube o endereço pode ser uma lista inteira: só o primeiro item, como no player.
    guard = ["--playlist-items", "1"]
    if allow_direct_link:
        guard.extend(("--match-filter", "!is_live"))
    else:
        # Num link direto o yt-dlp não distingue um arquivo de uma rádio: só passa o que tem duração.
        guard.extend(("--match-filter", "!is_live & duration", "--match-filter", "!is_live & !direct"))
    return tuple(guard)


def is_finite_direct_link(url, *, timeout_seconds=10) -> bool:
    """Se o servidor entrega *url* como um arquivo de tamanho conhecido, e não um stream contínuo."""
    for method in ("HEAD", "GET"):
        request = urllib.request.Request(str(url), method=method, headers={"User-Agent": _PROBE_USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                headers = response.headers
                if any(str(name).lower().startswith("icy-") for name in headers.keys()):
                    return False
                if str(headers.get("Content-Type") or "").lower().startswith("text/"):
                    return False
                return (_to_int(headers.get("Content-Length")) or 0) > 0
        except (OSError, ValueError):
            # Há servidores que recusam HEAD; o GET lê só os cabeçalhos.
            continue
    return False


def parse_progress_line(line: str) -> DownloadProgress | None:
    """Lê ``KTP|estado|baixado|total|total_estimado``; o campo ausente vem como ``NA``."""
    if not line.startswith(PROGRESS_PREFIX):
        return None
    fields = line[len(PROGRESS_PREFIX):].split("|")
    if len(fields) < 4:
        return None
    downloaded = _to_int(fields[1])
    total = _to_int(fields[2]) or _to_int(fields[3])
    if downloaded is None:
        return None
    return DownloadProgress(
        downloaded_bytes=downloaded,
        total_bytes=total or 0,
        finished=fields[0].strip() == "finished",
    )


def parse_result_line(line: str):
    """Lê ``KTF|caminho|altura|abr`` e devolve ``(caminho, altura)``."""
    if not line.startswith(RESULT_PREFIX):
        return None
    # O caminho pode conter "|"; os dois últimos campos nunca contêm.
    fields = line[len(RESULT_PREFIX):].rsplit("|", 2)
    if len(fields) != 3 or not fields[0].strip():
        return None
    return fields[0].strip(), _to_int(fields[1])


def _to_int(value):
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def run_download(url: str, choice: DownloadChoice, plan: DownloadPlan, **options) -> DownloadResult:
    try:
        return _run_download(url, choice, plan, **options)
    except _EndlessStreamRefused:
        # Barrado por não ter duração: um arquivo num link direto também não tem.
        if is_youtube_url(url) or not is_finite_direct_link(url):
            raise
    return _run_download(url, choice, plan, allow_direct_link=True, **options)


def _run_download(
    url: str,
    choice: DownloadChoice,
    plan: DownloadPlan,
    *,
    ffmpeg_directory="",
    cookie_file_path="",
    http_headers=None,
    js_runtimes=None,
    file_stem="",
    progress_callback=None,
    processing_callback=None,
    cancel_token: DownloadCancelToken | None = None,
    allow_direct_link=False,
) -> DownloadResult:
    executable_path = find_yt_dlp_executable_path()
    if executable_path is None:
        raise RuntimeError(
            _("O executável yt-dlp não está disponível. Ative os Recursos adicionais do YouTube Music "
              "ou use uma build do player que já inclua o yt-dlp.")
        )

    raw_directory = str(choice.directory or "").strip()
    if not raw_directory:
        raise RuntimeError(_("Escolha uma pasta de destino para o download."))
    try:
        output_directory = Path(raw_directory).expanduser()
        output_directory.mkdir(parents=True, exist_ok=True)
        output_directory = output_directory.resolve()
    except OSError as exc:
        raise RuntimeError(_("Não foi possível usar a pasta de download escolhida.")) from exc

    command = build_command(
        executable_path,
        url,
        choice,
        plan,
        output_directory=output_directory,
        ffmpeg_directory=ffmpeg_directory,
        cookie_file_path=cookie_file_path,
        http_headers=http_headers,
        js_runtimes=js_runtimes,
        file_stem=file_stem,
        allow_direct_link=allow_direct_link,
    )
    _logger.info("Starting download (%s) with format %s", choice.kind, plan.format_selector)

    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            # Com --print o yt-dlp manda o progresso para o stderr; juntar os
            # dois deixa um só fluxo para ler.
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError as exc:
        raise RuntimeError(_("Não foi possível iniciar o download pelo yt-dlp.")) from exc

    if cancel_token is not None:
        cancel_token.attach(process)

    downloaded_paths: list[str] = []
    downloaded_height = None
    saw_result = False
    output_tail: list[str] = []
    try:
        for raw_line in process.stdout:
            line = _ANSI_PATTERN.sub("", raw_line).strip()
            if not line:
                continue

            progress = parse_progress_line(line)
            if progress is not None:
                if progress_callback is not None:
                    progress_callback(progress)
                if progress.finished and processing_callback is not None:
                    processing_callback()
                continue

            result = parse_result_line(line)
            if result is not None:
                saw_result = True
                path, height = result
                resolved = _path_inside(output_directory, path)
                if resolved is not None:
                    downloaded_paths.append(str(resolved))
                    downloaded_height = height if height is not None else downloaded_height
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
        raise DownloadCancelled(_("Download cancelado."))
    if not saw_result and _was_filtered_out(return_code, output_tail):
        if is_youtube_url(url):
            raise _EndlessStreamRefused(_("Não é possível baixar uma transmissão ao vivo."))
        raise _EndlessStreamRefused(
            _("Não é possível baixar uma transmissão ao vivo ou contínua, como uma rádio.")
        )
    if return_code != 0 or not downloaded_paths:
        raise RuntimeError(_error_message_from_output(output_tail))
    return DownloadResult(paths=tuple(downloaded_paths), height=downloaded_height)


def _was_filtered_out(return_code, output_tail) -> bool:
    if any(_FILTERED_OUT_MARKER in line for line in output_tail):
        return True
    # Com --print o yt-dlp não diz que barrou o item: termina bem, sem arquivo e sem erro.
    return return_code == 0 and not any(line.startswith("ERROR:") for line in output_tail)


def _path_inside(directory: Path, candidate_text: str):
    candidate = Path(candidate_text)
    if not candidate.is_absolute():
        candidate = directory / candidate
    try:
        resolved = candidate.resolve()
        resolved.relative_to(directory)
    except (OSError, ValueError):
        return None
    return resolved if resolved.is_file() else None


def _error_message_from_output(output_tail) -> str:
    error_lines = [line for line in output_tail if line.startswith("ERROR:")]
    message = error_lines[-1][len("ERROR:"):].strip() if error_lines else ""
    if not message and output_tail:
        message = output_tail[-1]
    message = sanitize_sensitive_text(message)
    return message or _("O yt-dlp não conseguiu baixar a mídia.")
