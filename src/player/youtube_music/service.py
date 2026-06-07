import os

from .auth import (
    YTMUSIC_BROWSER_AUTH_FILE_NAME,
    get_browser_auth_file_path,
    get_browser_auth_cookie_file_path,
    harden_sensitive_file_permissions,
    prepare_browser_auth_input,
    read_auth_file_text,
    write_browser_auth_cookie_file,
)
from .client_provider import YouTubeMusicClientProvider
from .dependencies import import_ytmusicapi_module
from .feedback_manager import YouTubeMusicFeedbackManager
from .library_manager import YouTubeMusicLibraryManager
from .playlists import (
    build_playlist_source as build_playlist_source_fn,
    build_watch_url as build_watch_url_fn,
    is_youtube_music_media as is_youtube_music_media_fn,
)
from .stream_cache import YouTubeMusicStreamCache, normalize_media_path
from .streams import ResolvedStreamPlayback, resolve_stream_playback as resolve_music_stream_playback
from ..log import get_logger


_logger = get_logger(__name__)


class YouTubeMusicAuthValidationError(RuntimeError):
    def __init__(self, message, *, should_disconnect):
        super().__init__(message)
        self.should_disconnect = bool(should_disconnect)


class InvalidYouTubeMusicAuthError(YouTubeMusicAuthValidationError):
    def __init__(self, message="A autenticação salva do YouTube Music não é mais válida."):
        super().__init__(message, should_disconnect=True)


class TemporaryYouTubeMusicAuthError(YouTubeMusicAuthValidationError):
    def __init__(self, message="Não foi possível validar a autenticação do YouTube Music agora."):
        super().__init__(message, should_disconnect=False)


_INVALID_YOUTUBE_MUSIC_AUTH_ERROR_MARKERS = (
    "authentication",
    "authorization",
    "cookie",
    "credential",
    "credentials",
    "logged in",
    "login",
    "sign in",
    "unauthorized",
    "forbidden",
    "401",
    "403",
    "sapisidhash",
    "x-goog-authuser",
    "__secure-3papisid",
)


def _is_probably_invalid_saved_auth_error(error):
    messages = []
    current_error = error
    visited_error_ids = set()
    while current_error is not None and id(current_error) not in visited_error_ids:
        visited_error_ids.add(id(current_error))
        messages.append(f"{type(current_error).__name__}: {current_error}")
        current_error = getattr(current_error, "__cause__", None) or getattr(current_error, "__context__", None)

    normalized_message = " ".join(messages).casefold()
    return any(marker in normalized_message for marker in _INVALID_YOUTUBE_MUSIC_AUTH_ERROR_MARKERS)


