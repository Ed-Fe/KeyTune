import math
import os
import queue
import sys
import threading
import time

import wx

from ..audio_output import is_selectable_audio_output_device_id, normalize_audio_output_device_id
from ..constants import PROGRESS_GAUGE_RANGE, SHORT_FADE_MS, SHORT_FADE_STEPS
from ..library import folder_display_name, is_audio_playback_media
from ..mpv_backend import PlayerEventType, create_player_instance
from ..playlists import PlaylistState
from ..youtube_music import is_music_youtube_url, is_youtube_music_media


class FramePlaybackMixin:
    _YOUTUBE_MUSIC_HISTORY_MINIMUM_MS = 15000
    _YOUTUBE_MUSIC_HISTORY_MAXIMUM_MS = 30000
    _YOUTUBE_MUSIC_HISTORY_PROGRESS_FRACTION = 0.3

    def _video_output_enabled(self):
        return not bool(getattr(self.settings, "disable_video_output", False))

    def _selected_audio_output_device_id(self):
        selected_device_id = normalize_audio_output_device_id(getattr(self.settings, "audio_output_device_id", ""))
        if not is_selectable_audio_output_device_id(selected_device_id):
            return ""
        return selected_device_id

    def _initialize_player_state(self):
        self._bind_player_to_window()
        if self.settings.restore_session_on_startup and self._restore_session():
            return

        self._update_title()
        self._announce("Nenhuma mídia tocando agora.")

    def _create_player_backend(self):
        self._playback_request_serial = 0
        self._playback_queue = queue.Queue()
        self._playback_worker = threading.Thread(target=self._playback_worker_loop, daemon=True)
        self._player_keys = ("primary", "secondary")
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

        self._active_player_key = self._player_keys[0]
        self.instance = self._player_instances[self._active_player_key]
        self.player = self._players[self._active_player_key]
        self._crossfade_state = None
        self._playback_worker.start()

    def _build_player_instance(self):
        return create_player_instance(
            video_output_enabled=self._video_output_enabled(),
            audio_output_device_id=self._selected_audio_output_device_id(),
        )

    def _audio_output_devices(self):
        inspected_players = []
        active_player = getattr(self, "player", None)
        if active_player is not None:
            inspected_players.append(active_player)

        for player_key in getattr(self, "_player_keys", ()): 
            player = self._managed_player(player_key)
            if player is not None and player not in inspected_players:
                inspected_players.append(player)

        for player in inspected_players:
            try:
                devices = player.list_audio_output_devices()
            except Exception:
                continue
            if devices:
                return devices

        return []

    def _current_audio_output_device_id(self):
        player = getattr(self, "player", None)
        if player is None:
            return ""

        try:
            current_device_id = normalize_audio_output_device_id(player.get_audio_output_device())
            if not is_selectable_audio_output_device_id(current_device_id):
                return ""
            return current_device_id
        except Exception:
            return ""

    def _apply_audio_output_device_to_players(self, device_id):
        normalized_device_id = normalize_audio_output_device_id(device_id)
        if normalized_device_id and not is_selectable_audio_output_device_id(normalized_device_id):
            normalized_device_id = ""
        applied_to_any_player = False
        for player_key in getattr(self, "_player_keys", ()): 
            player = self._managed_player(player_key)
            if player is None:
                continue
            player.set_audio_output_device(normalized_device_id)
            applied_to_any_player = True

        return applied_to_any_player

    def _set_audio_output_device(self, device_id, *, announce=True, previous_device_id=None):
        normalized_device_id = normalize_audio_output_device_id(device_id)
        if normalized_device_id and not is_selectable_audio_output_device_id(normalized_device_id):
            normalized_device_id = ""
        previous_normalized_device_id = normalize_audio_output_device_id(
            previous_device_id if previous_device_id is not None else getattr(self.settings, "audio_output_device_id", "")
        )
        if previous_normalized_device_id and not is_selectable_audio_output_device_id(previous_normalized_device_id):
            previous_normalized_device_id = ""

        try:
            self._apply_audio_output_device_to_players(normalized_device_id)
        except Exception as exc:
            self.settings.audio_output_device_id = previous_normalized_device_id
            try:
                self._apply_audio_output_device_to_players(previous_normalized_device_id)
            except Exception:
                pass
            refresh_audio_output_menu = getattr(self, "_refresh_audio_output_menu", None)
            if callable(refresh_audio_output_menu):
                refresh_audio_output_menu()
            if announce:
                self._announce(f"Não foi possível trocar o dispositivo de áudio: {exc}.")
            return False

        self.settings.audio_output_device_id = normalized_device_id
        self._save_settings()
        refresh_audio_output_menu = getattr(self, "_refresh_audio_output_menu", None)
        if callable(refresh_audio_output_menu):
            refresh_audio_output_menu()

        if announce:
            if normalized_device_id:
                selected_device = None
                for device in self._audio_output_devices():
                    if device.device_id == normalized_device_id:
                        selected_device = device
                        break
                device_label = selected_device.menu_label if selected_device else normalized_device_id
                self._announce(f"Dispositivo de áudio alterado para {device_label}.")
            else:
                self._announce("Dispositivo de áudio alterado para o padrão do sistema.")

        return True

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
            raise RuntimeError("Instância do backend de reprodução indisponível para o player.")

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

    def _on_media_player_error(self, _event, player_key):
        wx.CallAfter(self._handle_player_error, player_key)

    def _handle_player_end_reached(self, player_key):
        crossfade_state = getattr(self, "_crossfade_state", None)
        if crossfade_state and player_key == crossfade_state.get("outgoing_key"):
            crossfade_state["outgoing_ended"] = True
            return

        if player_key != getattr(self, "_active_player_key", None):
            return

        self._handle_media_end()

    def _handle_player_started(self, player_key):
        crossfade_state = getattr(self, "_crossfade_state", None)
        if not crossfade_state:
            return

        if crossfade_state.get("phase") != "pending":
            return

        if crossfade_state.get("incoming_key") != player_key:
            return

        self._begin_pending_crossfade()

    def _handle_player_error(self, player_key):
        crossfade_state = getattr(self, "_crossfade_state", None)
        if not crossfade_state or crossfade_state.get("incoming_key") != player_key:
            return

        if self._fallback_pending_crossfade_to_regular_playback():
            return

        self._cancel_crossfade_transition(stop_incoming=True, stop_outgoing=False, invalidate_requests=False)
        self._announce("Não foi possível iniciar a próxima faixa para o crossfade.")

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

        return self._apply_volume_to_player(self._active_player_key, self.current_volume)

    def _crossfade_duration_ms(self):
        crossfade_seconds = int(getattr(self.settings, "crossfade_seconds", 0) or 0)
        return max(0, crossfade_seconds * 1000)

    def _crossfade_startup_headroom_ms(self):
        duration_ms = self._crossfade_duration_ms()
        if duration_ms <= 0:
            return 0

        return max(300, min(1200, duration_ms // 2))

    def _crossfade_pending_timeout_seconds(self, media_path=None, *, outgoing_ended=False):
        if is_youtube_music_media(media_path):
            return 20.0 if outgoing_ended else 15.0

        return 5.0

    def _normalize_media_comparison_path(self, media_path):
        normalized_path = str(media_path or "").strip()
        if not normalized_path:
            return ""

        if "://" in normalized_path:
            return normalized_path.casefold()

        return os.path.normcase(os.path.normpath(normalized_path))

    def _media_paths_match(self, first_path, second_path):
        return self._normalize_media_comparison_path(first_path) == self._normalize_media_comparison_path(second_path)

    def _youtube_music_service_for_playback(self):
        youtube_music_service = getattr(self, "_youtube_music_service", None)
        if youtube_music_service is not None:
            return youtube_music_service

        get_service = getattr(self, "_get_youtube_music_service", None)
        if callable(get_service):
            return get_service()

        return None

    def _clear_youtube_music_history_tracking(self):
        self._youtube_music_history_tracking = {}

    def _prepare_youtube_music_history_tracking(self, media_path):
        normalized_media_path = str(media_path or "").strip()
        if not is_music_youtube_url(normalized_media_path):
            self._clear_youtube_music_history_tracking()
            return False

        self._youtube_music_history_tracking = {
            "media_path": normalized_media_path,
            "attempted": False,
            "reported": False,
        }
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

    def _can_crossfade_to_media(self, media_path):
        if self._crossfade_duration_ms() <= 0 or self._crossfade_state is not None:
            return False

        current_media_path = self._player_loaded_media_path()
        if not current_media_path or not media_path:
            return False

        if self._media_paths_match(current_media_path, media_path):
            return False

        if not is_audio_playback_media(current_media_path) or not is_audio_playback_media(media_path):
            return False

        if self._youtube_music_media_requires_prefetched_stream(media_path):
            self._prefetch_media_stream(media_path)

        if self.player.get_media() is None or not self.player.is_playing():
            return False

        media_length = self.player.get_length()
        return media_length is not None and media_length > 0

    def _start_crossfade(self, media_path, *, tab_index, announce_message=None):
        duration_ms = self._crossfade_duration_ms()
        if duration_ms <= 0 or self._crossfade_state is not None:
            return False

        outgoing_key = self._active_player_key
        incoming_key = self._inactive_player_key()
        if not outgoing_key or not incoming_key:
            return False

        self._stop_player(incoming_key, unload=True)
        self._apply_volume_to_player(outgoing_key, self.current_volume)
        request = self._queue_media_start(
            media_path,
            tab_index=tab_index,
            announce_message=announce_message,
            player_key=incoming_key,
            initial_volume=0,
            crossfade=True,
        )
        self._crossfade_state = {
            "phase": "pending",
            "duration_ms": duration_ms,
            "incoming_key": incoming_key,
            "outgoing_key": outgoing_key,
            "request_serial": request["serial"],
            "tab_index": tab_index,
            "media_path": media_path,
            "announce_message": announce_message,
            "created_at": time.monotonic(),
            "started_at": None,
            "outgoing_ended": False,
            "pending_timeout_seconds": self._crossfade_pending_timeout_seconds(media_path),
        }
        return True

    def _cancel_crossfade_transition(
        self,
        *,
        stop_incoming=True,
        stop_outgoing=False,
        invalidate_requests=False,
    ):
        crossfade_state = getattr(self, "_crossfade_state", None)
        if invalidate_requests:
            # Bump the serial unconditionally so that any in-flight playback
            # request (e.g. a YouTube Music stream still being resolved on
            # the worker thread) is treated as stale by `_finish_media_start`
            # and its player is stopped instead of silently starting playback
            # after the user already stopped/closed/unloaded.
            self._next_playback_request_serial()

        if not crossfade_state:
            return

        incoming_key = crossfade_state.get("incoming_key")
        outgoing_key = crossfade_state.get("outgoing_key")
        phase = crossfade_state.get("phase")

        if stop_incoming and incoming_key:
            should_stop_incoming = phase == "pending" or incoming_key != self._active_player_key
            if should_stop_incoming:
                self._stop_player(incoming_key, unload=True)

        if stop_outgoing and outgoing_key:
            self._stop_player(outgoing_key, unload=True)

        self._crossfade_state = None
        self._apply_current_volume()

    def _apply_crossfade_volumes(self):
        crossfade_state = getattr(self, "_crossfade_state", None)
        if not crossfade_state or crossfade_state.get("phase") != "running":
            return False

        started_at = crossfade_state.get("started_at")
        duration_ms = max(1, int(crossfade_state.get("duration_ms") or 0))
        if started_at is None:
            return False

        elapsed_ms = max(0, int(round((time.monotonic() - started_at) * 1000)))
        progress = max(0.0, min(1.0, elapsed_ms / duration_ms))
        incoming_volume = int(round(self.current_volume * math.sin((math.pi / 2.0) * progress)))
        outgoing_volume = int(round(self.current_volume * math.cos((math.pi / 2.0) * progress)))

        if crossfade_state.get("outgoing_ended"):
            outgoing_volume = 0

        self._apply_volume_to_player(crossfade_state["incoming_key"], incoming_volume)
        self._apply_volume_to_player(crossfade_state["outgoing_key"], outgoing_volume)

        if progress >= 1.0:
            self._finish_crossfade()

        return True

    def _finish_crossfade(self):
        crossfade_state = getattr(self, "_crossfade_state", None)
        if not crossfade_state:
            return

        outgoing_key = crossfade_state.get("outgoing_key")
        if outgoing_key:
            self._apply_volume_to_player(outgoing_key, 0)
            self._stop_player(outgoing_key, unload=True)

        self._crossfade_state = None
        self._apply_current_volume()

    def _tick_crossfade(self):
        crossfade_state = getattr(self, "_crossfade_state", None)
        if not crossfade_state:
            self._maybe_start_automatic_crossfade()
            return

        if crossfade_state.get("phase") == "pending":
            created_at = crossfade_state.get("created_at")
            pending_timeout_seconds = float(
                crossfade_state.get(
                    "pending_timeout_seconds",
                    self._crossfade_pending_timeout_seconds(
                        crossfade_state.get("media_path"),
                        outgoing_ended=bool(crossfade_state.get("outgoing_ended")),
                    ),
                )
            )
            if crossfade_state.get("outgoing_ended"):
                pending_timeout_seconds = max(
                    pending_timeout_seconds,
                    self._crossfade_pending_timeout_seconds(
                        crossfade_state.get("media_path"),
                        outgoing_ended=True,
                    ),
                )
                crossfade_state["pending_timeout_seconds"] = pending_timeout_seconds

            if created_at is not None and (time.monotonic() - created_at) > pending_timeout_seconds:
                if not self._fallback_pending_crossfade_to_regular_playback():
                    self._cancel_crossfade_transition(
                        stop_incoming=True, stop_outgoing=False, invalidate_requests=False,
                    )
                return
            incoming_player = self._managed_player(crossfade_state.get("incoming_key"))
            if incoming_player is not None and incoming_player.is_playing():
                self._begin_pending_crossfade()
            return

        if crossfade_state.get("phase") == "running":
            self._apply_crossfade_volumes()

    def _begin_pending_crossfade(self):
        crossfade_state = getattr(self, "_crossfade_state", None)
        if not crossfade_state or crossfade_state.get("phase") != "pending":
            return False

        tab_index = crossfade_state.get("tab_index")
        media_path = crossfade_state.get("media_path")
        player_key = crossfade_state.get("incoming_key")
        state = self._get_playlist_state(tab_index)
        if not state or state.current_media_path != media_path:
            self._cancel_crossfade_transition(stop_incoming=True, stop_outgoing=False, invalidate_requests=False)
            return False

        incoming_player = self._managed_player(player_key)
        if incoming_player is None:
            self._cancel_crossfade_transition(stop_incoming=True, stop_outgoing=False, invalidate_requests=False)
            return False

        self._apply_equalizer_state_to_player(incoming_player, state)
        self._set_active_player(player_key)
        self._bind_player_to_window()
        self._prepare_youtube_music_history_tracking(media_path)
        self._update_title()
        self._update_time_bar()
        self._refresh_playlist_browser()

        announce_message = crossfade_state.get("announce_message")
        if announce_message is not None:
            if announce_message:
                self._announce(announce_message)
        else:
            self._announce(self._describe_playlist_position(state))

        self._apply_volume_to_player(player_key, 0)

        outgoing_player = self._managed_player(crossfade_state.get("outgoing_key"))
        if crossfade_state.get("outgoing_ended") or outgoing_player is None or not outgoing_player.is_playing():
            crossfade_state["duration_ms"] = 500
        else:
            outgoing_time = outgoing_player.get_time()
            outgoing_length = outgoing_player.get_length()
            if (
                outgoing_time is not None
                and outgoing_time >= 0
                and outgoing_length is not None
                and outgoing_length > 0
            ):
                actual_remaining = max(0, outgoing_length - outgoing_time)
                crossfade_state["duration_ms"] = max(
                    500, min(crossfade_state["duration_ms"], actual_remaining),
                )

        crossfade_state["phase"] = "running"
        crossfade_state["started_at"] = time.monotonic()
        self._apply_crossfade_volumes()
        self._prefetch_upcoming_media_stream(state)
        return True

    def _fallback_pending_crossfade_to_regular_playback(self):
        crossfade_state = getattr(self, "_crossfade_state", None)
        if not crossfade_state or crossfade_state.get("phase") != "pending":
            return False

        tab_index = crossfade_state.get("tab_index")
        media_path = crossfade_state.get("media_path")
        announce_message = crossfade_state.get("announce_message")
        state = self._get_playlist_state(tab_index)
        if not state or state.current_media_path != media_path:
            return False

        self._cancel_crossfade_transition(
            stop_incoming=True,
            stop_outgoing=False,
            invalidate_requests=True,
        )
        self._queue_media_start(
            media_path,
            tab_index=tab_index,
            announce_message=announce_message,
        )
        return True

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
            player = self._managed_player(player_key)
            player_instance = self._instance_for_player(player_key)
            try:
                if player_instance is None:
                    raise RuntimeError("Instância do backend de reprodução indisponível.")
                playback_media_path, playback_http_headers = self._resolve_media_for_playback(request["media_path"])
                media = player_instance.media_new(playback_media_path, http_headers=playback_http_headers)
                if player is None:
                    raise RuntimeError("Player de reprodução indisponível.")
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
                f"Resolvendo {self._media_label(media_path)}...",
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
                self._announce(f"Não foi possível iniciar a mídia: {error_message}.")
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
            return

        self._set_active_player(player_key)
        self._apply_equalizer_state()
        self._prepare_youtube_music_history_tracking(media_path)

        self._apply_current_volume()
        # The MPV backend already applies the resume position and pause-on-start
        # via loadfile options, so we just refresh the UI here. Avoid re-issuing
        # set_time after-the-fact: it raced with the user's first arrow seeks on
        # YouTube Music streams and snapped playback back to the saved position.

        self._update_title()
        self._update_time_bar()
        self._refresh_playlist_browser()
        self._prefetch_upcoming_media_stream(state)

        announce_message = request.get("announce_message")
        if hasattr(self, "_set_status_message"):
            now_playing_label = self._media_label(media_path)
            self._set_status_message(f"Tocando: {now_playing_label}", auto_clear_ms=0)
        if announce_message is not None:
            if announce_message:
                self._announce(announce_message)
            return

        self._announce(self._describe_playlist_position(state))

    def _handle_playback_timer_tick(self):
        self._tick_crossfade()

    def _shutdown_player_backend(self):
        self._cancel_crossfade_transition(stop_incoming=True, stop_outgoing=True, invalidate_requests=True)
        if hasattr(self, "_playback_queue"):
            self._playback_queue.put({"kind": "shutdown"})
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

    def _perform_short_fade_out(self, player_key, on_complete):
        """Quick fade-out on `player_key` then run `on_complete()` on the UI thread.

        Used by pause/stop to soften the audio cut. Falls back to running
        `on_complete` immediately when the player is missing or already silent.
        """

        def finish():
            if on_complete is not None:
                on_complete()

        player = self._managed_player(player_key)
        if player is None:
            finish()
            return

        try:
            start_volume = max(0, min(100, int(self.current_volume)))
        except (TypeError, ValueError):
            start_volume = 0

        if start_volume <= 0 or not player.is_playing():
            finish()
            return

        steps = max(1, int(SHORT_FADE_STEPS))
        step_delay_seconds = max(0.001, (SHORT_FADE_MS / 1000.0) / steps)

        def worker():
            for step in range(1, steps + 1):
                fade_volume = int(round(start_volume * (1.0 - step / steps)))
                self._apply_volume_to_player(player_key, fade_volume)
                if step < steps:
                    time.sleep(step_delay_seconds)
            wx.CallAfter(finish)

        threading.Thread(target=worker, daemon=True).start()

    def _unload_player(self):
        self._cancel_crossfade_transition(stop_incoming=True, stop_outgoing=True, invalidate_requests=True)
        self._stop_all_players(unload=False)
        self._clear_youtube_music_history_tracking()
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

    def _bind_player_to_window(self, index=None):
        handle = self._video_output_handle(index)
        if not handle:
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
                continue

    def _load_media(self, media_path):
        player_instance = self._instance_for_player(self._active_player_key)
        if player_instance is None:
            raise RuntimeError("Instância do backend de reprodução indisponível.")

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

    def _resolve_media_for_playback(self, media_path):
        if not is_youtube_music_media(media_path):
            return media_path, {}

        youtube_music_service = self._youtube_music_service_for_playback()
        if youtube_music_service is None:
            return media_path, {}

        resolved_playback = youtube_music_service.resolve_stream_playback(media_path)
        return resolved_playback.stream_url, dict(getattr(resolved_playback, "http_headers", {}) or {})

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
            return "Sem mídia"

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

    def _format_time_ms(self, milliseconds):
        if milliseconds is None or milliseconds < 0:
            return "tempo desconhecido"

        total_seconds = int(milliseconds // 1000)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        if hours:
            return f"{hours}:{minutes:02}:{seconds:02}"
        return f"{minutes}:{seconds:02}"

    def _time_bar_accessible_value(self):
        return self.progress_label.GetLabel()

    def _update_time_bar(self):
        if not hasattr(self, "progress_label") or not hasattr(self, "progress_gauge"):
            return

        media = self.player.get_media() if hasattr(self, "player") else None
        if media is None:
            self.progress_label.SetLabel("Tempo: nenhuma mídia carregada.")
            self.progress_gauge.SetValue(0)
            self._refresh_player_visual_hints()
            return

        current_time = self.player.get_time()
        if current_time is None or current_time < 0:
            current_time = 0

        total_time = self.player.get_length()
        current_label = self._format_time_ms(current_time)

        if total_time is None or total_time <= 0:
            self.progress_label.SetLabel(f"Tempo: {current_label} / duração desconhecida")
            if self.player.is_playing():
                self.progress_gauge.Pulse()
            else:
                self.progress_gauge.SetValue(0)
            self._refresh_player_visual_hints()
            return

        bounded_current_time = max(0, min(current_time, total_time))
        percentage = int(round((bounded_current_time / total_time) * 100)) if total_time > 0 else 0
        gauge_value = int(round((bounded_current_time / total_time) * PROGRESS_GAUGE_RANGE)) if total_time > 0 else 0
        total_label = self._format_time_ms(total_time)

        self.progress_label.SetLabel(f"Tempo: {current_label} / {total_label} ({percentage}%)")
        self.progress_gauge.SetValue(max(0, min(PROGRESS_GAUGE_RANGE, gauge_value)))
        self._refresh_player_visual_hints()

    def _seek_relative(self, delta_ms):
        if self._crossfade_state:
            if self._crossfade_state.get("phase") == "running":
                self._finish_crossfade()
            else:
                self._cancel_crossfade_transition(stop_incoming=True, stop_outgoing=False, invalidate_requests=True)

        if self.player.get_media() is None:
            return

        current_time = self.player.get_time()
        if current_time is None or current_time < 0:
            current_time = 0

        target_time = max(0, current_time + delta_ms)
        self.player.set_time(target_time)
        self._update_time_bar()

    def _change_volume(self, delta):
        self.current_volume = max(0, min(100, self.current_volume + delta))
        self._apply_current_volume()

    def _seek_to_start(self):
        if self._crossfade_state:
            if self._crossfade_state.get("phase") == "running":
                self._finish_crossfade()
            else:
                self._cancel_crossfade_transition(stop_incoming=True, stop_outgoing=False, invalidate_requests=True)

        if self.player.get_media() is None:
            return

        self.player.set_time(0)
        self._update_time_bar()
        self._announce("Início do arquivo.")

    def _seek_to_end(self):
        if self._crossfade_state:
            if self._crossfade_state.get("phase") == "running":
                self._finish_crossfade()
            else:
                self._cancel_crossfade_transition(stop_incoming=True, stop_outgoing=False, invalidate_requests=True)

        if self.player.get_media() is None:
            return

        media_length = self.player.get_length()
        if media_length is None or media_length <= 0:
            self.player.set_position(0.99)
        else:
            self.player.set_time(max(0, media_length - 1000))

        self._update_time_bar()
        self._announce("Fim do arquivo.")

    def _reset_player(self):
        active_player_key = getattr(self, "_active_player_key", self._player_keys[0])
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

        self._crossfade_state = None
        self._set_active_player(active_player_key if active_player_key in self._players else self._player_keys[0])
        self._bind_player_to_window()
        self._apply_equalizer_state()
        self._apply_current_volume()
        self._update_time_bar()

    def _toggle_play_pause(self):
        state = self._get_playlist_state()
        if not self.player.get_media():
            self.on_open(None)
            return

        if self._crossfade_state:
            if self._crossfade_state.get("phase") == "running":
                self._finish_crossfade()
            else:
                self._cancel_crossfade_transition(stop_incoming=True, stop_outgoing=False, invalidate_requests=True)

        if self.player.is_playing():
            active_player_key = self._active_player_key

            def finish_pause():
                player = self._managed_player(active_player_key)
                if player is not None:
                    try:
                        player.pause()
                    except Exception:
                        pass
                self._apply_volume_to_player(active_player_key, self.current_volume)
                if state:
                    state.was_playing = False
                self._update_time_bar()
                self._announce("Pausado.")
                if hasattr(self, "_set_status_message") and state and state.current_media_path:
                    self._set_status_message(
                        f"Pausado: {self._media_label(state.current_media_path)}",
                        auto_clear_ms=0,
                    )
                refresh_smtc = getattr(self, "_refresh_smtc_state", None)
                if callable(refresh_smtc):
                    refresh_smtc()

            self._perform_short_fade_out(active_player_key, finish_pause)
        else:
            self._bind_player_to_window()
            self.player.play()
            if state:
                state.was_playing = True
            self._update_time_bar()
            self._announce("Reprodução retomada.")
            if hasattr(self, "_set_status_message") and state and state.current_media_path:
                self._set_status_message(
                    f"Tocando: {self._media_label(state.current_media_path)}",
                    auto_clear_ms=0,
                )
            refresh_smtc = getattr(self, "_refresh_smtc_state", None)
            if callable(refresh_smtc):
                refresh_smtc()

    def _announce_playback_time(self):
        if not self.player.get_media():
            self._announce("Nenhuma mídia carregada.")
            return

        current_time = self.player.get_time()
        if current_time is None or current_time < 0:
            current_time = 0

        total_time = self.player.get_length()
        current_label = self._format_time_ms(current_time)

        if total_time is None or total_time <= 0:
            self._announce(f"Tempo atual: {current_label}.")
            return

        total_label = self._format_time_ms(total_time)
        percentage = int(max(0, min(100, round((max(0, current_time) / total_time) * 100)))) if total_time > 0 else 0
        self._announce(f"Tempo atual: {current_label} de {total_label}. {percentage}%.")

    def _announce_current_volume(self):
        self._announce(f"Volume atual: {self.current_volume}%.")

    def _announce_player_status(self):
        current_tab = self._get_tab_state()
        state = self._get_playlist_state()
        status_parts = []

        if current_tab:
            status_parts.append(f"Aba atual: {current_tab.title}.")

        if state and current_tab is not state:
            status_parts.append(f"Aba de mídia ativa: {state.title}.")

        if state:
            if state.is_folder_tab and state.folder_current_path:
                status_parts.append(f"Pasta atual: {folder_display_name(state.folder_current_path)}.")

        media_path = state.current_media_path if state else None
        if not media_path:
            status_parts.append("Nenhuma mídia tocando agora.")
            status_parts.append(f"Volume atual: {self.current_volume}%.")
            if state:
                shuffle_label = "ligado" if state.shuffle_enabled else "desligado"
                status_parts.append(f"Aleatório {shuffle_label}.")
                status_parts.append(self._repeat_mode_message(state.repeat_mode) + ".")
            self._announce(" ".join(status_parts))
            return

        media_name = self._media_label(media_path)
        playback_state = "tocando" if self.player.is_playing() else "pausado"
        status_parts.append(f"Mídia: {media_name}. Estado: {playback_state}.")

        if state and state.item_count > 0:
            status_parts.append(f"Item {state.current_index + 1} de {state.item_count}.")
            shuffle_label = "ligado" if state.shuffle_enabled else "desligado"
            status_parts.append(f"Aleatório {shuffle_label}.")
            status_parts.append(self._repeat_mode_message(state.repeat_mode) + ".")

        current_time = self.player.get_time()
        if current_time is None or current_time < 0:
            current_time = 0

        total_time = self.player.get_length()
        if total_time is not None and total_time > 0:
            percentage = int(max(0, min(100, round((current_time / total_time) * 100))))
            status_parts.append(
                f"Tempo {self._format_time_ms(current_time)} de {self._format_time_ms(total_time)}. {percentage}%."
            )
        else:
            status_parts.append(f"Tempo atual: {self._format_time_ms(current_time)}.")

        status_parts.append(f"Volume atual: {self.current_volume}%.")
        self._announce(" ".join(status_parts))
