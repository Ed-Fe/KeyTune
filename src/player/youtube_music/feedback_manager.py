import threading
import time

from .feedback_store import YouTubeMusicFeedbackStore
from .playlists import (
    extract_video_id_from_text,
    is_music_youtube_url,
)
from .stream_cache import normalize_media_path
from ..log import get_logger
from ..i18n import _


_logger = get_logger(__name__)


def _normalize_like_status(value):
    if value is None:
        return None

    normalized = str(value).strip().upper()
    if normalized in {"LIKE", "DISLIKE", "INDIFFERENT"}:
        return normalized
    if normalized in {"LIKED", "FAVORITE"}:
        return "LIKE"
    if normalized == "DISLIKED":
        return "DISLIKE"

    return None


def _extract_like_status_from_watch_playlist(watch_playlist, video_id):
    if not isinstance(watch_playlist, dict):
        return None

    normalized_video_id = str(video_id or "").strip()
    for track in watch_playlist.get("tracks") or []:
        if not isinstance(track, dict):
            continue

        candidates = [track]
        counterpart = track.get("counterpart")
        if isinstance(counterpart, dict):
            candidates.append(counterpart)

        for candidate in candidates:
            if str(candidate.get("videoId") or "").strip() != normalized_video_id:
                continue
            return _normalize_like_status(candidate.get("likeStatus"))

    return None


