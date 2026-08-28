import contextlib
import math
import queue
import sys
import threading


from ...i18n import _
import wx

from ...log import get_logger
from ...mpv_backend import PlayerEventType, create_player_instance
from .helpers import is_youtube_music_media


_logger = get_logger(__name__)


class PlayerBackendMixin:
    def _video_output_enabled(self):
        return not bool(getattr(self.settings, "disable_video_output", False))

    def _create_player_backend(self):
        self._playback_request_serial = 0
        self._playback_backend_lock = threading.Lock()
        self._playback_queue = queue.Queue()
        self._playback_worker = threading.Thread(target=self._playback_worker_loop, daemon=True)
        self._player_keys = ("primary", "secondary")
        self._player_instances = {}
        self._players = {}
        self._player_event_managers = {}
        self._player_loaded_media_paths = {}
        self._current_track_gain_db = 0.0
        for player_key in self._player_keys:
            instance = self._build_player_instance()
            self._player_instances[player_key] = instance
            player, event_manager = self._create_managed_player(player_key, instance)
            self._players[player_key] = player
            self._player_event_managers[player_key] = event_manager
            self._player_loaded_media_paths[player_key] = None

        self._active_player_key = self._player_keys[0]
        self.instance = self._player_instances[self._active_player_key]
        self.player = self._players[self._active_player_key]
        self._crossfade_state = None
        # Cache of the last window binding applied by `_bind_player_to_window`.
        # Keyed by (handle, players_generation) so we skip redundant native
        # re-parenting during EVT_SIZE storms (the handle never changes while
        # dragging the border) and on repeated binds, while still rebinding
        # whenever the active tab's handle changes or the players are rebuilt.
        self._players_generation = 0
        self._bound_video_binding = None
        self._known_audio_output_device_labels = {}
        self._audio_device_observer_installed = False
        self._last_healthy_playback_snapshot = None
        # ``None`` until the first audio-device-list event is processed; this
        # avoids treating the initial population of the device list as a
        # "reconnect" and triggering the SMTC pause-suppression window for no
        # reason on startup.
        self._known_audio_output_device_ids = None
        # When a Bluetooth/USB audio device reconnects, AVRCP-class accessories
        # (Echo/Alexa, headphones, speakers) routinely send a spurious PAUSE
        # via SMTC right after the A2DP link is restored. We ignore SMTC pause
        # commands during a short window after each detected reappearance so
        # the user doesn't have to press play again on every reconnect.
        self._suppress_smtc_pause_until = 0.0
        self._playback_worker.start()
        self._install_audio_output_device_observer()
        self._validate_initial_audio_output_device()
        _logger.info("Playback backend initialized")

    def _build_player_instance(self):
        return create_player_instance(
            video_output_enabled=self._video_output_enabled(),
            audio_output_device_id=self._selected_audio_output_device_id(),
        )

    def _instance_for_player(self, player_key=None):
        if player_key is None:
            player_key = getattr(self, "_active_player_key", None)

        player_instances = getattr(self, "_player_instances", None)
        if player_instances:
            instance = player_instances.get(player_key)
            if instance is not None:
                return instance

        return getattr(self, "instance", None)

    def _create_managed_player(self, player_key, instance=None):
        target_instance = instance or self._instance_for_player(player_key)
        if target_instance is None:
            raise RuntimeError(_("Instância do backend de reprodução indisponível para o player."))

        player = target_instance.media_player_new()
        try:
            player.video_set_key_input(False)
        except Exception:
            pass
        try:
            player.video_set_mouse_input(False)
        except Exception:
            pass
        event_manager = player.event_manager()
        event_manager.event_attach(
            PlayerEventType.MEDIA_PLAYER_END_REACHED,
            self._on_media_end_reached,
            player_key,
        )
        event_manager.event_attach(
            PlayerEventType.MEDIA_PLAYER_PLAYING,
            self._on_media_player_playing,
            player_key,
        )
        event_manager.event_attach(
            PlayerEventType.MEDIA_PLAYER_ERROR,
            self._on_media_player_error,
            player_key,
        )
        return player, event_manager

    def _managed_player(self, player_key=None):
        if player_key is None:
            player_key = getattr(self, "_active_player_key", None)

        if not hasattr(self, "_players"):
            return None

        return self._players.get(player_key)

    def _inactive_player_key(self):
        for player_key in getattr(self, "_player_keys", ()):
            if player_key != getattr(self, "_active_player_key", None):
                return player_key
        return None

    def _set_active_player(self, player_key):
        player = self._managed_player(player_key)
        if player is None:
            return None

        self._active_player_key = player_key
        self.instance = self._instance_for_player(player_key)
        self.player = player
        return player

    def _player_loaded_media_path(self, player_key=None):
        if player_key is None:
            player_key = getattr(self, "_active_player_key", None)
        return str(getattr(self, "_player_loaded_media_paths", {}).get(player_key) or "").strip() or None

    def _set_player_loaded_media_path(self, player_key, media_path):
        if not hasattr(self, "_player_loaded_media_paths"):
            return
        self._player_loaded_media_paths[player_key] = str(media_path or "").strip() or None

    def _recreate_player_slot(self, player_key, *, index=None):
        lock = getattr(self, "_playback_backend_lock", None)
        with lock if lock is not None else contextlib.nullcontext():
            existing_player = self._managed_player(player_key)
            if existing_player is not None:
                try:
                    existing_player.stop()
                except Exception:
                    pass
                try:
                    existing_player.release()
                except Exception:
                    pass

            existing_instance = getattr(self, "_player_instances", {}).get(player_key)
            if existing_instance is not None:
                try:
                    existing_instance.release()
                except Exception:
                    pass

            instance = self._build_player_instance()
            self._player_instances[player_key] = instance
            player, event_manager = self._create_managed_player(player_key, instance)
            self._players[player_key] = player
            self._player_event_managers[player_key] = event_manager
            self._set_player_loaded_media_path(player_key, None)
            self._players_generation += 1

            if player_key == getattr(self, "_active_player_key", None):
                self.instance = instance
                self.player = player

        self._bind_player_to_window(index=index)
        return player

    def _video_output_handle(self, index=None):
        if not self._video_output_enabled():
            return None

        video_panel = self._get_video_panel(index)
        if not video_panel:
            return None

        handle = video_panel.GetHandle()
        if not handle:
            return None

        try:
            return int(handle)
        except (TypeError, ValueError):
            return None

    def _on_media_end_reached(self, _event, player_key):
        wx.CallAfter(self._handle_player_end_reached, player_key)

    def _on_media_player_playing(self, _event, player_key):
        wx.CallAfter(self._handle_player_started, player_key)
        wx.CallAfter(self._smtc_refresh_if_active, player_key)

    def _on_media_player_error(self, event, player_key):
        error_detail = str(getattr(event, "detail", "") or "").strip()
        wx.CallAfter(self._handle_player_error, player_key, error_detail)

    def _handle_player_end_reached(self, player_key):
        crossfade_state = getattr(self, "_crossfade_state", None)
        if crossfade_state and player_key == crossfade_state.get("outgoing_key"):
            _logger.debug("End reached on outgoing crossfade slot %r; marking ended.", player_key)
            crossfade_state["outgoing_ended"] = True
            return

        active_player_key = getattr(self, "_active_player_key", None)
        if player_key != active_player_key:
            _logger.debug(
                "End reached on non-active slot %r (active=%r); ignoring.", player_key, active_player_key
            )
            return

        _logger.debug("End reached on active slot %r; handling media end.", player_key)
        self._handle_media_end()

    def _handle_player_started(self, player_key):
        if player_key == getattr(self, "_active_player_key", None):
            self._refresh_active_runtime_stream_title(force=True)

        crossfade_state = getattr(self, "_crossfade_state", None)
        if not crossfade_state:
            return

        if crossfade_state.get("phase") != "pending":
            return

        if crossfade_state.get("incoming_key") != player_key:
            return

        self._begin_pending_crossfade()

    def _handle_player_error(self, player_key, error_detail=""):
        _logger.warning(
            "MPV playback error on player slot '%s' (%s)",
            player_key,
            error_detail or "no detail",
        )
        crossfade_state = getattr(self, "_crossfade_state", None)
        media_path = self._player_loaded_media_path(player_key)
        is_http_403 = str(error_detail or "").strip().upper() == "HTTP 403"
        if is_http_403 and is_youtube_music_media(media_path):
            service = self._youtube_music_service_for_playback()
            next_playback_mode = (
                service.advance_stream_playback_after_http_403()
                if service is not None
                else ""
            )
            if next_playback_mode:
                if hasattr(self, "_set_status_message"):
                    retry_message = _("O YouTube recusou a reprodução. Tentando outro perfil...")
                    self._set_status_message(
                        retry_message,
                        auto_clear_ms=0,
                    )
                if crossfade_state and crossfade_state.get("incoming_key") == player_key:
                    if self._fallback_pending_crossfade_to_regular_playback():
                        return
                elif player_key == getattr(self, "_active_player_key", None):
                    tab_index = self._get_active_playlist_index()
                    state = self._get_playlist_state(tab_index)
                    if state and state.current_media_path == media_path:
                        self._queue_media_start(
                            media_path,
                            tab_index=tab_index,
                            announce_message="",
                        )
                        return

        if not crossfade_state or crossfade_state.get("incoming_key") != player_key:
            if player_key == getattr(self, "_active_player_key", None):
                message = _("Não foi possível reproduzir a mídia.")
                if error_detail:
                    message = _("Não foi possível reproduzir a mídia: {detail}.").format(detail=error_detail)
                if hasattr(self, "_set_status_message"):
                    self._set_status_message(message)
                self._announce(message)
            return

        if self._fallback_pending_crossfade_to_regular_playback():
            return

        self._cancel_crossfade_transition(stop_incoming=True, stop_outgoing=False, invalidate_requests=False)
        self._announce(_("Não foi possível iniciar a próxima faixa para o crossfade."))

    def _smtc_refresh_if_active(self, player_key):
        if player_key != getattr(self, "_active_player_key", None):
            return
        refresh_smtc = getattr(self, "_refresh_smtc_state", None)
        if callable(refresh_smtc):
            refresh_smtc()

    def _apply_volume_to_player(self, player_key, volume):
        player = self._managed_player(player_key)
        if player is None:
            return False

        try:
            player.audio_set_volume(max(0, min(100, int(volume))))
        except Exception:
            return False

        return True

    def _apply_current_volume(self):
        if not hasattr(self, "player"):
            return False

        if self._crossfade_state and self._crossfade_state.get("phase") == "running":
            return self._apply_crossfade_volumes()

        gain_db = float(getattr(self, "_current_track_gain_db", 0.0) or 0.0)
        adjusted_volume = self.current_volume * math.pow(10.0, gain_db / 20.0)
        return self._apply_volume_to_player(self._active_player_key, adjusted_volume)

    def _apply_playback_rate_to_player(self, player_key, rate):
        player = self._managed_player(player_key)
        if player is None:
            return False

        try:
            player.set_rate(rate)
        except Exception:
            return False

        return True

    def _apply_current_playback_rate(self):
        if not hasattr(self, "player"):
            return False

        return self._apply_playback_rate_to_player(self._active_player_key, getattr(self, "current_playback_rate", 1.0))

    def _pitch_shift_filter_segment(self):
        # Speed (mpv's `speed` property) already preserves pitch on its own via
        # scaletempo2, so this is a separate, deliberate pitch shift (changing
        # the key) via the rubberband filter's independent pitch-scale option.
        semitones = getattr(self, "current_pitch_semitones", 0)
        if not semitones:
            return ""

        pitch_scale = 2.0 ** (semitones / 12.0)
        return f"rubberband=pitch-scale={pitch_scale:.6f}"

    def _apply_audio_filter_chain_to_player(self, player, equalizer_chain="", extra_lavfi_filters=()):
        if player is None:
            return False

        filter_parts = [equalizer_chain] if equalizer_chain else []
        autodj_filters = [str(part) for part in extra_lavfi_filters if part]
        if autodj_filters:
            filter_parts.append(f"@autodj_mix:lavfi=[{','.join(autodj_filters)}]")
        pitch_filter = self._pitch_shift_filter_segment()
        if pitch_filter:
            filter_parts.append(pitch_filter)

        try:
            player.set_audio_filters(",".join(filter_parts))
        except Exception:
            return False

        return True

    def _shutdown_player_backend(self):
        self._begin_player_backend_shutdown()
        self._finish_player_backend_shutdown()

    def _begin_player_backend_shutdown(self):
        self._cancel_crossfade_transition(stop_incoming=True, stop_outgoing=True, invalidate_requests=True)
        if hasattr(self, "_playback_queue"):
            self._playback_queue.put({"kind": "shutdown"})

    def _finish_player_backend_shutdown(self):
        if hasattr(self, "_playback_worker") and self._playback_worker.is_alive():
            self._playback_worker.join(timeout=1.0)
        for player_key in getattr(self, "_player_keys", ()):
            player = self._managed_player(player_key)
            if player is None:
                continue
            try:
                player.stop()
            except Exception:
                pass
            try:
                player.release()
            except Exception:
                pass

        for instance in getattr(self, "_player_instances", {}).values():
            try:
                instance.release()
            except Exception:
                pass

        self._player_instances = {}

    def _stop_player(self, player_key, *, unload=False):
        player = self._managed_player(player_key)
        if player is None:
            return

        try:
            player.stop()
        except Exception:
            pass

        if unload:
            try:
                player.set_media(None)
            except Exception:
                pass
            self._set_player_loaded_media_path(player_key, None)

    def _stop_all_players(self, *, unload=False):
        for player_key in getattr(self, "_player_keys", ()):
            self._stop_player(player_key, unload=unload)

    def _bind_player_to_window(self, index=None):
        handle = self._video_output_handle(index)
        if not handle:
            return

        binding_key = (handle, getattr(self, "_players_generation", 0))
        if getattr(self, "_bound_video_binding", None) == binding_key:
            # Same handle and same player generation: the native surface is
            # already bound, so skip the redundant set_hwnd/set_xwindow calls
            # (this is the common case during resize storms and replays).
            return

        for player_key in getattr(self, "_player_keys", ()):
            player = self._managed_player(player_key)
            if player is None:
                continue

            try:
                if sys.platform.startswith("win"):
                    player.set_hwnd(handle)
                elif sys.platform.startswith("linux"):
                    player.set_xwindow(handle)
                elif sys.platform == "darwin":
                    player.set_nsobject(int(handle))
            except Exception:
                # Leave the cache unset so the next call retries the binding.
                self._bound_video_binding = None
                continue

        self._bound_video_binding = binding_key

    def _reset_player(self):
        active_player_key = getattr(self, "_active_player_key", self._player_keys[0])
        lock = getattr(self, "_playback_backend_lock", None)
        with lock if lock is not None else contextlib.nullcontext():
            for player_key in getattr(self, "_player_keys", ()):
                player = self._managed_player(player_key)
                if player is None:
                    continue
                try:
                    player.release()
                except Exception:
                    pass

            for instance in getattr(self, "_player_instances", {}).values():
                try:
                    instance.release()
                except Exception:
                    pass

            self._player_instances = {}
            self._players = {}
            self._player_event_managers = {}
            self._player_loaded_media_paths = {}
            for player_key in self._player_keys:
                instance = self._build_player_instance()
                self._player_instances[player_key] = instance
                player, event_manager = self._create_managed_player(player_key, instance)
                self._players[player_key] = player
                self._player_event_managers[player_key] = event_manager
                self._player_loaded_media_paths[player_key] = None

        self._players_generation += 1
        self._crossfade_state = None
        stop_crossfade_timer = getattr(self, "_stop_crossfade_timer", None)
        if callable(stop_crossfade_timer):
            stop_crossfade_timer()
        self._set_active_player(active_player_key if active_player_key in self._players else self._player_keys[0])
        self._bind_player_to_window()
        self._apply_equalizer_state()
        self._apply_current_volume()
        self._apply_current_playback_rate()
        self._update_time_bar()
