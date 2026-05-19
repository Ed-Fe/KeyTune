from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

from .audio_output import (
    AudioOutputDevice,
    audio_output_device_from_mpv_entry,
    is_selectable_audio_output_device_id,
    normalize_audio_output_device_id,
)


_mpv_module = None


def _load_mpv_module():
    global _mpv_module
    if _mpv_module is None:
        _mpv_module = importlib.import_module("mpv")
    return _mpv_module


class PlayerEventType(Enum):
    MEDIA_PLAYER_END_REACHED = "media-player-end-reached"
    MEDIA_PLAYER_PLAYING = "media-player-playing"
    MEDIA_PLAYER_ERROR = "media-player-error"


@dataclass(slots=True)
class MPVMedia:
    path: str
    http_headers: dict[str, str] | None = None


class MPVEventManager:
    def __init__(self):
        self._callbacks: dict[PlayerEventType, list[tuple[Callable[..., Any], tuple[Any, ...]]]] = {
            event_type: [] for event_type in PlayerEventType
        }

    def event_attach(self, event_type: PlayerEventType, callback: Callable[..., Any], *args: Any):
        if event_type not in self._callbacks:
            self._callbacks[event_type] = []
        self._callbacks[event_type].append((callback, args))

    def emit(self, event_type: PlayerEventType, event: Any = None):
        for callback, args in list(self._callbacks.get(event_type, [])):
            try:
                callback(event, *args)
            except Exception:
                continue


