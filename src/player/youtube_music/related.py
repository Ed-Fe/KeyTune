"""Os vídeos relacionados de um vídeo do YouTube comum (não do YouTube Music).

O rádio do YouTube Music só entende músicas: para um vídeo comum ele devolve faixas
sem relação. A coluna "A seguir" do próprio YouTube, lida pelo YouTube.js, é o que
o site e o app mostram depois do vídeo.
"""

from __future__ import annotations

from ..i18n import _
from . import youtubejs_runtime
from .account_session import optional_account_session
from .models import YouTubeMusicPlaylistContent
from .playlists import build_youtube_watch_url
from .search import normalize_youtube_entry


def youtube_related_content(video_id, fallback_title="", *, limit=50, exclude_video_ids=None):
    """Os vídeos que o YouTube sugere depois de *video_id*, prontos para uma playlist do player."""
    video_id = str(video_id or "").strip()
    if not video_id:
        raise RuntimeError(_("O vídeo do YouTube não tem videoId válido."))

    cookie_header, account_index = optional_account_session()
    entries = youtubejs_runtime.related_videos(
        build_youtube_watch_url(video_id), cookie_header=cookie_header, account_index=account_index
    )
    excluded = {str(candidate or "").strip() for candidate in (exclude_video_ids or ())}
    item_urls = []
    item_labels = []
    for entry in entries:
        result = normalize_youtube_entry(entry)
        if result is None or result.result_type != "video" or not result.playback_url:
            continue
        if result.video_id == video_id or result.video_id in excluded:
            continue
        item_urls.append(result.playback_url)
        item_labels.append(result.choice_label)
        if len(item_urls) >= limit:
            break

    return YouTubeMusicPlaylistContent(
        playlist_id="",
        title=str(fallback_title or _("Conteúdo relacionado")).strip(),
        item_urls=item_urls,
        item_labels=item_labels,
    )
