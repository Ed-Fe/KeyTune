import contextlib
import queue
import sys


from ...i18n import _
import wx

from ...library import is_audio_playback_media
from .helpers import is_youtube_music_media


class PlaybackEngineMixin:
    def _initialize_player_state(self):
        self._bind_player_to_window()
        self._remote_media_metadata_request_serial = 0
        self._last_runtime_stream_title = ""
        self._next_runtime_stream_title_refresh = 0.0
        if self.settings.restore_session_on_startup and self._restore_session():
            return

        self._update_title()
        self._announce(_("Nenhuma mídia tocando agora."))

    def _next_playback_request_serial(self):
        self._playback_request_serial += 1
        return self._playback_request_serial

    def _playback_worker_loop(self):
        while True:
            request = self._playback_queue.get()
            while True:
                try:
                    newer_request = self._playback_queue.get_nowait()
                except queue.Empty:
                    break
                request = newer_request

            if request.get("kind") == "shutdown":
                return

            if request.get("kind") != "play":
                continue

            request_serial = request.get("serial")
            if request_serial != self._playback_request_serial:
                continue

            success = True
            error_message = ""
            player_key = request.get("player_key", self._active_player_key)
            try:
                (
                    playback_media_path,
                    playback_http_headers,
                    resolved_display_title,
                    resolved_display_artist,
                ) = self._resolve_media_for_playback_details(
                    request["media_path"]
                )
                lock = getattr(self, "_playback_backend_lock", None)
                with lock if lock is not None else contextlib.nullcontext():
                    # Re-fetch the player/instance now that we hold the lock: a
                    # concurrent `_reset_player()` on the UI thread may have torn
                    # down and rebuilt the backend while we were resolving the
                    # (possibly network-bound) media path above.
                    player = self._managed_player(player_key)
                    player_instance = self._instance_for_player(player_key)
                    if player_instance is None:
                        raise RuntimeError(_("Instância do backend de reprodução indisponível."))
                    if player is None:
                        raise RuntimeError(_("Player de reprodução indisponível."))
                    media = player_instance.media_new(playback_media_path, http_headers=playback_http_headers)
                    player.stop()
                    player.set_media(media)
                    video_output_handle = request.get("video_output_handle")
                    if sys.platform.startswith("win") and video_output_handle:
                        try:
                            player.set_hwnd(video_output_handle)
                        except Exception:
                            pass
                    self._set_player_loaded_media_path(player_key, request["media_path"])
                    initial_volume = request.get("initial_volume", self.current_volume)
                    try:
                        player.audio_set_volume(max(0, min(100, int(initial_volume))))
                    except Exception:
                        pass
                    play_kwargs = {}
                    if not request.get("crossfade"):
                        raw_restore_position_ms = request.get("restore_position_ms", 0) or 0
                        try:
                            normalized_restore_position_ms = int(raw_restore_position_ms)
                        except (TypeError, ValueError):
                            normalized_restore_position_ms = 0
                        if normalized_restore_position_ms > 0:
                            play_kwargs["start_seconds"] = normalized_restore_position_ms / 1000.0
                        if request.get("pause_after_start"):
                            play_kwargs["pause_on_start"] = True
                    player.play(**play_kwargs)
                    if request.get("crossfade"):
                        try:
                            player.audio_set_volume(0)
                        except Exception:
                            pass
                request["resolved_display_title"] = resolved_display_title
                request["resolved_display_artist"] = resolved_display_artist
            except Exception as exc:
                success = False
                error_message = str(exc)

            wx.CallAfter(
                self._finish_media_start,
                request,
                success,
                error_message,
            )

    def _queue_media_start(
        self,
        media_path,
        *,
        tab_index,
        announce_message=None,
        restore_position_ms=0,
        pause_after_start=False,
        player_key=None,
        initial_volume=None,
        crossfade=False,
    ):
        target_player_key = player_key or self._active_player_key
        target_player = self._managed_player(target_player_key)
        if (
            sys.platform.startswith("win")
            and self._video_output_enabled()
            and not crossfade
            and not is_audio_playback_media(media_path)
            and target_player is not None
            and (
                self._player_loaded_media_path(target_player_key)
                or target_player.get_media() is not None
            )
        ):
            self._recreate_player_slot(target_player_key, index=tab_index)

        self._bind_player_to_window(index=tab_index)

        request = {
            "kind": "play",
            "serial": self._next_playback_request_serial(),
            "media_path": media_path,
            "tab_index": tab_index,
            "video_output_handle": self._video_output_handle(tab_index),
            "announce_message": announce_message,
            "restore_position_ms": restore_position_ms,
            "pause_after_start": pause_after_start,
            "player_key": target_player_key,
            "initial_volume": self.current_volume if initial_volume is None else initial_volume,
            "crossfade": bool(crossfade),
        }
        if (
            not crossfade
            and is_youtube_music_media(media_path)
            and hasattr(self, "_set_status_message")
        ):
            self._set_status_message(
                _("Resolvendo {label}...").format(label=self._media_label(media_path)),
                auto_clear_ms=0,
            )
        self._playback_queue.put(request)
        return request

    def _refresh_player_backend_for_video_output_setting(self):
        self._capture_active_playlist_state()
        active_index = self._get_active_playlist_index()
        active_state = self._get_active_playlist_state()
        current_media_path = getattr(active_state, "current_media_path", None)
        restore_position_ms = int(getattr(active_state, "last_position_ms", 0) or 0) if active_state else 0
        pause_after_restore = not bool(getattr(active_state, "was_playing", False)) if active_state else False

        self._cancel_crossfade_transition(stop_incoming=True, stop_outgoing=True, invalidate_requests=True)
        self._stop_all_players(unload=False)
        self._reset_player()

        if active_state and active_index != wx.NOT_FOUND and current_media_path:
            self._queue_media_start(
                current_media_path,
                tab_index=active_index,
                restore_position_ms=restore_position_ms,
                pause_after_start=pause_after_restore,
                announce_message="",
            )
            return

        self._update_title()
        self._update_time_bar()

    def _finish_media_start(self, request, success, error_message):
        player_key = request.get("player_key", self._active_player_key)
        if request.get("serial") != self._playback_request_serial:
            # The request was invalidated (e.g. the tab was closed while we
            # were still resolving the stream URL on the worker thread). The
            # worker may have started the player after `_unload_player` ran,
            # so make sure the player tied to this stale request is stopped.
            if success:
                self._stop_player(player_key, unload=True)
            return

        tab_index = request.get("tab_index")
        media_path = request.get("media_path")
        state = self._get_playlist_state(tab_index)
        if not state or state.current_media_path != media_path:
            if request.get("crossfade") or success:
                self._stop_player(player_key, unload=True)
            return

        if not success:
            self._set_player_loaded_media_path(player_key, None)
            if request.get("crossfade"):
                if self._fallback_pending_crossfade_to_regular_playback():
                    return
                self._cancel_crossfade_transition(stop_incoming=True, stop_outgoing=False, invalidate_requests=False)
            if error_message:
                handled = False
                if is_youtube_music_media(media_path) and hasattr(self, "_handle_youtube_javascript_runtime_error"):
                    try:
                        handled = bool(self._handle_youtube_javascript_runtime_error(error_message))
                    except Exception:
                        handled = False
                if not handled:
                    self._announce(_("Não foi possível iniciar a mídia: {error}.").format(error=error_message))
            return

        if request.get("crossfade"):
            crossfade_state = getattr(self, "_crossfade_state", None)
            if not crossfade_state:
                self._stop_player(player_key, unload=True)
                return
            if (
                crossfade_state.get("request_serial") != request.get("serial")
                or crossfade_state.get("incoming_key") != player_key
            ):
                self._stop_player(player_key, unload=True)
            else:
                self._apply_equalizer_state_to_player(self._managed_player(player_key), state)
                self._apply_volume_to_player(player_key, 0)
                self._apply_playback_rate_to_player(player_key, getattr(self, "current_playback_rate", 1.0))
                # Carry the resolved title/artist to the crossfade completion so
                # it can refresh the display metadata and lyrics for the incoming
                # track (this early return skips that work below).
                crossfade_state["resolved_display_title"] = str(request.get("resolved_display_title", "") or "").strip()
                crossfade_state["resolved_display_artist"] = str(request.get("resolved_display_artist", "") or "").strip()
            return

        self._set_active_player(player_key)
        self._apply_equalizer_state()
        self._prepare_youtube_music_history_tracking(media_path)
        self._prepare_smart_library_tracking(media_path)
        self._last_runtime_stream_title = ""
        self._next_runtime_stream_title_refresh = 0.0

        self._apply_current_volume()
        self._apply_current_playback_rate()
        # The MPV backend already applies the resume position and pause-on-start
        # via loadfile options, so we just refresh the UI here. Avoid re-issuing
        # set_time after-the-fact: it raced with the user's first arrow seeks on
        # YouTube Music streams and snapped playback back to the saved position.

        self._update_title()
        self._update_time_bar()
        self._refresh_playlist_browser()
        self._prefetch_upcoming_media_stream(state)
        resolved_display_title = str(request.get("resolved_display_title", "") or "").strip()
        resolved_display_artist = str(request.get("resolved_display_artist", "") or "").strip()
        self._apply_media_display_metadata(media_path, resolved_display_title, resolved_display_artist)
        self._emit_plugin_event(
            "playback.media_changed",
            {
                "media_path": media_path,
                "title": resolved_display_title,
                "artist": resolved_display_artist,
                "playlist_index": tab_index,
            },
        )
        
        # Busca a letra da faixa que acabou de entrar. O caminho de crossfade
        # (_begin_pending_crossfade) chama o mesmo helper, já que ele retorna
        # antes deste ponto durante uma transição.
        self._refresh_lyrics_for_active_media(resolved_display_title, resolved_display_artist)

        if not resolved_display_title:
            self._queue_remote_media_metadata_resolution(media_path)

        announce_message = request.get("announce_message")
        if hasattr(self, "_set_status_message"):
            now_playing_label = self._media_label(media_path)
            self._set_status_message(_("Tocando: {name}").format(name=now_playing_label), auto_clear_ms=0)
        if announce_message is not None:
            if announce_message:
                self._announce(announce_message)
            return

        self._announce(self._describe_playlist_position(state))

    def _refresh_lyrics_for_active_media(self, resolved_display_title, resolved_display_artist):
        """Kick off the lyrics lookup for the media that just became active.

        Shared by the normal start (``_finish_media_start``) and the crossfade
        completion (``_begin_pending_crossfade``) so lyrics follow every track
        change regardless of how the transition happened.
        """
        lyrics_panel = getattr(self, "lyrics_panel", None)
        if lyrics_panel is None:
            return

        title = str(resolved_display_title or "").strip()
        artist = str(resolved_display_artist or "").strip()
        if title:
            # Basta o título; a busca lida com o artista ausente.
            lyrics_panel.load_lyrics_for_track(artist, title)
        else:
            # Título ainda desconhecido: limpa e deixa o media_metadata.py
            # preencher quando ele for resolvido.
            lyrics_panel.reset_loaded_track()
            lyrics_panel.update_lyrics(_("Letra não encontrada para esta mídia."))

    def _load_media(self, media_path):
        player_instance = self._instance_for_player(self._active_player_key)
        if player_instance is None:
            raise RuntimeError(_("Instância do backend de reprodução indisponível."))

        playback_media_path, playback_http_headers = self._resolve_media_for_playback(media_path)
        media = player_instance.media_new(playback_media_path, http_headers=playback_http_headers)
        self.player.set_media(media)
        self._set_player_loaded_media_path(self._active_player_key, media_path)
        self._update_title()
        self._update_time_bar()

    def _player_has_loaded_media(self, media_path):
        if not media_path or not hasattr(self, "player"):
            return False

        if self.player.get_media() is None:
            return False

        loaded_media_path = self._player_loaded_media_path()
        if not loaded_media_path:
            return False

        return self._media_paths_match(media_path, loaded_media_path)

    def _unload_player(self):
        self._cancel_crossfade_transition(stop_incoming=True, stop_outgoing=True, invalidate_requests=True)
        self._flush_smart_library_playback_state()
        self._stop_all_players(unload=False)
        self._clear_youtube_music_history_tracking()
        self._clear_smart_library_tracking()

        # Limpa o painel de letras quando o player parar totalmente
        if hasattr(self, 'lyrics_panel'):
            self.lyrics_panel.reset_loaded_track()
            self.lyrics_panel.update_lyrics(_("Sem mídia"))
            
        try:
            for player_key in getattr(self, "_player_keys", ()):
                player = self._managed_player(player_key)
                if player is None:
                    continue
                player.set_media(None)
                self._set_player_loaded_media_path(player_key, None)
            self._bind_player_to_window()
        except Exception:
            self._reset_player()
        self._update_time_bar()
