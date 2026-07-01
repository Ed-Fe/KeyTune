from .playlists import (
    extract_video_id_from_text,
    is_music_youtube_url,
)
from .stream_cache import normalize_media_path
from ..log import get_logger
from ..i18n import _


_logger = get_logger(__name__)


class YouTubeMusicFeedbackManager:
    """Handles like/dislike ratings, history reporting, and search-result saving.

    Receives callables for obtaining the ``YTMusic`` client and for importing
    the ``ytmusicapi`` module so that the caller controls dependency resolution
    and test-time patching.
    """

    def __init__(self, get_client_fn, import_module_fn):
        self._get_client = get_client_fn
        self._import_module = import_module_fn

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

    def get_media_feedback_status(self, media_path):
        """Return the like status (``LIKE``, ``DISLIKE``, ``INDIFFERENT``) of a media item, or ``None``."""
        normalized_media_path = normalize_media_path(media_path)
        video_id = extract_video_id_from_text(normalized_media_path)
        if not video_id:
            return None

        client = self._get_client(require_auth=True)
        song = client.get_song(video_id)
        if not isinstance(song, dict):
            return None

        like_status = str(song.get("likeStatus") or "").strip().upper()
        if like_status in {"LIKE", "DISLIKE", "INDIFFERENT"}:
            return like_status
        return None

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

        confirmed_song = client.get_song(video_id)
        confirmed_status = ""
        if isinstance(confirmed_song, dict):
            confirmed_status = str(confirmed_song.get("likeStatus") or "").strip().upper()

        if confirmed_status != normalized_rating:
            confirmed_label = confirmed_status or "indisponível"
            return (
                f"A avaliação foi enviada, mas o servidor ainda retornou likeStatus={confirmed_label}."
            )

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
