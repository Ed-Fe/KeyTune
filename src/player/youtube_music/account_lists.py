"""As listas do YouTube que só a conta lê: o início, Assistir mais tarde, os curtidos e os Shorts."""

from __future__ import annotations

from . import youtubejs_runtime
from .account_session import require_account_session
from .models import YouTubeResultPage
from .playlists import extract_video_id_from_text
from .search import normalize_youtube_entry


# Os identificadores que o YouTube dá às playlists fixas da conta.
WATCH_LATER_PLAYLIST_ID = "WL"
LIKED_VIDEOS_PLAYLIST_ID = "LL"


def _page(entries, has_more):
    results = [normalize_youtube_entry(entry) for entry in entries]
    return YouTubeResultPage(
        results=tuple(result for result in results if result is not None and result.result_type == "video"),
        has_more=has_more,
    )


def home_feed_page(start, count):
    """O que o YouTube recomenda à conta no início, do mais ao menos relevante."""
    cookie_header, account_index = require_account_session()
    entries, has_more = youtubejs_runtime.home_feed_page(cookie_header, start=start, count=count, account_index=account_index)
    return _page(entries, has_more)


def playlist_page(playlist_id):
    """A função de página de uma playlist que só a conta lê (``(início, quantidade)`` -> página)."""

    def fetch(start, count):
        cookie_header, account_index = require_account_session()
        entries, has_more = youtubejs_runtime.account_playlist_page(
            cookie_header, playlist_id, start=start, count=count, account_index=account_index
        )
        return _page(entries, has_more)

    return fetch


def shorts_page(start, count):
    """A sequência de Shorts que o YouTube sugere à conta."""
    cookie_header, account_index = require_account_session()
    entries, has_more = youtubejs_runtime.shorts_page(cookie_header, start=start, count=count, account_index=account_index)
    return _page(entries, has_more)


def add_to_playlist(playlist_id, media_url):
    """Põe o vídeo *media_url* na playlist da conta; ``False`` quando o YouTube não aceitou."""
    if not extract_video_id_from_text(media_url):
        return False
    cookie_header, account_index = require_account_session()
    return youtubejs_runtime.playlist_add_video(cookie_header, playlist_id, media_url, account_index=account_index)


def remove_from_playlist(playlist_id, media_url):
    """Tira o vídeo *media_url* da playlist da conta; ``False`` quando o YouTube não aceitou."""
    if not extract_video_id_from_text(media_url):
        return False
    cookie_header, account_index = require_account_session()
    return youtubejs_runtime.playlist_remove_video(cookie_header, playlist_id, media_url, account_index=account_index)
