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

    def __init__(self, get_client_fn, import_module_fn):
        self._get_client = get_client_fn
        self._import_module = import_module_fn
        self._feedback_cache = {}

    def clear_cache(self):
        self._feedback_cache.clear()

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
        client.rate_song(video_id, like_status)
        self._feedback_cache[video_id] = normalized_rating

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