class MPVPlayer:
    def __init__(self, *, video_output_enabled: bool = True, audio_output_device_id: str = ""):
        self._mpv = _load_mpv_module()
        self._event_manager = MPVEventManager()
        self._media: MPVMedia | None = None
        self._loaded_media_path: str | None = None
        self._needs_load = False
        self._bound_handle: str | None = None
        self._bound_video_output = video_output_enabled
        self._last_end_reason: int | None = None
        player_kwargs = {
            "input_default_bindings": False,
            "input_vo_keyboard": False,
            "osc": False,
            "keep_open": "yes",
            "ytdl": False,
            # When the active audio output disappears (e.g. Bluetooth speaker
            # disconnects), fall back to the null AO so playback keeps
            # advancing instead of pausing or rewinding. We then re-attach a
            # real AO via ``ao-reload`` once a device is available again.
            # This mirrors the behavior of MPV's official
            # TOOLS/lua/ao-null-reload.lua script.
            "audio_fallback_to_null": "yes",
        }
        if not video_output_enabled:
            player_kwargs["video"] = False
        try:
            self._player = self._mpv.MPV(**player_kwargs)
        except Exception as exc:
            raise RuntimeError(
                "Não foi possível iniciar uma instância do MPV. "
                f"Detalhes: {exc}"
            ) from exc
        try:
            self.set_audio_output_device(audio_output_device_id)
        except Exception:
            pass
        self._register_callbacks()

    def _default_audio_output_option_value(self) -> str:
        if sys.platform.startswith("win"):
            return "wasapi"
        return "auto"

    def _get_option(self, option_name: str, default=None):
        try:
            return self._player[option_name]
        except Exception:
            python_option_name = option_name.replace("-", "_")
            try:
                return getattr(self._player, python_option_name)
            except Exception:
                return default

    def _set_option(self, option_name: str, value):
        python_option_name = option_name.replace("-", "_")
        try:
            self._player[option_name] = value
            return
        except Exception:
            setattr(self._player, python_option_name, value)

    def _get_runtime_property(self, property_name: str, default=None):
        python_property_name = property_name.replace("-", "_")
        try:
            return getattr(self._player, python_property_name)
        except Exception:
            return default

    def _core_is_idle(self):
        try:
            return bool(self._player.core_idle)
        except Exception:
            return True

    def _register_callbacks(self):
        end_file_enum = getattr(self._mpv, "MpvEventEndFile", None)
        error_reason = getattr(end_file_enum, "ERROR", None)
        eof_reason = getattr(end_file_enum, "EOF", None)

        @self._player.event_callback("end-file")
        def _on_end_file(event):
            end_event = getattr(event, "data", None)
            reason = getattr(end_event, "reason", None)
            self._last_end_reason = reason
            if error_reason is not None and reason == error_reason:
                self._loaded_media_path = None
                self._needs_load = True
                self._event_manager.emit(PlayerEventType.MEDIA_PLAYER_ERROR, event)
                return
            if eof_reason is not None and reason == eof_reason:
                self._needs_load = True
                self._event_manager.emit(PlayerEventType.MEDIA_PLAYER_END_REACHED, event)

        @self._player.event_callback("file-loaded", "playback-restart")
        def _on_playback_event(event):
            self._needs_load = False
            self._loaded_media_path = self._media.path if self._media else self._loaded_media_path
            self._event_manager.emit(PlayerEventType.MEDIA_PLAYER_PLAYING, event)

    def event_manager(self):
        return self._event_manager

    def video_set_key_input(self, _enabled):
        return None

    def video_set_mouse_input(self, _enabled):
        return None

    def set_hwnd(self, handle):
        self._set_window_handle(handle)

    def set_xwindow(self, handle):
        self._set_window_handle(handle)

    def set_nsobject(self, handle):
        self._set_window_handle(handle)

    def _set_window_handle(self, handle):
        if not self._bound_video_output:
            return
        try:
            normalized_handle = str(int(handle))
        except (TypeError, ValueError):
            return
        self._bound_handle = normalized_handle
        try:
            self._player.wid = normalized_handle
        except Exception:
            try:
                self._player["wid"] = normalized_handle
            except Exception:
                return

    def set_media(self, media: MPVMedia | None):
        self._media = media
        self._loaded_media_path = None
        self._needs_load = media is not None

    def get_media(self):
        return self._media

    def play(self, *, start_seconds: float | None = None, pause_on_start: bool = False):
        if self._media is None:
            return
        if self._bound_handle and self._bound_video_output:
            self._set_window_handle(self._bound_handle)
        if self._needs_load or self._loaded_media_path != self._media.path:
            self._apply_media_http_headers()
            loadfile_options: dict[str, str] = {}
            if start_seconds is not None:
                try:
                    normalized_start_seconds = max(0.0, float(start_seconds))
                except (TypeError, ValueError):
                    normalized_start_seconds = 0.0
                if normalized_start_seconds > 0.0:
                    # Apply the resume position atomically as a load option so MPV
                    # honors it as soon as the file is ready. Setting time-pos via
                    # a follow-up command races with the asynchronous load and is
                    # unreliable for network streams (e.g. YouTube Music), where
                    # the seek can fail silently or be re-applied later, blocking
                    # subsequent user-initiated seeks.
                    loadfile_options["start"] = f"{normalized_start_seconds:.3f}"
            if pause_on_start:
                loadfile_options["pause"] = "yes"
                self._player.pause = True
            else:
                self._player.pause = False
            self._player.loadfile(self._media.path, "replace", **loadfile_options)
            self._loaded_media_path = self._media.path
            self._needs_load = False
            return
        self._player.pause = False

    def _apply_media_http_headers(self):
        raw_http_headers = getattr(self._media, "http_headers", None) if self._media is not None else None
        normalized_http_header_fields = []
        if isinstance(raw_http_headers, dict):
            for key, value in raw_http_headers.items():
                normalized_key = str(key or "").strip()
                normalized_value = str(value or "").strip()
                if not normalized_key or not normalized_value:
                    continue
                normalized_http_header_fields.append(f"{normalized_key}: {normalized_value}")

        self._set_option("http-header-fields", normalized_http_header_fields)

    def pause(self):
        self._player.pause = True

    def stop(self):
        try:
            self._player.stop()
        finally:
            self._needs_load = self._media is not None

    def release(self):
        try:
            self._player.stop()
        except Exception:
            pass
        self._player.terminate()

    def is_playing(self):
        try:
            return not bool(self._player.pause) and not self._core_is_idle()
        except Exception:
            return False

    def audio_set_volume(self, volume):
        self._player.volume = max(0, min(100, int(volume)))

    def list_audio_output_devices(self) -> list[AudioOutputDevice]:
        raw_devices = self._get_runtime_property("audio-device-list", default=[])
        return self._parse_audio_output_device_list(raw_devices)

    @staticmethod
    def _parse_audio_output_device_list(raw_devices) -> list[AudioOutputDevice]:
        devices: list[AudioOutputDevice] = []
        if not isinstance(raw_devices, list):
            return devices
        for raw_device in raw_devices:
            device = audio_output_device_from_mpv_entry(raw_device)
            if device is not None and device.device_id:
                devices.append(device)
        return devices

    def observe_audio_output_devices(self, callback: Callable[[list[AudioOutputDevice]], None]) -> None:
        def _on_audio_device_list_change(_property_name, raw_value):
            try:
                devices = self._parse_audio_output_device_list(raw_value)
            except Exception:
                return
            try:
                callback(devices)
            except Exception:
                pass

        try:
            self._player.observe_property("audio-device-list", _on_audio_device_list_change)
        except Exception:
            pass

    def get_audio_output_device(self) -> str:
        current_device = str(self._get_option("audio-device", default="") or "").strip()
        if not current_device:
            return ""
        if current_device.casefold() in {"auto", "default"}:
            return ""
        if sys.platform.startswith("win") and current_device.casefold() == "wasapi":
            return ""
        normalized_device = normalize_audio_output_device_id(current_device)
        if not is_selectable_audio_output_device_id(normalized_device):
            return ""
        return normalized_device

    def set_audio_output_device(self, device_id: str):
        normalized_device_id = normalize_audio_output_device_id(device_id)
        if normalized_device_id and not is_selectable_audio_output_device_id(normalized_device_id):
            normalized_device_id = ""
        self._set_option(
            "audio-device",
            normalized_device_id or self._default_audio_output_option_value(),
        )

    def reload_audio_output(self) -> bool:
        """Force MPV to reinitialize the audio output without reloading the
        file.

        MPV exposes the ``ao-reload`` command precisely for this scenario
        (a device was added/removed/changed). Without it, simply writing a new
        value to ``audio-device`` is not always enough, especially when the
        previous AO has fallen back to ``null`` after a device disappeared:
        MPV will keep using the null AO until a reload is requested.
        """
        for command_name in ("ao-reload", "audio-reload"):
            try:
                self._player.command(command_name)
                return True
            except Exception:
                continue
        return False

    def get_current_audio_output(self) -> str:
        """Return MPV's currently active audio output (e.g. ``wasapi`` or
        ``null``).

        Returns an empty string if the value cannot be read. ``"null"``
        indicates that MPV is silently dropping audio because no real device
        was available, which is what ``audio-fallback-to-null=yes`` produces
        when the active device disappears.
        """
        try:
            value = self._get_runtime_property("current-ao", default="")
        except Exception:
            return ""
        return str(value or "").strip()

    def snapshot_playback_state(self):
        """Return ``(time_pos_seconds, paused)`` for the currently loaded media.

        Returns ``None`` when no media is loaded or the state cannot be read.
        Callers can later replay this snapshot via :meth:`restore_playback_state`
        to recover from MPV's audio-chain reinitialization, which on some
        backends can rewind the file or flip the pause state asynchronously.
        """
        if not self._loaded_media_path:
            return None
        try:
            raw_time_pos = self._player.time_pos
        except Exception:
            raw_time_pos = None
        if raw_time_pos is None:
            time_pos_seconds = None
        else:
            try:
                time_pos_seconds = max(0.0, float(raw_time_pos))
            except (TypeError, ValueError):
                time_pos_seconds = None
        try:
            paused = bool(self._player.pause)
        except Exception:
            paused = None
        if time_pos_seconds is None and paused is None:
            return None
        return (time_pos_seconds, paused)

    def restore_playback_state(self, snapshot) -> bool:
        """Re-apply a snapshot from :meth:`snapshot_playback_state`.

        Returns ``True`` when the live state already matched the snapshot or
        was successfully nudged back toward it. Callers can poll this method a
        few times after changing ``audio-device`` to defeat the asynchronous
        rewind/pause that some MPV audio backends perform when the audio chain
        is reinitialized (e.g. on Bluetooth disconnect/reconnect).
        """
        if not snapshot or not self._loaded_media_path:
            return False
        target_time_pos, target_paused = snapshot
        adjusted = False
        if target_time_pos is not None:
            try:
                current_time_pos = self._player.time_pos
            except Exception:
                current_time_pos = None
            try:
                current_time_pos = float(current_time_pos) if current_time_pos is not None else None
            except (TypeError, ValueError):
                current_time_pos = None
            # Only seek back when MPV has clearly rewound (or jumped backward).
            # A small tolerance avoids fighting the user's own seeking.
            if current_time_pos is None or current_time_pos + 0.75 < target_time_pos:
                try:
                    self._player.time_pos = target_time_pos
                    adjusted = True
                except Exception:
                    pass
        if target_paused is not None:
            try:
                current_paused = bool(self._player.pause)
            except Exception:
                current_paused = None
            if current_paused is not None and current_paused != target_paused:
                try:
                    self._player.pause = target_paused
                    adjusted = True
                except Exception:
                    pass
        return adjusted

    def get_time(self):
        time_pos = self._player.time_pos
        if time_pos is None:
            return -1
        return int(round(float(time_pos) * 1000))

    def get_current_media_title(self) -> str:
        metadata_candidates = (
            self._get_runtime_property("metadata/by-key/icy-title", default=""),
            self._get_runtime_property("metadata/by-key/title", default=""),
            self._get_runtime_property("media-title", default=""),
        )
        for candidate in metadata_candidates:
            normalized_candidate = str(candidate or "").strip()
            if normalized_candidate:
                return normalized_candidate
        return ""

    def get_length(self):
        duration = self._player.duration
        if duration is None:
            return -1
        return int(round(float(duration) * 1000))

    def set_time(self, milliseconds):
        self._player.time_pos = max(0.0, float(milliseconds) / 1000.0)

    def set_position(self, position):
        percentage = max(0.0, min(1.0, float(position))) * 100.0
        self._player.percent_pos = percentage

    def set_audio_filters(self, filter_chain: str):
        self._player["af"] = filter_chain or ""


class MPVInstance:
    def __init__(self, *, video_output_enabled: bool = True, audio_output_device_id: str = ""):
        self._video_output_enabled = video_output_enabled
        self._audio_output_device_id = normalize_audio_output_device_id(audio_output_device_id)

    def media_player_new(self):
        return MPVPlayer(
            video_output_enabled=self._video_output_enabled,
            audio_output_device_id=self._audio_output_device_id,
        )

    def media_new(self, media_path, *, http_headers=None):
        return MPVMedia(path=str(media_path or "").strip(), http_headers=dict(http_headers or {}))

    def release(self):
        return None


def create_player_instance(*, video_output_enabled: bool = True, audio_output_device_id: str = ""):
    return MPVInstance(
        video_output_enabled=video_output_enabled,
        audio_output_device_id=audio_output_device_id,
    )
