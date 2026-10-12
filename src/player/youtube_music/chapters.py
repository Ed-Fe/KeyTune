"""Os capítulos de um vídeo do YouTube, para ir direto a um deles."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..log import get_logger
from . import youtubejs_runtime
from .dependencies import youtubejs_resolver_enabled


_logger = get_logger(__name__)

# "0:00 Introdução", "1:02:03 - Final": o que o YouTube lê na descrição como capítulo.
_DESCRIPTION_CHAPTER = re.compile(r"^\s*(?:(\d{1,2}):)?(\d{1,2}):(\d{2})\s*[-–—:.)]*\s*(.+?)\s*$")
_MINIMUM_DESCRIPTION_CHAPTERS = 3


@dataclass(frozen=True)
class YouTubeChapter:
    title: str
    start_seconds: int


def chapters_from_description(description):
    """Os capítulos que a *description* marca; o YouTube exige o primeiro em 0:00 e três ao todo."""
    chapters = []
    for line in str(description or "").splitlines():
        match = _DESCRIPTION_CHAPTER.match(line)
        if match is None:
            continue
        hours, minutes, seconds, title = match.groups()
        chapters.append(YouTubeChapter(title, int(hours or 0) * 3600 + int(minutes) * 60 + int(seconds)))
    if len(chapters) < _MINIMUM_DESCRIPTION_CHAPTERS or chapters[0].start_seconds != 0:
        return []
    starts = [chapter.start_seconds for chapter in chapters]
    return chapters if starts == sorted(set(starts)) else []


def media_chapters(media_url, description_loader=None):
    """Os capítulos de *media_url*, em ordem; lista vazia quando o vídeo não os tem."""
    media_url = str(media_url or "").strip()
    if youtubejs_resolver_enabled():
        try:
            entries, _automatic = youtubejs_runtime.media_chapters(media_url)
            chapters = [
                YouTubeChapter(str(entry.get("title") or "").strip(), int(entry.get("start_seconds") or 0))
                for entry in entries
                if str(entry.get("title") or "").strip()
            ]
            if chapters:
                return chapters
        except Exception as exc:
            _logger.warning("O YouTube.js não trouxe os capítulos; lendo a descrição: %s", exc)
    if description_loader is None:
        from .details import media_details

        def description_loader(url):
            return media_details(url).description

    return chapters_from_description(description_loader(media_url))
