import math
import sys

import wx

from ...announcements import ANNOUNCE_PLAYBACK
from ...i18n import _
from ...monitor_output import MonitorOutput


def monitoring_enabled(settings):
    return sys.platform == "win32" and getattr(settings, "monitor_output_enabled", False)


def playback_output_volume(frame):
    settings = getattr(frame, "settings", None)
    return settings.broadcast_volume if monitoring_enabled(settings) else frame.current_volume


def track_output_volume(frame):
    gain_db = float(getattr(frame, "_current_track_gain_db", 0.0) or 0.0)
    return playback_output_volume(frame) * math.pow(10.0, gain_db / 20.0)


class MonitorPlaybackMixin:
    def _refresh_monitor_output(self, devices=None, *, retry=False):
        monitor = getattr(self, "_monitor_output", None)
        if getattr(self, "_monitor_output_closing", False):
            return
        if not monitoring_enabled(self.settings):
            if monitor is not None:
                monitor.stop()
            return
        # Device events during startup must not open the copy before the
        # session has restored monitor_volume. Callers that never restore
        # (tests, already-running windows) are treated as ready.
        if not getattr(self, "_monitor_volume_restored", True):
            return

        if monitor is None:
            monitor = self._monitor_output = MonitorOutput(self.monitor_volume, self._on_monitor_output_error)
        monitor.set_volume(self.monitor_volume)
        self._install_audio_output_device_observer()
        monitor.configure(
            self._selected_audio_output_device_id(),
            self.settings.monitor_output_device_id,
            self._audio_output_devices() if devices is None else devices,
            retry=retry,
        )

    def _on_monitor_output_error(self, stopped, message):
        def announce():
            if not stopped.is_set():
                self._set_status_message(message)
                self._announce(message, ANNOUNCE_PLAYBACK)

        wx.CallAfter(announce)

    def _close_monitor_output(self):
        self._monitor_output_closing = True
        monitor = getattr(self, "_monitor_output", None)
        if monitor is not None:
            monitor.close()

    def _set_monitor_volume(self, volume):
        self.monitor_volume = max(0, min(100, volume))
        monitor = getattr(self, "_monitor_output", None)
        if monitor is not None:
            monitor.set_volume(self.monitor_volume)

    def _apply_monitor_preferences(self, previous_settings, monitor_volume):
        was_enabled = monitoring_enabled(previous_settings)
        enabled = monitoring_enabled(self.settings)
        self._set_monitor_volume(monitor_volume)
        if enabled != was_enabled or (enabled and self.settings.broadcast_volume != previous_settings.broadcast_volume):
            self._apply_broadcast_volume()
        self._refresh_monitor_output(retry=True)
        if was_enabled and not enabled:
            return _("Monitoração desativada. A saída de áudio voltou ao volume de {volume}%.").format(
                volume=self.current_volume
            )
        return ""

    def _apply_broadcast_volume(self):
        self._apply_current_volume()
        sound_player = getattr(self, "_autodj_sound_player", None)
        if sound_player is not None:
            try:
                sound_player.audio_set_volume(playback_output_volume(self))
            except Exception:
                pass

    def _change_broadcast_volume(self, delta):
        if not monitoring_enabled(self.settings):
            return
        self.settings.broadcast_volume = max(0, min(100, self.settings.broadcast_volume + delta))
        self._apply_broadcast_volume()
        self._save_settings()
        self._announce(
            _("Volume da transmissão: {volume}%.").format(volume=self.settings.broadcast_volume),
            ANNOUNCE_PLAYBACK,
        )

    def _monitor_and_broadcast_volume_status(self):
        return _("Monitoração {monitor}%. Transmissão {broadcast}%.").format(
            monitor=self.monitor_volume, broadcast=self.settings.broadcast_volume
        )