class YouTubeMusicService:
    """Facade that orchestrates YouTube Music operations.

    Delegates to focused helper classes for client management, stream
    caching, library browsing, and feedback/history actions while
    exposing the same public interface consumed by the frame mixins
    and tests.
    """

    _STREAM_CACHE_TTL_SECONDS = 300
    _STREAM_CACHE_EXPIRY_SAFETY_MARGIN_SECONDS = 30
    _HOME_ROWS_PLAYLIST_DISCOVERY_LIMIT = 30

    def __init__(self):
        self._client_provider = YouTubeMusicClientProvider()
        self._stream_cache_manager = YouTubeMusicStreamCache()
        self._account_info = None

        # Library and feedback managers use late-binding lambdas so that
        # unittest.mock.patch on *this* module's names (e.g. get_client,
        # import_ytmusicapi_module) is picked up at call time.
        self._library = YouTubeMusicLibraryManager(
            get_client_fn=lambda **kw: self.get_client(**kw),
            build_watch_url_fn=lambda video_id, playlist_id=None: self.build_watch_url(video_id, playlist_id=playlist_id),
        )
        self._feedback = YouTubeMusicFeedbackManager(
            get_client_fn=lambda **kw: self.get_client(**kw),
            import_module_fn=lambda **kw: import_ytmusicapi_module(**kw),
        )

    # -- Compatibility property ------------------------------------------------
    # Tests inspect ``service._stream_cache`` (the raw dict) directly.

    @property
    def _stream_cache(self):
        return self._stream_cache_manager._cache

    @_stream_cache.setter
    def _stream_cache(self, value):
        self._stream_cache_manager._cache = value

    @property
    def _stream_cache_lock(self):
        return self._stream_cache_manager._lock

    @property
    def _stream_prefetch_in_progress(self):
        return self._stream_cache_manager._prefetch_in_progress

    # -- Auth file paths -------------------------------------------------------

    @property
    def browser_auth_file_path(self):
        return get_browser_auth_file_path()

    @property
    def token_file_path(self):
        return self.browser_auth_file_path

    @property
    def browser_auth_cookie_file_path(self):
        return get_browser_auth_cookie_file_path()

    # -- Auth state ------------------------------------------------------------

    def has_saved_browser_auth(self):
        return os.path.isfile(self.browser_auth_file_path)

    def has_saved_auth(self):
        return self.has_saved_browser_auth()

    def is_authenticated(self):
        if not self.has_saved_browser_auth():
            return False

        try:
            self.validate_saved_authentication()
        except Exception:
            self.clear_client_cache()
            return False

        return True

    def validate_saved_authentication(self):
        if not self.has_saved_browser_auth():
            return False

        self.get_account_info()
        return True

    def clear_client_cache(self):
        self._client_provider.clear_cache()
        self._account_info = None
        self._stream_cache_manager.clear()

    # -- Stream cache (delegated) ----------------------------------------------

    def _normalize_stream_cache_key(self, media_path):
        return normalize_media_path(media_path)

    def get_cached_stream_url(self, media_path):
        return self._stream_cache_manager.get_cached_stream_url(media_path)

    def get_cached_stream_playback(self, media_path):
        return self._stream_cache_manager.get_cached_stream_playback(media_path)

    def _cache_stream_playback(self, media_path, resolved_playback):
        return self._stream_cache_manager.cache_stream_playback(media_path, resolved_playback)

    def _stream_cache_ttl_seconds(self, stream_url):
        return self._stream_cache_manager._cache_ttl_seconds(stream_url)

    def prefetch_stream_url(self, media_path):
        return self._stream_cache_manager.prefetch_stream_url(
            media_path,
            resolve_fn=resolve_music_stream_playback,
        )

    def resolve_stream_url(self, media_path):
        return self.resolve_stream_playback(media_path).stream_url

    def resolve_stream_playback(self, media_path):
        return self._stream_cache_manager.resolve_stream_playback(
            media_path,
            resolve_fn=resolve_music_stream_playback,
        )

    # -- Disconnect / connect --------------------------------------------------

    def disconnect(self):
        self.clear_client_cache()
        removed = False
        try:
            os.remove(self.browser_auth_file_path)
            removed = True
        except FileNotFoundError:
            pass
        try:
            os.remove(self.browser_auth_cookie_file_path)
            removed = True
        except FileNotFoundError:
            pass
        _logger.info("YouTube Music disconnected (auth files removed=%s)", removed)
        return removed

    def save_browser_auth(self, headers_raw=None, source_file_path=None):
        target_path = self.browser_auth_file_path
        target_cookie_file_path = self.browser_auth_cookie_file_path

        normalized_headers_raw = ""
        raw_auth_input = ""
        source_name = "texto colado"
        if source_file_path:
            normalized_source_file_path = os.path.abspath(os.path.normpath(str(source_file_path or "").strip()))
            if not normalized_source_file_path or not os.path.isfile(normalized_source_file_path):
                raise RuntimeError("Selecione um arquivo válido de browser.json, JSON de cookies ou cookies.txt.")
            raw_auth_input = read_auth_file_text(normalized_source_file_path)
            source_name = os.path.basename(normalized_source_file_path)
            normalized_headers_raw = prepare_browser_auth_input(
                raw_auth_input,
                source_name=source_name,
            )
        else:
            raw_auth_input = str(headers_raw or "")
            normalized_headers_raw = prepare_browser_auth_input(raw_auth_input, source_name=source_name)

        if not normalized_headers_raw:
            raise RuntimeError(
                "Cole os dados de conexão do navegador ou selecione um arquivo válido de browser.json, JSON de cookies ou cookies.txt."
            )

        ytmusicapi = import_ytmusicapi_module()
        ytmusicapi.setup(filepath=target_path, headers_raw=normalized_headers_raw)
        harden_sensitive_file_permissions(target_path)
        write_browser_auth_cookie_file(
            raw_auth_input,
            target_cookie_file_path,
            source_name=source_name,
            fallback_headers_raw=normalized_headers_raw,
        )
        harden_sensitive_file_permissions(target_cookie_file_path)
        self.clear_client_cache()
        _logger.info("YouTube Music browser auth saved (source=%s)", source_name)
        return target_path

    # -- Account info ----------------------------------------------------------

    def get_account_info(self):
        if self._account_info is not None:
            return self._account_info

        client = self.get_client()
        try:
            account_info = client.get_account_info()
        except Exception as exc:
            _logger.warning("Failed to retrieve YouTube Music account info: %s", exc)
            self.clear_client_cache()
            if _is_probably_invalid_saved_auth_error(exc):
                raise InvalidYouTubeMusicAuthError() from exc
            raise TemporaryYouTubeMusicAuthError() from exc

        if not isinstance(account_info, dict):
            raise TemporaryYouTubeMusicAuthError(
                "A resposta da conta do YouTube Music veio em formato inválido."
            )

        self._account_info = account_info
        _logger.debug(
            "YouTube Music account info retrieved: %s",
            str(account_info.get("accountName") or account_info.get("channelHandle") or "(unknown)"),
        )
        return account_info

    def get_connected_account_name(self):
        account_info = self.get_account_info()
        return str(account_info.get("accountName") or account_info.get("channelHandle") or "Conta do YouTube Music").strip()

    # -- Client factory (delegated) --------------------------------------------

    def get_client(self, *, require_auth=True):
        ytmusicapi = import_ytmusicapi_module()
        return self._client_provider.get_client(
            ytmusicapi_module=ytmusicapi,
            require_auth=require_auth,
            auth_file_path=self.browser_auth_file_path,
            has_saved_auth=self.has_saved_browser_auth(),
        )

    # -- Library (delegated) ---------------------------------------------------

    def search(self, query, *, search_scope):
        return self._library.search(query, search_scope=search_scope)

    def get_user_library_playlists(self, *, limit=None):
        return self._library.get_user_library_playlists(limit=limit)

    def get_personalized_mixes(self, *, limit=None):
        return self._library.get_personalized_mixes(limit=limit)

    def get_library_playlists(self):
        return self._library.get_library_playlists()

    def get_playlist_content(self, playlist_id, fallback_title="", *, require_auth=False):
        return self._library.get_playlist_content(playlist_id, fallback_title, require_auth=require_auth)

    # -- Feedback / history (delegated) ----------------------------------------

    def save_search_result(self, search_result):
        return self._feedback.save_search_result(search_result)

    def get_media_feedback_status(self, media_path):
        return self._feedback.get_media_feedback_status(media_path)

    def rate_media_feedback(self, media_path, rating):
        return self._feedback.rate_media_feedback(media_path, rating)

    def report_playback_to_history(self, media_path):
        return self._feedback.report_playback_to_history(media_path)

    # -- Static helpers --------------------------------------------------------

    def build_watch_url(self, video_id, playlist_id=None):
        return build_watch_url_fn(video_id, playlist_id=playlist_id)

    def build_playlist_source(self, playlist_id):
        return build_playlist_source_fn(playlist_id)

    @staticmethod
    def is_youtube_music_media(media_path):
        return is_youtube_music_media_fn(media_path)
