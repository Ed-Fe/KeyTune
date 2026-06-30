import os
import threading
import time

import wx

from ...i18n import _

from ...library import is_remote_media_path
from ...playlists import PlaylistState
from ...remote_media_metadata import resolve_remote_media_metadata, resolve_remote_media_playback
from .helpers import _should_apply_runtime_stream_title, is_youtube_music_media


class MediaMetadataMixin:
    def _normalize_media_comparison_path(self, media_path):
        normalized_path = str(media_path or "").strip()
        if not normalized_path:
            return ""

        if "://" in normalized_path:
            return normalized_path.casefold()

        return os.path.normcase(os.path.normpath(normalized_path))

    def _media_paths_match(self, first_path, second_path):
        return self._normalize_media_comparison_path(first_path) == self._normalize_media_comparison_path(second_path)

    def _resolve_media_for_playback_details(self, media_path):
        if is_remote_media_path(media_path) and not is_youtube_music_media(media_path):
            resolved_playback = resolve_remote_media_playback(media_path)
            return (
                resolved_playback.stream_url or str(media_path or "").strip(),
                dict(getattr(resolved_playback, "http_headers", {}) or {}),
                str(getattr(resolved_playback, "title", "") or "").strip(),
                str(getattr(resolved_playback, "artist", "") or "").strip(),
            )

        if not is_youtube_music_media(media_path):
            return media_path, {}, "", ""

        youtube_music_service = self._youtube_music_service_for_playback()
        if youtube_music_service is None:
            return media_path, {}, "", ""

        resolved_playback = youtube_music_service.resolve_stream_playback(media_path)
        return (
            resolved_playback.stream_url,
            dict(getattr(resolved_playback, "http_headers", {}) or {}),
            str(getattr(resolved_playback, "display_title", "") or "").strip(),
            str(getattr(resolved_playback, "display_artist", "") or "").strip(),
        )

    def _resolve_media_for_playback(self, media_path):
        playback_media_path, playback_http_headers, _display_title, _display_artist = self._resolve_media_for_playback_details(media_path)
        return playback_media_path, playback_http_headers

    def _media_label_from_playlist_state(self, state, media_path):
        if not isinstance(state, PlaylistState):
            return None

        media_index = state.index_of_item(media_path)
        if media_index is None:
            return None

        if 0 <= media_index < len(state.browser_item_labels):
            label = str(state.browser_item_labels[media_index] or "").strip()
            if label:
                return label

        return None

    def _media_label(self, media_path):
        if not media_path:
            return _("Sem mídia")

        checked_states = []
        current_state = self._get_playlist_state()
        if current_state is not None:
            checked_states.append(current_state)
        active_state = self._get_active_playlist_state()
        if active_state is not None and active_state is not current_state:
            checked_states.append(active_state)
        for state in getattr(self, "playlists", []):
            if state not in checked_states:
                checked_states.append(state)

        for state in checked_states:
            playlist_label = self._media_label_from_playlist_state(state, media_path)
            if playlist_label:
                return playlist_label

        normalized_path = str(media_path).rstrip("\\/")
        media_name = os.path.basename(normalized_path)
        return media_name or normalized_path

    def _apply_media_display_metadata(self, media_path, title, artist=""):
        normalized_media_path = str(media_path or "").strip()
        normalized_title = str(title or "").strip()
        normalized_artist = str(artist or "").strip()
        if not normalized_media_path or not normalized_title:
            return False

        item_label = normalized_title
        if normalized_artist and normalized_artist.casefold() not in normalized_title.casefold():
            item_label = f"{normalized_artist} — {normalized_title}"

        updated = False
        for state in getattr(self, "playlists", []):
            if not isinstance(state, PlaylistState):
                continue

            media_index = state.index_of_item(normalized_media_path)
            if media_index is None:
                continue

            while len(state.browser_item_labels) <= media_index:
                state.browser_item_labels.append("")

            if state.browser_item_labels[media_index] != item_label:
                state.browser_item_labels[media_index] = item_label
                state.refresh_browser_item_labels()
                updated = True

            if len(state.items) == 1 and not state.source_path and state.title != item_label:
                state.title = item_label
                state_index = self._resolve_playlist_state_index(state)
                if state_index != wx.NOT_FOUND:
                    self.notebook.SetPageText(state_index, item_label)
                updated = True

        if not updated:
            return False

        self._update_title()
        self._refresh_playlist_browser()
        refresh_smtc = getattr(self, "_refresh_smtc_state", None)
        if callable(refresh_smtc):
            refresh_smtc()
        return True

    def _queue_remote_media_metadata_resolution(self, media_path):
        normalized_media_path = str(media_path or "").strip()
        if not normalized_media_path or not is_remote_media_path(normalized_media_path):
            return
        if is_youtube_music_media(normalized_media_path):
            return

        self._remote_media_metadata_request_serial += 1
        request_serial = self._remote_media_metadata_request_serial

        def worker():
            metadata = resolve_remote_media_metadata(normalized_media_path)
            wx.CallAfter(
                self._finish_remote_media_metadata_resolution,
                normalized_media_path,
                metadata.title,
                metadata.artist,
                request_serial,
            )

        threading.Thread(target=worker, daemon=True).start()

    def _finish_remote_media_metadata_resolution(self, media_path, title, artist, request_serial):
        if request_serial != getattr(self, "_remote_media_metadata_request_serial", 0):
            return
        self._apply_media_display_metadata(media_path, title, artist)

    def _refresh_active_runtime_stream_title(self, *, force=False):
        state = self._get_playlist_state()
        media_path = str(getattr(state, "current_media_path", "") or "").strip() if state else ""
        if not media_path or not is_remote_media_path(media_path):
            self._last_runtime_stream_title = ""
            self._next_runtime_stream_title_refresh = 0.0
            return

        now = time.monotonic()
        if not force and now < float(getattr(self, "_next_runtime_stream_title_refresh", 0.0) or 0.0):
            return
        self._next_runtime_stream_title_refresh = now + 2.0

        player = getattr(self, "player", None)
        if player is None:
            return

        try:
            runtime_title = str(player.get_current_media_title() or "").strip()
        except Exception:
            runtime_title = ""

        if not runtime_title or runtime_title == getattr(self, "_last_runtime_stream_title", ""):
            return

        current_label = self._media_label_from_playlist_state(state, media_path) if state else ""
        if not _should_apply_runtime_stream_title(media_path, current_label, runtime_title):
            return

        self._last_runtime_stream_title = runtime_title
        self._apply_media_display_metadata(media_path, runtime_title)
