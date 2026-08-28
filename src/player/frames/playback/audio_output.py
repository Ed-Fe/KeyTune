import time

import wx

from ...audio_output import is_selectable_audio_output_device_id, normalize_audio_output_device_id
from ...i18n import _
from ...log import get_logger


_logger = get_logger(__name__)


class AudioOutputMixin:
    _AUDIO_RECONNECT_PAUSE_SUPPRESSION_SECONDS = 10.0

    def _selected_audio_output_device_id(self):
        selected_device_id = normalize_audio_output_device_id(getattr(self.settings, "audio_output_device_id", ""))
        if not is_selectable_audio_output_device_id(selected_device_id):
            return ""
        return selected_device_id

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
                self._remember_audio_output_device_labels(devices)
                return devices

        return []

    def _remember_audio_output_device_labels(self, devices):
        labels = getattr(self, "_known_audio_output_device_labels", None)
        if labels is None:
            labels = {}
            self._known_audio_output_device_labels = labels
        for device in devices:
            device_id = normalize_audio_output_device_id(getattr(device, "device_id", ""))
            if not is_selectable_audio_output_device_id(device_id):
                continue
            label = getattr(device, "menu_label", "") or device_id
            labels[device_id] = label

    def _label_for_audio_output_device(self, device_id):
        normalized_device_id = normalize_audio_output_device_id(device_id)
        if not is_selectable_audio_output_device_id(normalized_device_id):
            return ""
        labels = getattr(self, "_known_audio_output_device_labels", {}) or {}
        return labels.get(normalized_device_id, normalized_device_id)

    def _install_audio_output_device_observer(self):
        if getattr(self, "_audio_device_observer_installed", False):
            return
        primary_player = self._managed_player(self._player_keys[0]) if getattr(self, "_player_keys", ()) else None
        if primary_player is None:
            return
        observe = getattr(primary_player, "observe_audio_output_devices", None)
        if not callable(observe):
            return
        try:
            observe(self._on_audio_output_device_list_changed)
        except Exception:
            return
        self._audio_device_observer_installed = True

    def _on_audio_output_device_list_changed(self, devices):
        wx.CallAfter(self._handle_audio_output_device_list_changed, list(devices or []))

    def _should_suppress_external_pause(self) -> bool:
        """Return True while we are inside the post-reconnect grace window.

        Used by the SMTC bridge to drop spurious AVRCP PAUSE commands that
        Bluetooth audio accessories send right after reconnecting (Alexa,
        headphones, speakers all do this to advertise their playback state to
        the target).
        """
        deadline = float(getattr(self, "_suppress_smtc_pause_until", 0.0) or 0.0)
        return deadline > 0.0 and time.monotonic() < deadline

    def _handle_audio_output_device_list_changed(self, devices):
        self._remember_audio_output_device_labels(devices)
        available_ids = {
            normalize_audio_output_device_id(getattr(device, "device_id", ""))
            for device in devices
        }
        available_ids.discard("")

        previous_ids = getattr(self, "_known_audio_output_device_ids", None)
        newly_appeared_ids = (
            available_ids - previous_ids if previous_ids is not None else set()
        )
        self._known_audio_output_device_ids = set(available_ids)
        if newly_appeared_ids:
            _logger.info("Audio output device(s) reappeared: %s", newly_appeared_ids)
            # Block AVRCP-style PAUSE for a short window after any device
            # reappears; covers Alexa's voice-prompt -> A2DP-resume PAUSE and
            # headphone reconnect noises.
            self._suppress_smtc_pause_until = (
                time.monotonic() + self._AUDIO_RECONNECT_PAUSE_SUPPRESSION_SECONDS
            )
            # A reconnecting endpoint often leaves the SMTC session stale, so
            # transport commands from the device stop arriving. Reclaim it.
            reassert_smtc = getattr(self, "_reassert_smtc_after_reconnect", None)
            if callable(reassert_smtc):
                try:
                    reassert_smtc()
                except Exception:
                    pass

        preferred_device_id = self._selected_audio_output_device_id()
        current_device_id = self._current_audio_output_device_id()

        announcement = ""
        device_swap_requested = False
        if preferred_device_id and preferred_device_id not in available_ids:
            # Preferred device is gone (e.g., Bluetooth disconnected). With
            # ``audio-fallback-to-null=yes`` MPV keeps the file playing on a
            # null AO without rewinding or pausing; we just rewrite the
            # ``audio-device`` selection so a future ``ao-reload`` picks up
            # the system default. The user's saved preference is preserved.
            _logger.info(
                "Preferred audio output device unavailable: %r; falling back to system default",
                preferred_device_id,
            )
            if current_device_id != "":
                try:
                    self._apply_audio_output_device_to_players("")
                    device_swap_requested = True
                except Exception:
                    pass
            label = self._label_for_audio_output_device(preferred_device_id) or preferred_device_id
            announcement = _("Dispositivo de áudio '{label}' indisponível. Usando o padrão do sistema.").format(label=label)
        elif preferred_device_id and preferred_device_id in available_ids and current_device_id != preferred_device_id:
            _logger.info("Preferred audio output device restored: %r", preferred_device_id)
            try:
                self._apply_audio_output_device_to_players(preferred_device_id)
                device_swap_requested = True
            except Exception:
                pass
            label = self._label_for_audio_output_device(preferred_device_id) or preferred_device_id
            announcement = _("Dispositivo de áudio '{label}' restaurado.").format(label=label)

        # Whenever the device list changes, ask MPV to reattach a real audio
        # output if it had fallen back to ``null`` (e.g. while no device was
        # available). This is the recovery path documented in MPV's
        # TOOLS/lua/ao-null-reload.lua and is required on WASAPI.
        if not device_swap_requested:
            self._reload_audio_output_if_null()

        refresh_audio_output_menu = getattr(self, "_refresh_audio_output_menu", None)
        if callable(refresh_audio_output_menu):
            try:
                refresh_audio_output_menu()
            except Exception:
                pass

        if announcement:
            try:
                self._announce(announcement)
            except Exception:
                pass

    def _reload_audio_output_if_null(self):
        for player_key in getattr(self, "_player_keys", ()):
            player = self._managed_player(player_key)
            if player is None:
                continue
            try:
                current_ao = (player.get_current_audio_output() or "").casefold()
            except Exception:
                current_ao = ""
            if current_ao != "null":
                continue
            try:
                player.reload_audio_output()
            except Exception:
                continue

    def _validate_initial_audio_output_device(self):
        preferred_device_id = self._selected_audio_output_device_id()
        if not preferred_device_id:
            return
        try:
            devices = self._audio_output_devices()
        except Exception:
            devices = []
        available_ids = {
            normalize_audio_output_device_id(getattr(device, "device_id", ""))
            for device in devices
        }
        available_ids.discard("")
        if preferred_device_id in available_ids:
            return
        # Preferred device is not connected at startup; fall back to default
        # without overwriting the saved preference.
        try:
            self._apply_audio_output_device_to_players("")
        except Exception:
            pass

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

        active_player = getattr(self, "player", None)
        playback_snapshot = self._best_playback_snapshot_for_audio_swap(active_player)

        applied_to_any_player = False
        for player_key in getattr(self, "_player_keys", ()):
            player = self._managed_player(player_key)
            if player is None:
                continue
            player.set_audio_output_device(normalized_device_id)
            # Force MPV to actually close the old audio chain and open the
            # new device. Without ``audio-reload`` MPV (especially on WASAPI)
            # may keep the broken AO bound to the now-disconnected device,
            # which manifests as silent playback or a stuck pause/rewind.
            try:
                player.reload_audio_output()
            except Exception:
                pass
            applied_to_any_player = True

        sound_player = getattr(self, "_autodj_sound_player", None)
        if sound_player is not None:
            sound_player.set_audio_output_device(normalized_device_id)
            try:
                sound_player.reload_audio_output()
            except Exception:
                pass

        if playback_snapshot is not None and active_player is not None:
            self._schedule_audio_output_state_restore(active_player, playback_snapshot)

        return applied_to_any_player

    def _best_playback_snapshot_for_audio_swap(self, active_player):
        """Return the most reliable playback snapshot to re-assert after a
        device swap.

        When an audio device disappears (e.g. Bluetooth disconnect), MPV's
        WASAPI/PulseAudio chain may pause and rewind the file *before* our
        device-list observer fires. Reading state at that point captures the
        already-broken values, so we prefer the last healthy state observed by
        the progress timer in the moments leading up to the change.
        """
        cached_snapshot = self._consume_recent_playback_snapshot()
        if cached_snapshot is not None:
            return cached_snapshot
        if active_player is None:
            return None
        try:
            return active_player.snapshot_playback_state()
        except Exception:
            return None

    def _record_playback_state_snapshot(self):
        """Record the current playing state for use after audio-device swaps.

        Called every progress timer tick. Only records while MPV reports it is
        actively playing, so a Bluetooth disconnect that pauses/rewinds MPV
        cannot overwrite the last known good values: by the time MPV stops
        reporting ``is_playing``, the previous tick's snapshot already holds
        the user's intended state.
        """
        active_player = getattr(self, "player", None)
        if active_player is None:
            return
        try:
            media = active_player.get_media()
        except Exception:
            media = None
        if media is None:
            self._last_healthy_playback_snapshot = None
            return
        try:
            is_playing = bool(active_player.is_playing())
        except Exception:
            return
        if not is_playing:
            return
        try:
            time_pos_ms = int(active_player.get_time())
        except Exception:
            time_pos_ms = -1
        if time_pos_ms is None or time_pos_ms < 0:
            return
        time_pos_seconds = time_pos_ms / 1000.0
        snapshot = (time_pos_seconds, False)
        self._last_healthy_playback_snapshot = (time.monotonic(), snapshot)

    def _consume_recent_playback_snapshot(self):
        """Return the cached snapshot if it was recorded recently enough.

        The audio-device-list observer fires shortly after MPV's audio chain
        breaks; a snapshot captured within the last few seconds reflects the
        user's actual playing state, not the post-failure rewind/pause.
        """
        cached = getattr(self, "_last_healthy_playback_snapshot", None)
        if not cached:
            return None
        timestamp, snapshot = cached
        if time.monotonic() - timestamp > 5.0:
            return None
        return snapshot

    def _schedule_audio_output_state_restore(self, target_player, snapshot):
        """Re-assert ``snapshot`` on ``target_player`` over a short window.

        Switching ``audio-device`` while playing causes MPV to reinitialize the
        audio chain. On some backends (notably WASAPI when a Bluetooth sink
        disappears or returns) this is asynchronous: MPV can rewind the file
        and/or flip pause back on shortly after the property change. A single
        synchronous restore is not enough; we poll for ~3 s after the change
        and re-apply the snapshot whenever MPV has drifted away from it.
        """
        delays_ms = (60, 180, 360, 700, 1200, 1800, 2500, 3200)

        def _attempt_restore():
            if getattr(self, "player", None) is not target_player:
                return
            try:
                target_player.restore_playback_state(snapshot)
            except Exception:
                pass
            # Keep the cached snapshot fresh so a subsequent device-list event
            # (e.g. Bluetooth reconnect after a disconnect) still has the
            # original healthy state to fall back to.
            self._last_healthy_playback_snapshot = (time.monotonic(), snapshot)

        for delay_ms in delays_ms:
            try:
                wx.CallLater(delay_ms, _attempt_restore)
            except Exception:
                continue

    def _set_audio_output_device(self, device_id, *, announce=True, previous_device_id=None):
        normalized_device_id = normalize_audio_output_device_id(device_id)
        if normalized_device_id and not is_selectable_audio_output_device_id(normalized_device_id):
            normalized_device_id = ""
        previous_normalized_device_id = normalize_audio_output_device_id(
            previous_device_id if previous_device_id is not None else getattr(self.settings, "audio_output_device_id", "")
        )
        if previous_normalized_device_id and not is_selectable_audio_output_device_id(previous_normalized_device_id):
            previous_normalized_device_id = ""

        _logger.info(
            "Changing audio output device to %r",
            normalized_device_id or "(system default)",
        )
        try:
            self._apply_audio_output_device_to_players(normalized_device_id)
        except Exception as exc:
            _logger.warning("Failed to set audio output device to %r: %s", normalized_device_id, exc)
            self.settings.audio_output_device_id = previous_normalized_device_id
            try:
                self._apply_audio_output_device_to_players(previous_normalized_device_id)
            except Exception:
                pass
            refresh_audio_output_menu = getattr(self, "_refresh_audio_output_menu", None)
            if callable(refresh_audio_output_menu):
                refresh_audio_output_menu()
            if announce:
                self._announce(_("Não foi possível trocar o dispositivo de áudio: {error}.").format(error=exc))
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
                self._announce(_("Dispositivo de áudio alterado para {label}.").format(label=device_label))
            else:
                self._announce(_("Dispositivo de áudio alterado para o padrão do sistema."))

        return True
