import os
import tempfile

from .auth import (
    YTMUSIC_BROWSER_AUTH_FILE_NAME,
    export_cookies_from_browser,
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
from ..i18n import _


_logger = get_logger(__name__)


class YouTubeMusicAuthValidationError(RuntimeError):
    def __init__(self, message, *, should_disconnect):
        super().__init__(message)
        self.should_disconnect = bool(should_disconnect)


class InvalidYouTubeMusicAuthError(YouTubeMusicAuthValidationError):
    def __init__(self, message=None):
        if message is None:
            message = _("A autenticação salva do YouTube Music não é mais válida.")
        super().__init__(message, should_disconnect=True)


class TemporaryYouTubeMusicAuthError(YouTubeMusicAuthValidationError):
    def __init__(self, message=None):
        if message is None:
            message = _("Não foi possível validar a autenticação do YouTube Music agora.")
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
        self._anonymous_stream_playback_enabled = False
        self._anonymous_stream_fallback_enabled = False
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
            resolve_fn=self._resolve_stream_playback_uncached,
        )

    def resolve_stream_url(self, media_path):
        return self.resolve_stream_playback(media_path).stream_url

    def resolve_stream_playback(self, media_path):
        return self._stream_cache_manager.resolve_stream_playback(
            media_path,
            resolve_fn=self._resolve_stream_playback_uncached,
        )

    def _resolve_stream_playback_uncached(self, media_path):
        return resolve_music_stream_playback(
            media_path,
            use_account_cookies=not self._anonymous_stream_playback_enabled,
            anonymous_player_client=(
                "tv_simply"
                if self._anonymous_stream_fallback_enabled
                else ""
            ),
        )

    def advance_stream_playback_after_http_403(self):
        if not self._anonymous_stream_playback_enabled:
            self._anonymous_stream_playback_enabled = True
            self._anonymous_stream_fallback_enabled = not self.has_saved_browser_auth()
            # Replace the manager so a prefetch from the previous profile cannot
            # repopulate the cache after the session changes profile.
            self._stream_cache_manager = YouTubeMusicStreamCache()
            if self._anonymous_stream_fallback_enabled:
                _logger.warning("YouTube Music stream playback switched to tv_simply for this session")
                return "tv_simply"
            _logger.warning("YouTube Music stream playback switched to visionos for this session")
            return "visionos"

        if not self._anonymous_stream_fallback_enabled:
            self._anonymous_stream_fallback_enabled = True
            self._stream_cache_manager = YouTubeMusicStreamCache()
            _logger.warning("YouTube Music stream playback switched to tv_simply for this session")
            return "tv_simply"

        return ""

    def _reset_stream_playback_mode(self):
        self._anonymous_stream_playback_enabled = False
        self._anonymous_stream_fallback_enabled = False
        self._stream_cache_manager = YouTubeMusicStreamCache()

    # -- Disconnect / connect --------------------------------------------------

    def disconnect(self):
        self.clear_client_cache()
        self._reset_stream_playback_mode()
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
                raise RuntimeError(_("Selecione um arquivo válido de browser.json, JSON de cookies ou cookies.txt."))
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
                _("Cole os dados de conexão do navegador ou selecione um arquivo válido de browser.json, JSON de cookies ou cookies.txt.")
            )

        target_dir = os.path.dirname(target_path)
        os.makedirs(target_dir, exist_ok=True)
        ytmusicapi = import_ytmusicapi_module()
        with tempfile.TemporaryDirectory(prefix="ytmusic_auth_", dir=target_dir) as staging_dir:
            staged_auth_path = os.path.join(staging_dir, YTMUSIC_BROWSER_AUTH_FILE_NAME)
            staged_cookie_path = os.path.join(staging_dir, "ytmusic_cookies.txt")

            ytmusicapi.setup(filepath=staged_auth_path, headers_raw=normalized_headers_raw)
            if not os.path.isfile(staged_auth_path) or os.path.getsize(staged_auth_path) == 0:
                raise RuntimeError(_("Não foi possível preparar a autenticação do YouTube Music."))

            written_cookie_path = write_browser_auth_cookie_file(
                raw_auth_input,
                staged_cookie_path,
                source_name=source_name,
                fallback_headers_raw=normalized_headers_raw,
            )
            if not written_cookie_path:
                raise RuntimeError(_("A autenticação informada não contém cookies válidos do YouTube."))

            candidate_client = ytmusicapi.YTMusic(staged_auth_path)
            account_info = candidate_client.get_account_info()
            if not isinstance(account_info, dict):
                raise RuntimeError(_("A resposta da conta do YouTube Music veio em formato inválido."))

            harden_sensitive_file_permissions(staged_auth_path)
            harden_sensitive_file_permissions(staged_cookie_path)
            os.replace(staged_auth_path, target_path)
            os.replace(staged_cookie_path, target_cookie_file_path)

        self.clear_client_cache()
        self._account_info = account_info
        self._reset_stream_playback_mode()
        _logger.info("YouTube Music browser auth saved (source=%s)", source_name)
        return target_path

    def save_browser_auth_from_browser(self, browser_name: str) -> str:
        """Exporta cookies diretamente do navegador instalado e salva a autenticação.

        Para qualquer navegador não reconhecido, o chamador deve usar
        :meth:`save_browser_auth` com arquivo ou texto manual.

        Args:
            browser_name: Identificador do navegador (chave yt-dlp).

        Returns:
            Caminho do arquivo ``ytmusic_browser.json`` gerado.

        Raises:
            RuntimeError: Se o navegador não for suportado, o yt-dlp não
                          estiver disponível, ou a exportação falhar.
        """
        _logger.info("YouTube Music browser auth export requested (browser=%s)", browser_name)
        with tempfile.TemporaryDirectory(prefix="keytune_browser_auth_") as temp_dir:
            exported_cookie_path = os.path.join(temp_dir, "cookies.txt")
            export_cookies_from_browser(browser_name, exported_cookie_path)
            raw_cookie_content = read_auth_file_text(exported_cookie_path)
            saved_path = self.save_browser_auth(headers_raw=raw_cookie_content)
        _logger.info(
            "YouTube Music browser auth from browser saved (browser=%s, path=%s)",
            browser_name,
            saved_path,
        )
        return saved_path

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
                _("A resposta da conta do YouTube Music veio em formato inválido.")
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

    def get_charts(self, country_code):
        return self._library.get_charts(country_code)

    def get_mood_categories(self):
        return self._library.get_mood_categories()

    def get_mood_playlists(self, params, *, badge=None):
        if badge is None:
            badge = _("Mood ou gênero")
        return self._library.get_mood_playlists(params, badge=badge)

    def get_liked_songs(self, *, limit=100):
        return self._library.get_liked_songs(limit=limit)

    def get_history(self):
        return self._library.get_history()

    def get_user_library_playlists(self, *, limit=None):
        return self._library.get_user_library_playlists(limit=limit)

    def get_personalized_mixes(self, *, limit=None):
        return self._library.get_personalized_mixes(limit=limit)

    def get_library_playlists(self):
        return self._library.get_library_playlists()

    def get_playlist_content(self, playlist_id, fallback_title="", *, require_auth=False):
        return self._library.get_playlist_content(playlist_id, fallback_title, require_auth=require_auth)

    def get_radio_content(self, video_id, fallback_title=None, *, limit=50):
        if fallback_title is None:
            fallback_title = _("Conteúdo relacionado")
        return self._library.get_radio_content(video_id, fallback_title, limit=limit)

    # -- Feedback / history (delegated) ----------------------------------------

    def save_search_result(self, search_result):
        return self._feedback.save_search_result(search_result)

    def get_media_feedback_status(self, media_path):
        return self._feedback.get_media_feedback_status(media_path)

    def rate_media_feedback(self, media_path, rating):
        return self._feedback.rate_media_feedback(media_path, rating)

    def report_playback_to_history(self, media_path):
        return self._feedback.report_playback_to_history(media_path)

    def add_tracks_to_playlist(self, playlist_id, video_ids):
        return self._library.add_tracks_to_playlist(playlist_id, video_ids)

    def remove_tracks_from_playlist(self, playlist_id, video_ids):
        return self._library.remove_tracks_from_playlist(playlist_id, video_ids)

    def create_playlist(self, title, *, description="", privacy_status="PRIVATE", video_ids=None):
        return self._library.create_playlist(
            title,
            description=description,
            privacy_status=privacy_status,
            video_ids=video_ids,
        )

    def delete_playlist(self, playlist_id):
        return self._library.delete_playlist(playlist_id)

    # -- Static helpers --------------------------------------------------------

    def build_watch_url(self, video_id, playlist_id=None):
        return build_watch_url_fn(video_id, playlist_id=playlist_id)

    def build_playlist_source(self, playlist_id):
        return build_playlist_source_fn(playlist_id)

    @staticmethod
    def is_youtube_music_media(media_path):
        return is_youtube_music_media_fn(media_path)
