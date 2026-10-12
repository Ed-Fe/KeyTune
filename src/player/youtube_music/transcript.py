"""A transcrição de um vídeo do YouTube: a legenda lida como texto, com o tempo de cada fala.

O YouTube.js não alcança o texto das legendas sem um token que o YouTube exige; o
yt-dlp sabe pedi-lo, então é ele que lista as legendas e dá o endereço de cada uma.
"""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass

from ..i18n import _
from .content_locale import content_language
from .dependencies import ensure_yt_dlp_executable_available
from .search import _clean_external_tool_error
from .yt_dlp_runtime import extract_info as extract_yt_dlp_info


SOCKET_TIMEOUT_SECONDS = 20


@dataclass(frozen=True)
class TranscriptLine:
    start_seconds: int
    text: str


@dataclass(frozen=True)
class YouTubeTranscript:
    language: str
    automatic: bool
    lines: tuple


def _language_preferences(video_language):
    """Os códigos de idioma que valem, do mais ao menos desejado."""
    wanted = []
    for code in (content_language(), video_language, "en"):
        code = str(code or "").strip()
        if not code:
            continue
        for candidate in (code, code.split("-")[0]):
            if candidate and candidate not in wanted:
                wanted.append(candidate)
    return wanted


def _json3_url(entries):
    for entry in entries or []:
        if entry.get("ext") == "json3" and entry.get("url"):
            return entry["url"]
    return ""


def _pick_track(info):
    """``(idioma, url, automática)`` da melhor legenda do vídeo, ou ``None``.

    A do autor no idioma do usuário vem primeiro; depois a gerada no idioma original
    do vídeo (``xx-orig``) e, por fim, a automática já traduzida para o idioma dele.
    """
    manual = info.get("subtitles") or {}
    automatic = info.get("automatic_captions") or {}
    preferences = [language.casefold() for language in _language_preferences(info.get("language"))]

    def matches(code, language):
        code = code.casefold()
        return code == language or code.startswith(language + "-")

    for language in preferences:
        for code, entries in manual.items():
            url = _json3_url(entries)
            if url and matches(code, language):
                return code, url, False
    for code, entries in automatic.items():
        url = _json3_url(entries)
        if url and code.endswith("-orig"):
            return code, url, True
    for language in preferences:
        for code, entries in automatic.items():
            url = _json3_url(entries)
            if url and matches(code, language):
                return code, url, True
    return None


def parse_json3(payload):
    """As falas de uma legenda no formato json3 do YouTube."""
    lines = []
    for event in (payload or {}).get("events") or []:
        segments = event.get("segs")
        if not segments:
            continue
        text = "".join(str(segment.get("utf8") or "") for segment in segments).replace("\n", " ").strip()
        if not text:
            continue
        lines.append(TranscriptLine(int(event.get("tStartMs") or 0) // 1000, text))
    return lines


def media_transcript(media_url):
    """A transcrição de *media_url*; erro com o motivo quando o vídeo não tem legenda."""
    ensure_yt_dlp_executable_available()
    try:
        info = extract_yt_dlp_info(
            str(media_url or "").strip(),
            noplaylist=True,
            ignore_no_formats_error=True,
            socket_timeout_seconds=SOCKET_TIMEOUT_SECONDS,
            quiet=True,
            no_warnings=True,
        ).data
    except Exception as exc:
        raise RuntimeError(
            _clean_external_tool_error(exc) or _("O yt-dlp não conseguiu consultar as legendas do vídeo.")
        ) from exc

    track = _pick_track(info or {})
    if track is None:
        raise RuntimeError(_("Este vídeo não tem legenda no seu idioma, nem no idioma original, para transcrever."))
    language, url, automatic = track
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(request, timeout=SOCKET_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except Exception as exc:
        raise RuntimeError(_("Não foi possível baixar a legenda do vídeo.")) from exc

    lines = parse_json3(payload)
    if not lines:
        raise RuntimeError(_("A legenda deste vídeo veio vazia."))
    return YouTubeTranscript(language=language, automatic=automatic, lines=tuple(lines))


def format_clock(total_seconds):
    total_seconds = max(0, int(total_seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"


def transcript_reading_text(transcript):
    """O texto da caixa de leitura: um aviso curto e uma fala por linha, com o tempo dela."""
    origin = _("legenda automática") if transcript.automatic else _("legenda do autor")
    header = _("Transcrição ({origin}, {language}).").format(origin=origin, language=transcript.language)
    body = "\n".join(f"{format_clock(line.start_seconds)}  {line.text}" for line in transcript.lines)
    return header + "\n\n" + body
