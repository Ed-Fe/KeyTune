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

    def add_tracks_to_playlist(self, playlist_id, video_ids):
        """Add one or more tracks to an editable user playlist.

        ``video_ids`` may contain duplicates or empty values; they are
        de-duplicated (preserving order) and validated.  Returns the number of
        tracks the server reported as added.  Raises if the playlist refused
        the edit (e.g. the tracks are already present or the playlist is not
        editable), so the caller's error path can surface the failure instead
        of silently reporting a false success.
        """
        normalized_playlist_id = str(playlist_id or "").strip()
        if not normalized_playlist_id:
            raise RuntimeError("A playlist selecionada é inválida.")

        normalized_video_ids = self._dedupe_video_ids(video_ids)
        if not normalized_video_ids:
            raise RuntimeError("Nenhuma faixa válida do YouTube Music foi selecionada.")

        client = self._get_client(require_auth=True)
        response = client.add_playlist_items(normalized_playlist_id, normalized_video_ids)

        status_text = self._playlist_edit_status_text(response)
        if "SUCCEEDED" not in status_text.upper():
            raise RuntimeError(
                "O YouTube Music não adicionou as faixas. Elas já podem estar na"
                " playlist ou a playlist não permite edição."
            )

        added_count = self._playlist_edit_result_count(response)
        return added_count if added_count is not None else len(normalized_video_ids)

    def create_playlist(self, title, *, description="", privacy_status="PRIVATE", video_ids=None):
        """Create a new playlist and return its server-assigned id.

        ``video_ids`` is optional: when present (e.g. the user is creating a
        playlist seeded with the current selection) the ids are de-duplicated
        and passed so the playlist is created already populated in a single
        request.  Raises if the title is empty or the server did not return an
        id, so the caller can surface the failure.
        """
        normalized_title = str(title or "").strip()
        if not normalized_title:
            raise RuntimeError("Informe um nome para a nova playlist.")

        normalized_description = str(description or "").strip()
        normalized_privacy_status = self._normalize_privacy_status(privacy_status)
        normalized_video_ids = self._dedupe_video_ids(video_ids) if video_ids else []

        client = self._get_client(require_auth=True)
        response = client.create_playlist(
            normalized_title,
            normalized_description,
            privacy_status=normalized_privacy_status,
            video_ids=normalized_video_ids or None,
        )

        new_playlist_id = self._extract_created_playlist_id(response)
        if not new_playlist_id:
            raise RuntimeError(
                "O YouTube Music não confirmou a criação da playlist. Tente novamente."
            )
        return new_playlist_id

    def delete_playlist(self, playlist_id):
        """Delete an entire playlist the account owns.

        Only playlists you created can be deleted (collaborators and
        saved/public playlists cannot), and personalized mixes/radios are not
        deletable at all.  We fetch the playlist once to confirm ownership and
        raise a clear error otherwise instead of letting the server fail with
        an opaque message.  Returns the deleted playlist id.
        """
        normalized_playlist_id = str(playlist_id or "").strip()
        if not normalized_playlist_id:
            raise RuntimeError("A playlist selecionada é inválida.")
        if is_watch_playlist_id(normalized_playlist_id):
            raise RuntimeError("Mixes e rádios do YouTube Music não podem ser excluídos.")

        client = self._get_client(require_auth=True)
        # A small fetch is enough to read the ``owned`` flag; we don't need the
        # full track listing just to confirm deletion is allowed.
        playlist = client.get_playlist(normalized_playlist_id, limit=1)
        if not self._playlist_is_owned(playlist):
            raise RuntimeError("Você só pode excluir playlists que você criou.")

        response = client.delete_playlist(normalized_playlist_id)
        status_text = self._playlist_edit_status_text(response)
        if status_text and "SUCCEEDED" not in status_text.upper():
            raise RuntimeError(
                f"O YouTube Music não excluiu a playlist (status: {status_text})."
            )
        return normalized_playlist_id

    def remove_tracks_from_playlist(self, playlist_id, video_ids):
        """Remove one or more tracks from an editable user playlist.

        ``remove_playlist_items`` requires each track's playlist-specific
        ``setVideoId``, which is not part of the playable URL.  We fetch the
        playlist once to map ``videoId -> setVideoId`` and only remove the
        tracks that are actually present.  Returns the number of tracks removed.
        """
        normalized_playlist_id = str(playlist_id or "").strip()
        if not normalized_playlist_id:
            raise RuntimeError("A playlist selecionada é inválida.")

        normalized_video_ids = self._dedupe_video_ids(video_ids)
        if not normalized_video_ids:
            raise RuntimeError("Nenhuma faixa válida do YouTube Music foi selecionada.")

        client = self._get_client(require_auth=True)
        # The playlist detail also tells us whether the account can edit it
        # (``owned`` for playlists you created, ``collaborators`` for shared
        # ones). We already need this fetch to map setVideoIds, so the
        # editability check is free — saved/public playlists you don't own
        # reach here only if the UI guard was bypassed.
        playlist = client.get_playlist(normalized_playlist_id, limit=None)
        if not self._playlist_is_editable(playlist):
            raise RuntimeError(
                "Você só pode remover faixas de playlists que criou ou onde é colaborador."
            )

        set_video_id_by_video_id = self._map_set_video_ids(playlist)

        videos_to_remove = []
        for video_id in normalized_video_ids:
            set_video_id = set_video_id_by_video_id.get(video_id)
            if set_video_id:
                videos_to_remove.append({"videoId": video_id, "setVideoId": set_video_id})

        if not videos_to_remove:
            raise RuntimeError("As faixas selecionadas não foram encontradas nesta playlist.")

        response = client.remove_playlist_items(normalized_playlist_id, videos_to_remove)
        status_text = self._playlist_edit_status_text(response)
        if status_text and "SUCCEEDED" not in status_text.upper():
            raise RuntimeError(
                f"O YouTube Music não removeu as faixas (status: {status_text})."
            )

        return len(videos_to_remove)

    @staticmethod
    def _dedupe_video_ids(video_ids):
        normalized_video_ids = []
        seen_video_ids = set()
        for video_id in video_ids or []:
            normalized_video_id = str(video_id or "").strip()
            if not normalized_video_id or normalized_video_id in seen_video_ids:
                continue
            normalized_video_ids.append(normalized_video_id)
            seen_video_ids.add(normalized_video_id)
        return normalized_video_ids

    @staticmethod
    def _playlist_is_editable(playlist):
        """Whether the authenticated account can add/remove tracks.

        ytmusicapi's ``get_playlist`` sets ``owned`` for playlists created by
        the account and exposes ``collaborators`` for shared playlists the
        account can also edit.  Saved/subscribed public playlists have neither.
        """
        if not isinstance(playlist, dict):
            return False
        return bool(playlist.get("owned")) or "collaborators" in playlist

    @staticmethod
    def _playlist_is_owned(playlist):
        """Whether the account created the playlist (deletion requires this).

        Unlike :meth:`_playlist_is_editable`, being a collaborator is not
        enough: only the owner can delete a playlist.
        """
        return isinstance(playlist, dict) and bool(playlist.get("owned"))

    @staticmethod
    def _normalize_privacy_status(privacy_status):
        normalized_privacy_status = str(privacy_status or "").strip().upper()
        if normalized_privacy_status in {"PUBLIC", "PRIVATE", "UNLISTED"}:
            return normalized_privacy_status
        return "PRIVATE"

    @staticmethod
    def _extract_created_playlist_id(response):
        """Normalize ``create_playlist``'s return value to a playlist id.

        ytmusicapi returns the new playlist id as a string on success, or the
        full response dict (which may still carry ``playlistId``) on error.
        """
        if isinstance(response, str):
            return response.strip()
        if isinstance(response, dict):
            return str(response.get("playlistId") or "").strip()
        return ""

    @staticmethod
    def _map_set_video_ids(playlist):
        tracks = playlist.get("tracks") if isinstance(playlist, dict) else None
        set_video_id_by_video_id = {}
        for track in tracks or []:
            video_id = str(track.get("videoId") or "").strip()
            set_video_id = str(track.get("setVideoId") or "").strip()
            if video_id and set_video_id:
                set_video_id_by_video_id.setdefault(video_id, set_video_id)
        return set_video_id_by_video_id

    @staticmethod
    def _playlist_edit_status_text(response):
        """Normalize the status from ``add``/``remove`` playlist responses.

        ytmusicapi returns either a status string (e.g. ``"STATUS_FAILED"``)
        or a dict like ``{"status": "STATUS_SUCCEEDED", "playlistEditResults":
        [...]}`` depending on the outcome.
        """
        if isinstance(response, dict):
            return str(response.get("status") or "").strip()
        return str(response or "").strip()

    @staticmethod
    def _playlist_edit_result_count(response):
        if not isinstance(response, dict):
            return None
        edit_results = response.get("playlistEditResults")
        if isinstance(edit_results, list):
            return len(edit_results)
        return None

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
