"""O histórico do YouTube da conta: a lista do que foi assistido e o registro de um vídeo nele.

O histórico do YouTube Music é lido e escrito pelo ytmusicapi (``feedback_manager``).
Os vídeos do YouTube comum passam por aqui, pelo YouTube.js com os cookies da conta.
"""

from __future__ import annotations

from . import youtubejs_runtime
from .account_session import optional_account_session, require_account_session
from .models import YouTubeResultPage
from .playlists import extract_video_id_from_text
from .search import normalize_youtube_entry


def watch_history_page(start, count):
    """Os vídeos do histórico do YouTube da conta, do mais recente para o mais antigo."""
    cookie_header, account_index = require_account_session()
    entries, has_more = youtubejs_runtime.watch_history_page(
        cookie_header, start=start, count=count, account_index=account_index
    )
    results = [normalize_youtube_entry(entry) for entry in entries]
    return YouTubeResultPage(results=tuple(result for result in results if result is not None), has_more=has_more)


def report_video_watched(media_url):
    """Põe o vídeo *media_url* no histórico do YouTube da conta; ``False`` sem conta ou sem YouTube.js."""
    media_url = str(media_url or "").strip()
    if not extract_video_id_from_text(media_url):
        return False
    cookie_header, account_index = optional_account_session()
    if not cookie_header:
        return False
    return youtubejs_runtime.add_to_watch_history(cookie_header, media_url, account_index=account_index)


def report_watch_position(media_url, position_seconds):
    """Diz ao YouTube até onde a conta assistiu *media_url*, para continuar em outro aparelho.

    ``False`` sem conta, sem YouTube.js ou quando *media_url* não é um vídeo do YouTube.
    """
    media_url = str(media_url or "").strip()
    if not extract_video_id_from_text(media_url):
        return False
    cookie_header, account_index = optional_account_session()
    if not cookie_header:
        return False
    return youtubejs_runtime.update_watch_time(
        cookie_header, media_url, position_seconds, account_index=account_index
    )
