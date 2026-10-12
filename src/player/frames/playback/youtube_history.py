import threading
import time

import wx

from ...playlists import PlaylistState
from .helpers import is_music_youtube_url, is_youtube_music_media


def _is_regular_youtube_media(media_path):
    from ...youtube_music.playlists import is_regular_youtube_media

    return is_regular_youtube_media(media_path)


class YouTubeHistoryMixin:
    _YOUTUBE_MUSIC_HISTORY_MINIMUM_MS = 15000
    _YOUTUBE_MUSIC_HISTORY_MAXIMUM_MS = 30000
    _YOUTUBE_MUSIC_HISTORY_PROGRESS_FRACTION = 0.3
    # De quanto em quanto tempo o YouTube fica sabendo até onde o vídeo foi assistido, e o
    # quanto a posição precisa ter mudado para valer um aviso novo.
    _YOUTUBE_WATCH_TIME_INTERVAL_SECONDS = 30.0
    _YOUTUBE_WATCH_TIME_MINIMUM_CHANGE_MS = 5000

    def _youtube_music_service_for_playback(self):
        youtube_music_service = getattr(self, "_youtube_music_service", None)
        if youtube_music_service is not None:
            return youtube_music_service

        get_service = getattr(self, "_get_youtube_music_service", None)
        if callable(get_service):
            return get_service()

        return None

    def _clear_youtube_music_history_tracking(self):
        self._flush_youtube_watch_time()
        self._youtube_music_history_tracking = {}

    def _prepare_youtube_music_history_tracking(self, media_path):
        # O vídeo que estava tocando avisa onde parou antes de dar lugar ao próximo.
        self._flush_youtube_watch_time()
        normalized_media_path = str(media_path or "").strip()
        # Vale para as faixas do YouTube Music e para os vídeos do YouTube comum.
        if not is_youtube_music_media(normalized_media_path):
            self._clear_youtube_music_history_tracking()
            return False

        self._youtube_music_history_tracking = {
            "media_path": normalized_media_path,
            "attempted": False,
            "reported": False,
            # Só os vídeos do YouTube comum têm barra de progresso para continuar depois.
            "watch_time": _is_regular_youtube_media(normalized_media_path),
        }
        return True

    def _maybe_report_youtube_watch_time(self):
        """Avisa o YouTube, de tempos em tempos, até onde o vídeo atual já foi assistido."""
        tracking_state = getattr(self, "_youtube_music_history_tracking", None)
        if not tracking_state or not tracking_state.get("watch_time") or not tracking_state.get("reported"):
            return False

        media_path = str(tracking_state.get("media_path") or "").strip()
        if not media_path or not self._media_paths_match(media_path, self._player_loaded_media_path()):
            return False
        if not hasattr(self, "player") or self.player.get_media() is None:
            return False

        current_time = self.player.get_time()
        if current_time is None or current_time < 0:
            return False

        tracking_state["position_ms"] = int(current_time)
        elapsed = time.monotonic() - tracking_state.get("watch_time_sent_at", 0.0)
        if elapsed < self._YOUTUBE_WATCH_TIME_INTERVAL_SECONDS:
            return False
        return self._send_youtube_watch_time(tracking_state)

    def _flush_youtube_watch_time(self):
        """Manda a última posição conhecida do vídeo que está saindo, sem esperar o intervalo."""
        tracking_state = getattr(self, "_youtube_music_history_tracking", None)
        if not tracking_state or not tracking_state.get("watch_time") or not tracking_state.get("reported"):
            return False
        return self._send_youtube_watch_time(tracking_state)

    def _send_youtube_watch_time(self, tracking_state):
        position_ms = tracking_state.get("position_ms")
        if position_ms is None or tracking_state.get("watch_time_busy"):
            return False
        sent_position_ms = tracking_state.get("watch_time_sent_position_ms")
        if (
            sent_position_ms is not None
            and abs(position_ms - sent_position_ms) < self._YOUTUBE_WATCH_TIME_MINIMUM_CHANGE_MS
        ):
            return False

        tracking_state["watch_time_busy"] = True
        tracking_state["watch_time_sent_at"] = time.monotonic()
        tracking_state["watch_time_sent_position_ms"] = position_ms
        media_path = str(tracking_state.get("media_path") or "").strip()

        def worker():
            try:
                from ...youtube_music.watch_history import report_watch_position

                report_watch_position(media_path, position_ms / 1000)
            except Exception:
                # O aviso seguinte leva a posição nova; um que falhou não faz falta.
                pass
            finally:
                tracking_state["watch_time_busy"] = False

        threading.Thread(target=worker, daemon=True, name="youtube-watch-time").start()
        return True

    def _youtube_music_history_threshold_ms(self, total_time_ms):
        try:
            normalized_total_time_ms = int(total_time_ms)
        except (TypeError, ValueError):
            normalized_total_time_ms = 0

        if normalized_total_time_ms <= 0:
            return self._YOUTUBE_MUSIC_HISTORY_MINIMUM_MS

        threshold_ms = int(round(normalized_total_time_ms * self._YOUTUBE_MUSIC_HISTORY_PROGRESS_FRACTION))
        return max(
            self._YOUTUBE_MUSIC_HISTORY_MINIMUM_MS,
            min(self._YOUTUBE_MUSIC_HISTORY_MAXIMUM_MS, threshold_ms),
        )

    def _maybe_report_youtube_music_history(self):
        tracking_state = getattr(self, "_youtube_music_history_tracking", None)
        if not tracking_state or tracking_state.get("attempted"):
            return False

        settings = getattr(self, "settings", None)
        if settings is not None and not getattr(settings, "youtube_music_save_history", True):
            return False

        media_path = str(tracking_state.get("media_path") or "").strip()
        if not media_path or not self._media_paths_match(media_path, self._player_loaded_media_path()):
            return False

        if not hasattr(self, "player") or self.player.get_media() is None or not self.player.is_playing():
            return False

        current_time = self.player.get_time()
        if current_time is None or current_time < 0:
            return False

        total_time = self.player.get_length()
        if current_time < self._youtube_music_history_threshold_ms(total_time):
            return False

        youtube_music_service = self._youtube_music_service_for_playback()
        if youtube_music_service is None:
            tracking_state["attempted"] = True
            return False

        if not getattr(youtube_music_service, "has_saved_browser_auth", lambda: False)():
            tracking_state["attempted"] = True
            return False

        tracking_state["attempted"] = True

        def worker(expected_media_path):
            success = False
            try:
                success = bool(youtube_music_service.report_playback_to_history(expected_media_path))
            except Exception:
                success = False

            def finish():
                current_tracking_state = getattr(self, "_youtube_music_history_tracking", None)
                if not current_tracking_state:
                    return

                current_media_path = str(current_tracking_state.get("media_path") or "").strip()
                if not self._media_paths_match(current_media_path, expected_media_path):
                    return

                current_tracking_state["reported"] = success

            wx.CallAfter(finish)

        threading.Thread(target=worker, args=(media_path,), daemon=True).start()
        return True

    def _youtube_music_media_requires_prefetched_stream(self, media_path):
        if not is_youtube_music_media(media_path):
            return False

        youtube_music_service = self._youtube_music_service_for_playback()
        if youtube_music_service is None:
            return False

        return not bool(youtube_music_service.get_cached_stream_url(media_path))

    def _prefetch_media_stream(self, media_path):
        if not is_youtube_music_media(media_path):
            return False

        youtube_music_service = self._youtube_music_service_for_playback()
        if youtube_music_service is None:
            return False

        return bool(youtube_music_service.prefetch_stream_url(media_path))

    def _prefetch_upcoming_media_stream(self, state):
        if not isinstance(state, PlaylistState) or state.is_folder_tab or not state.current_media_path:
            return False

        should_wrap = str(getattr(state, "repeat_mode", "")).strip().lower() == "all"
        next_media_path = state.peek_in_playback_order(1, wrap=should_wrap)
        if not next_media_path:
            return False

        return self._prefetch_media_stream(next_media_path)
