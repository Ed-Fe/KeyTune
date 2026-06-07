import threading
import time
from urllib.parse import parse_qs, urlparse

from .playlists import is_youtube_music_media as is_youtube_music_media_fn
from .streams import ResolvedStreamPlayback
from ..log import get_logger


_logger = get_logger(__name__)


def normalize_media_path(media_path):
    """Normalize a media path string for use as a cache key."""
    return str(media_path or "").strip()


class YouTubeMusicStreamCache:
    """Thread-safe cache for resolved YouTube Music stream URLs.

    Handles TTL calculation (including Google's ``expire`` query parameter),
    cache lookups, insertions, and background prefetch coordination.
    """

    _DEFAULT_TTL_SECONDS = 300
    _EXPIRY_SAFETY_MARGIN_SECONDS = 30

    def __init__(self):
        self._cache = {}
        self._lock = threading.Lock()
        self._prefetch_in_progress = set()

    def get_cached_stream_url(self, media_path):
        """Return the cached stream URL for *media_path*, or ``None``."""
        cached_playback = self.get_cached_stream_playback(media_path)
        if cached_playback is None:
            return None
        return cached_playback.stream_url

    def get_cached_stream_playback(self, media_path):
        """Return a cached :class:`ResolvedStreamPlayback`, or ``None``."""
        cache_key = normalize_media_path(media_path)
        if not is_youtube_music_media_fn(cache_key):
            return None

        now = time.monotonic()
        with self._lock:
            cache_entry = self._cache.get(cache_key)
            if not cache_entry:
                return None

            if cache_entry["expires_at"] <= now:
                self._cache.pop(cache_key, None)
                return None

            return ResolvedStreamPlayback(
                stream_url=cache_entry["resolved_url"],
                http_headers=dict(cache_entry.get("http_headers") or {}),
                display_title=str(cache_entry.get("display_title") or "").strip(),
                display_artist=str(cache_entry.get("display_artist") or "").strip(),
            )

    def cache_stream_playback(self, media_path, resolved_playback):
        """Store *resolved_playback* in the cache and return a normalized copy."""
        cache_key = normalize_media_path(media_path)
        normalized_resolved_url = str(getattr(resolved_playback, "stream_url", "") or "").strip()
        normalized_http_headers = dict(getattr(resolved_playback, "http_headers", {}) or {})
        normalized_display_title = str(getattr(resolved_playback, "display_title", "") or "").strip()
        normalized_display_artist = str(getattr(resolved_playback, "display_artist", "") or "").strip()
        if not cache_key or not normalized_resolved_url or not is_youtube_music_media_fn(cache_key):
            return resolved_playback

        cache_ttl_seconds = self._cache_ttl_seconds(normalized_resolved_url)
        if cache_ttl_seconds <= 0:
            return ResolvedStreamPlayback(
                stream_url=normalized_resolved_url,
                http_headers=normalized_http_headers,
                display_title=normalized_display_title,
                display_artist=normalized_display_artist,
            )

        with self._lock:
            self._cache[cache_key] = {
                "resolved_url": normalized_resolved_url,
                "http_headers": normalized_http_headers,
                "display_title": normalized_display_title,
                "display_artist": normalized_display_artist,
                "expires_at": time.monotonic() + cache_ttl_seconds,
            }

        return ResolvedStreamPlayback(
            stream_url=normalized_resolved_url,
            http_headers=normalized_http_headers,
            display_title=normalized_display_title,
            display_artist=normalized_display_artist,
        )

    def prefetch_stream_url(self, media_path, resolve_fn):
        """Start a background thread to resolve and cache a stream URL.

        Parameters
        ----------
        media_path:
            The YouTube Music URL to resolve.
        resolve_fn:
            A callable ``resolve_fn(media_path) -> ResolvedStreamPlayback``
            used to obtain the stream playback when the cache misses.

        Returns ``True`` if a prefetch was started or the result is already
        cached, ``False`` otherwise.
        """
        cache_key = normalize_media_path(media_path)
        if not is_youtube_music_media_fn(cache_key):
            return False

        if self.get_cached_stream_url(cache_key):
            return True

        with self._lock:
            if cache_key in self._prefetch_in_progress:
                return False
            self._prefetch_in_progress.add(cache_key)

        def worker():
            try:
                resolved = resolve_fn(cache_key)
                self.cache_stream_playback(cache_key, resolved)
            except Exception:
                pass
            finally:
                with self._lock:
                    self._prefetch_in_progress.discard(cache_key)

        threading.Thread(target=worker, daemon=True).start()
        return True

    def resolve_stream_playback(self, media_path, resolve_fn):
        """Return a :class:`ResolvedStreamPlayback`, using the cache when possible.

        Parameters
        ----------
        media_path:
            The YouTube Music URL to resolve.
        resolve_fn:
            A callable ``resolve_fn(media_path) -> ResolvedStreamPlayback``
            used to obtain the stream playback when the cache misses.
        """
        normalized_media_path = normalize_media_path(media_path)
        cached_stream_playback = self.get_cached_stream_playback(normalized_media_path)
        if cached_stream_playback is not None:
            _logger.debug("Stream cache hit for: %s", normalized_media_path)
            return cached_stream_playback

        _logger.debug("Stream cache miss; delegating resolution for: %s", normalized_media_path)
        resolved_stream_playback = resolve_fn(normalized_media_path)
        return self.cache_stream_playback(normalized_media_path, resolved_stream_playback)

    def clear(self):
        """Discard all cached entries and cancel pending prefetch tracking."""
        with self._lock:
            self._cache = {}
            self._prefetch_in_progress = set()

    def _cache_ttl_seconds(self, stream_url):
        """Compute how long a resolved stream URL should be cached.

        Google's signed URLs contain an ``expire`` query parameter.  When
        present, the TTL is capped to the remaining lifetime of the URL
        minus a small safety margin.
        """
        default_ttl_seconds = int(self._DEFAULT_TTL_SECONDS)
        normalized_stream_url = str(stream_url or "").strip()
        if not normalized_stream_url:
            return default_ttl_seconds

        try:
            expire_value = parse_qs(urlparse(normalized_stream_url).query).get("expire", [""])[0]
            expiration_timestamp = int(float(expire_value))
        except (TypeError, ValueError):
            return default_ttl_seconds

        remaining_seconds = expiration_timestamp - int(time.time()) - self._EXPIRY_SAFETY_MARGIN_SECONDS
        if remaining_seconds <= 0:
            return 0

        return min(default_ttl_seconds, remaining_seconds)