class YouTubeMusicFeedbackManager:
    """Handles like/dislike ratings, history reporting, and search-result saving.

    Receives callables for obtaining the ``YTMusic`` client and for importing
    the ``ytmusicapi`` module so that the caller controls dependency resolution
    and test-time patching.
    """

    _ACCOUNT_SYNC_TTL_SECONDS = 300

    def __init__(self, get_client_fn, import_module_fn, feedback_store=None):
        self._get_client = get_client_fn
        self._import_module = import_module_fn
        self._feedback_cache = {}
        self._feedback_store = feedback_store or YouTubeMusicFeedbackStore()
        self._last_account_sync_at = 0.0
        self._account_sync_lock = threading.Lock()

    def clear_cache(self):
        self._feedback_cache.clear()

    def clear_active_account(self):
        self._feedback_store.clear_active_account()
        self._last_account_sync_at = 0.0

    def set_active_account(self, account_info):
        return self._feedback_store.set_active_account(account_info)

    def _remember_client_account(self, client):
        try:
            account_info = client.get_account_info()
        except Exception:
            return False
        return self._feedback_store.set_active_account(account_info)

    def sync_account_feedback(self, force=False):
        """Merge remotely visible account ratings into the persistent cache.

        YouTube Music does not expose a bulk "disliked songs" collection. Its
        authenticated history and liked-songs responses do carry ``likeStatus``
        for recently visible tracks, so they are used as an incremental account
        synchronization source.
        """
        with self._account_sync_lock:
            now = time.monotonic()
            if not force and now - self._last_account_sync_at < self._ACCOUNT_SYNC_TTL_SECONDS:
                return 0

            client = self._get_client(require_auth=True)
            self._remember_client_account(client)

            observed_items = []
            errors = []
            try:
                history = client.get_history()
            except Exception as exc:
                errors.append(exc)
            else:
                if isinstance(history, list):
                    observed_items.extend(history)

            try:
                liked = client.get_liked_songs(limit=500)
            except Exception as exc:
                errors.append(exc)
            else:
                liked_tracks = liked.get("tracks") if isinstance(liked, dict) else liked
                if isinstance(liked_tracks, list):
                    observed_items.extend(liked_tracks)

            if not observed_items and errors:
                raise errors[0]

            self.observe_feedback_items(observed_items)
            self._last_account_sync_at = now
            return len(observed_items)

    def is_media_disliked(self, media_path):
        video_id = extract_video_id_from_text(normalize_media_path(media_path))
        return bool(video_id and self._feedback_store.is_disliked(video_id))

    def disliked_video_ids(self):
        return self._feedback_store.disliked_video_ids()

    def observe_feedback_items(self, items):
        self._feedback_store.ingest_items(items)
        for item in items or []:
            if not isinstance(item, dict):
                continue
            video_id = str(item.get("videoId") or "").strip()
            status = _normalize_like_status(item.get("likeStatus"))
            if video_id and status:
                self._feedback_cache[video_id] = status

    def save_search_result(self, search_result):
        """Save a search result (song or playlist) to the user's library."""
        client = self._get_client(require_auth=True)

        result_type = str(getattr(search_result, "result_type", "") or "").strip().lower()
        playlist_id = str(getattr(search_result, "playlist_id", "") or "").strip()
        feedback_add_token = str(getattr(search_result, "feedback_add_token", "") or "").strip()
        feedback_remove_token = str(getattr(search_result, "feedback_remove_token", "") or "").strip()

        ytmusicapi = self._import_module()
        LikeStatus = ytmusicapi.LikeStatus

        if result_type == "playlist" and playlist_id:
            client.rate_playlist(playlist_id, LikeStatus.LIKE)
            return "Playlist salva na biblioteca do YouTube Music."

        if result_type == "song":
            if feedback_remove_token and not feedback_add_token:
                return _("A faixa já estava salva na biblioteca do YouTube Music.")
            if feedback_add_token:
                client.edit_song_library_status([feedback_add_token])
                return "Faixa salva na biblioteca do YouTube Music."

        raise RuntimeError(_("O resultado selecionado não pode ser salvo no YouTube Music."))

    def get_media_feedback_status(self, media_path, force_refresh=False):
        """Return the like status (``LIKE``, ``DISLIKE``, ``INDIFFERENT``) of a media item, or ``None``."""
        normalized_media_path = normalize_media_path(media_path)
        video_id = extract_video_id_from_text(normalized_media_path)
        if not video_id:
            return None

        if not force_refresh and video_id in self._feedback_cache:
            return self._feedback_cache[video_id]

        client = self._get_client(require_auth=True)
        try:
            watch_playlist = client.get_watch_playlist(videoId=video_id, limit=1)
        except Exception:
            return self._feedback_cache.get(video_id)

        like_status = _extract_like_status_from_watch_playlist(watch_playlist, video_id)
        if like_status:
            self._feedback_cache[video_id] = like_status
            if like_status in {"LIKE", "DISLIKE"}:
                self._feedback_store.record(video_id, like_status)
            return like_status

        return self._feedback_cache.get(video_id)

    def rate_media_feedback(self, media_path, rating):
        """Send a like/dislike/indifferent rating for a media item."""
        normalized_media_path = normalize_media_path(media_path)
        video_id = extract_video_id_from_text(normalized_media_path)
        if not video_id:
            raise RuntimeError(_("A mídia atual não tem um vídeo compatível para curtir ou marcar como não gostei."))

        ytmusicapi = self._import_module()
        LikeStatus = ytmusicapi.LikeStatus

        normalized_rating = str(rating or "").strip().upper()
        rating_map = {
            "LIKE": LikeStatus.LIKE,
            "DISLIKE": LikeStatus.DISLIKE,
            "INDIFFERENT": LikeStatus.INDIFFERENT,
        }
        like_status = rating_map.get(normalized_rating)
        if like_status is None:
            raise RuntimeError(_("A avaliação solicitada para a mídia atual é inválida."))

        client = self._get_client(require_auth=True)
        self._remember_client_account(client)
        client.rate_song(video_id, like_status)
        self._feedback_cache[video_id] = normalized_rating
        self._feedback_store.record(video_id, normalized_rating)

        if like_status == LikeStatus.LIKE:
            return _("Mídia atual curtida no YouTube Music.")
        if like_status == LikeStatus.DISLIKE:
            return _("Mídia atual marcada como não gostei no YouTube Music.")
        return _("Avaliação da mídia atual removida no YouTube Music.")

    def report_playback_to_history(self, media_path):
        """Report a media item as played to the user's YouTube Music history."""
        normalized_media_path = normalize_media_path(media_path)
        if not is_music_youtube_url(normalized_media_path):
            return False

        video_id = extract_video_id_from_text(normalized_media_path)
        if not video_id:
            return False

        client = self._get_client(require_auth=True)
        song = client.get_song(video_id)
        response = client.add_history_item(song)
        return getattr(response, "status_code", None) == 204
