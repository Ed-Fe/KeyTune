import threading

import wx

from ...constants import (
    REPEAT_OFF,
    YOUTUBE_MUSIC_RADIO_FETCH_LIMIT,
    YOUTUBE_MUSIC_RADIO_NEW_STATION_ATTEMPTS,
    YOUTUBE_MUSIC_RADIO_RECENT_LIMIT,
)
from ...i18n import _
from ...log import get_logger
from ...playlists import PlaylistState
from ...youtube_music.playlists import extract_video_id_from_text, is_youtube_music_media


_logger = get_logger(__name__)


class StationRadioMixin:
    """Create a fresh radio tab from the current YouTube Music track."""

    def _youtube_music_radio_recent_video_ids(self):
        recent = getattr(self, "_youtube_music_radio_recent", None)
        if not isinstance(recent, list):
            recent = []
            self._youtube_music_radio_recent = recent
        return recent

    def _remember_youtube_music_radio_playback(self, media_path):
        if not is_youtube_music_media(media_path):
            return False
        video_id = extract_video_id_from_text(media_path)
        if not video_id:
            return False

        recent = self._youtube_music_radio_recent_video_ids()
        recent[:] = [candidate for candidate in recent if candidate != video_id]
        recent.append(video_id)
        del recent[:-YOUTUBE_MUSIC_RADIO_RECENT_LIMIT]
        return True

    def _restore_youtube_music_radio_recent(self, values):
        if not isinstance(values, (list, tuple)):
            values = ()
        recent = []
        for value in values or ():
            video_id = str(value or "").strip()
            if video_id and video_id not in recent:
                recent.append(video_id)
        self._youtube_music_radio_recent = recent[-YOUTUBE_MUSIC_RADIO_RECENT_LIMIT:]

    def _youtube_music_radio_recent_for_session(self):
        return list(self._youtube_music_radio_recent_video_ids())

    def _new_station_excluded_video_ids(self, source_state, seed_video_id):
        excluded = set(self._youtube_music_radio_recent_video_ids())
        if isinstance(source_state, PlaylistState):
            last_seen_index = max(0, int(source_state.current_index or 0))
            for media_path in source_state.items[: last_seen_index + 1]:
                video_id = extract_video_id_from_text(media_path)
                if video_id:
                    excluded.add(video_id)
        excluded.discard(seed_video_id)
        return excluded

    def on_start_radio_from_current(self, _event=None):
        source_state = self._get_active_playlist_state()
        media_path = str(getattr(source_state, "current_media_path", "") or "").strip()
        if not media_path:
            self._announce(_("Nenhuma mídia está tocando para iniciar uma rádio."))
            return False
        if not is_youtube_music_media(media_path):
            self._announce(_("A mídia atual não é uma faixa compatível do YouTube Music."))
            return False

        seed_video_id = extract_video_id_from_text(media_path)
        youtube_music_service = self._youtube_music_service_for_playback()
        if not seed_video_id or youtube_music_service is None:
            self._announce(_("O serviço do YouTube Music não está disponível para iniciar a rádio."))
            return False

        self._capture_active_playlist_state()
        source_label = self._media_label(media_path)
        excluded_video_ids = self._new_station_excluded_video_ids(source_state, seed_video_id)
        self._remember_youtube_music_radio_playback(media_path)
        self._related_autoplay = None

        target_index = self._create_empty_playlist_tab(select=False)
        target_state = self._get_playlist_state(target_index)
        if target_state is None:
            return False

        target_state.finish_library_load()
        target_state.clear_folder_location()
        target_state.title = _("Rádio: {name}").format(name=source_label)
        target_state.source_path = None
        target_state.shuffle_enabled = False
        target_state.repeat_mode = REPEAT_OFF
        target_state.radio_queue_playlist_id = None
        target_state.set_items_prepared(
            [media_path],
            {media_path: 0},
            [source_label],
            start_index=0,
        )
        target_state.last_position_ms = max(0, int(getattr(source_state, "last_position_ms", 0) or 0))
        target_state.was_playing = bool(getattr(source_state, "was_playing", False))

        self.notebook.SetPageText(target_index, target_state.title)
        self._select_tab(target_index, announce=False)
        self._refresh_playlist_browser()
        message = _("Nova rádio iniciada com {name} como primeira faixa.").format(name=source_label)
        self._announce(message)
        if hasattr(self, "_set_status_message"):
            self._set_status_message(_("Buscando músicas inéditas para a nova rádio."))

        self._fetch_new_station_tracks(
            target_state,
            media_path,
            seed_video_id,
            excluded_video_ids,
        )
        return True

    def _fetch_new_station_tracks(self, target_state, seed_media_path, seed_video_id, excluded_video_ids):
        youtube_music_service = self._youtube_music_service_for_playback()
        if youtube_music_service is None:
            return False

        def worker():
            collected_urls = []
            collected_labels = []
            known_video_ids = set(excluded_video_ids or ())
            known_video_ids.add(seed_video_id)
            radio_playlist_id = ""
            last_error = ""
            target_count = max(1, YOUTUBE_MUSIC_RADIO_FETCH_LIMIT - 1)

            for _attempt in range(YOUTUBE_MUSIC_RADIO_NEW_STATION_ATTEMPTS):
                try:
                    content = youtube_music_service.get_radio_content(
                        seed_video_id,
                        limit=YOUTUBE_MUSIC_RADIO_FETCH_LIMIT,
                        exclude_video_ids=known_video_ids,
                        continue_playlist_id=None,
                    )
                except Exception as exc:
                    last_error = str(exc) or exc.__class__.__name__
                    _logger.warning("Fresh YouTube Music radio fetch failed: %s", exc, exc_info=True)
                    continue

                item_urls = list(getattr(content, "item_urls", None) or [])
                item_labels = list(getattr(content, "item_labels", None) or [])
                if item_urls:
                    radio_playlist_id = str(getattr(content, "playlist_id", "") or "").strip() or radio_playlist_id
                for index, item_url in enumerate(item_urls):
                    video_id = extract_video_id_from_text(item_url)
                    if not video_id or video_id in known_video_ids:
                        continue
                    known_video_ids.add(video_id)
                    collected_urls.append(item_url)
                    collected_labels.append(item_labels[index] if index < len(item_labels) else "")
                    if len(collected_urls) >= target_count:
                        break
                if len(collected_urls) >= target_count:
                    break

            wx.CallAfter(
                self._finish_new_station_tracks,
                target_state,
                seed_media_path,
                collected_urls,
                collected_labels,
                radio_playlist_id,
                last_error,
            )

        threading.Thread(target=worker, daemon=True).start()
        return True

    def _finish_new_station_tracks(
        self,
        target_state,
        seed_media_path,
        item_urls,
        item_labels,
        radio_playlist_id,
        error_message="",
    ):
        if self._resolve_playlist_state_index(target_state) == wx.NOT_FOUND:
            return False
        if not target_state.items or target_state.items[0] != seed_media_path:
            return False

        if item_urls:
            target_state.append_items(item_urls, item_labels)
            target_state.radio_queue_playlist_id = str(radio_playlist_id or "").strip() or None
            if self._is_current_playlist_state(target_state):
                self._refresh_playlist_browser()
                prefetch_upcoming = getattr(self, "_prefetch_upcoming_media_stream", None)
                if callable(prefetch_upcoming):
                    prefetch_upcoming(target_state)
            message = _("Nova rádio pronta com {count} músicas sem repetição recente.").format(
                count=len(item_urls) + 1
            )
        elif error_message:
            message = _("A rádio foi criada, mas não foi possível buscar músicas relacionadas: {error}.").format(
                error=error_message
            )
        else:
            message = _("A rádio foi criada, mas o YouTube Music não retornou músicas inéditas agora.")

        if hasattr(self, "_set_status_message"):
            self._set_status_message(message)
        self._announce(message)
        return bool(item_urls)
