import threading

import wx

from ...constants import (
    REPEAT_ALL,
    REPEAT_ONE,
    YOUTUBE_MUSIC_RADIO_FETCH_LIMIT,
    YOUTUBE_MUSIC_RADIO_MAX_SEED_ATTEMPTS,
    YOUTUBE_MUSIC_RADIO_PREFETCH_LEAD_MS,
)
from ...i18n import _
from ...log import get_logger
from ...playlists import PlaylistState
from ...youtube_music.playlists import extract_video_id_from_text, is_youtube_music_media


_logger = get_logger(__name__)


class RelatedAutoplayMixin:
    def _related_autoplay_seed_video_id(self, state):
        """Return the seed videoId if *state* is currently sitting on the last
        item of a YouTube Music playlist that is eligible for related autoplay.

        Returns ``("", "")`` when related autoplay does not apply (option off,
        folder tab, not the last item, repeat modes that never end, or the
        current item is not a YouTube Music track with a usable videoId).
        """
        if not getattr(self.settings, "youtube_music_autoplay_related", False):
            return "", ""

        if not isinstance(state, PlaylistState) or state.is_folder_tab:
            return "", ""

        # Repeat-one replays forever and repeat-all wraps back to the start, so
        # the playlist never actually ends — related content is only needed when
        # we would otherwise run out of items.
        if state.repeat_mode in (REPEAT_ONE, REPEAT_ALL):
            return "", ""

        # Only act on the genuine last item (no next track without wrapping).
        if state.peek_in_playback_order(1) is not None:
            return "", ""

        seed_media_path = str(state.current_media_path or "").strip()
        if not is_youtube_music_media(seed_media_path):
            return "", ""

        video_id = extract_video_id_from_text(seed_media_path)
        if not video_id:
            return "", ""

        return seed_media_path, video_id

    def _maybe_prefetch_related_youtube_music(self):
        """Proactively fetch related content shortly before the last track ends.

        Runs on the progress timer. When the active playlist is about to finish
        its last YouTube Music track (and the option is enabled), this starts the
        radio fetch in the background so the new items — and the stream URL of the
        first one — are ready by the time the track ends, giving a seamless
        transition instead of pausing on the last frame while we look them up.
        """
        state = self._get_active_playlist_state()
        seed_media_path, _video_id = self._related_autoplay_seed_video_id(state)
        if not seed_media_path:
            return

        existing_request = getattr(self, "_related_autoplay", None)
        if existing_request is not None:
            if existing_request.get("seed") == seed_media_path:
                # Already fetching/appended/failed for this exact seed.
                return
            # The active track changed since the last request; drop the stale one
            # so this new last item can get its own related content.
            self._related_autoplay = None

        if self._youtube_music_service_for_playback() is None:
            return

        player = getattr(self, "player", None)
        if player is None or player.get_media() is None or not player.is_playing():
            return

        current_time = player.get_time()
        total_time = player.get_length()
        if current_time is None or current_time < 0 or total_time is None or total_time <= 0:
            return

        if (total_time - current_time) > YOUTUBE_MUSIC_RADIO_PREFETCH_LEAD_MS:
            return

        _logger.info("Proactively prefetching related content near the end of the last track.")
        self._begin_related_youtube_music_fetch(seed_media_path, advance_when_ready=False)

    def _try_autoplay_related_youtube_music(self, state):
        """Continue playback with related content when the playlist ends.

        Called from the end-of-media handler once there is no next track. If a
        proactive prefetch is already in flight (or finished) for this seed we
        reuse it; otherwise we start a fresh fetch. Returns ``True`` when related
        autoplay will handle the end (so the caller should not announce the
        playlist as finished).
        """
        seed_media_path, _video_id = self._related_autoplay_seed_video_id(state)
        if not seed_media_path:
            return False

        request = getattr(self, "_related_autoplay", None)
        if request and request.get("seed") == seed_media_path:
            status = request.get("status")
            if status == "pending":
                # Proactive fetch still running: advance as soon as it lands.
                request["advance_when_ready"] = True
                _logger.debug("Related autoplay: awaiting in-flight prefetch for the seed track.")
                self._announce(_("Buscando conteúdo relacionado no YouTube Music."))
                return True
            if status == "appended":
                # Items were already added proactively; advance into them now.
                return self._advance_into_related_content(state)
            if status == "failed":
                _logger.debug("Related autoplay: previous fetch failed for the seed track.")
                return False

        if self._youtube_music_service_for_playback() is None:
            _logger.debug("Related autoplay skipped: YouTube Music service unavailable.")
            return False

        _logger.info("Fetching related content (radio) at end of playlist.")
        self._announce(_("Buscando conteúdo relacionado no YouTube Music."))
        self._begin_related_youtube_music_fetch(seed_media_path, advance_when_ready=True)
        return True

    def _begin_related_youtube_music_fetch(self, seed_media_path, *, advance_when_ready):
        video_id = extract_video_id_from_text(seed_media_path)
        if not video_id or self._youtube_music_service_for_playback() is None:
            return

        self._related_autoplay = {
            "seed": seed_media_path,
            "status": "pending",
            "advance_when_ready": bool(advance_when_ready),
            "tried_video_ids": [video_id],
        }
        self._dispatch_related_youtube_music_fetch(seed_media_path, video_id)

    def _related_autoplay_known_video_ids(self, state):
        """videoIds the playlist already holds, so the radio cannot repeat them."""
        known_video_ids = []
        for item in getattr(state, "items", None) or ():
            video_id = extract_video_id_from_text(item)
            if video_id:
                known_video_ids.append(video_id)
        return known_video_ids

    def _dispatch_related_youtube_music_fetch(self, seed_media_path, radio_video_id):
        youtube_music_service = self._youtube_music_service_for_playback()
        if youtube_music_service is None:
            return

        state = self._active_state_awaiting_related(seed_media_path)
        exclude_video_ids = self._related_autoplay_known_video_ids(state) if state is not None else []
        continue_playlist_id = getattr(state, "radio_queue_playlist_id", None) if state is not None else None

        def worker():
            radio_content = None
            error_message = ""
            try:
                radio_content = youtube_music_service.get_radio_content(
                    radio_video_id,
                    limit=YOUTUBE_MUSIC_RADIO_FETCH_LIMIT,
                    exclude_video_ids=exclude_video_ids,
                    continue_playlist_id=continue_playlist_id,
                )
            except Exception as exc:
                error_message = str(exc) or exc.__class__.__name__
                _logger.warning(
                    "Related content fetch failed for videoId=%s: %s", radio_video_id, exc, exc_info=True
                )

            wx.CallAfter(
                self._finish_related_youtube_music_fetch,
                seed_media_path,
                radio_content,
                error_message,
            )

        threading.Thread(target=worker, daemon=True).start()

    def _next_related_autoplay_seed(self, state, tried_video_ids):
        """Pick an earlier track of the playlist to seed a different radio."""
        already_tried = set(tried_video_ids or ())
        for item in reversed(getattr(state, "items", None) or ()):
            video_id = extract_video_id_from_text(item)
            if video_id and video_id not in already_tried:
                return video_id
        return None

    def _retry_related_youtube_music_with_new_seed(self, request, state, seed_media_path):
        """Re-seed the radio when a fetch brought back only known tracks.

        The last track's radio revolves around the very tracks that produced it,
        so once they are all filtered out an earlier item is a better seed than
        giving up and ending the playlist.
        """
        tried_video_ids = request.setdefault("tried_video_ids", [])
        if len(tried_video_ids) >= YOUTUBE_MUSIC_RADIO_MAX_SEED_ATTEMPTS:
            return False

        next_video_id = self._next_related_autoplay_seed(state, tried_video_ids)
        if not next_video_id:
            return False

        tried_video_ids.append(next_video_id)
        request["status"] = "pending"
        # The remembered queue had nothing new either, so stop trying to continue
        # it and let the new seed open a fresh radio.
        state.radio_queue_playlist_id = None
        _logger.info("Related content had no new tracks; retrying the radio with an earlier seed track.")
        self._dispatch_related_youtube_music_fetch(seed_media_path, next_video_id)
        return True

    def _active_state_awaiting_related(self, seed_media_path):
        """Return the active playlist state if it is still sitting on *seed*."""
        state = self._get_active_playlist_state()
        if (
            isinstance(state, PlaylistState)
            and not state.is_folder_tab
            and str(state.current_media_path or "").strip() == seed_media_path
        ):
            return state
        return None

    def _finish_related_youtube_music_fetch(self, seed_media_path, radio_content, error_message=""):
        request = getattr(self, "_related_autoplay", None)
        if not request or request.get("seed") != seed_media_path:
            # A newer request (or playback change) superseded this fetch.
            return

        advance_when_ready = bool(request.get("advance_when_ready"))
        state = self._active_state_awaiting_related(seed_media_path)
        if state is None:
            # The seed is no longer the active track; discard the result.
            self._related_autoplay = None
            return

        if error_message:
            request["status"] = "failed"
            if advance_when_ready:
                self._related_autoplay = None
                self._announce(
                    _("Playlist {title} finalizada. Não foi possível buscar conteúdo relacionado: {error}.").format(title=state.title, error=error_message)
                )
            return

        item_urls = list(getattr(radio_content, "item_urls", None) or [])
        if not item_urls:
            if self._retry_related_youtube_music_with_new_seed(request, state, seed_media_path):
                return
            _logger.info("Related content fetch returned no usable tracks for the seed track.")
            request["status"] = "failed"
            if advance_when_ready:
                self._related_autoplay = None
                self._announce(_("Playlist {title} finalizada. Nenhum conteúdo relacionado encontrado.").format(title=state.title))
            return

        if request.get("status") != "appended":
            _logger.info("Related content added %d track(s) to playlist %r.", len(item_urls), state.title)
            # Remember the queue so the next fetch continues it instead of
            # opening a new radio around the same pool of tracks.
            state.radio_queue_playlist_id = str(getattr(radio_content, "playlist_id", "") or "").strip() or None
            state.append_items(item_urls, getattr(radio_content, "item_labels", None))
            request["status"] = "appended"
            self._refresh_playlist_browser()
            # Resolve the first new track's stream ahead of time, exactly like the
            # normal next-track prefetch, so the upcoming transition is seamless.
            prefetch_upcoming = getattr(self, "_prefetch_upcoming_media_stream", None)
            if callable(prefetch_upcoming):
                prefetch_upcoming(state)
            if not advance_when_ready and hasattr(self, "_set_status_message"):
                self._set_status_message(_("Conteúdo relacionado adicionado à playlist."))

        if advance_when_ready:
            self._related_autoplay = None
            self._advance_into_related_content(state)

    def _advance_into_related_content(self, state):
        target = state.move_in_playback_order(1)
        if not target:
            self._announce(_("Playlist {title} finalizada.").format(title=state.title))
            return False

        self._play_media(
            index=self._get_active_playlist_index(),
            announce_message=_("Conteúdo relacionado. {position}").format(position=self._describe_playlist_position(state)),
        )
        return True
