import os
import threading
import time
from urllib.parse import parse_qs, urlparse

from .auth import (
    YTMUSIC_BROWSER_AUTH_FILE_NAME,
    get_browser_auth_file_path,
    get_browser_auth_cookie_file_path,
    harden_sensitive_file_permissions,
    prepare_browser_auth_input,
    read_auth_file_text,
    write_browser_auth_cookie_file,
)
from .dependencies import import_ytmusicapi_module
from .models import YouTubeMusicPlaylistContent, YouTubeMusicPlaylistSummary, get_search_scope_option
from .playlists import (
    build_playlist_source as build_playlist_source_fn,
    build_watch_url as build_watch_url_fn,
    extract_video_id_from_text,
    extract_personalized_mix_summaries,
    is_music_youtube_url,
    is_watch_playlist_id,
    is_youtube_music_media as is_youtube_music_media_fn,
    playlist_track_count_text,
    track_display_label,
)
from .search import normalize_music_search_results, search_youtube_videos
from .streams import ResolvedStreamPlayback, resolve_stream_playback as resolve_music_stream_playback


class YouTubeMusicService:
    _STREAM_CACHE_TTL_SECONDS = 300
    _STREAM_CACHE_EXPIRY_SAFETY_MARGIN_SECONDS = 30
    _HOME_ROWS_PLAYLIST_DISCOVERY_LIMIT = 60

    def __init__(self):
        self._client = None
        self._account_info = None
        self._stream_cache = {}
        self._stream_cache_lock = threading.Lock()
        self._stream_prefetch_in_progress = set()

    @property
    def browser_auth_file_path(self):
        return get_browser_auth_file_path()

    @property
    def token_file_path(self):
        return self.browser_auth_file_path

    @property
    def browser_auth_cookie_file_path(self):
        return get_browser_auth_cookie_file_path()

    def has_saved_browser_auth(self):
        return os.path.isfile(self.browser_auth_file_path)

    def has_saved_auth(self):
        return self.has_saved_browser_auth()

    def is_authenticated(self):
        if not self.has_saved_browser_auth():
            return False

        try:
            self.get_account_info()
        except Exception:
            self.clear_client_cache()
            return False

        return True

    def clear_client_cache(self):
        self._client = None
        self._account_info = None
        with self._stream_cache_lock:
            self._stream_cache = {}
            self._stream_prefetch_in_progress = set()

    def _normalize_stream_cache_key(self, media_path):
        return str(media_path or "").strip()

    def get_cached_stream_url(self, media_path):
        cached_playback = self.get_cached_stream_playback(media_path)
        if cached_playback is None:
            return None
        return cached_playback.stream_url

    def get_cached_stream_playback(self, media_path):
        cache_key = self._normalize_stream_cache_key(media_path)
        if not is_youtube_music_media_fn(cache_key):
            return None

        now = time.monotonic()
        with self._stream_cache_lock:
            cache_entry = self._stream_cache.get(cache_key)
            if not cache_entry:
                return None

            if cache_entry["expires_at"] <= now:
                self._stream_cache.pop(cache_key, None)
                return None

            return ResolvedStreamPlayback(
                stream_url=cache_entry["resolved_url"],
                http_headers=dict(cache_entry.get("http_headers") or {}),
            )

    def _cache_stream_playback(self, media_path, resolved_playback):
        cache_key = self._normalize_stream_cache_key(media_path)
        normalized_resolved_url = str(getattr(resolved_playback, "stream_url", "") or "").strip()
        normalized_http_headers = dict(getattr(resolved_playback, "http_headers", {}) or {})
        if not cache_key or not normalized_resolved_url or not is_youtube_music_media_fn(cache_key):
            return resolved_playback

        cache_ttl_seconds = self._stream_cache_ttl_seconds(normalized_resolved_url)
        if cache_ttl_seconds <= 0:
            return ResolvedStreamPlayback(
                stream_url=normalized_resolved_url,
                http_headers=normalized_http_headers,
            )

        with self._stream_cache_lock:
            self._stream_cache[cache_key] = {
                "resolved_url": normalized_resolved_url,
                "http_headers": normalized_http_headers,
                "expires_at": time.monotonic() + cache_ttl_seconds,
            }

        return ResolvedStreamPlayback(
            stream_url=normalized_resolved_url,
            http_headers=normalized_http_headers,
        )

    def _stream_cache_ttl_seconds(self, stream_url):
        default_ttl_seconds = int(self._STREAM_CACHE_TTL_SECONDS)
        normalized_stream_url = str(stream_url or "").strip()
        if not normalized_stream_url:
            return default_ttl_seconds

        try:
            expire_value = parse_qs(urlparse(normalized_stream_url).query).get("expire", [""])[0]
            expiration_timestamp = int(float(expire_value))
        except (TypeError, ValueError):
            return default_ttl_seconds

        remaining_seconds = expiration_timestamp - int(time.time()) - self._STREAM_CACHE_EXPIRY_SAFETY_MARGIN_SECONDS
        if remaining_seconds <= 0:
            return 0

        return min(default_ttl_seconds, remaining_seconds)

    def prefetch_stream_url(self, media_path):
        cache_key = self._normalize_stream_cache_key(media_path)
        if not is_youtube_music_media_fn(cache_key):
            return False

        if self.get_cached_stream_url(cache_key):
            return True

        with self._stream_cache_lock:
            if cache_key in self._stream_prefetch_in_progress:
                return False
            self._stream_prefetch_in_progress.add(cache_key)

        def worker():
            try:
                self.resolve_stream_url(cache_key)
            except Exception:
                pass
            finally:
                with self._stream_cache_lock:
                    self._stream_prefetch_in_progress.discard(cache_key)

        threading.Thread(target=worker, daemon=True).start()
        return True

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
                raise RuntimeError("Selecione um arquivo browser.json, JSON de cookies ou cookies.txt válido.")
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
                "Cole os cabeçalhos do navegador ou selecione um browser.json, JSON de cookies ou cookies.txt válido."
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
        return target_path

    def get_account_info(self):
        if self._account_info is not None:
            return self._account_info

        client = self.get_client()
        try:
            account_info = client.get_account_info()
        except Exception as exc:
            self.clear_client_cache()
            raise RuntimeError("Não foi possível verificar se a conta do YouTube Music está conectada.") from exc

        if not isinstance(account_info, dict):
            raise RuntimeError("A resposta da conta do YouTube Music veio em formato inválido.")

        self._account_info = account_info
        return account_info

    def get_connected_account_name(self):
        account_info = self.get_account_info()
        return str(account_info.get("accountName") or account_info.get("channelHandle") or "Conta do YouTube Music").strip()

    def search(self, query, *, search_scope):
        normalized_query = str(query or "").strip()
        if not normalized_query:
            return []

        scope_option = get_search_scope_option(search_scope)
        if scope_option.requires_auth:
            client = self.get_client()
            raw_results = client.search(
                normalized_query,
                filter=scope_option.music_filter or None,
                limit=scope_option.limit,
            )
            return normalize_music_search_results(raw_results)

        return search_youtube_videos(normalized_query, limit=scope_option.limit)

    def get_library_playlists(self):
        client = self.get_client()
        try:
            raw_playlists = client.get_library_playlists(limit=None)
        except TypeError:
            raw_playlists = client.get_library_playlists()

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

        try:
            home_rows = client.get_home(limit=self._HOME_ROWS_PLAYLIST_DISCOVERY_LIMIT)
        except Exception:
            home_rows = []

        for item in extract_personalized_mix_summaries(home_rows):
            if item.playlist_id in seen_playlist_ids:
                continue
            playlists.append(item)
            seen_playlist_ids.add(item.playlist_id)

        playlists.sort(key=lambda playlist: playlist.title.casefold())
        return playlists

    def get_playlist_content(self, playlist_id, fallback_title=""):
        client = self.get_client()
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

            item_urls.append(self.build_watch_url(video_id, playlist_id=normalized_playlist_id))
            item_labels.append(track_display_label(track))

        return YouTubeMusicPlaylistContent(
            playlist_id=normalized_playlist_id,
            title=playlist_title,
            item_urls=item_urls,
            item_labels=item_labels,
        )

    def get_client(self):
        if self._client is not None:
            return self._client

        ytmusicapi = import_ytmusicapi_module()
        YTMusic = ytmusicapi.YTMusic

        if not self.has_saved_browser_auth():
            raise RuntimeError("Faça a autenticação do navegador antes de buscar playlists.")

        self._client = YTMusic(self.browser_auth_file_path)
        return self._client

    def save_search_result(self, search_result):
        client = self.get_client()

        result_type = str(getattr(search_result, "result_type", "") or "").strip().lower()
        playlist_id = str(getattr(search_result, "playlist_id", "") or "").strip()
        video_id = str(getattr(search_result, "video_id", "") or "").strip()
        feedback_add_token = str(getattr(search_result, "feedback_add_token", "") or "").strip()
        feedback_remove_token = str(getattr(search_result, "feedback_remove_token", "") or "").strip()

        ytmusicapi = import_ytmusicapi_module()
        LikeStatus = ytmusicapi.LikeStatus

        if result_type == "playlist" and playlist_id:
            client.rate_playlist(playlist_id, LikeStatus.LIKE)
            return "Playlist salva na biblioteca do YouTube Music."

        if result_type == "song":
            if feedback_remove_token and not feedback_add_token:
                return "A faixa já estava salva na biblioteca do YouTube Music."
            if feedback_add_token:
                client.edit_song_library_status([feedback_add_token])
                return "Faixa salva na biblioteca do YouTube Music."

        if video_id:
            client.rate_song(video_id, LikeStatus.LIKE)
            return "Resultado curtido no YouTube Music."

        raise RuntimeError("O resultado selecionado não pode ser salvo no YouTube Music.")

    def rate_media_feedback(self, media_path, rating):
        normalized_media_path = self._normalize_stream_cache_key(media_path)
        video_id = extract_video_id_from_text(normalized_media_path)
        if not video_id:
            raise RuntimeError("A mídia atual não tem um vídeo compatível para curtir ou marcar como não gostei.")

        ytmusicapi = import_ytmusicapi_module()
        LikeStatus = ytmusicapi.LikeStatus

        normalized_rating = str(rating or "").strip().upper()
        rating_map = {
            "LIKE": LikeStatus.LIKE,
            "DISLIKE": LikeStatus.DISLIKE,
            "INDIFFERENT": LikeStatus.INDIFFERENT,
        }
        like_status = rating_map.get(normalized_rating)
        if like_status is None:
            raise RuntimeError("A avaliação solicitada para a mídia atual é inválida.")

        client = self.get_client()
        client.rate_song(video_id, like_status)
        if like_status == LikeStatus.LIKE:
            return "Mídia atual curtida no YouTube Music."
        if like_status == LikeStatus.DISLIKE:
            return "Mídia atual marcada como não gostei no YouTube Music."
        return "Avaliação da mídia atual removida no YouTube Music."

    def add_search_result_to_playlist(self, search_result, target_playlist_id):
        client = self.get_client()

        normalized_target_playlist_id = str(target_playlist_id or "").strip()
        if not normalized_target_playlist_id:
            raise RuntimeError("Selecione uma playlist de destino do YouTube Music.")

        video_id = str(getattr(search_result, "video_id", "") or "").strip()
        if not video_id:
            raise RuntimeError("O resultado selecionado não tem um vídeo reproduzível para adicionar.")

        client.add_playlist_items(normalized_target_playlist_id, [video_id])
        return "Resultado adicionado à playlist selecionada do YouTube Music."

    def report_playback_to_history(self, media_path):
        normalized_media_path = self._normalize_stream_cache_key(media_path)
        if not is_music_youtube_url(normalized_media_path):
            return False

        video_id = extract_video_id_from_text(normalized_media_path)
        if not video_id:
            return False

        client = self.get_client()
        song = client.get_song(video_id)
        response = client.add_history_item(song)
        return getattr(response, "status_code", None) == 204

    def resolve_stream_url(self, media_path):
        return self.resolve_stream_playback(media_path).stream_url

    def resolve_stream_playback(self, media_path):
        normalized_media_path = self._normalize_stream_cache_key(media_path)
        cached_stream_playback = self.get_cached_stream_playback(normalized_media_path)
        if cached_stream_playback is not None:
            return cached_stream_playback

        resolved_stream_playback = resolve_music_stream_playback(normalized_media_path)
        return self._cache_stream_playback(normalized_media_path, resolved_stream_playback)

    def build_watch_url(self, video_id, playlist_id=None):
        return build_watch_url_fn(video_id, playlist_id=playlist_id)

    def build_playlist_source(self, playlist_id):
        return build_playlist_source_fn(playlist_id)

    @staticmethod
    def is_youtube_music_media(media_path):
        return is_youtube_music_media_fn(media_path)
