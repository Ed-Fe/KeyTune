"""Localização e instalação opcional do FFmpeg usado pelo yt-dlp.

O FFmpeg só é necessário para converter o áudio (MP3, FLAC, taxa de
amostragem) e para unir vídeo e áudio em alta resolução. Ele é procurado
primeiro na pasta de recursos do KeyTune e só depois no sistema; quando não
existe em lugar nenhum, o usuário pode instalá-lo por aqui, a partir das builds
oficiais recomendadas pelo próprio yt-dlp, com verificação de integridade.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import platform
import shutil
import sys
import tempfile
import threading
import zipfile
from urllib import error, request

from ..constants import APP_TITLE, APP_VERSION, UPDATE_DOWNLOAD_CHUNK_SIZE, UPDATE_HTTP_TIMEOUT_SECONDS
from ..i18n import _
from ..session import get_app_storage_dir


IS_WINDOWS = sys.platform.startswith("win")
FFMPEG_EXECUTABLE_NAME = "ffmpeg.exe" if IS_WINDOWS else "ffmpeg"
FFPROBE_EXECUTABLE_NAME = "ffprobe.exe" if IS_WINDOWS else "ffprobe"
FFMPEG_PATH_ENV = "KEYTUNE_FFMPEG_PATH"
FFMPEG_BUILDS_URL = "https://github.com/yt-dlp/FFmpeg-Builds/releases/latest/download"
FFMPEG_CHECKSUMS_ASSET_NAME = "checksums.sha256"
# A variante "shared" é bem menor: os executáveis ficam finos e as bibliotecas
# vêm ao lado, na mesma pasta.
FFMPEG_ARCHIVE_TEMPLATE = "ffmpeg-master-latest-{platform}-gpl-shared.zip"
FFMPEG_APPROXIMATE_DOWNLOAD_MB = 90

_INSTALL_LOCK = threading.Lock()
_EXTRACTED_SUFFIXES = (".dll",)
_EXTRACTED_NAMES = frozenset({FFMPEG_EXECUTABLE_NAME.lower(), FFPROBE_EXECUTABLE_NAME.lower()})


class FFmpegInstallCancelled(RuntimeError):
    pass


def get_managed_ffmpeg_dir() -> Path:
    return Path(get_app_storage_dir()) / "resources" / "ffmpeg" / "bin"


def _directory_has_ffmpeg(directory: Path) -> bool:
    # O yt-dlp usa o ffprobe para reconhecer o áudio antes de convertê-lo.
    return (directory / FFMPEG_EXECUTABLE_NAME).is_file() and (directory / FFPROBE_EXECUTABLE_NAME).is_file()


def find_ffmpeg_directory() -> Path | None:
    """Pasta com ffmpeg e ffprobe, na ordem: variável de ambiente, recursos do
    KeyTune, ao lado do executável e, por fim, o PATH do sistema."""
    candidates: list[Path] = []

    env_override = str(os.environ.get(FFMPEG_PATH_ENV) or "").strip()
    if env_override:
        override_path = Path(env_override)
        candidates.append(override_path if override_path.is_dir() else override_path.parent)

    candidates.append(get_managed_ffmpeg_dir())
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent)

    path_match = shutil.which("ffmpeg")
    if path_match:
        candidates.append(Path(path_match).resolve().parent)

    for candidate in candidates:
        try:
            if _directory_has_ffmpeg(candidate):
                return candidate
        except OSError:
            continue
    return None


def ffmpeg_available() -> bool:
    return find_ffmpeg_directory() is not None


def ffmpeg_install_supported() -> bool:
    """A instalação automática só existe para Windows; nos demais sistemas o
    FFmpeg vem do gerenciador de pacotes."""
    return IS_WINDOWS


def _archive_asset_name() -> str:
    machine = platform.machine().strip().lower()
    platform_label = "winarm64" if machine in {"arm64", "aarch64"} else "win64"
    return FFMPEG_ARCHIVE_TEMPLATE.format(platform=platform_label)


def install_managed_ffmpeg(*, progress_callback=None, cancel_event: threading.Event | None = None) -> Path:
    """Baixa, confere e instala o FFmpeg na pasta de recursos do KeyTune.

    *progress_callback* recebe ``(bytes_baixados, bytes_totais)``. Devolve a
    pasta onde ``ffmpeg`` e ``ffprobe`` ficaram.
    """
    if not ffmpeg_install_supported():
        raise RuntimeError(_("A instalação automática do FFmpeg só está disponível no Windows."))

    asset_name = _archive_asset_name()
    target_dir = get_managed_ffmpeg_dir()

    with _INSTALL_LOCK:
        if _directory_has_ffmpeg(target_dir):
            return target_dir

        work_dir = Path(tempfile.mkdtemp(prefix="keytune-ffmpeg-"))
        try:
            archive_path = work_dir / asset_name
            _download_file(
                f"{FFMPEG_BUILDS_URL}/{asset_name}",
                archive_path,
                progress_callback=progress_callback,
                cancel_event=cancel_event,
            )
            checksums_path = work_dir / FFMPEG_CHECKSUMS_ASSET_NAME
            _download_file(f"{FFMPEG_BUILDS_URL}/{FFMPEG_CHECKSUMS_ASSET_NAME}", checksums_path)

            expected = expected_checksum(checksums_path.read_text(encoding="utf-8"), asset_name)
            if _sha256(archive_path).casefold() != expected.casefold():
                raise RuntimeError(_("O FFmpeg baixado não passou na validação de integridade."))

            staging_dir = work_dir / "bin"
            _extract_binaries(archive_path, staging_dir)
            if not _directory_has_ffmpeg(staging_dir):
                raise RuntimeError(_("O pacote do FFmpeg veio sem os executáveis esperados."))

            _replace_directory(staging_dir, target_dir)
            return target_dir
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)


def expected_checksum(checksums_text: str, asset_name: str) -> str:
    """Lê o SHA-256 de *asset_name* em um arquivo no formato ``hash  arquivo``."""
    for line in str(checksums_text or "").splitlines():
        parts = line.strip().split()
        if len(parts) >= 2 and parts[-1].lstrip("*") == asset_name and len(parts[0]) == 64:
            return parts[0]
    raise RuntimeError(_("Não foi possível localizar o checksum oficial do FFmpeg baixado."))


def _download_file(url: str, destination: Path, *, progress_callback=None, cancel_event=None) -> None:
    download_request = request.Request(
        url,
        headers={"Accept": "application/octet-stream", "User-Agent": f"{APP_TITLE}/{APP_VERSION}"},
    )
    try:
        with request.urlopen(download_request, timeout=max(10, UPDATE_HTTP_TIMEOUT_SECONDS)) as response:
            total = int(response.headers.get("Content-Length") or 0)
            downloaded = 0
            with open(destination, "wb") as target_file:
                while True:
                    if cancel_event is not None and cancel_event.is_set():
                        raise FFmpegInstallCancelled(_("A instalação do FFmpeg foi cancelada."))
                    chunk = response.read(UPDATE_DOWNLOAD_CHUNK_SIZE)
                    if not chunk:
                        break
                    target_file.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback is not None:
                        progress_callback(downloaded, total)
    except (error.HTTPError, error.URLError, OSError) as exc:
        raise RuntimeError(_("Não foi possível baixar o FFmpeg. Verifique a conexão e tente novamente.")) from exc


def _sha256(file_path: Path) -> str:
    digest = hashlib.sha256()
    with open(file_path, "rb") as source_file:
        for chunk in iter(lambda: source_file.read(UPDATE_DOWNLOAD_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _extract_binaries(archive_path: Path, destination: Path) -> None:
    """Extrai só ffmpeg, ffprobe e as DLLs da pasta ``bin`` do pacote.

    Usa apenas o nome do arquivo de cada entrada, então nada do pacote consegue
    escrever fora de *destination*.
    """
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue
            parts = member.filename.replace("\\", "/").split("/")
            if len(parts) < 2 or parts[-2] != "bin":
                continue
            name = parts[-1]
            lowered = name.lower()
            if lowered not in _EXTRACTED_NAMES and not lowered.endswith(_EXTRACTED_SUFFIXES):
                continue
            with archive.open(member) as source, open(destination / name, "wb") as target:
                shutil.copyfileobj(source, target, length=UPDATE_DOWNLOAD_CHUNK_SIZE)


def _replace_directory(staging_dir: Path, target_dir: Path) -> None:
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    if target_dir.exists():
        shutil.rmtree(target_dir, ignore_errors=True)
    shutil.move(str(staging_dir), str(target_dir))
