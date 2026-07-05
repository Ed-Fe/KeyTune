from __future__ import annotations

from ..i18n import _
from .models import YOUTUBE_SEARCH_SOURCE_MUSIC, YouTubeMediaSearchResult


# ``YTMusic.get_charts`` groups the top playlists in several sections.  The
# ``daily``/``weekly`` sections replace ``videos`` for premium accounts, while
# ``genres`` is only present for the United States.  Each entry is rendered as
# an openable playlist result so it flows through the existing search-results
# list, playback, and "save to library" paths unchanged.
_CHART_SECTION_BADGES = (
    ("daily", _("Em alta · diário")),
    ("weekly", _("Em alta · semanal")),
    ("videos", _("Em alta · vídeos")),
    ("genres", _("Em alta · gênero")),
)


def normalize_chart_results(raw_charts):
    """Convert a ``get_charts`` response into openable playlist results."""
    if not isinstance(raw_charts, dict):
        return []

    results = []
    seen_playlist_ids = set()
    for section_key, badge in _CHART_SECTION_BADGES:
        for item in raw_charts.get(section_key) or []:
            normalized_result = _normalize_chart_playlist(item, badge=badge)
            if normalized_result is None:
                continue
            if normalized_result.playlist_id in seen_playlist_ids:
                continue
            results.append(normalized_result)
            seen_playlist_ids.add(normalized_result.playlist_id)

    return results


def _normalize_chart_playlist(item, *, badge):
    if not isinstance(item, dict):
        return None

    playlist_id = str(item.get("playlistId") or "").strip()
    title = str(item.get("title") or "").strip()
    if not playlist_id or not title:
        return None

    return YouTubeMediaSearchResult(
        source=YOUTUBE_SEARCH_SOURCE_MUSIC,
        result_type="playlist",
        title=title,
        playlist_id=playlist_id,
        source_badge=badge,
    )
