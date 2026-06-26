from .browse import (
    extract_browse_playlists_from_response,
    normalize_mood_categories,
    normalize_mood_playlists,
    normalize_track_items,
)
from .charts import normalize_chart_results
from .models import YouTubeMusicPlaylistContent, YouTubeMusicPlaylistSummary, get_search_scope_option
from .playlists import (
    extract_personalized_mix_summaries,
    is_watch_playlist_id,
    playlist_track_count_text,
    track_display_label,
)
from .search import normalize_music_search_results, search_youtube_videos
from ..log import get_logger


_logger = get_logger(__name__)


class YouTubeMusicLibraryManager:
    """Handles YouTube Music library queries, playlist browsing, and search.

    Receives a *get_client_fn* callable so the caller controls how the
    ``YTMusic`` client is obtained (authenticated vs. public).  A separate
    *build_watch_url_fn* callable builds the playable URL for each track.
    """

    _HOME_ROWS_PLAYLIST_DISCOVERY_LIMIT = 30

    def __init__(self, get_client_fn, build_watch_url_fn):
        self._get_client = get_client_fn
        self._build_watch_url = build_watch_url_fn

    def search(self, query, *, search_scope):
        """Search YouTube Music or YouTube and return normalized results."""
        normalized_query = str(query or "").strip()
        if not normalized_query:
            return []

        scope_option = get_search_scope_option(search_scope)
        if scope_option.requires_auth:
            client = self._get_client(require_auth=True)
            raw_results = client.search(
                normalized_query,
                filter=scope_option.music_filter or None,
                limit=scope_option.limit,
            )
            return normalize_music_search_results(raw_results)

        if scope_option.source == "youtube_music":
            client = self._get_client(require_auth=False)
            raw_results = client.search(
                normalized_query,
                filter=scope_option.music_filter or None,
                limit=scope_option.limit,
            )
            return normalize_music_search_results(raw_results)

        return search_youtube_videos(normalized_query, limit=scope_option.limit)

    def get_charts(self, country_code):
        """Return the "em alta" (charts) playlists for a country as results.

        Uses the public client so trending can be browsed without connecting an
        account; ``country_code`` is an ISO 3166-1 alpha-2 code (``ZZ`` =
        Global).
        """
        normalized_country_code = str(country_code or "").strip().upper() or "ZZ"
        client = self._get_client(require_auth=False)
        raw_charts = client.get_charts(normalized_country_code)
        return normalize_chart_results(raw_charts)

    def get_mood_categories(self):
        """Return the "Moods & Genres" categories grouped by section.

        Uses the public client so the catalog can be browsed without an
        account.  Returns a list of ``(section_title, [YouTubeMoodCategory,
        ...])`` pairs.
        """
        client = self._get_client(require_auth=False)
        raw_categories = client.get_mood_categories()
        return normalize_mood_categories(raw_categories)

    def get_mood_playlists(self, params, *, badge="Mood ou gênero"):
        """Return the playlists for a "Moods & Genres" category as results.

        ``params`` is the opaque token obtained from :meth:`get_mood_categories`.
        Uses the public client; the resulting playlist results can be opened or
        saved like any other.
        """
        normalized_params = str(params or "").strip()
        if not normalized_params:
            return []
        client = self._get_client(require_auth=False)
        try:
            raw_playlists = client.get_mood_playlists(normalized_params)
        except Exception:
            # ytmusicapi 1.12.0 crashes parsing the "Genres" category pages
            # (they lead with a songs carousel). Fall back to a resilient parse
            # of the raw browse response so genres still work.
            raw_playlists = self._fetch_mood_playlists_fallback(client, normalized_params)
        return normalize_mood_playlists(raw_playlists, badge=badge)

    @staticmethod
    def _fetch_mood_playlists_fallback(client, params):
        send_request = getattr(client, "_send_request", None)
        if not callable(send_request):
            return []
        try:
            response = send_request(
                "browse",
                {"browseId": "FEmusic_moods_and_genres_category", "params": params},
            )
        except Exception:
            return []
        return extract_browse_playlists_from_response(response)

    def get_liked_songs(self, *, limit=100):
        """Return the account's "Curtidas" (Liked Music) tracks as results."""
        client = self._get_client(require_auth=True)
        try:
            normalized_limit = max(1, int(limit))
        except (TypeError, ValueError):
            normalized_limit = 100
        raw_liked = client.get_liked_songs(limit=normalized_limit)
        raw_tracks = raw_liked.get("tracks") if isinstance(raw_liked, dict) else raw_liked
        return normalize_track_items(raw_tracks, badge="Curtida")

    def get_history(self):
        """Return the account's play history as song results (most recent first)."""
        client = self._get_client(require_auth=True)
        raw_history = client.get_history()
        return normalize_track_items(raw_history, badge="Histórico")

    def get_user_library_playlists(self, *, limit=None):
        """Return the user's library playlists sorted by title.

        Returns a ``(playlists, has_more)`` tuple.
        """
        client = self._get_client(require_auth=True)
        normalized_limit = None
        if limit is not None:
            try:
                normalized_limit = max(1, int(limit))
            except (TypeError, ValueError):
                normalized_limit = None

        try:
            raw_playlists = client.get_library_playlists(limit=normalized_limit)
        except TypeError:
            raw_playlists = client.get_library_playlists()

        raw_playlist_count = len(raw_playlists or [])

        playlists = []
        seen_playlist_ids = set()
        for item in raw_playlists or []:
            playlist_id = str(item.get("playlistId") or item.get("browseId") or "").strip()
            title = str(item.get("title") or "").strip()
            if not playlist_id or not title:
                continue
            if playlist_id in seen_playlist_ids:
                continue

            track_count_text = playlist_track_count_text(item)
            playlists.append(
                YouTubeMusicPlaylistSummary(
                    playlist_id=playlist_id,
                    title=title,
                    track_count_text=track_count_text,
                )
            )
            seen_playlist_ids.add(playlist_id)

        has_more = bool(normalized_limit) and raw_playlist_count >= normalized_limit
        playlists.sort(key=lambda playlist: playlist.title.casefold())
        return playlists, has_more

    def get_personalized_mixes(self, *, limit=None):
        """Return personalized mixes discovered from the user's home feed."""
        client = self._get_client(require_auth=True)
        try:
            home_limit = int(limit) if limit is not None else self._HOME_ROWS_PLAYLIST_DISCOVERY_LIMIT
        except (TypeError, ValueError):
            home_limit = self._HOME_ROWS_PLAYLIST_DISCOVERY_LIMIT
        home_limit = max(1, home_limit)
        try:
            home_rows = client.get_home(limit=home_limit)
        except Exception:
            home_rows = []

        mixes = []
        seen_playlist_ids = set()
        for item in extract_personalized_mix_summaries(home_rows):
            if item.playlist_id in seen_playlist_ids:
                continue
            mixes.append(item)
            seen_playlist_ids.add(item.playlist_id)

        mixes.sort(key=lambda playlist: playlist.title.casefold())
        return mixes

    def get_library_playlists(self):
        """Return user library playlists merged with personalized mixes."""
        playlists, _ = self.get_user_library_playlists(limit=None)
        seen_playlist_ids = {playlist.playlist_id for playlist in playlists}

        for mix in self.get_personalized_mixes():
            if mix.playlist_id in seen_playlist_ids:
                continue
            playlists.append(mix)
            seen_playlist_ids.add(mix.playlist_id)

        playlists.sort(key=lambda playlist: playlist.title.casefold())
        return playlists

    def get_radio_content(self, video_id, fallback_title="Conteúdo relacionado", *, limit=50):
        """Fetch tracks related to *video_id* (YouTube Music's radio/"Watch Next").

        Uses the public client so related tracks can be fetched even when the
        seed track was played without an authenticated session.
        """
        normalized_video_id = str(video_id or "").strip()
        if not normalized_video_id:
            return YouTubeMusicPlaylistContent(
                playlist_id="", title=str(fallback_title or "").strip(), item_urls=[], item_labels=[]
            )

        try:
            normalized_limit = max(1, int(limit))
        except (TypeError, ValueError):
            normalized_limit = 50

        client = self._get_client(require_auth=False)
        try:
            radio = client.get_watch_playlist(videoId=normalized_video_id, radio=True, limit=normalized_limit)
        except TypeError:
            # Older ytmusicapi builds may not accept the ``radio`` keyword; the
            # plain watch playlist (autoplay queue) is radio-like already.
            radio = client.get_watch_playlist(videoId=normalized_video_id, limit=normalized_limit)

        radio_playlist_id = str(radio.get("playlistId") or "").strip() if isinstance(radio, dict) else ""
        tracks = radio.get("tracks") or [] if isinstance(radio, dict) else []
        _logger.info(
            "Radio for videoId=%s returned %d raw track(s) (playlistId=%s).",
            normalized_video_id,
            len(tracks),
            radio_playlist_id or "(none)",
        )

        item_urls = []
        item_labels = []
        for track in tracks:
            track_video_id = str(track.get("videoId") or "").strip()
            if not track_video_id or track_video_id == normalized_video_id:
                continue

            item_urls.append(self._build_watch_url(track_video_id, playlist_id=radio_playlist_id or None))
            item_labels.append(track_display_label(track))

        return YouTubeMusicPlaylistContent(
            playlist_id=radio_playlist_id,
            title=str(fallback_title or "Conteúdo relacionado").strip(),
            item_urls=item_urls,
            item_labels=item_labels,
        )

    def get_playlist_content(self, playlist_id, fallback_title="", *, require_auth=False):
        """Fetch the full track listing of a playlist."""
        client = self._get_client(require_auth=require_auth)
        normalized_playlist_id = str(playlist_id or "").strip()

        if is_watch_playlist_id(normalized_playlist_id):
            playlist = client.get_watch_playlist(playlistId=normalized_playlist_id, limit=200)
            playlist_title = str(fallback_title or "Mix do YouTube Music").strip()
            tracks = playlist.get("tracks") or []
        else:
            playlist = client.get_playlist(normalized_playlist_id, limit=None)
            playlist_title = str(playlist.get("title") or fallback_title or "Playlist do YouTube Music").strip()
            tracks = playlist.get("tracks") or []

        item_urls = []
        item_labels = []

        for track in tracks:
            video_id = str(track.get("videoId") or "").strip()
            if not video_id:
                continue

            item_urls.append(self._build_watch_url(video_id, playlist_id=normalized_playlist_id))
            item_labels.append(track_display_label(track))

        return YouTubeMusicPlaylistContent(
            playlist_id=normalized_playlist_id,
            title=playlist_title,
            item_urls=item_urls,
            item_labels=item_labels,
        )
