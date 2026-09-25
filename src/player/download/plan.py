"""Montagem, sem efeitos colaterais, do que o yt-dlp deve baixar.

Traduz a escolha do usuário (áudio ou vídeo, qualidade, taxa de amostragem) em
seletor de formato e argumentos de pós-processamento. Sempre que a qualidade
pedida não existir, o seletor cai para a melhor disponível ("qualidade
original"), e quando falta FFmpeg o plano recua para o que o yt-dlp consegue
entregar sozinho.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

from ..i18n import _
from .options import (
    AUDIO_QUALITY_SPECS,
    DOWNLOAD_KIND_VIDEO,
    SAMPLE_RATE_ORIGINAL,
    VIDEO_QUALITY_BEST,
)


YOUTUBE_HOSTS = frozenset(
    {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"}
)


@dataclass(frozen=True, slots=True)
class DownloadChoice:
    kind: str
    audio_quality: str
    video_quality: str
    sample_rate: int
    directory: str


@dataclass(frozen=True, slots=True)
class DownloadPlan:
    format_selector: str
    arguments: tuple[str, ...]
    needs_ffmpeg: bool
    # O que o usuário pediu exigia FFmpeg, mas ele não está disponível.
    reduced_without_ffmpeg: bool


def download_source_url(media_path) -> str:
    """Devolve a URL baixável de uma mídia do YouTube ou vazio se não houver.

    Só aceita um vídeo individual: listas, buscas e referências internas
    (``ytmusic://``) não são baixadas, para nunca puxar uma playlist inteira sem
    o usuário pedir.
    """
    normalized = str(media_path or "").strip()
    parsed = urlparse(normalized)
    if parsed.scheme.lower() not in {"http", "https"}:
        return ""

    host = (parsed.netloc or "").lower()
    if host not in YOUTUBE_HOSTS:
        return ""

    if host == "youtu.be":
        return normalized if parsed.path.strip("/") else ""

    path = parsed.path.rstrip("/")
    if path == "/watch":
        return normalized if parse_qs(parsed.query).get("v") else ""
    if path.startswith(("/shorts/", "/live/", "/embed/")):
        return normalized
    return ""


def requires_ffmpeg(choice: DownloadChoice) -> bool:
    """Se o pedido depende do FFmpeg para ser atendido por completo."""
    if choice.kind == DOWNLOAD_KIND_VIDEO:
        # Vídeo em alta resolução chega separado do áudio e precisa ser unido.
        return True
    return AUDIO_QUALITY_SPECS[choice.audio_quality].converts


def build_download_plan(choice: DownloadChoice, *, ffmpeg_available: bool) -> DownloadPlan:
    needs_ffmpeg = requires_ffmpeg(choice)
    if choice.kind == DOWNLOAD_KIND_VIDEO:
        return _build_video_plan(choice, ffmpeg_available=ffmpeg_available)
    return _build_audio_plan(choice, ffmpeg_available=ffmpeg_available, needs_ffmpeg=needs_ffmpeg)


def _build_audio_plan(choice, *, ffmpeg_available, needs_ffmpeg):
    spec = AUDIO_QUALITY_SPECS[choice.audio_quality]
    selector = "bestaudio/best"
    if not ffmpeg_available:
        return DownloadPlan(selector, (), needs_ffmpeg, reduced_without_ffmpeg=needs_ffmpeg)

    arguments = ["--embed-metadata"]
    if spec.converts:
        arguments.extend(("-x", "--audio-format", spec.codec))
        if spec.bitrate_kbps:
            arguments.extend(("--audio-quality", f"{spec.bitrate_kbps}K"))
        # A taxa de amostragem só se aplica ao converter: o áudio original é
        # copiado como veio e não passa pelo FFmpeg.
        if choice.sample_rate != SAMPLE_RATE_ORIGINAL:
            arguments.extend(("--postprocessor-args", f"ExtractAudio:-ar {int(choice.sample_rate)}"))
    return DownloadPlan(selector, tuple(arguments), needs_ffmpeg, reduced_without_ffmpeg=False)


def _build_video_plan(choice, *, ffmpeg_available):
    limit = "" if choice.video_quality == VIDEO_QUALITY_BEST else f"[height<={int(choice.video_quality)}]"
    if not ffmpeg_available:
        # Sem FFmpeg só dá para baixar formatos que já trazem imagem e som.
        return DownloadPlan(f"b{limit}/b" if limit else "b", (), True, reduced_without_ffmpeg=True)

    # A última alternativa de cada grupo é a "qualidade original": se nada
    # couber no limite pedido, baixa a melhor que existir.
    selector = f"bv*{limit}+ba/b{limit}/bv*+ba/b" if limit else "bv*+ba/b"
    return DownloadPlan(
        selector,
        ("--embed-metadata", "--merge-output-format", "mp4"),
        True,
        reduced_without_ffmpeg=False,
    )


def describe_quality_difference(choice: DownloadChoice, downloaded_height) -> str:
    """Aviso para quando o vídeo baixado não tem a altura pedida; vazio se igual."""
    if choice.kind != DOWNLOAD_KIND_VIDEO or choice.video_quality == VIDEO_QUALITY_BEST:
        return ""
    if not downloaded_height or int(downloaded_height) == int(choice.video_quality):
        return ""
    return _("A qualidade {requested}p não estava disponível; o vídeo foi baixado em {actual}p.").format(
        requested=choice.video_quality,
        actual=int(downloaded_height),
    )


# Teto de itens numa só fila de download: acima disso o excedente fica de fora
# (com aviso), para um clique não virar horas de download.
MAX_BATCH_ITEMS = 200

_INVALID_FOLDER_CHARACTERS = '<>:"/\\|?*'


@dataclass(frozen=True, slots=True)
class DownloadItem:
    url: str
    title: str = ""


@dataclass(frozen=True, slots=True)
class DownloadSelection:
    items: tuple[DownloadItem, ...]
    # Itens que não são baixáveis (arquivos locais, outros sites) e ficaram de fora.
    skipped: int = 0
    # Itens baixáveis além de MAX_BATCH_ITEMS, também deixados de fora.
    truncated: int = 0


def select_download_items(entries) -> DownloadSelection:
    """Filtra ``(caminho, título)`` deixando só o que o yt-dlp baixa do YouTube.

    Repetições contam uma vez só: a mesma faixa duas vezes na lista não deve ser
    baixada duas vezes.
    """
    items: list[DownloadItem] = []
    seen: set[str] = set()
    skipped = 0
    truncated = 0
    for media_path, title in entries:
        url = download_source_url(media_path)
        if not url:
            skipped += 1
            continue
        if url in seen:
            continue
        seen.add(url)
        if len(items) >= MAX_BATCH_ITEMS:
            truncated += 1
            continue
        items.append(DownloadItem(url=url, title=str(title or "").strip()))
    return DownloadSelection(items=tuple(items), skipped=skipped, truncated=truncated)


def safe_folder_name(name, fallback="Playlist") -> str:
    """Nome de pasta válido no Windows a partir do título de uma playlist."""
    cleaned = "".join("_" if char in _INVALID_FOLDER_CHARACTERS or ord(char) < 32 else char for char in str(name or ""))
    # O Windows recusa nomes terminados em ponto ou espaço.
    cleaned = cleaned.strip().rstrip(". ")[:100].rstrip(". ")
    return cleaned or fallback


_MAX_FILE_STEM_LENGTH = 180


def download_file_stem(title) -> str:
    """Nome de arquivo (sem extensão) igual ao título mostrado no KeyTune.

    Devolve vazio quando não há um título aproveitável (ausente ou, como
    acontece sem rótulo, o próprio endereço da mídia); aí vale o nome que o
    yt-dlp escolhe.
    """
    text = " ".join(str(title or "").split())
    if not text or "://" in text or "watch?v=" in text:
        return ""
    cleaned = "".join("_" if char in _INVALID_FOLDER_CHARACTERS or ord(char) < 32 else char for char in text)
    # O Windows recusa nomes terminados em ponto ou espaço.
    return cleaned[:_MAX_FILE_STEM_LENGTH].rstrip(". ")


def unique_file_stem(stem: str, used_stems: set) -> str:
    """*stem* sem repetir um nome já usado na mesma fila (sem diferenciar maiúsculas)."""
    if not stem:
        return ""
    candidate = stem
    counter = 2
    while candidate.casefold() in used_stems:
        candidate = f"{stem} ({counter})"
        counter += 1
    used_stems.add(candidate.casefold())
    return candidate
